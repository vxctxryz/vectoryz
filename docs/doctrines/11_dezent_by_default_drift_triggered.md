# 11 — Calm-by-default, drift-triggered escalation

## The principle

Audit-surfaces are **calm by default**. They escalate to full visibility only when actual drift is detected — or when the user manually requests deeper view.

## Why this matters

A system that audits itself in public is good. A system that *renders identical retry-iterations three times on every answer regardless of necessity* is bloat. The chat experience becomes noisy. The user reads the same paragraph three times. Bandwidth burns. Cognitive overhead climbs.

The discipline: **prove your work, but only when it is informative**.

## Operational implementation

| Surface | Default state | Escalation trigger |
|---|---|---|
| Faktampel-tier markers | always shown (compact) | always — small tag per claim |
| Tribunal-witnesses output | runs internally, hidden by default | shown if drift between initial classification and tribunal-verdict crosses threshold |
| Retry-cycles | collapsed if identical | expanded if divergent (= audit evidence) |
| Phase-timeline | one-line compact summary | full breakdown on click |
| Verbose model-internals | hidden | "always-deep-audit" user toggle |

## Why this is doctrinally aligned

This is Rule 1 applied to UI: we would not want to be force-fed information we did not ask for, so we do not force-feed our users.

This is `stay-irie-mirror-laser` applied at the interface layer: the surface is calm (irie) by default; the deep examination (ovastandin) is available on request or when needed.

## Anti-pattern

What this avoids:

- the system showing three identical retry-iterations in a row, padding the chat output to triple length when the model in fact converged on the first attempt;
- the Tribunal-verdicts being rendered as a wall of `maybefact` annotations on every sentence of a routine answer, indistinguishable from informative drift-flags;
- the phase-timeline displaying eight processing-phase rows on a one-second response.

In each case, the audit-discipline is preserved internally; only the visible rendering is calmed.

## Target metric (operator-articulated)

- response latency: substantially faster than today's typical 3-5 minutes for standard queries
- accuracy: at least 98% correct across all stated claims
- audit-visibility: full only when needed (drift detected, or user request)

These three are not in tension; they are reachable together if the audit-rendering is gated by drift, not run unconditionally.

## Implementation status

- this doctrine is **target-state**, queued for v0.1.6
- the current implementation runs full audit-rendering on every answer
- the current implementation has a display bug where 60 s does not roll over to the next minute (showing "4 m 60 s" instead of "5 m 0 s") — fix queued

## Related

- [09_curiosity_reward_doctrine.md](09_curiosity_reward_doctrine.md) — same principle applied at the publication level
- [10_benchmark_failures_2026_05_23.md](10_benchmark_failures_2026_05_23.md) — the failures that revealed why this matters

## License

MIT — adopt, modify, dismiss.
