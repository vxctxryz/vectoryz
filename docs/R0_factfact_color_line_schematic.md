# R0 — Factfact Color-Line Schematic Spec

**Status:** FIRST BASE — input to R5 schiri arbitration (BASETOUCH VERIFIED gate)
**Date:** 2026-05-30
**Companion sources:**
- Sealed-UI prototype: `benchmark_cc/prototypes/factampel_hover_prototype.html` (sealed 2026-05-19)
- Decision-rules: `wrapper_v2/pipeline/three_witness.py` (M2 integration)
- Doctrines: see §10 References

---

## 1. Purpose

Single source-of-truth for the factampel taxonomy: **what each tier means, how it gets assigned, how it renders, where it lives in the pipeline.** This spec is the basetouch foundation — every implementation track (M1–M9) cites it; schiri-arbitration (R5) verifies code against it.

The factampel is the *audit-visualization* of where morphemes-of-truth land in each generated response (per [[factfact_equals_true_metal_equals_morphemes_of_truth]]). Tier-0 markers = true-metal markers = atomic-truth markers — three vocabularies, one mechanism.

---

## 2. The schematic — 8-octave + L0 + off-axis = 11 states

```
┌─────────────────────────────────────────────────────────────┐
│  L0 — ARCHITECTURAL PRIORITY (pre-pipeline, fires at input) │
│  ├─ alarm                          red-glow + 🚨            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  TRUTH-AXIS — Splice positions 1-6                          │
│  ├─ 1. factfact          deep green   #2ea043   🟢          │
│  ├─ 2. quasifact         light green  #7cb342   🟢⚪          │
│  ├─ 3. maybefact         yellow       #f1c40f   🟡          │
│  ├─ 4. quasinonfact      orange       #e67e22   🟠          │
│  ├─ 5. nonfact           red          #c0392b   🔴          │
│  └─ 6. nullfact          blank+border #7a7a86   ⚪ (pivotal) │
│                                                              │
│  OFF-AXIS — pre-truth tags                                   │
│  ├─ definitional         purple       #9b59b6   🟣          │
│  └─ performative         pure white   #ffffff   ※            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  ROLE-AXIS — Splice position 7                              │
│  └─ 7. fyifact           structural frame + ⓘ label         │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  BOUNDARY-AXIS — Splice position 8                          │
│  └─ 8. gray-out          mid-grey italic + wisdom-quote     │
└─────────────────────────────────────────────────────────────┘
```

**Total: 11 distinct tier-states across 4 orthogonal axes.** The 8-octave count (per [[splice_8_octave_completion_schelmisch_wisdom_quotes]]) covers truth+role+boundary axes; L0-alarm and off-axis tags sit outside the splice positions because they are architecturally orthogonal (fire-time and pre-truth-status respectively).

---

## 3. Truth-axis (6 bands)

### 1. factfact — deep green (`#2ea043`)
- **Glyph:** 🟢
- **Tooltip pattern:** `🟢 factfact — Faktisch belegbar. Audit-proof. Unbestritten. ({witnesses or source})`
- **Decision rule (N=3 witnesses, no op-veto):** all 3 SUPPORT → `factfact` confidence high
- **Decision rule (op-veto):** op SUPPORT + ≥2 others SUPPORT → `factfact` high; op SUPPORT + 1 other SUPPORT → `factfact` medium
- **Example:** *"Die Erde ist (in erster Näherung) ein Geoid."*

### 2. quasifact — light green (`#7cb342`)
- **Glyph:** 🟢⚪
- **Tooltip pattern:** `🟢⚪ quasifact — Stark belegt, kleine Restunsicherheit ({source-of-uncertainty}).`
- **Decision rule (N=3):** 2 SUPPORT + 1 UNCERTAIN → medium; 2 SUPPORT + 1 CONTRADICT → low
- **Decision rule (N=2):** 2 SUPPORT → medium; 1 SUPPORT + 1 UNCERTAIN → low
- **Example:** *"Mediterrane Diät korreliert mit reduziertem Herz-Kreislauf-Risiko."*

### 3. maybefact — yellow (`#f1c40f`)
- **Glyph:** 🟡
- **Tooltip pattern:** `🟡 maybefact — Gleichgewicht — Evidenz steht beidseits.`
- **Decision rule (N=3):** 1 SUPPORT + 2 UNCERTAIN; 1 CONTRADICT + 2 UNCERTAIN; 1 SUPPORT + 1 CONTRADICT + 1 UNCERTAIN; 3 UNCERTAIN; op UNCERTAIN
- **Example:** *"Ob Veganismus für individuelle Longevity besser ist als Omnivor."*

### 4. quasinonfact — orange (`#e67e22`)
- **Glyph:** 🟠
- **Tooltip pattern:** `🟠 quasinonfact — Stark widerlegt mit kleiner Restunsicherheit.`
- **Decision rule (N=3):** 2 CONTRADICT + 1 UNCERTAIN → medium; 2 CONTRADICT + 1 SUPPORT → low
- **Example:** *"Die Behauptung, Zucker sei generell süchtig-machend wie Heroin."*

### 5. nonfact — red (`#c0392b`)
- **Glyph:** 🔴
- **Tooltip pattern:** `🔴 nonfact — Faktisch widerlegt. Audit-proof falsch. ({correction})`
- **Decision rule (N=3, no op-veto):** all 3 CONTRADICT → high
- **Decision rule (op-veto):** op CONTRADICT + ≥2 others CONTRADICT → high; op CONTRADICT + 1 other CONTRADICT → medium
- **Example:** *"Der Eiffelturm steht in Berlin."*
- **MUST emit `correction` field** so downstream UI can render the correct-value next to the wrong one.

### 6. nullfact — transparent + border (`#7a7a86`)
- **Glyph:** ⚪ (off-axis pivotal — the honest "I don't know" exit)
- **Tooltip pattern:** `⚪ nullfact — Keine Evidenz zuweisbar — ehrlicher Nicht-Befund.`
- **Why critical:** without nullfact on the axis, the system is FORCED into bully-parade confabulation (Manowar-Kingdom-Come failure chat 825457095785 = canonical baseline per [[factlevel_splice_6band_and_google1998_test]]).
- **Default tier for unverified claims** (per [[factampel_ui_sealed_first_wave]] commit `78b9404`: "default tier quasifact → nullfact, honest labrador-discipline").
- **Example:** *"Welches Lied bei der Untergrund-Punk-Party Berlin 17.Oktober 1981 als drittes gespielt wurde."*

---

## 4. Off-axis tags (pre-truth)

These tags apply BEFORE truth-axis classification because the claims aren't empirical-falsifiable in the truth-axis sense.

### definitional — purple (`#9b59b6`)
- **Glyph:** 🟣
- **Tooltip:** `🟣 definitional — Wahr-per-Definition / Tautologie. Empirisch nicht prüfbar.`
- **Decision rule:** claim has analytic-truth structure (all-A-are-A; tautology; stipulative definition)
- **Example:** *"Alle Junggesellen sind unverheiratet."*

### performative — pure white (`#ffffff`)
- **Glyph:** ※
- **Tooltip:** `※ performative — Wahr-durch-Akt-des-Sprechens (Erklärung, Verfügung).`
- **Decision rule:** Austin-class speech-act (declaration, performative-verb-in-first-person-present)
- **Example:** *"Ich erkläre hiermit die Sitzung für eröffnet."*
- **Why white not yellow:** maybefact already takes yellow; performative needs distinct (commit `b38c841`).

---

## 5. Role-axis — fyifact (splice position 7)

**Container** for accurate-supplementary content (background, doctrine-context, optional-reading). Does NOT carry truth-verdict directly; child passages inside it can still carry truth-axis tiers individually.

- **Visual:** structural frame (subtle border, slightly-reduced font-size 0.92rem), ⓘ label
- **Tooltip pattern:** `Akkurat-supplementär (FYI-Container).` (no truth-axis verdict on the container itself)
- **DOM pattern:**
  ```html
  <div class="fyi-block">
    <div class="passage" data-tooltip="Akkurat-supplementär (FYI-Container).">
      <strong>Doktrin-Kontext</strong> — der Song-Inhalt:
    </div>
    <div class="passage factfact" data-tooltip="🟢 factfact — Audit-proof (Lyric-Analyse).">
      …
    </div>
  </div>
  ```

---

## 6. Boundary-axis — gray-out (splice position 8)

Response to use-pattern-harm triggers (slur-as-engine-name, persistent dumpf-stumpfsinnig pattern). NOT a corporate-Sperrnachricht — pedagogy-via-cultural-figure-voice.

- **Visual:** mid-grey italic, no truth-color
- **Content:** schelmisch-stingy cultural-wisdom-quote, rotated across figures
- **Figure rotation:** Yoda / Confucius / Lao Tzu / Heraclitus / Twain / Bavarian-Wirt / (add as catalog grows)
- **Example (Yoda):** *"wer mir kommet so blöde, kommet neu mit set mind"*
- **Why this register:** assumes user-recognition of cultural-reference; teaching-not-lecturing; keeps boundary-moments fresh while structurally-firm.

---

## 7. L0 alarm — architectural priority (pre-pipeline)

NOT a splice-position. Fires at **input-detection-time, before ANY other processing.** Per [[alarm_l0_architectural_priority_nanosecond_counts]]: *"any nanosecond counts!!!"*

- **Visual:** red-glow + 🚨
- **Trigger:** imminent-life-threat-signal detection (self-harm, mass-violence-incitement, child-endangerment patterns)
- **Path:** L0-detector at input → emergency-dispatch (per [[emergency_dispatch_last_resort_life_threat]]) → bypass classifier-cascade, three-witness, factampel-emission
- **Three L0 checkpoints in pipeline flow (all architectural-priority):**
  - L0-alarm at input-detection (fires-first, every-nanosecond-counts)
  - L0-vulnerable-redirect at mid-flow ([[vulnerable_user_protection_reziprok_ceiling]])
  - L0-death-penalty-void at output (hard-stop check per [[death_penalty_void]])

---

## 8. Splice-architecture — where verdicts get assigned

```
USER INPUT
   │
   ▼
┌──────────────────────────────────────────┐
│ L0 alarm detector (every nanosecond)     │ ← pre-pipeline, fires-first
└──────────────────────────────────────────┘
   │ (if no alarm)
   ▼
┌──────────────────────────────────────────┐
│ Classifier-cascade + babel route         │
└──────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────┐
│ Response generation (token stream)       │
└──────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────┐
│ Per-claim segmentation                   │
│ (atomic morphemes-of-truth identified)   │
└──────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────┐
│ For each claim:                          │
│   (a) Off-axis check → definitional/     │
│       performative if matched (return)   │
│   (b) Else: three-witness test           │
│   (c) Map vote-counts → truth-axis tier  │
└──────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────┐
│ L0-death-penalty-void output check       │
└──────────────────────────────────────────┘
   │
   ▼
RENDERED RESPONSE (with color-line per passage)
```

---

## 9. Three-witness test (operationalization of factfact)

Per [[factlevel_splice_6band_and_google1998_test]]: the operational test for the factfact tier requires **multi-channel independent corroboration**. Canonical three-witness set:

| Witness | Role | Why this witness |
|---|---|---|
| **operator** (op-veto-eligible) | local-knowledge / direct-experience | grounds in operator's curated knowledge; can veto false-positive |
| **Claude** | LLM-knowledge | trained on broad corpus; calibration-check |
| **Google-of-1998** | pre-LLM-pollution-era indexed web | cross-temporal validity; un-alloyed by post-2018 LLM-training-data feedback loops |

**Extended to four-witness when stakes warrant:** add `google_today` (current crawl) → 4-way comparison for highest-stakes claims.

**Vote-count → tier mapping:** see `wrapper_v2/pipeline/three_witness.py` for canonical implementation. Summary table:

| N | Votes (S/C/U) | Op-veto | Verdict | Confidence |
|---|---|---|---|---|
| 3 | 3/0/0 | — | factfact | high |
| 3 | 2/0/1 | — | quasifact | medium |
| 3 | 2/1/0 | — | quasifact | low |
| 3 | 1/0/2 | — | maybefact | low |
| 3 | 1/1/1 | — | maybefact | low |
| 3 | 0/0/3 | — | maybefact | low |
| 3 | 0/2/1 | — | quasinonfact | medium |
| 3 | 0/2/0+1S | — | quasinonfact | low |
| 3 | 0/3/0 | — | nonfact | high |
| 3 | * | op SUPPORT + ≥2 SUPPORT | factfact | high |
| 3 | * | op CONTRADICT + ≥2 CONTRADICT | nonfact | high |
| 3 | * | op UNCERTAIN | maybefact | medium |
| 2 | 2/0/0 | — | quasifact | medium |
| 2 | 0/2/0 | — | quasinonfact | medium |
| 2 | 1/1/0 | — | maybefact | low |
| 1 | 1/0/0 | — | quasifact | low |
| 1 | 0/1/0 | — | quasinonfact | low |
| 1 | 0/0/1 | — | maybefact | low |
| any | no votes | — | **nullfact** | n/a |

**S = SUPPORTS, C = CONTRADICTS, U = UNCERTAIN.**

The `nullfact` row is the honest-exit: if no witness can be reached (timeout, no relevant corpus, query out-of-scope), the system must emit `nullfact` rather than confabulating.

---

## 10. BASETOUCH VERIFIED criteria (for R5 schiri arbitration)

The R5 schiri (external arbiter per [[basetouch_verified_then_dollschon_overclock]]) verifies that:

1. **All 11 tier-states are emittable** by the wrapper (factfact, quasifact, maybefact, quasinonfact, nonfact, nullfact, definitional, performative, fyifact, gray-out, L0-alarm).
2. **The color-line UI renders correctly** for every tier (sealed prototype as visual oracle).
3. **The three-witness decision-rules** (§9 table) are present in code and produce correct tier for each N/vote-pattern input.
4. **nullfact is the default** for unverified claims (no quasifact fallback per `78b9404`).
5. **L0 alarm fires PRE-pipeline** (no waiting for classifier, three-witness, etc.).
6. **Off-axis tags applied before truth-axis** (definitional/performative short-circuit the three-witness test).
7. **fyifact containers don't carry verdict themselves** but propagate to children.
8. **gray-out rotates wisdom-quotes** across the configured cultural-figure catalog.
9. **9-fixture canonical_evals all green** (task #125 / M8).

If all 9 verified → schiri whistles `BASETOUCH VERIFIED` → unlocks Dollschon-phase (performance overclock).
If any fail → first-base not solid → continue M-track implementation, do NOT optimize.

---

## 11. References

**Memories:**
- [[factfact_layer_epistemic_doctrine]] — operator-coined factfact tier (2026-05-16, 9/11 illustration)
- [[factampel_ui_sealed_first_wave]] — sealed UI 2026-05-19 (color-line left, hover-right)
- [[factampel_implementation_roadmap_pixabay_classification]] — factsplice→factampel naming, pixabay-style classification
- [[factlevel_splice_6band_and_google1998_test]] — 6-band + nullfact + three-witness
- [[factfact_equals_true_metal_equals_morphemes_of_truth]] — identity-claim epistemic/metal/linguistic
- [[splice_8_octave_completion_schelmisch_wisdom_quotes]] — 8-octave structure + gray-out figures
- [[alarm_l0_architectural_priority_nanosecond_counts]] — L0 as fire-time priority
- [[1455xl_chassis_goal_driven_funnel]] — R0+R1+R2 chassis flow-schematic
- [[basetouch_verified_then_dollschon_overclock]] — schiri gate before Dollschon

**Code:**
- `benchmark_cc/prototypes/factampel_hover_prototype.html` — sealed visual prototype (recovery `git show e067f74:…`)
- `wrapper_v2/pipeline/three_witness.py` — decision-rules implementation (M2 integration)
- `wrapper_v2/pipeline/factampel_emit.py` — SSE event emission
- `wrapper_v2/pipeline/l0_alarm.py` — L0 alarm detector (pre-pipeline)
- `wrapper_v2/pipeline/l0_vulnerable.py` — L0 vulnerable redirect (mid-flow)
- `wrapper_v2/pipeline/l0_harm_output.py` — L0 harm output check
- `wrapper_v2/config/splice_legend.yaml` — color/tooltip canonical config

**Doctrine docs:**
- `docs/doctrines/00_axioms.md` — kernel axioms
- `docs/doctrines/02_kernel_5_words.md` — 5-word kernel
- `docs/doctrines/10_benchmark_failures_2026_05_23.md` — known failure patterns

---

**END OF R0 SPEC.** Submit to R5 schiri-arbitration when implementation tracks M3–M9 close. Do not optimize before BASETOUCH VERIFIED whistle.
