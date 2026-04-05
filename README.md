# Deus

Claude Code-style AI coding assistant that runs on your own GPU.

## The problem it solves

Proprietary coding assistants charge per token — and token anxiety kills the "just let it figure it out" workflow. Every file read, every search, every iteration costs money and sends your code to someone else's server. Deus runs on a GPU you rent by the hour: analyze your entire codebase, run the agent in loops, explore freely. Flat rate. Your data stays yours.

## How it works

```
Your prompt
    ↓
Complexity detection (simple? skip planning)
    ↓
Planner → action plan (files to read, searches to run, files to create)
    ↓
Parallel pre-loading (reads files + runs searches before agent starts)
    ↓
Agent loop (reads files, writes code, runs commands, searches web)
    ↓
Result
```

The planner analyzes your task and pre-loads all relevant context before the agent starts. Instead of the agent discovering it needs a file 3 turns in, it begins with everything already loaded.

## Quick start

### 1. Install

```bash
pip install deuscode
```

### 2. Launch a GPU on RunPod

```bash
deus setup --runpod
```

Interactive wizard: picks model → GPU size → launches vLLM → writes your config automatically.

> 💡 **Support Deus development** by using our RunPod affiliate link:
> **[runpod.io/ref/ww1q3uhd](https://runpod.io?ref=ww1q3uhd)**
>
> - **~40x cheaper** than API tokens for intensive use
> - **Flat hourly rate** — no token counting, no throttling
> - **Code never leaves your pod** — not sent to any third-party API
> - **Auto-stop built in** — Deus stops your pod when done, no idle charges
> - **Any open-source model** — Qwen2.5-Coder, DeepSeek, Llama 3, and more

### 3. Start coding

```bash
cd your-project
deus "add Stripe payment integration"
```

Or launch the interactive REPL:

```bash
deus
```

## Features

### Intelligent planning

Every prompt goes through complexity detection first. Simple questions go straight to the agent. Complex tasks get a full action plan: which files to read, which docs to search, what to create, and how to validate the result. The agent starts with context already loaded.

### Web search built in

Before the agent writes a line of code, the planner can queue web searches. Latest API docs, Stack Overflow answers, package changelogs — fetched and injected into context automatically. Uses DuckDuckGo by default; swap to Brave Search with an API key.

### Full tool suite

- **Read/write files** — diff preview and confirmation before any write
- **Bash commands** — explicit confirmation before execution
- **Web search** — DuckDuckGo (default) or Brave Search
- **Repo-map** — scans your codebase structure, passed to every prompt

### Model management

```bash
deus model list                    # see downloaded models on your pod
deus model download --size small   # pick and download a model
```

**Coding models:**

| Model | VRAM | Notes |
|---|---|---|
| Qwen2.5-Coder-1.5B | 4 GB | Tiny, any GPU |
| Qwen2.5-Coder-3B | 8 GB | Small but capable |
| Qwen2.5-Coder-7B | 16 GB | Fast, cheap, good |
| Qwen2.5-Coder-14B | 28 GB | Best mid-size |
| DeepSeek-Coder-V2-Lite | 32 GB | MoE, strong for size |
| Qwen2.5-Coder-32B | 64 GB | Top quality, needs A100 |

**General models:** Llama 3.1/3.2 (1B–70B), Mistral 7B/Nemo 12B, Gemma 2 (9B/27B).

### Pod management

```bash
deus setup --runpod    # launch a new pod
deus connect --runpod  # connect to an existing pod
deus setup --stop      # stop pod (stop paying)
```

Enable `auto_stop_runpod: true` in `~/.deus/config.yaml` to stop the pod automatically after each prompt.

## CLI reference

```
deus "your prompt"              ask anything
deus "prompt" --path ./src      specify working directory
deus "prompt" --no-map          skip repo-map (faster for large repos)
deus "prompt" --model MODEL_ID  override active model

deus setup --runpod             launch a new RunPod pod
deus setup --stop               stop current pod
deus connect --runpod           connect to existing pod

deus model list                 list downloaded + available models
deus model download             download a model to your pod
deus model download --size small  filter by size (small/medium/big/all)
```

In-chat commands (REPL only):
```
--model                show active model and downloaded list
--model MODEL_ID       switch active model mid-session
```

## Comparison

| | Deus | Claude Code | Cursor |
|---|:---:|:---:|:---:|
| Runs on your GPU | ✅ | ❌ | ❌ |
| No per-token cost | ✅ | ❌ | ❌ |
| Code stays private | ✅ | ❌ | ❌ |
| Any open-source model | ✅ | ❌ | ❌ |
| Task planning | ✅ | ✅ | ✅ |
| Web search | ✅ | ✅ | ✅ |
| Terminal-native | ✅ | ✅ | ❌ |
| Free to use | ✅ | ❌ | ❌ |

## Configuration

Config lives at `~/.deus/config.yaml`. Created automatically on first run.

```yaml
base_url: https://your-runpod-endpoint/v1
api_key: your-key
model: Qwen/Qwen2.5-Coder-7B-Instruct
max_tokens: 8192
auto_stop_runpod: false
search_backend: duckduckgo   # or: brave
brave_api_key: ""            # required if search_backend: brave
```

## Requirements

- Python 3.12+
- A RunPod account — or any OpenAI-compatible vLLM endpoint
- GPU with 4 GB+ VRAM (16 GB+ recommended for coding tasks)

## License

AGPL-3.0 — free to use, modify, and distribute. Commercial use requires a separate license. See [LICENSE](LICENSE) for details.
