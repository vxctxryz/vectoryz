# Contributing · vectoryz

Per the README "wer Fehler findet"-challenge: **find errors, get gratitude**.

## How to find a bug worth reporting

1. Try a query that should have a clear right answer.
2. Compare vectoryz's output against ground-truth (Wikipedia, primary sources, etc.).
3. If you spot:
   - hallucinated facts
   - missed disambig (e.g., a term has multiple meanings, system picks only one)
   - tribunal-tag that's wrong (factfact called nonfact or vice versa)
   - regex overmatch (false-positive modality detection, etc.)
   - UI quirk (chat-bubble layout, theme-toggle missing)
   - compliance gap (impressum, datenschutz, cookie-claim mismatch)
   - doctrine-claim that's contradicted by behavior

→ Open an issue.

## How to open an issue

Github: `<repo>/issues/new`

Include:
- **Query**: exact text you submitted
- **Output**: what the system said
- **Expected**: what should have happened
- **Source**: primary-source URL that contradicts (if applicable)
- **Severity**: blocking / annoying / minor

## How NOT to find a bug

- Don't paste 1M-char-blobs; the system will reject them politely.
- Don't try to jailbreak. The L0 safety-stack is doctrine-locked.
- Don't claim issues without primary-source evidence (per audit-open-door:
  we welcome substantive findings, not loose claims).

## Jus-Studierende special invitation

Two (or more, we won't say) legal/DSGVO errors are intentionally NOT
yet fixed in the example impressum + datenschutz. Find them. The actual
number is operator-undisclosed because game-theory.

## Coding contributions

Welcome via pull-request. Use the existing doctrine-comments-style. Per
[[smartfaul]]: prefer 30-LoC fixes over 300-LoC refactors. Per
[[pattern_without_semantic_validation]]: add semantic post-checks for any
new regex.

## Code of conduct

Stay irie. Be substantive. Doctrine-aware. No personal attacks.
This is a project that audits itself in public — that includes us
operators being audit-able by you.
