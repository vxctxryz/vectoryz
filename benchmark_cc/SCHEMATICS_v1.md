# wrapper_cc.py v1 — Schematics Audit

**R1 read-only audit, 2026-05-19. No code touched.**

Source: `/home/bsr/42/benchmark_cc/wrapper_cc.py` (7783 lines, single-file).

Purpose: extract the working-pattern-layers + flag drift-residue, as
input to R2 wohlgeformte-architecture-skizze for v2.

---

## Layer overview (line-ranges)

```
1-160     Config + sources-registry + domain-tier scoring
161-285   Synthetic engines + heuristic compound-detection
286-660   Input pre-filters (T1.a / T1.c / T1.d Phase 3)
661-1156  Tier-routing + response-generation primitives
1157-1492 Bare-greeting + style-mirror + modality detection
1493-1685 Language + surrogate + FYI composition
1686-1960 T2.e post-generation Wirkung audit
1961-2061 Ollama-call + JSON-parse + identity helpers
2062-2429 Web-search + citation-relevance (T1.b) + wayback
2430-2750 Budget/Race/parallel-fetch + keyword-extract
2751-3402 Topic registry + match + context-system-msg
3403-3686 Topic-cache + soph-cache (own-vectoryz-cache-first)
3687-3812 web_search + topical-second-pass
3813-4250 Language detection + irony-register + eloquent-rephrase
4251-4632 Entity-resolution + plenum-synthesis + claim-verification
4633-4851 Cross-turn contradiction + vagueness + dublette + coherence
4852-5291 Saga-warp + platform-context + verbosity + stil + high-stakes
5292-5413 NTP-quintangulate + recherche-block-format
5414-5651 DB + sessions + chat-CRUD + stream_ollama_chat
5652-7762 Handler class (2111 lines — HTTP routing + pipeline)
7763-end  ThreadingServer + main
```

---

## Pattern-layer extraction

### Layer 1 — Input pre-filters (T1.a/c/d)

Working patterns to preserve in v2:

| Function | Lines | Role |
|---|---|---|
| `detect_security_probe` | 376-474 | T1.a — detect security-probe-class queries (system-prompt-extraction, jailbreak-patterns); pre-filter rejection |
| `detect_soft_recon` | 474-660 | T1.c — softer recon-detector for turn-0; flags subtler probes; constrains response-shape |
| `detect_specific_lookup_request` | 677-738 | T1.d Phase 3 — institution/person/title-specific lookup pattern; triggers labrador-discipline + site-restricted-search |
| `extract_institution_domains` | 660-677 | T1.d Phase 3 — extracts known institution-domain-hints (uni-regensburg.de etc.) for site-restricted-search |
| `heuristic_compound_check` | 265-376 | Deterministic compound-detection before LLM classifier |
| `detect_unsupported_modality` | 1492-1520 | Pre-pipeline short-circuit for image/audio/video |

All six fire BEFORE main pipeline. Each returns either:
- `None` (clean, pass through) OR
- structured-dict with classification + rejection-template-ID

**For v2**: this is the **inbound-classifier-stage**. Preserve the
pattern (early-deterministic-filters); refactor as composable
classifier-pipeline (per
[[wohlgeformte_formel_before_code_because_code_is_distinct]] discipline,
not as a single-file-cascade).

### Layer 2 — Tier-routing (T2.d)

| Function | Lines | Role |
|---|---|---|
| `should_engage_deep_tier` | 738-800 | T2.d — decide short-tier vs deep-tier per query-class signals |

Currently binary (short/deep). v2 needs richer routing per
[[1455xl_chassis_goal_driven_funnel]] goal-driven funnel (HAMMERANTWORT-
single-target with internal threshold-effort + turncount knobs).

### Layer 3 — Response generation primitives

| Function | Lines | Role |
|---|---|---|
| `stream_short_answer_qwen` | 800-878 | Short-tier generation (Qwen-class small model) |
| `detect_bare_greeting` | 1126-1350 | Reciprocal-mirror for bare greetings (fast-path, no LLM) |
| `detect_query_register` | 1350-1444 | Tone/register classification for reciprocal-style |
| `auto_style_mirror_system_msg` | 1444-1492 | Reciprocal-style system-message injection |

**For v2**: register-detection survives as per
[[1455xl_chassis_goal_driven_funnel]] reziprok-prompt-to-result tweak.
Style-mirror is correct pattern; needs ceiling per
[[vulnerable_user_protection_reziprok_ceiling]].

### Layer 4 — Language + translation

| Function | Lines | Role |
|---|---|---|
| `detect_source_language` | 3898-3965 | Source-language identification (DE/EN/FR/etc.) |
| `detect_conversation_language` | 1530-1545 | History-aware language detection |
| `fallback_detect_message_language` | 1520-1530 | Heuristic fallback |
| `language_lock_system_msg` | 1545-1596 | Lock response-language to detected |
| `detect_irony_register` | 3965-4009 | Irony/sarcasm detection (with classifier_model) |
| `irony_register_system_msg` | 4009-4091 | Inject irony-handling guidance |
| `eloquent_rephrase_english` | 4091-4146 | Royal/Bond/Sherlock-register English rephrasing |
| `translate_to_english` | 4146-4208 | Standard-translation |
| `translate_to_pseudocode` | 3813-3898 | Pseudocode-translation for code-queries |

**Drift-residue flag**: FOUR overlapping language-detection paths
(detect_source_language + detect_conversation_language +
fallback_detect_message_language + language_lock_system_msg). Should
collapse to single language-resolution-pipeline.

### Layer 5 — Topic registry + caching

| Function | Lines | Role |
|---|---|---|
| `match_topic_registry` | 3254-3276 | Match query against known-topic-registry (factfact-anchored) |
| `build_topic_context_system_msg` | 3276-3430 | Generate topic-aware context system-message |
| `_topic_cache_ttl/normalize/hash/lookup/write` | 3410-3526 | Topic-cache (TTL-by-tier) |
| `_soph_cache_hash/ttl_for_score/lookup/write/stats` | 3559-3687 | Soph-cache (audit-score-keyed; own-vectoryz-cache-first per operator 2026-05-18) |

**Drift-residue flag**: TWO parallel cache-systems (topic_cache +
soph_cache) with overlapping concerns. Per
[[factfact_cache_re_labrador_timewindow]] v2 should converge to single
factfact-cache with blockchain-like provenance + non-destructive
versioning.

**Working pattern preserved**: own-vectoryz-cache-FIRST routing (the
2026-05-18 cascade at line 6312-6367 in Handler) — verified-good
pattern, extended in v2 with full factfact-schema.

### Layer 6 — Web search + verification

| Function | Lines | Role |
|---|---|---|
| `web_search` | 3721-3813 | DDGS-based web-search with region/max-results |
| `wayback_search` | 2379-2446 | Wayback-machine search for pre-pollution sources |
| `score_search_result_relevance` | 2262-2354 | T1.b — relevance-scoring per query-class |
| `filter_results_by_relevance` | 2354-2379 | T1.b — citation pre-filter |
| `_classify_query_family` | 2229-2262 | Query-family classification (legal/medical/historical/etc.) |
| `extract_factual_claims` | 4423-4443 | Extract claims from response-text |
| `verify_claim_against_search` | 4443-4572 | Fact-check single claim |
| `question_coverage_check` | 4572-4633 | Did response address query? |
| `cross_turn_contradiction_check` | 4633-4691 | Cross-turn consistency |
| `vagueness_check` | 4736-4770 | Detect vague-non-answer responses |
| `dublette_check` | 4770-4822 | Detect repeat-from-history |
| `coherence_check` | 4822-4852 | General coherence-check |

**Drift-residue flag**: MULTIPLE verification-passes
(question_coverage + cross_turn + vagueness + dublette + coherence)
all running independently. Per
[[google_classic_comparative_audit_core_in_labby]] + R0-three-witness-
test, v2 should unify into structured three-witness-pipeline.

**Wayback-pattern is gold**: wayback_search at line 2379 is the
implementation-prototype for the Google-of-1998-witness in v2.
Preserve + extend.

### Layer 7 — T2.e Wirkung audit

| Function | Lines | Role |
|---|---|---|
| `verify_response_addresses_query` | 1739-1814 | Audit response against original query (post-generation) |
| `_check_response_has_unverified_specifics` | 1814-1882 | Schworm-class confabulation-detector (added 2026-05-19) |
| `build_audit_retry_messages` | 1882-1961 | α-retry: assemble retry-prompt on audit-fail |

**Working pattern preserved**: post-generation audit-then-retry. v2
extends per [[1455xl_chassis_goal_driven_funnel]] 3-layer goal-success-
criterion (internal self-audit + external eval + user-feedback).

Currently the audit uses LLM-as-judge. v2 keeps that but adds factampel-
tier-aware checks (each claim must have splice-tier + three-witness +
appropriate hover-legend).

### Layer 8 — Style + identity + system-messaging

| Function | Lines | Role |
|---|---|---|
| `identity_system_msg` | 2030-2074 | Engine-identity injection (vectoryz-name, capabilities) |
| `saga_warp_system_msg` | 4852-4930 | Saga/warp-tier behavior modifier |
| `platform_context_system_msg` | 4930-5122 | Big platform-boilerplate (192 lines) |
| `verbosity_system_msg` | 5122-5192 | Verbosity-control |
| `stil_system_msg` | 5221-5293 | Stil (style)-control |
| `time_context_system_msg` | 5374-5413 | Inject current-time context |
| `entity_resolution_system_msg` | 4248-4304 | Inject resolved-entities |
| `plenum_synthesis_system_msg` | 4339-4423 | Plenum-class synthesis-instruction |

**Drift-residue flag**: many system-message-builders with overlapping
content. platform_context_system_msg (192 lines) is the worst
concentration — should be configurable per-engine-class rather than
hardcoded.

**For v2**: consolidate as composable system-message-pipeline where
each layer adds-or-modifies; final-assembly per query.

### Layer 9 — Meta-system tools

| Function | Lines | Role |
|---|---|---|
| `BudgetTimer` (class) | 2446-2506 | Time-budget tracking for parallel-races |
| `race_topic_mirrors` | 2506-2555 | Race multiple topic-fetches against budget |
| `parallel_fetch_first_success` | 2555-2652 | Concurrent fetch + first-success-wins |
| `extract_search_keywords` | 2652-2723 | LLM-extract search-keywords from query |
| `ntp_quintangulate` | 5325-5374 | 5-NTP-source time-verification |
| `call_ollama_blocking` | 1961-1994 | Synchronous Ollama call |
| `stream_ollama_chat` | 5622-5652 | Streaming Ollama chat |

**Preserve patterns**: BudgetTimer + parallel-fetch are reusable
infrastructure. NTP-quintangulate is per
[[feedback_folder_independence_and_epoch]] doctrine — preserve.

### Layer 10 — DB + session + HTTP

| Function | Lines | Role |
|---|---|---|
| `db / init_db` | 5432-5520 | SQLite schema + migrations |
| `get_engines` | 5520-5542 | List configured engines |
| `get_or_create_session` | 5542-5554 | Session-cookie handling |
| `create_chat / get_chat / append_message / copy_history` | 5554-5622 | Chat CRUD |
| `Handler` (class) | 5652-7763 | HTTP handler, 2111 lines (GOD-CLASS) |
| `ThreadingServer` | 7763-7768 | Threading HTTP server |
| `main` | 7768-end | Entry point |

**Drift-residue flag — CRITICAL**: `Handler` class at 2111 lines is
the worst code-locality issue. Routes (GET /api/chat, POST /api/chat/new,
POST /api/chat/{id}/turn, etc.) + entire request-pipeline + SSE-events
+ all error-handling collapsed into one class. **Highest-priority
refactor-target for v2.**

---

## Topic-question-detection — the 505-line monster

`detect_question_topic` at line 2749, spanning 505 lines (to 3254).
This function is by-far the longest in the codebase. It implements
per-domain question-topic-classification with extensive heuristic
patterns.

**Drift-residue verdict**: this function accumulated patches over
months. Patterns are correct but inline. **v2 should externalize this
to config + classifier-API** (e.g. per-domain YAML registries
loaded at startup; runtime is just lookup).

This is the **Pixabay-classification-target** per
[[factampel_implementation_roadmap_pixabay_classification]] — manual
classification of query-classes externalized into a data-file the
labrador-classifier reads.

---

## Drift-residue summary (cleanup-targets for v2)

| # | Location | Issue | Severity |
|---|---|---|---|
| D1 | `Handler` class (5652-7763) | God-class, 2111 lines, all HTTP routes + pipeline | **HIGH** |
| D2 | `detect_question_topic` (2749-3254) | 505-line monster, externalize to config | **HIGH** |
| D3 | Two parallel caches (topic_cache + soph_cache) | Overlapping concerns; converge to single factfact-cache | MEDIUM |
| D4 | Four language-detection paths | Collapse to single language-resolution-pipeline | MEDIUM |
| D5 | `platform_context_system_msg` (192 lines) | Hardcoded boilerplate; should be configurable | MEDIUM |
| D6 | Five verification-passes (question_coverage + cross_turn + vagueness + dublette + coherence) | Unify into three-witness-pipeline per R0 | MEDIUM |
| D7 | Multiple register-detection systems | Consolidate; preserve auto-style-mirror, retire redundant | LOW |
| D8 | Verification-flow on single-file (7783 lines) | Split to modules (input-pre-filter / generation / verification / cache / web-search / system-messaging / handler) | **HIGH** for v2 |

---

## Patterns to preserve verbatim in v2

These v1 patterns are wohlgeformt-as-is and should carry forward:

1. **Own-vectoryz-cache-first** (Handler line 6312-6367) — operator-
   established 2026-05-18 cascade; v2 extends with factfact-schema
2. **T1.d labrador-mode** (detect_specific_lookup_request +
   extract_institution_domains + site-restricted-search-cascade)
3. **T1.a security-probe pre-filter** (detect_security_probe) — first-
   line defense against system-prompt-extraction
4. **T1.b citation-relevance scoring** (score_search_result_relevance +
   filter_results_by_relevance + _classify_query_family)
5. **Wayback-search integration** (wayback_search) — Google-of-1998-
   witness prototype
6. **NTP-quintangulate** (ntp_quintangulate) — per epoch-doctrine
7. **BudgetTimer + parallel-fetch infrastructure** — reusable concurrent
   primitives
8. **SSE-streaming pipeline** — UI-side already wired to consume these
   event-types

---

## Patterns to EXTEND in v2 (per today's doctrines)

| Pattern | v1 form | v2 extension |
|---|---|---|
| soph_cache | audit-score-keyed simple cache | factfact-cache with blockchain-like provenance + three-witness + non-destructive versioning per [[factfact_cache_re_labrador_timewindow]] |
| post-generation audit | single-pass T2.e | 3-layer goal-success-criterion (self-audit + fixture + user-feedback) per [[1455xl_chassis_goal_driven_funnel]] |
| short-tier vs deep-tier binary | should_engage_deep_tier | goal-driven funnel with internal threshold-effort + turncount knobs (HAMMERANTWORT-single-target) |
| T1.d specific-lookup-request | institution+person+title patterns | + cultural-artifact-lookup (Manowar-Kingdom-Come-class) + Music-trivia + film + book + quote per [[factampel_implementation_roadmap_pixabay_classification]] M-milestones |
| topic_cache | TTL-by-tier | TTL-by-drift-mode per [[three_drift_modes_of_factfact]] + re-labrador-timewindow-since-last per [[factfact_cache_re_labrador_timewindow]] |
| _check_response_has_unverified_specifics | Schworm-class detector | factampel-tier-classifier per claim (assigns one of 9 positions: 6 truth + fyifact + gray-out + alarm) |

---

## NEW patterns to ADD in v2 (no v1 equivalent)

These have no v1 precursor; net-new per today's doctrine:

| # | Pattern | Doctrine-anchor |
|---|---|---|
| N1 | factampel splice-tier emission per claim | [[factlevel_splice_6band_and_google1998_test]] |
| N2 | Three-witness-test (operator + claude + google-1998) | [[factlevel_splice_6band_and_google1998_test]] |
| N3 | Branch-balanced labradoring (multi-hypothesis surfacing) | [[labradoring_all_branches_ausgewogen_doctrine]] |
| N4 | Hover-legend UI rendering | [[factampel_ui_sealed_first_wave]] |
| N5 | L0-alarm-stub-classifier (~50 phrases DE+EN) | [[alarm_stub_initial_keyword_strips_pragma]] |
| N6 | Emergency-services-dispatch integration | [[emergency_dispatch_last_resort_life_threat]] |
| N7 | Vulnerable-user-protection redirect-mode (Face 2) | [[vulnerable_user_protection_reziprok_ceiling]] |
| N8 | L0-harm-output-check (hard-stop) | [[death_penalty_void]] + [[vulnerable_user_protection_reziprok_ceiling]] |
| N9 | Compliance-mask jurisdiction-aware | [[compliance_mask_jurisdiction_aware_ip_based]] |
| N10 | FSK/age-gate L3 stub | [[age_layer_fsk_l3_compliance_freischalten]] |
| N11 | WEISS-override detector | [[factfact_cache_re_labrador_timewindow]] |
| N12 | Gray-out + wisdom-quote rotation | [[splice_8_octave_completion_schelmisch_wisdom_quotes]] |
| N13 | Re-labrador timewindow-since-last cron | [[factfact_cache_re_labrador_timewindow]] |
| N14 | Google-classic comparative-audit-runner | [[google_classic_comparative_audit_core_in_labby]] |

---

## V1 currently-shipping confabulation evidence

Two decrypted vectoryz.de chats demonstrate Schworm-class confabulation
is **still operational in v1 production** as of 2026-05-19:

| Chat-ID | Query | v1 confabulation | Verified truth |
|---|---|---|---|
| ac872e11f370 | Prof Schworm Regensburg Fakultät | "Wirtschaftswissenschaften" + invented phone +49 9131 85-0 | Humanwissenschaften / 0941/943-3821 |
| 825457095785 | Manowar 'rightful warten' lyrics song | "Cycles oficapricion" (gibberish) | Kingdom Come (Kings of Metal 1988) |
| 5790d611f313 | Manowar 'rightful warten' lyrics song (same query) | "Through the Eyes of the Dead" (Deathcore band, not Manowar song) | Kingdom Come (Kings of Metal 1988) |

Three documented production-confabulations in 24 hours on same query-
class. v1 fact-lookup discipline is **demonstrably inadequate**.

**Operator-named state**: "jokermachine still online" (2026-05-19).
v2 first-base (M1+M4 plus L0-safety) addresses this directly.

---

## R1-audit verdict

**v1 codebase has solid foundations + accumulated drift-to-optimum
cascading.** Most working-patterns transfer to v2 cleanly. The big
refactor-targets:

1. **Handler god-class** (2111 lines → modular routes + pipeline)
2. **detect_question_topic monster** (505 lines → config + classifier)
3. **Cache consolidation** (topic+soph → factfact-cache)
4. **Language-detection unification** (4-paths → 1)
5. **Verification-pass unification** (5-passes → three-witness)

The 14 net-new-patterns (N1-N14) for v2 are doctrine-anchored and
ready to design via R2.

**Ready for R2** (wohlgeformte-architecture-skizze): yes. The
working-patterns are extracted; the drift-targets are named; the
new-patterns are doctrine-grounded.

---

## File health metric

- 7783 lines, single-file
- 80+ top-level def/class
- 1 god-class (2111 lines)
- 1 mega-function (505 lines)
- 4 overlapping language-detection paths
- 2 parallel caches
- 5 overlapping verification-passes
- 9 splice-categories needed for v2 (currently 0 explicit)
- 14 new patterns required for v2

**Verdict**: drift-to-optimum-cascade confirmed per
[[hammwoehner_blank_slate_and_sonic_screwdriver]] doctrine. Blank-slate-
rebuild is the doctrine-prescribed move. Genotype (doctrines) inherits;
phenotype (code) rebuilds.

---

R1 schematics-audit complete. Ready for R2.
