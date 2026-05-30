# ai-chat-wrapper

A minimal AI chat wrapper with verification + audit features. MIT-licensed.
Bring your own LLM engine, your own UI brand.

## What this is

A self-auditing chat backend in Python (stdlib-first). Each response is
classified at the claim level (factfact / quasifact / maybefact /
quasinonfact / nullfact / fyifact) with optional multi-witness
verification, drift-detection, and explicit "I don't know" instead of
confabulation.

Ships as **engine + reference UI**:

- `wrapper_v2/` — the Python wrapper (engine integration + verification pipeline + SSE streaming + storage)
- `examples/static-www/` — minimal HTML/CSS/JS reference UI, plug-and-play substitutable via `site.config` + `init_site.sh`
- `tests/` — smoke test
- `LICENSE` — MIT

## Quick start

```bash
# 1. Dependencies
pip install -r requirements.txt

# 2. Point at your LLM engine + configure storage
cp .env.example .env
# edit .env — set OLLAMA_URL, DEFAULT_MODEL, STATE_DB

# 3. Run the wrapper
python -m wrapper_v2.entry

# 4. (optional) Build the static-www UI
cd examples/static-www
cp site.config.example site.config     # edit with your domain + project name
./init_site.sh                          # produces _output/ ready to deploy
```

Default listens on `127.0.0.1:8042`. Front served via static-www. Put
Caddy / nginx in front for TLS.

## Configuration surface (minimal)

The only things you have to adjust:

- **LLM engine endpoint** — `OLLAMA_URL` env (or compatible OpenAI-shape endpoint)
- **Model name** — `DEFAULT_MODEL` env
- **Storage path** — `STATE_DB` env (SQLite file)
- **UI brand placeholders** — `examples/static-www/site.config` (domain, project name, legal entity, etc.)

Everything else has sensible defaults. See `docs/CONFIGURE.md` for the full list.

## Architecture (one paragraph)

User-input → language-detection (FastText) → routing through
linguistic-distance P-Matrix → optional disambig pre-fetch → context
assembly → main LLM call → multi-hop search if model emits search-markers
→ optional tribunal-peek for drift-detection → retry-loop if
quasinonfact-rate exceeds threshold OR coverage incomplete → final
per-claim verdict tagging emitted to UI.

Each layer is designed against a specific failure-mode. See `wrapper_v2/`
sub-modules — each module's docstring documents its purpose.

## Tests

```bash
pip install pytest
pytest tests/
python -m wrapper_v2.tests.run_all      # full wrapper_v2 suite
```

## License

[MIT](LICENSE) — do what you want, attribution appreciated, no warranty.

## Acknowledgments

Standing on the shoulders of: llama.cpp, Ollama, FastText (Meta),
Wikipedia REST API, ddgs, Caddy, Python stdlib.
