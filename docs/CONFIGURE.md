# Configure

Configuration is environment-variable driven. Copy `.env.example` to
`.env`, edit, and source it before running.

## Required

| Env var | Default | Purpose |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | LLM engine endpoint (OpenAI-compatible) |
| `DEFAULT_MODEL` | _(none)_ | Model identifier the engine will route to |
| `STATE_DB` | `./state.db` | SQLite file for session + chat storage |

## Optional behaviour switches

| Env var | Default | Purpose |
|---|---|---|
| `WRAPPER_V2_TRIBUNAL` | `0` | Set to `1` to enable multi-witness verification |
| `WRAPPER_V2_FACTAMPEL` | `1` | Per-claim verdict tagging in SSE output |
| `WRAPPER_V2_RETRY_THRESHOLD` | `0.25` | quasinonfact-rate at which retry triggers |
| `WRAPPER_V2_PORT` | `8042` | HTTP bind port |
| `WRAPPER_V2_BIND` | `127.0.0.1` | HTTP bind address |

## Static-www UI placeholders

The reference UI (`examples/static-www/`) reads `site.config` for the
following placeholders. See `site.config.example` for the comprehensive
list — the key categories are:

- **Project identity**: `YOUR_PROJECT_NAME` (+ `_CAP` + `_UP` variants)
- **Domains**: `YOUR_DOMAIN`, optional sibling TLDs (`_NET`, `_EU`, etc.)
- **Legal entity** (impressum + datenschutz): `YOUR_LEGAL_NAME`,
  `YOUR_STREET`, `YOUR_POSTAL_CITY`, `YOUR_CITY`, `YOUR_COUNTRY_CODE`,
  `YOUR_EMAIL`, `YOUR_CONTACT_EMAIL`, `YOUR_SECURITY_EMAIL`,
  `YOUR_PHONE`, `YOUR_PHONE_E164`, `YOUR_VAT_NUMBER`
- **Release metadata**: `YOUR_RELEASE_DATE`, `YOUR_VERSION`
- **Hosting**: `YOUR_HOSTING_PROVIDER`, `YOUR_HOSTING_COUNTRY`
- **Repos**: `YOUR_CODEBERG_REPO`, `YOUR_GITHUB_REPO`
- **Social**: `YOUR_FEDIVERSE_HANDLE`

`init_site.sh` flags any placeholder that's still unsubstituted after
running, so you can iterate until clean.

## Customisation guidance

The wrapper is intentionally minimal. Sensible places to extend:

- **Add a verification source**: implement an adapter in
  `wrapper_v2/verify/` (existing examples: three_witness, doublecheck,
  wiki_wortwolke)
- **Add a pre-filter**: implement in `wrapper_v2/pre_filters/`
  (existing: age_gate)
- **Customise the SSE event types**: see
  `wrapper_v2/sse/events.py` `KNOWN_EVENT_TYPES`

Each sub-package's `__init__.py` documents the API surface.
