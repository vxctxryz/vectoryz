# Three-Layer Storage Doctrine

**Status:** active · canonical · enforced via `default_prophylactic_debroeslar` v2
**Originated:** 2026-05-22 conversation, operator-articulated
**Headline:** *cookie = deprecated void · client-state transparent · server-state opt-in*

---

## The kernel

vectoryz distinguishes three independent storage layers, each with
its own doctrine, its own enforcement, and its own claim. Conflating
them is dishonest; separating them is the credibility.

```
┌───────────────────────────────────────────────────────────────────────┐
│  Layer 1 — HTTP cookies        DEPRECATED-VOID                        │
│  Layer 2 — Client-state        TRANSPARENT + MINIMAL + FUNCTION-BOUND │
│  Layer 3 — Server-state        ZERO-BY-DEFAULT (v0.2; opt-in via Share)│
└───────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — HTTP cookies = DEPRECATED VOID

### The claim

vectoryz emits **zero HTTP cookies**. Not minimized, not consented-to —
**voided**. The category "technisch notwendige Cookies" is gone in 2026
(see [[broselfrei_2026_decree]]); every former cookie use-case has a
non-cookie surrogate, enumerated in
[`cookie_function_surrogates.md`](cookie_function_surrogates.md).

### Why specifically cookies (and not "all client storage")

The HTTP cookie mechanism is uniquely problematic because:

1. **Auto-transmission**: the browser sends matching cookies on
   *every* HTTP request to the origin, unrequested and unconditional.
   localStorage and friends do not.
2. **Server-settable**: the server can plant cookies via
   `Set-Cookie` response headers without JS involvement. localStorage
   has no server-header equivalent.
3. **Cross-request stateful tracking by design**: cookies were
   purpose-built for tracking. localStorage is a generic key-value
   store with no transmission semantics.
4. **Legal-regulatory weight**: §25 TTDSG / ePrivacy 5(3) gives cookies
   special prominence in the consent regime — even when both are
   covered, the popular understanding equates "tracking" with
   "cookies".

→ The doctrine targets the mechanism that *uniquely* enables
unrequested-transmission of identifying state. That mechanism = deprecated
void in our architecture.

### Enforcement

`default_prophylactic_debroeslar.js` runs on every page-load:

1. Scans `document.cookie` for any entries
2. If found: sweeps each across all plausible path/domain combinations
   with `Max-Age=0` deletion attributes
3. Surfaces a red ALARM banner naming the swept cookie(s)
4. Bottom-right badge turns red + pulsing

The wrapper's `Set-Cookie` emission was self-audited in commit `006358f`
and is now a permanent delete-instruction (`vctz_session=; Max-Age=0`),
so any legacy cookie left in a user's jar gets actively expired on next
visit to `/cc/api/*`.

---

## Layer 2 — Client-state = TRANSPARENT + MINIMAL + FUNCTION-BOUND

### The claim

vectoryz uses client-side storage (localStorage / sessionStorage /
IndexedDB) **only for declared, function-bound user-data** — never
for tracking, never auto-transmitted, always disclosed in datenschutz.

### Current policy (v0.1.x)

| Store          | Allowed entries        | Function                                                  |
|----------------|------------------------|-----------------------------------------------------------|
| localStorage   | `vctz-theme`           | theme persistence (light/dark) — declared in datenschutz §7 |
| sessionStorage | *(none)*               | no use-case identified                                    |
| IndexedDB      | *(none)*               | reserved for v0.2 Option A: `vectoryz-local-chats` + `vectoryz-favorites` (user-owned archive, explicit opt-in) |

### The principled distinction from Layer 1

Even when EU regulators treat localStorage and cookies together for
consent purposes, the operational reality is different:

```
                       HTTP cookie         localStorage / sessionStorage / IDB
                       ───────────         ───────────────────────────────────
Server-transmittable   ✓ always            ✗ never (requires JS to read+POST)
Server-settable        ✓ Set-Cookie header ✗ no equivalent
Tracking-by-default    ✓ inherent          ✗ requires JS that explicitly tracks
Server-visibility      ✓ Cookie header     ✗ blind unless JS exposes
```

→ localStorage cannot track passively. Our doctrine says it must also
not track *actively*: our JS never reads vctz-theme and sends it
anywhere. The value lives and dies in the user's browser.

### Enforcement

`default_prophylactic_debroeslar` v2 scans all three client-state
stores against the whitelist:

1. **localStorage**: any key outside `{"vctz-theme"}` → sweep
   (`removeItem`) + ALARM
2. **sessionStorage**: any key (empty whitelist) → sweep + ALARM
3. **IndexedDB**: any database name (empty whitelist in v0.1.x) →
   ALARM (no auto-delete: IndexedDB might hold user-owned data; user
   must clear via browser settings if surprised)

### Transparency surface

- datenschutz §7 declares the `vctz-theme` entry
- debroeslar badge tooltip shows live counts + named entries
- This doctrine document publicly enumerates the policy
- MIT-license + git history makes the code auditable

---

## Layer 3 — Server-state = ZERO-BY-DEFAULT (v0.2)

### The claim (target state)

By default, vectoryz keeps **no server-side record of a user's chat**.
The encrypted blob is persisted only when the user explicitly clicks
"Share" — at which point the 7-day TTL applies.

### Current state (v0.1.x)

Server still stores all chats by default (legacy architecture). The
v0.1.x mitigation:

- 7-day TTL on all stored chats (systemd-timer
  `vectoryz-chat-vault-ttl.timer`)
- E2E AES-256-GCM with key in URL fragment; server cannot decrypt
- Auto-delete fully implemented + tested

### v0.2 target (Option A)

See [`../architecture/option_a_client_side_default.md`](../architecture/option_a_client_side_default.md)
for the architecture plan. Summary:

- `/api/chat/stream` becomes default (no server persistence)
- `/api/chat/share` is the only persistence endpoint (opt-in)
- Client-side chat history lives in IndexedDB (Layer 2 whitelist
  expands to include `vectoryz-local-chats` + `vectoryz-favorites`)

### Why this is "Layer 3" and not part of Layer 2

Layer 2 is about *what the user's browser stores*. Layer 3 is about
*what our server stores* on behalf of the user. They're independent
choices with independent enforcement. We can be strict on one and
loose on the other (currently: Layer 1 strict, Layer 2 strict, Layer
3 transitional).

---

## The asymmetry summary

| Layer | Storage location | Default | Audit surface |
|---|---|---|---|
| 1 | browser cookie jar (transmitted) | **VOID** | debroeslar sweep + ALARM |
| 2 | browser local storage (not transmitted) | **declared whitelist** | debroeslar scan + sweep-unknown |
| 3 | server SQLite | **opt-in via Share** (v0.2 target) | systemd-timer TTL + datenschutz §4 |

Each layer's claim is **independently checkable** by an auditor.

---

## Why three layers (not one, not five)

The three layers correspond to three distinct **trust + transmission
boundaries**:

1. **Cross-boundary auto-transmission** (cookies → server, on every
   request, automatic) — must be voided
2. **In-browser, no transmission** (localStorage/etc. → never crosses
   network unless our code chooses) — must be transparent + minimal
3. **Server-side persistence** (state.db → only what we explicitly
   chose to keep) — must be opt-in by user

Combining them ("we have no client state") would be either dishonest
(if localStorage is used) or unnecessarily restrictive (forcing
session-only behavior even when localStorage is innocuous). Splitting
into more (e.g., separating localStorage from sessionStorage as
different doctrines) would be over-elaboration. Three is the natural
joint structure of the system.

---

## Public-facing summary

For datenschutz / public communications, the doctrine condenses to:

> **vectoryz storage doctrine:**
> - **HTTP cookies:** zero. The category "technically necessary
>   cookies" is obsolete in 2026; every former use-case has a
>   non-cookie surrogate.
> - **Browser local-storage:** only `vctz-theme` for theme preference.
>   Never transmitted to server. User can clear in browser settings.
> - **Server-side chat persistence:** by default none (v0.2; current
>   v0.1.x: 7-day TTL on all). Sharing a chat-link is opt-in to
>   server-storage with 7-day auto-delete.

A live, scannable audit of all three layers runs on every page-load
via `default_prophylactic_debroeslar.js`. The bottom-right badge
shows current state; click to inspect details.

---

## Related doctrines

- [[broselfrei_2026_decree]] — root of the cookie-voiding argument
- [[default_prophylactic_debroeslar]] — the enforcement engine
- [[seven_day_retention_doctrine]] — the Layer 3 v0.1.x mitigation
- [[audit_open_door_doctrine]] — why we make the scan visible
- [[doctrine_evolution_arc]] — how each layer was exposed by the
  previous

---

## File references

- Enforcement code: `examples/static-www/default_prophylactic_debroeslar.js`
- Surrogate inventory: `docs/doctrines/cookie_function_surrogates.md`
- v0.2 architecture: `docs/architecture/option_a_client_side_default.md`
- Public disclosure: `examples/static-www/datenschutz.html` §3, §4, §7
