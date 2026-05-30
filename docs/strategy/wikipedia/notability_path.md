# Notability Path — drift-free Wikipedia strategy

## Why this document exists

A premature, self-authored Wikipedia article on the project is likely to:

- be flagged for conflict of interest (WP:COI),
- fail notability checks (WP:NOTABILITY, WP:NCORP) for lack of independent secondary sources,
- be deleted, leaving a "deletion log entry" that complicates any later attempt.

A patient, properly-grounded path produces a more stable article.

## Six-stage path

### Stage 1 — publish the press release (here, now)

The project publishes a press release on its own domain:

- `vectoryz.de/press/2026-05-22-early-access-de.html`
- `vectoryz.de/press/2026-05-22-early-access-en.html`

This is primary-source material. It supports detail-claims but does not establish notability on its own.

### Stage 2 — distribute the press release

Email the press release to specialist outlets:

- Heise, Golem.de, c't, Netzpolitik.org, t3n (German-language tech press)
- The Register, Ars Technica, Hacker News (English-language tech press)
- relevant academic groups (computational linguistics, AI safety, FLOSS research)

Do **not** treat the press release as a Wikipedia source. It is bait for independent coverage.

### Stage 3 — harden the project documentation

In parallel, develop the project's own documentation so that future coverage has solid material to reference:

- architecture diagram
- privacy model
- threat model
- deletion + retention logic
- model selection and rationale (kept in the repo, not in the press release — see `01_motto_front_door.md` in `docs/doctrines/` for the "no-stigmata" reasoning)
- limitations and known issues (see `10_benchmark_failures_2026_05_23.md` in `docs/doctrines/`)

### Stage 4 — generate independent coverage

This stage is the precondition for a Wikipedia article. Without three to five independent secondary sources, no article should be attempted.

Suitable sources (illustrative, not exhaustive):

- a feature article in a recognised tech publication;
- an independent benchmark or review;
- mention in an academic, FLOSS, or privacy-research context;
- broader external analyses of the project's technical approach.

Reprints or republications of the press release are **not** suitable — they share the press release's primary-source status.

### Stage 5 — create a Wikidata item

Once the project exists in independent published form (Stage 4), a Wikidata item becomes appropriate. Wikidata has a lower notability threshold than Wikipedia article-namespace.

A Wikidata item can later be linked from an eventual Wikipedia article as a structured-data anchor.

### Stage 6 — Wikipedia draft

Once independent secondary sources exist:

1. Create the draft in a user sandbox (`User:.../vectoryz`) or via Articles for Creation (AfC).
2. Disclose the conflict of interest on the talk page using `{{COI}}` or `{{Connected contributor}}`.
3. Submit through AfC for review by an uninvolved editor, rather than placing the article directly in mainspace.
4. After acceptance, all subsequent edits should go through the article talk page rather than directly amending the article.

The DE-draft (`draft-de.md`) and EN-draft (`draft-en.md`) in this directory are the starting templates.

## What makes a good Wikipedia seed

> The best Wikipedia seed is not maximally complete; it is minimal, neutral, verifiable, and unspectacular. Precisely those properties make it drift-resistant.

(Source: paraphrased from a third-party AI assistant's audit-pass on this strategy, 2026-05-23.)

## Time estimate

- Stages 1-3: same week as publication
- Stage 4: 2-12 months, depending on coverage
- Stage 5: 1 week once Stage 4 yields material
- Stage 6: 4-8 weeks for draft, AfC review, mainspace placement

There is no hurry. A clean article in 12 months is structurally better than a deleted-and-flagged article in 1 week.

## Licence

MIT (see root LICENSE).
