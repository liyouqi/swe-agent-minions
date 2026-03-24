# SWE-Agent-Minions

This repo is a small experiment: a minimal coding agent loop built with the OpenAI Python SDK.

No framework, no heavy architecture, just one script you can read end-to-end.

## What is in this repo

- `agent.py`: main loop (prompt -> model -> command -> observation)
- `requirements.txt`: Python dependencies
- `Product.md`: product notes and direction

## Quick start

### 1. Create a Conda environment

```bash
conda create -n swe-agent-minions python=3.10 -y
conda activate swe-agent-minions
```

You need to run `conda activate swe-agent-minions` again when you open a new terminal.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

The script reads these values:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `MODEL_NAME`

Set them in your shell:

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
```

Or create a `.env` file in project root:

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
```

### 4. Run

```bash
python agent.py
```

## Notes

- If you see `ModuleNotFoundError: No module named 'openai'`, your environment is probably not activated.
- If you see `OPENAI_API_KEY` related errors, check whether your variables are loaded in the current shell.
- This is an experiment project, so the focus is clarity and iteration speed rather than a production-ready system.

## intitial

I built this repo to understand the core mechanics of an SWE-style agent before adding complexity.

If you also prefer learning by building from first principles, this project should feel familiar.
