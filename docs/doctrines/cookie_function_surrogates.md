# Cookie-Function Surrogates — engineering rigor behind "deprecated void"

**Status:** active reference table for the
[`three_layer_storage_doctrine.md`](three_layer_storage_doctrine.md)
**Originated:** 2026-05-22 — operator pushed: "what defines a cookie? are
we surrogating or oversacrificing?"

---

## The principle being defended

When [[broselfrei_2026_decree]] said "no technically necessary cookies
in 2026 — every former cookie use-case has a non-cookie alternative", it
made a structural claim that needs structural proof. This document is
that proof: every plausible cookie-function with its vectoryz surrogate
(or its NOT-NEEDED justification).

If a CCC-class auditor finds a cookie-function we missed *and* for which
no surrogate exists, the doctrine has a gap. We accept the challenge —
see [`docs/contributing/wer_fehler_findet.md`](../contributing/wer_fehler_findet.md)
(planned).

---

## The inventory

| # | Cookie function | Traditional implementation | vectoryz surrogate | Status |
|---|-----------------|---------------------------|--------------------|---|
| 1 | Authentication / login session | session-cookie | **NONE NEEDED** — anon-only by design; no accounts | ✓ architecture-eliminated |
| 2 | CSRF protection | double-submit cookie or hidden form-token | **NONE NEEDED** — no cookies = no Cross-Site-Request-Forgery attack vector exists in the first place | ✓ category-collapsed |
| 3 | Shopping cart / form state | session-cookie holding cart-id | **NONE NEEDED** — no commerce on vectoryz | ✓ feature-absent |
| 4 | Theme preference (light/dark) | preference-cookie | **`localStorage[vctz-theme]`** — declared in datenschutz §7, light=default, respects OS `prefers-color-scheme` if unset | ✓ surrogated |
| 5 | Language preference | language-cookie | **`Accept-Language` HTTP header** — browser sends automatically; server reads as-needed for content-negotiation | ✓ surrogated (browser-native) |
| 6 | Cookie-consent state (the meta-cookie) | own consent-cookie | **NONE NEEDED** — zero cookies means nothing to consent to; the kategorische Selbstauflösung | ✓ recursive-resolved |
| 7 | Load-balancer sticky session | LB-injected cookie | **NONE NEEDED** — single-host architecture (holodome); no LB-routing concerns | ✓ architecture-eliminated |
| 8 | Anti-replay nonce / OAuth state | nonce-cookie | **server-side in-memory map** — nonce lives briefly in process memory, validates the inbound, then dropped; no client persistence needed | ✓ surrogated (server-memory) |
| 9 | A/B test bucket | bucket-cookie | **NONE NEEDED** — vectoryz does not A/B-test users; all users get the same experience | ✓ feature-absent |
| 10 | Analytics tracking (Google/Plausible/etc.) | 3rd-party cookies | **NONE — by doctrine** — no analytics. The site is server-log-minimum (7d TTL) and that's the entire telemetry surface | ✓ doctrine-forbidden |
| 11 | Chat continuity (resume an ongoing chat) | chat-session-cookie | **URL state**: `?id=<chatId>` query param + `#k=<key>` fragment. The chat-id identifies the server-blob, the key decrypts it. Browser-only key, never sent. | ✓ surrogated (URL-state) |
| 12 | Resume-on-page-reload (within same chat) | session-cookie | **URL state** (same as #11) — reloading the URL is the resume mechanism | ✓ surrogated (URL-state) |
| 13 | Multi-device continuity | logged-in user cookie | **NONE NEEDED** — anon-by-design; user copies URL between devices manually. Deliberate friction = privacy property | ✓ architecture-aligned |
| 14 | Personalization preferences (font-size etc.) | pref-cookie | **`localStorage`** if added — would join `vctz-theme` in the declared whitelist, with documented function. Not currently used. | ✓ template-ready |
| 15 | Performance metrics (real-user monitoring) | RUM-cookie | **NONE — by doctrine** — no client-side telemetry of any kind | ✓ doctrine-forbidden |
| 16 | Crash / error reporting | session-id cookie | **NONE — by doctrine** — server-side errors logged in 7d-rotated logs; client-side errors stay client-side | ✓ doctrine-forbidden |
| 17 | Feature flags / experiments | flag-cookie | **NONE NEEDED** — config served as part of static HTML; no per-user variation | ✓ architecture-aligned |
| 18 | Cross-tab synchronization | shared-state cookie | **`BroadcastChannel` API** if needed; not currently used. Not a cookie use-case in 2026 anyway. | ✓ surrogated (modern-API) |

**Tally:**
- 13 of 18 functions are **NOT NEEDED** (architecture-eliminated, feature-absent, doctrine-forbidden, or category-collapsed)
- 4 of 18 are **surrogated** by non-cookie mechanisms (localStorage, HTTP headers, URL state, server memory, BroadcastChannel)
- 1 of 18 (#14) is template-ready: if we ever need a new preference, it joins the localStorage whitelist declaratively

→ **Zero cookies are needed.** The "deprecated-void" claim survives the inventory.

---

## How to challenge this table

If you can identify a cookie-function vectoryz genuinely needs that
isn't covered above — or for which our proposed surrogate doesn't
actually work — we want to know. File an issue at:

→ https://codeberg.org/vxctxryz/vectoryz/issues
→ https://github.com/vxctxryz/vectoryz/issues

Tag: `cookie-surrogate-challenge`. The doctrine is falsifiable, and
that's the point.

---

## What this table does NOT cover

- **HTTP headers other than `Set-Cookie`** that might leak info
  (e.g., ETag, `Strict-Transport-Security`). These are fingerprinty
  in some scenarios but not in the cookie-doctrine scope.
- **TLS-level fingerprinting** (JA3/JA4) — outside the scope of any
  application-layer doctrine.
- **Server-side logs** — covered by [[seven_day_retention_doctrine]].
- **Chat-content storage** — covered by Layer 3 of the
  [[three_layer_storage_doctrine]] (server-state-opt-in).

The table is specifically about the **`Set-Cookie` / `Cookie` HTTP
mechanism**.

---

## Related

- [[three_layer_storage_doctrine]] — the framework this table feeds
- [[broselfrei_2026_decree]] — the original claim this table proves
- [[default_prophylactic_debroeslar]] — runtime enforcement on the
  client side
- [[audit_open_door_doctrine]] — why we publish the table at all
