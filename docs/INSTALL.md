# Install

Two pieces: the Python wrapper + the static-www UI.

## Wrapper (Python)

Requires Python ≥ 3.10.

```bash
git clone <repo-url>
cd ai-chat-wrapper
pip install -r requirements.txt
```

Install in development mode if you intend to modify it:

```bash
pip install -e .[dev]
```

## LLM engine

The wrapper expects a local OpenAI-compatible LLM endpoint. We test
against [Ollama](https://ollama.com) but anything that speaks the
OpenAI chat-completions wire-format works.

```bash
# Example: Ollama
ollama pull llama3.2   # or any model you prefer
ollama serve           # listens on 127.0.0.1:11434
```

## Static-www UI (optional but recommended)

The reference UI is plain HTML/CSS/JS — no build step.

```bash
cd examples/static-www
cp site.config.example site.config

# Edit site.config — fill in YOUR_DOMAIN, YOUR_PROJECT_NAME,
# YOUR_LEGAL_NAME (impressum), etc.

./init_site.sh
# → produces _output/ with all {{PLACEHOLDER}} markers substituted

# Deploy
rsync -avz _output/ user@yourserver:/var/www/yoursite/
```

Put a TLS-terminating reverse proxy in front (Caddy / nginx / Traefik).

## Verify

```bash
# Smoke test
python -m pytest tests/

# Full wrapper test suite
python -m wrapper_v2.tests.run_all
```

Both should report all-pass.

## Next

- `docs/CONFIGURE.md` — full configuration reference
