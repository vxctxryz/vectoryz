# 10 — Benchmark Failures (2026-05-23)

## Why this file exists

Audit-open-door is the discipline that what fails publicly does not get hidden. This file documents four failures discovered during a comparative-benchmark run on 2026-05-23, when vectoryz responses were compared against Google and Ecosia on identical questions.

The point is not self-flagellation; it is engineering record-keeping. By their deeds shall ye know them — including our own.

## Test conditions

- date: 2026-05-23
- engines compared: Google, Ecosia, vectoryz.de
- prompts: four single-term and short-phrase questions
- evaluation: comparative content quality, latency, hallucination, completeness

## Round 1 — "irie and ovastandin?"

Two terms from Iyaric (Rastafari language register). Operator-curated test for cultural-linguistic knowledge.

| Engine | Result |
|---|---|
| Google | correct; identified Iyaric origin, gave meaning, cited sources |
| Ecosia | honestly admitted partial knowledge, asked for context |
| vectoryz | **hallucinated** — invented a "West-African skin-care product" for *irie* and a cholesterol drug ("Ovastatin") for *ovastandin* |

**Failure class: phonetic substitution + cultural blind spot.**

The model substituted *ovastandin* → *ovastatin* (statin family, cholesterol drug) because the trained suffix `-statin` had higher distribution mass than the unknown Iyaric term. The cultural register of Rastafari language was not represented in trainable form.

## Round 2 — "what is a google?"

Standard mainstream-tech query. Should be easy.

| Engine | Result |
|---|---|
| Google | comprehensive, branded, complete |
| Ecosia | structured, complete, with sustainability angle |
| vectoryz | **shallow + slow** — three paragraphs of generic phrasing, missed standard facts (founders' names, Stanford origin, parent company, current CEO, key products), took 3 m 24 s |

**Failure class: shallowness + normative overstatement.**

Where Google and Ecosia delivered concrete facts, vectoryz delivered evaluative adjectives ("indispensable instrument", "success story", "synonymous with online search"). The Tribunal layer correctly flagged "unverzichtbares Instrument" as `quasinonfact`, but did not detect missing standard facts.

## Round 3 — "was ist ein vectoryz?"

A self-recognition test. The project's own name.

| Engine | Result |
|---|---|
| Google | honestly admitted unknown; suggested possible typo for "Vektor" (mathematical), offered to search for the specific name |
| Ecosia | honestly admitted unknown; asked for context |
| vectoryz | **catastrophic prompt-leak** — emitted the internal decomposition staging prompt verbatim to the user; never produced a final answer; failed to recognise its own name |

**Failure class: prompt-leak + self-recognition failure.**

An internal decomposition prompt (named in the project as `navigatorBESTEFFORT`) was streamed to the user as if it were the final answer. The model also misread "vectoryz" as the unrelated concepts "vectorization" and "vector space".

## Round 4 — "what is a ecosia?"

| Engine | Result |
|---|---|
| Google | comprehensive |
| Ecosia | self-description |
| vectoryz | **functional — first solid result of the day**. Founder name, year, location, business model, transparency reports, the 200%-renewable-energy claim (correctly flagged by Tribunal as `quasinonfact` — that is the system working as designed). Latency still slow (4 m 60 s — also revealing a UI display bug where 60 s did not roll over to next minute). |

**Diagnosis: where the model has substantive training-data and unambiguous phonetics, the wrapper performs.**

## Cross-failure pattern

The four failure classes are distinct and uncorrelated:

1. cultural-linguistic blind spot + phonetic substitution
2. shallowness + normative overstatement (filling word-budget with adjectives rather than facts)
3. prompt-leak + self-recognition failure
4. (no failure class — round 4 worked)

Each warrants a different engineering response:

- **for class 1:** populate `knowledge_cache` with cultural-specific entries (Iyaric, Yiddish, regional dialects); add phonetic-substitution-guard;
- **for class 2:** add a `completeness-check` classifier (does the answer cover the standard-fact-set for this topic class?); reduce normative adjectives in system prompt;
- **for class 3:** add a strict prompt-leak guard (post-generation regex check for engine-internal markers); seed `knowledge_cache` with a self-description entry.

These tasks are queued for v0.1.6.

## Honest verdict

On the day of this test, on three out of four questions, vectoryz performed worse than a small green search engine that simply said "I don't know, could you give me context?" Honesty about knowing one's limits is itself a high-grade behavioural quality — and vectoryz, in three rounds out of four, failed to meet that quality.

Documenting this here is itself an application of Rule 2 + Check: prüfe, behalte das beste (= the diagnosis), wiederhole (= improve in v0.1.6), and let the deeds speak.

## License

MIT — adopt, modify, dismiss.
