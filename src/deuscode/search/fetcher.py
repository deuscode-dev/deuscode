import re

import httpx

MAX_CONTENT_CHARS = 3000


async def fetch_content(url: str) -> str:
    """
    Fetch URL content and extract readable text.
    Returns truncated plain text. Never raises.
    """
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Deus-CLI/1.0 (coding assistant)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = _strip_html(resp.text)
            if len(text) > MAX_CONTENT_CHARS:
                return text[:MAX_CONTENT_CHARS] + "... [truncated]"
            return text
    except Exception:
        return ""


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities."""
    text = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", "", html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()
