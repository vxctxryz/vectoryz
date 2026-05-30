# Architecture · vectoryz v0.1

One-page system overview.

## Layer cake (top → bottom)

```
┌──────────────────────────────────────────────────────┐
│  Frontend (static HTML/CSS/JS)                       │
│  Daymode + Nightmode · CSS logo · AES-256-GCM        │
│  zero-knowledge chat storage (URL-fragment key)      │
└────────────┬─────────────────────────────────────────┘
             │  HTTPS + SSE
┌────────────▼─────────────────────────────────────────┐
│  Caddy reverse-proxy (TLS auto)                      │
└────────────┬─────────────────────────────────────────┘
             │  HTTP localhost:8042
┌────────────▼─────────────────────────────────────────┐
│  vectoryz HTTP server (wrapper_cc.py)                │
│                                                       │
│  ┌─ Phase α: Babel-Cascade Türsteher                 │
│  │   FastText lid.176 → detect lang → P-Matrix      │
│  │                                                    │
│  ├─ Phase β: Pre-pipeline guards                    │
│  │   Bare-greeting · Modality-detector · Soft-recon │
│  │                                                    │
│  ├─ Phase γ: Pre-search                              │
│  │   Dialog-unwrap · Morpheme-dissolver ·            │
│  │   Wikipedia-disambig-coverage ·                   │
│  │   Web-search (ddgs) + per-source-tier            │
│  │                                                    │
│  ├─ Phase δ: Short-tier (qwen2.5:7b ~6s)            │
│  │   Skipped if pre-search-context already rich     │
│  │                                                    │
│  ├─ Phase ε: Deep-tier (configurable, ~30s)         │
│  │   System-msgs assembled with disambig-discipline │
│  │   FINALE ANTWORT-DISZIPLIN as last sys-msg       │
│  │                                                    │
│  ├─ Phase ζ: Multi-hop search (model-driven)         │
│  │   Triggered by [[SEARCH: ...]] markers            │
│  │                                                    │
│  ├─ Phase η: Audit-retry-loop                       │
│  │   verify_response_addresses_query → drift?       │
│  │   doublecheck (proper-name verification) →       │
│  │   tribunal-peek (4 witnesses, 8 claims) →        │
│  │   coverage-check (question by question) →        │
│  │   ↻ retry with explicit correctives              │
│  │                                                    │
│  ├─ Phase θ: Refusal-fanout                         │
│  │   If model blanket-refused, split user-blob      │
│  │   into items + per-item re-engage                 │
│  │                                                    │
│  ├─ Phase ι: Post-stream factampel emission         │
│  │   Per-claim splice-tier (factfact/quasifact/     │
│  │   maybefact/quasinonfact/nonfact/nullfact)       │
│  │                                                    │
│  └─ Phase κ: SSE events to client                   │
│      babel_route · token · factampel_tags ·         │
│      tribunal_peek_quality · deploy_stamp · done    │
└────────────┬─────────────────────────────────────────┘
             │  HTTP localhost:11434
┌────────────▼─────────────────────────────────────────┐
│  Ollama (LLM-inference)                              │
│  qwen2.5:7b (short) · dolphin-mixtral / vectoryzDE   │
│  (deep) · llama3.1:8b (witness)                      │
└──────────────────────────────────────────────────────┘
```

## Tribunal witnesses

The audit-CAB has multiple distinct witnesses with INDEPENDENT search-paths:

- **claude** — LLM-internal adversarial-disagree check (model-as-judge)
- **google_today** — live web-search (current, polluted)
- **google1998** — pre-LLM-era search via Wayback (clean but sparse)
- **wiki_graph** — Wikipedia-graph snap-connect (does Wiki document the connection?)
- **operator** — cache + manual override DB (operator-veto)

Witness-independence is doctrine-required per [[baal_whipper_doctrine]]:
verifiers must not share producer's leash, else echo-chamber.

## Factampel per-claim tiers

| Tier | Meaning | Color |
|---|---|---|
| factfact | strongly supported | 🟢 |
| quasifact | strongly supported, small uncertainty | 🟢⚪ |
| maybefact | balanced evidence both sides | 🟡 |
| quasinonfact | strongly contradicted, small uncertainty | 🟠 |
| nonfact | strongly contradicted | 🔴 |
| nullfact | no signal (initial pre-tribunal) | ⚪ |
| fyifact | for-your-info, opinion / framing | ⓘ |

## Files

- `vectoryz/pipeline/` — modular pipeline stages
- `vectoryz/server/wrapper_cc.py` — HTTP server + audit-retry-loop
- `vectoryz/config/babel_p_matrix.json` — language-routing config
- `vectoryz/classifiers/` — alarm-keywords, splice-legends
- `examples/static-www/` — UI (German base, plug-and-play)
- `examples/systemd/` + `examples/caddy/` — deployment templates
