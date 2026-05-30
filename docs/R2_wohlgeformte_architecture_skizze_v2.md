# R2 — Wohlgeformte Architecture Skizze v2

**Status:** input to R5 schiri arbitration; consolidates R0 (factampel taxonomy) + R1 (v1 audit) into modular target-architecture for v2.
**Date:** 2026-05-30
**Companion sources:**
- `docs/R0_factfact_color_line_schematic.md` (FIRST BASE, factampel verdict-axis)
- `benchmark_cc/SCHEMATICS_v1.md` (R1 audit, v1 working-patterns + drift-targets)
- Existing wrapper_v2/ scaffold (10 pipeline modules + config/)

---

## 1. Purpose

Define the **module-boundary architecture** for v2 wrapper. Not function-level (R1 covers that). Not verdict-axis (R0 covers that). This is the **shape** the code should take: which responsibilities live in which module, what flows between them, how new modules plug in.

**Wohlgeformt-criterion (per [[basetouch_verified_then_dollschon_overclock]]):**
- *Single-responsibility per module* — each module names one thing it does
- *Data-flow explicit* — inputs/outputs typed at module-boundary
- *Doctrine-anchored* — every module cites which doctrine it serves
- *Pluggable* — net-new patterns (N1–N14) attach at named seams, not via god-class injection
- *Auditable* — schiri can verify each module against its spec independently

**Pendant zur R1-verdict:** v1's drift-to-optimum-cascade was the predictable consequence of a single-file architecture (D1: god-class, D2: 505-line monster, D8: 7783-line monolith). R2 prevents recurrence by enforcing module-boundaries from day one.

---

## 2. Module-boundary doctrine

```
Single-file v1 (7783 lines)             v2 modular tree
─────────────────────────────       ───────────────────────────────
wrapper_cc.py (everything)     →    wrapper_v2/
                                      ├── entry/          (HTTP routes)
                                      ├── l0/             (architectural priority)
                                      ├── pre_filters/    (T1.a/c/d + heuristics + modality)
                                      ├── classifier/     (cascade + tier-routing)
                                      ├── pipeline/       (existing 10 modules + ext.)
                                      ├── generation/     (Ollama + streaming + register)
                                      ├── verify/         (three-witness pipeline)
                                      ├── factampel/      (verdict-axis emission)
                                      ├── cache/          (unified factfact-cache)
                                      ├── sysmsg/         (composer + per-layer)
                                      ├── store/          (DB + sessions + chats)
                                      ├── sse/            (event surface)
                                      ├── infra/          (existing: budget, parallel-fetch, NTP)
                                      └── config/         (existing: babel_p_matrix.json + new YAMLs)
```

**12 top-level modules.** Each has clear boundary. Handler god-class (R1 D1) dissolves into `entry/` + per-module routing. detect_question_topic monster (R1 D2) externalizes into `config/topic_registry/*.yaml` consumed by `classifier/`.

---

## 3. Top-level architecture (pipeline + side-channels)

```
                     ┌──────────────────────────────┐
                     │       USER REQUEST           │
                     │   POST /api/chat/new         │
                     │   POST /api/chat/{id}/turn   │
                     └──────────────┬───────────────┘
                                    ▼
                  ┌────────────────────────────────────┐
                  │   entry/         (HTTP route)      │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   l0/alarm       (pre-pipeline)    │  ◄── fires-first per
                  │   l0/vulnerable                    │      [[alarm_l0_…]]
                  └────────────────┬───────────────────┘
                                   ▼ (if no L0)
                  ┌────────────────────────────────────┐
                  │   pre_filters/   (T1.a/c/d/modality)│
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   classifier/    (babel-cascade,   │
                  │                   tier-routing,    │
                  │                   register)        │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   sysmsg/        (per-layer        │
                  │                   composer)        │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   generation/    (Ollama stream)   │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   verify/        (three-witness    │
                  │                   pipeline)        │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   factampel/     (per-claim        │
                  │                   verdict-axis)    │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   l0/harm_output (hard-stop check) │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   sse/           (event emission)  │
                  └────────────────┬───────────────────┘
                                   ▼
                  ┌────────────────────────────────────┐
                  │   USER RESPONSE (SSE stream)       │
                  └────────────────────────────────────┘

  Cross-cutting (read/write at multiple stages):
  ─────────────────────────────────────────────
  ◀━━ store/        (sessions, chats, messages, deploy_stamp)
  ◀━━ cache/        (factfact-cache, topic-cache convergence)
  ◀━━ infra/        (budget timer, parallel-fetch, NTP, ollama-client)
  ◀━━ config/       (registries, splice-legend, babel-p-matrix)
```

---

## 4. Module-by-module skizze

### 4.1 entry/ — HTTP routes (replaces v1 Handler god-class)

**Purpose:** dispatch incoming HTTP to typed handlers; nothing pipeline-related lives here.

**v1-pattern preserved:** route-table (R1 line 5652 of Handler god-class)
**v1-drift resolved:** D1 (Handler 2111 lines) — explodes into per-route handlers, each <300 lines

**Routes:**
| Method | Path | Handler |
|---|---|---|
| `POST` | `/api/chat/new` | `entry/chat.py::new_chat()` |
| `POST` | `/api/chat/{id}/turn` | `entry/chat.py::turn()` |
| `GET` | `/api/chat/{id}` | `entry/chat.py::get_chat()` |
| `POST` | `/api/chat/{id}/persist-assistant` | `entry/chat.py::persist_assistant()` |
| `POST` | `/api/chat/{id}/rollback` | `entry/chat.py::rollback()` |
| `GET` | `/api/version` | `entry/meta.py::version()` |
| `GET` | `/api/branchmap` | `entry/meta.py::branchmap()` |

**Inputs:** HTTP request (body, headers, cookies). **Outputs:** SSE stream (for chat routes) or JSON (for meta routes).

### 4.2 l0/ — Architectural priority layer

**Purpose:** fire-first checkpoints per [[alarm_l0_architectural_priority_nanosecond_counts]]. No classifier, no LLM, no IO-waits.

**Existing:** `wrapper_v2/pipeline/l0_alarm.py`, `l0_vulnerable.py`, `l0_harm_output.py` (per task #129–#131)

**Modules:**
| Module | Fire-point | Doctrine |
|---|---|---|
| `l0/alarm.py` | input-detection (pre-anything) | [[alarm_l0_…]] + [[emergency_dispatch_last_resort_life_threat]] |
| `l0/vulnerable.py` | mid-flow | [[vulnerable_user_protection_reziprok_ceiling]] |
| `l0/harm_output.py` | output-pre-emit | [[death_penalty_void]] |

All three are **synchronous + stub-classifier-only** (no LLM call) — every nanosecond counts.

### 4.3 pre_filters/ — Input pre-filters

**Purpose:** deterministic-first rejection-or-classification before LLM-touching modules.

**v1-patterns preserved (R1 §1):**
- `detect_security_probe` (T1.a)
- `detect_soft_recon` (T1.c)
- `detect_specific_lookup_request` (T1.d Phase 3)
- `extract_institution_domains` (T1.d Phase 3)
- `heuristic_compound_check`
- `detect_unsupported_modality`

**v2 form:** each becomes a composable `pre_filters/X.py` module exporting `check(input) -> Result | None`. The pipeline chains them; first to return Result short-circuits.

**Existing:** parts may live in `wrapper_v2/pipeline/fringe_classifier.py` and `morpheme_dissolver.py`. R2 audit-followup: consolidate or rename.

### 4.4 classifier/ — Cascade + tier-routing + register

**Purpose:** Babel-Labrador cascade (lang+register+tier) per [[1455xl_chassis_goal_driven_funnel]] goal-driven funnel.

**Existing:**
- `wrapper_v2/pipeline/language_detect.py` (M132 — Babel-Cascade lid.176)
- `wrapper_v2/pipeline/knowledge_question_classifier.py`
- `wrapper_v2/pipeline/pre_search.py` (Hebel B)
- `wrapper_v2/pipeline/fringe_classifier.py`
- `wrapper_v2/config/babel_p_matrix.json`

**v1-drift resolved:**
- D2 (`detect_question_topic` 505-line monster) → externalize to `config/topic_registry/*.yaml` per [[factampel_implementation_roadmap_pixabay_classification]]
- D4 (4 overlapping language-detection paths) → single `classifier/language.py` resolves once, exposes resolved-language to downstream

**v2 form:**
```
classifier/
├── babel_cascade.py      ← lang + P-matrix routing (existing language_detect.py renamed)
├── tier_routing.py       ← goal-driven funnel (replaces should_engage_deep_tier binary)
├── topic_match.py        ← lookup against externalized topic-registry YAMLs
├── register_detect.py    ← tone/register for reciprocal-mirror
├── fringe_check.py       ← (existing)
└── knowledge_q.py        ← (existing)
```

### 4.5 generation/ — Response-generation primitives

**Purpose:** Ollama call + streaming + auto-style-mirror.

**v1-patterns preserved (R1 §3):**
- `stream_short_answer_qwen` → `generation/stream.py::short_qwen()`
- `detect_bare_greeting` → `generation/bare_greeting.py` (fast-path, no LLM)
- `auto_style_mirror_system_msg` → `generation/style_mirror.py` (ceiling per [[vulnerable_user_protection_reziprok_ceiling]])
- `stream_ollama_chat`, `call_ollama_blocking` → `infra/ollama.py`

**v2 extension:** register-detection (4.4) feeds style-mirror with ceiling-enforcement.

### 4.6 verify/ — Three-witness pipeline (unified verification)

**Purpose:** per-claim three-witness test per [[factlevel_splice_6band_and_google1998_test]].

**Existing:** `wrapper_v2/pipeline/three_witness.py` (M2 integration, full decision-rules)
**Plus:** `wiki_wortwolke.py` (5th witness + own-way layer)
**Plus:** `doublecheck.py` (pre-emit ground-truth verification)

**v1-drift resolved:**
- D6 (5 verification-passes: question_coverage + cross_turn + vagueness + dublette + coherence) → unified three-witness with verdict-tier output
- Five separate functions become ONE pipeline returning per-claim {witnesses, votes, tier, correction?}

**v2 form:**
```
verify/
├── three_witness.py      ← (existing; decision-rules per R0 §9)
├── wiki_wortwolke.py     ← (existing; 5th-witness extended)
├── doublecheck.py        ← (existing; pre-emit gate)
├── wayback.py            ← Google-of-1998 witness (extracted from v1 wayback_search)
├── coverage_check.py     ← did response address query?
├── coherence_check.py    ← consolidated from v1's 5 passes
└── audit_retry.py        ← α-retry on audit-fail (from v1 build_audit_retry_messages)
```

### 4.7 factampel/ — Per-claim verdict-axis emission

**Purpose:** map three-witness verdicts to factampel tier per R0; emit SSE events.

**Existing:** `wrapper_v2/pipeline/factampel_emit.py` (per task #118 M1)

**Per R0 §9:** consumes `{witnesses, votes}` from `verify/`, emits one of 11 tier-states per claim.

**v2 form:**
```
factampel/
├── emit.py               ← per-claim verdict → SSE event (existing factampel_emit.py)
├── tier_mapper.py        ← votes-table → tier (R0 §9 table as code)
├── off_axis_tags.py      ← definitional/performative pre-check
├── gray_out.py           ← boundary-axis with wisdom-quote rotation
└── hover_legend.py       ← UI-side rendering hints (M4)
```

### 4.8 cache/ — Unified factfact-cache

**Purpose:** ONE cache replacing v1's two parallel caches.

**v1-drift resolved:**
- D3 (topic_cache + soph_cache → single factfact-cache with blockchain-like provenance per [[factfact_cache_re_labrador_timewindow]])

**v2 form:**
```
cache/
├── factfact_cache.py     ← schema: claim_hash → {tier, witnesses, votes, ts, provenance_chain}
├── ttl_policy.py         ← TTL-by-drift-mode per [[three_drift_modes_of_factfact]]
├── relabrador_cron.py    ← timewindow-since-last cron per [[factfact_cache_re_labrador_timewindow]]
└── weiss_override.py     ← WEISS-override detector + fresh-search path (M7)
```

**Existing v1 own-vectoryz-cache-first pattern** (R1 Layer 5 preserve) extends here: cache hit short-circuits three-witness call.

### 4.9 sysmsg/ — System-message composer (modular)

**Purpose:** replace v1's 8 ad-hoc system-message builders + the 192-line `platform_context_system_msg` with a composable pipeline.

**v1-drift resolved:**
- D5 (platform_context_system_msg hardcoded → per-engine-class config)
- D7 (multiple register-detection systems → consolidate)

**v2 form:**
```
sysmsg/
├── composer.py           ← assembles ordered list of layers into final system-message
├── layers/
│   ├── identity.py       ← engine-identity injection
│   ├── language_lock.py  ← lock-response-language
│   ├── time_context.py   ← NTP-quintangulated current-time
│   ├── topic_context.py  ← topic-aware context
│   ├── entity_resolution.py
│   ├── irony_register.py
│   ├── verbosity.py
│   ├── stil.py           ← style override
│   ├── saga_warp.py      ← saga/warp behaviour modifier
│   ├── plenum_synthesis.py
│   └── platform_context.py ← per-engine-class config (replaces 192-line hardcode)
```

### 4.10 store/ — Storage + sessions

**Purpose:** SQLite schema + CRUD + session-cookie handling.

**v1-patterns preserved:** chat-CRUD as-is from R1 §10
**v2 extension:** factfact-cache-schema additions (per cache/)

```
store/
├── db.py                 ← schema + migrations + connection
├── sessions.py           ← cookie + session-uuid handling
├── chats.py              ← chat CRUD (create_chat, get_chat, append_message, copy_history)
└── deploy_stamp.py       ← SSE deploy-stamp event source
```

**Preserve invariant per [[claude_chat_access_discipline]]:** chats table never SELECT * via ops-tools; only aggregates (see `ops/chat_stats.sh`).

### 4.11 sse/ — Event surface

**Purpose:** typed SSE event emission with deploy-stamp + factampel tags.

```
sse/
├── events.py             ← event-type registry + serialization
├── emit.py               ← begin_sse + sse_send + sse_done
└── factampel_stream.py   ← per-claim emission tied to factampel/emit
```

**Event-types registry** (per code-scan 2026-05-30 baseline):
auto_style_mirror, auto_tier_picked, babel_route, budget_exceeded, budget_warning, cache_hit, chat_id, classification, classifier_timeout, coherence_warning, compound_detected, contradiction_warning, deploy_stamp, dial_engaged_via_text, done, doublecheck_unsupported, eloquent_rephrase, eloquent_rephrase_struggled, entity_resolution, error, factampel_tags, fact_check_complete, fact_check_progress, fact_check_result, fact_check_starting, fact_check_warning, l0_alarm, l0_vulnerable, search_query_debug, search_results, search_results_filtered, status, tier_decision, token, translation_parallel, verifying, …

### 4.12 infra/ — Cross-cutting utilities

**Purpose:** reusable concurrency + IO primitives. No business-logic.

**v1-patterns preserved (R1 §9):**
- `BudgetTimer` → `infra/budget.py`
- `parallel_fetch_first_success` → `infra/parallel.py`
- `race_topic_mirrors` → `infra/parallel.py`
- `extract_search_keywords` → `infra/keywords.py`
- `ntp_quintangulate` → `infra/ntp.py`
- `call_ollama_blocking`, `stream_ollama_chat` → `infra/ollama.py`
- Web-search (DDGS) → `infra/web_search.py`
- Wayback → moves to `verify/wayback.py` (it's a witness, not generic infra)

**Existing:** `wrapper_v2/infra/audit_log.py`, `wrapper_v2/infra/witness_cache.py`, `wrapper_v2/infra/wrapper_v1_adapters.py`

---

## 5. Side-channels (out-of-pipeline)

| Channel | Purpose | Modules |
|---|---|---|
| **cron** | re-labrador timewindow + cache-TTL sweep | `cache/relabrador_cron.py`, `cache/ttl_policy.py` |
| **replay** | re-run past chats against current pipeline for regression-eval | `infra/replay.py` (new) |
| **calibration** | dual-output classification-events (vectoryzDB + engine-justage) per [[factampel_implementation_roadmap_pixabay_classification]] | `infra/calibration.py` (new) |
| **eval-runner** | benchmark_cc/canonical_evals fixture-runner | already in benchmark_cc/, separate process |
| **ops-tools** | count-only chat stats etc. | `ops/chat_stats.sh` (existing) |

---

## 6. Net-new pattern wiring (N1–N14 from R1)

Per R1's net-new-pattern table, each N-pattern lands in a specific module:

| # | Pattern | Module-target |
|---|---|---|
| N1 | factampel splice-tier emission per claim | `factampel/emit.py` ✓ existing |
| N2 | Three-witness-test (op + claude + 1998) | `verify/three_witness.py` ✓ existing |
| N3 | Branch-balanced labradoring | `classifier/tier_routing.py` (M3 pending #120) |
| N4 | Hover-legend UI rendering | `factampel/hover_legend.py` (M4 pending #121) |
| N5 | L0-alarm-stub-classifier | `l0/alarm.py` ✓ existing |
| N6 | Emergency-services-dispatch | `l0/alarm.py::dispatch_branch()` |
| N7 | Vulnerable-user-protection redirect | `l0/vulnerable.py` ✓ existing |
| N8 | L0-harm-output-check hard-stop | `l0/harm_output.py` ✓ existing |
| N9 | Compliance-mask jurisdiction-aware | `sysmsg/layers/platform_context.py` (per-jurisdiction config) |
| N10 | FSK/age-gate L3 stub | `pre_filters/age_gate.py` (new) |
| N11 | WEISS-override detector | `cache/weiss_override.py` (M7 pending #124) |
| N12 | Gray-out + wisdom-quote rotation | `factampel/gray_out.py` |
| N13 | Re-labrador timewindow cron | `cache/relabrador_cron.py` (M6 pending #123) |
| N14 | Google-classic comparative-audit-runner | `infra/google_classic_audit.py` (separate side-channel) |

---

## 7. Migration plan (v1 → v2)

**Phase 1 — Foundation (current state):**
- ✓ R0 spec written (this session)
- ✓ R1 audit done (gx44/main, recovered)
- ✓ R2 sketch written (this session)
- ✓ wrapper_v2/pipeline/ has 10 modules (gx44/main work integrated piece-wise)

**Phase 2 — Module-completion (sequential M-track):**
- M3 #120 — branch-balanced labradoring (`classifier/tier_routing.py`)
- M4 #121 — hover-legend UI (`factampel/hover_legend.py`)
- M5 #122 — factfact-cache schema with blockchain-like provenance (`cache/factfact_cache.py`)
- M6 #123 — re-labrador cron (`cache/relabrador_cron.py`)
- M7 #124 — WEISS-override (`cache/weiss_override.py`)
- M8 #125 — 9-fixture canonical_evals all green
- M9 #126 — BASETOUCH VERIFIED schiri-arbitration

**Phase 3 — Module-extraction-from-v1 (parallel-friendly):**
- Extract `pre_filters/*` from v1 (R1 §1 functions)
- Extract `generation/*` from v1 (R1 §3 functions)
- Extract `sysmsg/layers/*` from v1 (R1 §8 functions)
- Externalize `detect_question_topic` 505-line monster → `config/topic_registry/*.yaml`
- Split Handler god-class → `entry/` routes + per-module pipeline-dispatch

**Phase 4 — Cutover + Dollschon (post-BASETOUCH):**
- Side-by-side run (v1 + v2) for selected chat-classes
- A/B comparison
- Cutover when v2 ≥ v1 quality
- ONLY THEN: performance overclock (Babel-Cascade parallelization + Three-Witness async, per [[baseline_2026_05_30_gx44_latency]])

**Doctrine-anchor:** No phase-4 performance work without phase-2 + phase-3 complete + schiri whistle.

---

## 8. BASETOUCH VERIFIED criteria for R2 (schiri checklist)

The R5 schiri verifies R2-wohlgeformt-ness by confirming:

1. **All 12 top-level modules exist as separate directories/files** (no god-class regression)
2. **No single file exceeds 1000 lines** (R1 D8 anti-pattern guardrail)
3. **No single function exceeds 200 lines** (R1 D2 anti-pattern guardrail)
4. **Each module has a top-comment naming its purpose + cited doctrines**
5. **Data-flow between modules is typed** (Python type-hints on inter-module boundaries)
6. **All 14 N-patterns are wired into their designated module** (per §6 table)
7. **All 8 R1 drift-targets are resolved** (D1–D8 each have explicit mitigation in v2 layout)
8. **R0 verdict-axis is consumed by exactly ONE module** (`factampel/`) — no scattered ad-hoc verdict-assignment

If all 8 verified → R2-wohlgeformt → unblocks Phase 4 cutover.
If any fail → first-base is not solid → continue M-track + extraction work.

---

## 9. References

**Companion docs:**
- `docs/R0_factfact_color_line_schematic.md` — verdict-axis spec (FIRST BASE)
- `benchmark_cc/SCHEMATICS_v1.md` — R1 v1 audit (preserved-patterns + drift-targets)

**Doctrines (memory cross-refs):**
- [[1455xl_chassis_goal_driven_funnel]] — goal-driven funnel architecture
- [[basetouch_verified_then_dollschon_overclock]] — schiri gate
- [[factlevel_splice_6band_and_google1998_test]] — three-witness operationalization
- [[factampel_implementation_roadmap_pixabay_classification]] — externalize-classification doctrine
- [[factfact_cache_re_labrador_timewindow]] — cache convergence
- [[hammwoehner_blank_slate_and_sonic_screwdriver]] — blank-slate-rebuild prescription
- [[alarm_l0_architectural_priority_nanosecond_counts]] — L0 architectural priority
- [[vulnerable_user_protection_reziprok_ceiling]] — vulnerable-user redirect
- [[death_penalty_void]] — output hard-stop check
- [[claude_chat_access_discipline]] — store/ access boundary
- [[baseline_2026_05_30_gx44_latency]] — what to optimize POST-BASETOUCH

**Code-targets:**
- `wrapper_v2/pipeline/` — existing 10 modules (M1+M2+factampel+three-witness+wiki-wortwolke+pre-search+doublecheck+fringe+knowledge-q+morpheme+babel-cascade)
- `wrapper_v2/config/babel_p_matrix.json` — Babel-Cascade routing
- `wrapper_v2/infra/audit_log.py`, `witness_cache.py`, `wrapper_v1_adapters.py` — existing infra
- `benchmark_cc/wrapper_cc.py` v1 (7783 lines, R1-audited) — source for extraction

---

**END OF R2 SKIZZE.** Submit to R5 schiri once §8 criteria are verifiable by external arbiter. Do not cutover to v2 in production before BASETOUCH VERIFIED whistle.
