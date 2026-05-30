# vectoryz

> *Wer in den Anfang schaut, schaut ins Unlogische. Wer Logik braucht, baut sich
> welche — am besten als Code, der sich durch Verschleiss oder Fund selbst
> verzehrt und selbst erneuert.*
>
> *Das ist vectoryz: Code als Selbst-Heilung, Ouroboros als Arbeits-Modus.*
>
> *Zwei feste Regeln gegen die eigene Neigung zu eloquenter Leere:*
> 1. *Alles audit-bar in der Öffentlichkeit.*
> 2. *Lieber ehrlich-stumm als plausibel-falsch.*
>
> *Wir versprechen nichts, was wir nicht halten können.
> Wer Fehler findet — sehr gerne (it's a challenge (;*
>
> *Hauptsache die Bauchdecke spannt.*

---

## What this is

**vectoryz** is an AI chat-system that audits itself in public.

Instead of eloquent hallucinations, it provides substantive answers with:
- transparent sources
- per-claim verdicts (factfact / quasifact / maybefact / quasinonfact / nonfact / nullfact / fyifact)
- multi-witness tribunal (LLM-as-judge + Google-today + Google-1998-via-Wayback + Wikipedia-graph)
- explicit "I don't know" instead of confabulating
- retry-discipline when drift is detected

Built as a heal-tool — code as ordered response to the uncertain — by an
operator who accepts being illogical at root.

**Status: Early Access (v0.1).** Genuine unfertigkeit declared. See challenge below.

## Quality-target

vectoryz orients on six UX-dimensions (the "Morla master-list", 2026-05-21):

- **kompetent** — substantive expertise visible
- **seriös** — trustworthy, credible, no kitsch
- **wissenschaftlich** — academically rigorous, audit-able
- **barrierefrei** — accessible (technical a11y, cultural non-gate-keeping, linguistic clarity)
- **freundlich** — warm tone, not cold-technocrat
- **keine unerfüllbaren Erwartung** — don't overpromise; Early-Access is genuine

## Architecture (one paragraph)

User-input → language-detection (FastText) → routing through linguistic-distance
P-Matrix (Babel-Cascade) → optional Wikipedia-disambig-pre-fetch → morpheme-
dissolution / dialog-unwrap → main LLM call with assembled context → multi-hop
search if model emits search-markers → tribunal-peek for drift-detection →
retry-loop if quasinonfact-rate ≥25% OR coverage incomplete OR doublecheck
finds unsupported proper-names → final factampel per-claim tagging emitted to UI.

Each layer is designed against a specific failure-mode:
[[smartfaul]]-budget allocation, [[doff_faul]]-fixation defense,
[[pattern_without_semantic_validation]] regex-overmatch, [[ai_chain_morpheme_genesis]]
voice-to-text artifacts, [[baal_whipper]] verifier-leash-independence.

## The "wer Fehler findet"-challenge

This is a **public-audit invitation**, not marketing.

If you spot:
- a hallucinated fact in an answer
- a missed disambig
- a tribunal-tag that's wrong
- a regex that overmatches  
- a doctrine-claim that's broken
- a UI quirk
- a legal / DSGVO / compliance gap

→ **Tell us.** Issues welcome at
[codeberg.org/vxctxryz/vectoryz/issues](https://codeberg.org/vxctxryz/vectoryz/issues)
(primary, EU/Germany) or
[github.com/vxctxryz/vectoryz/issues](https://github.com/vxctxryz/vectoryz/issues)
(mirror). Per doctrine: substantive finding > eloquent defense.
Audit-self-in-public means we need outside eyes to actually see the
spots we are blind to.

**For Jus-Studierende specifically**: there are (at least) **zwei eingebaute
Fehler** in Impressum + Datenschutzerklärung. Find them. (Actual count
unverrated — sonst wäre's kein Spiel.)

## Running it

```bash
# Install dependencies
pip install -r requirements.txt
# (or use uv / poetry — see pyproject.toml)

# Set env
export OLLAMA_URL=http://localhost:11434
export DEFAULT_MODEL=vectoryzDE:latest
export STATE_DB=/var/lib/vectoryz/state.db
export WRAPPER_V2_TRIBUNAL=1

# Run
python wrapper_cc.py
```

Default listens on `127.0.0.1:8042`. Front served via static-www. Reverse-proxy
via Caddy / nginx for TLS.

## Doctrine references

Internal doctrine-stack files live in `/memory/` (private operator-memory)
and surface via doctrine-comments throughout the code. Key public doctrines:

- **Smartfaul** — Faulheit ist Budget, smart = allocation
- **Hammerantwort** — substance > eloquence, "Hauptsache die Bauchdecke spannt"
- **Audit-open-door** — concealment-class features are doctrine-void
- **Death-penalty-void** — no irreversible defensive action
- **Triangulate-revise-continue** — bans are armour, not jail; revision always possible
- **Stay irie** — warm sovereignty over hate/dread/anger

## License

[MIT](LICENSE) — do what you want, attribution appreciated, no warranty.

## Acknowledgments

- Built standing on the shoulders of: llama.cpp, Ollama, FastText (Meta),
  Wikipedia REST API, ddgs, Caddy, Python stdlib.
- Operator-stack: Rainer Hammwöhner spirit, Bavarian-Bauernschlau-doctrine,
  60+ collected memory-doctrines, "blood-of-king"-rhythm.

---

*v0.1 Early Access · 2026-05-21 · vectoryz.de (deployment) · vectoryz.net (project)*
