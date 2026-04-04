import asyncio

import httpx
import yaml

from deuscode import ui
from deuscode.config import CONFIG_PATH

_DONE_MARKER = "DEUS_DONE"
_FAIL_MARKER = "DEUS_FAIL"


async def list_downloaded_models(base_url: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base_url.rstrip('/')}/models")
            if r.status_code == 200:
                return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        pass
    return []


async def _pod_exec(api_key: str, pod_id: str, command: list[str]) -> str:
    url = f"https://api.runpod.io/v2/{pod_id}/runsync"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": {"command": command}},
        )
        r.raise_for_status()
        return r.json().get("output", {}).get("stdout", "")


async def get_pod_storage_info(api_key: str, pod_id: str) -> dict:
    output = await _pod_exec(api_key, pod_id, ["df", "-h", "/workspace"])
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[-1] == "/workspace":
            return {"used": parts[2], "total": parts[1], "free": parts[3]}
    return {"used": "?", "total": "?", "free": "?"}


async def download_model(api_key: str, pod_id: str, model_id: str) -> None:
    safe = model_id.replace("/", "--")
    log = f"/tmp/deus_dl_{safe}.log"
    script = (
        f"huggingface-cli download {model_id} --local-dir /workspace/models/{safe} "
        f">> {log} 2>&1 && echo {_DONE_MARKER} >> {log} || echo {_FAIL_MARKER} >> {log}"
    )
    await _pod_exec(api_key, pod_id, ["bash", "-c", f"nohup bash -c '{script}' &"])
    await _poll_download(api_key, pod_id, log, model_id)


async def _poll_download(api_key: str, pod_id: str, log: str, model_id: str) -> None:
    elapsed = 0
    timeout = 30 * 60
    while elapsed < timeout:
        await asyncio.sleep(5)
        elapsed += 5
        out = await _pod_exec(api_key, pod_id, ["bash", "-c", f"tail -2 {log} 2>/dev/null || echo 'starting...'"])
        mins, secs = divmod(elapsed, 60)
        ui.print_dim(f"[{mins}m{secs:02d}s] {out.strip()[-80:]}")
        if _DONE_MARKER in out:
            ui.console.print(f"[green]✓ Downloaded {model_id}[/green]")
            return
        if _FAIL_MARKER in out:
            raise RuntimeError(f"Download failed. See pod log: {log}")
    raise TimeoutError(f"Download timed out after 30 minutes")


async def set_active_model(model_id: str) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    config["model"] = model_id
    CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))
    ui.console.print(f"[green]✓ Active model set to {model_id}[/green]")
    ui.warning("Restart your pod to activate: deus setup --stop && deus setup --runpod")
