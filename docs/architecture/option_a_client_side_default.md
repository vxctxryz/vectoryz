# Option A — client-side default, server-share on-demand

**Status:** draft architecture plan, 2026-05-22
**Author:** Benjamin Resch (operator) — direction; Claude — synthesis
**Trigger:** operator insight "why do we save the chat? seldom it is shared"
**Doctrine:** [[broselfrei_2026_decree]], [[vault_guard_doctrine]],
[[audit_open_door_doctrine]], [[seven_day_retention_doctrine]]

---

## 0. The principle in one sentence

> By default, vectoryz keeps **no server-side record of a user's chat**.
> The encrypted blob is only persisted when the user explicitly clicks
> "Share" — at which point the standard 7-day TTL applies to that one
> snapshot.

The current implementation is already 60% of the way there
(AES-256-GCM client-side, key in URL fragment, `plaintext_history`
parameter accepted by wrapper). Option A finishes the journey:
default-no-persistence rather than default-persist-then-encrypt.

---

## 1. Why this matters (the architectural critique)

The data showed: 81% of chats are 1-turn drive-by curiosity.
~500 distinct anon sessions in 10 days, ~10 of which would have actually
benefited from a server-side blob (the few that someone might share).

The other ~490 chats are server-state we collect to support a use-case
that almost never happens. That's data-minimization-by-convenience-default,
not by principle. CCC-class scrutiny will spot this.

Apply the bröselfrei test (originally about cookies, structurally about
*all* server-side persistence): "what server-side state is *technically
necessary* in 2026 for this feature?" The answer for unshared chats:
none. The wrapper needs history *during* generation; it doesn't need to
persist it *after* generation.

→ Option A makes vectoryz the first AI chat where the **default
behavior is zero server-side conversation record**. This is a real
differentiator and lives up to the bröselfrei doctrine at its deepest
layer.

---

## 2. Current architecture (as built)

```
┌─ Browser ────────────┐   POST /api/chat/new {plaintext_history: [...]}
│ chatId = ?id= search │   ───────────────────────────────────────────►
│ key    = #k=fragment │
│ history= live DOM    │   ◄────────── SSE stream ─────────────────────
└──────────────────────┘   (server generates response token-by-token)

After stream completes:

┌─ Browser ────────────┐   POST /api/chat/{id}/persist-assistant
│ encrypts response    │   {chat_contents: ct_b64, chat_iv: iv_b64}
│ with AES-256-GCM     │   ───────────────────────────────────────────►
│ (key from fragment)  │
└──────────────────────┘   ◄────────── 200 OK ──────────────────────────

State persisted in state.db:
  sessions(uuid, created_at)
  chats(id, owner_session, parent_id, model, created_at, encrypted)
  messages(chat_id, role, content, ts, ciphertext_b64, iv_b64)
```

**Code locations** (verified 2026-05-22):

| Concern | File | Lines |
|---|---|---|
| `/api/chat/new` handler | wrapper_cc.py | 6482-6524 |
| `/api/chat/{id}/turn` handler | wrapper_cc.py | 6525-6571 |
| `/api/chat/{id}/persist-assistant` handler | wrapper_cc.py | 6573-6588 |
| `/api/chat/{id}/rollback` handler | wrapper_cc.py | 6596-6627 |
| `create_chat()` (DB write) | wrapper_cc.py | 5722-5728 |
| `copy_history()` (fork-on-write) | wrapper_cc.py | 5731+ |
| `plaintext_history` parameter | wrapper_cc.py | 6476, 6520, 6567, 6630+ |
| `append_message()` (DB write) | wrapper_cc.py | (around 5780) |
| Frontend `chatId` state | index.html | 1675 |
| Frontend `cryptoKey` from fragment | index.html | 1817-1823 |
| Frontend turn-send POST | index.html | 2956 |
| Frontend persist-assistant POST | index.html | (around 2999 / chat_id event) |

**Why the existing design persists by default:**
- Simplicity: server has the history, lookup-by-chatId always works
- Reload-resume: a user with the bookmarked URL+`#k=` can reload anytime
- Cross-device: another browser with the same URL+`#k=` can read it
  (assuming user copy-pastes the URL between devices)
- "Just in case": if user *might* share later, the data is already there

**Why none of those reasons survive scrutiny:**
- Simplicity → developer convenience, not user-need
- Reload-resume → could be done from client-side IndexedDB just as well
- Cross-device → ~0% of usage given anon model (no login = no cross-device-without-URL)
- "Just in case" → reverses the bröselfrei test (default-collect, justify-deletion vs. default-empty, justify-collection)

---

## 3. Target architecture (Option A)

```
┌─ Browser ────────────────────┐
│ chatId   = client-generated  │   POST /api/chat/stream
│           UUID (browser-only)│   {plaintext_history: [...all prior],
│ key      = (none until Share)│    user_message: "...",
│ history  = IndexedDB + DOM   │    engine: "...", options: {...}}
│                              │   ───────────────────────────────────►
└──────────────────────────────┘
                                  ◄────────── SSE stream ──────────────
                                  (server processes turn statelessly,
                                   PERSISTS NOTHING server-side)

State on server during turn:  in-memory only, dropped after response
State in state.db:            UNCHANGED (no new chat row)


When user clicks 🔗 Share:

┌─ Browser ────────────────────┐
│ Generates random AES-256 key │
│ Encrypts full chat history   │   POST /api/chat/share
│ Builds ciphertext + IV       │   {chat_contents: ct_b64, chat_iv: iv_b64,
│                              │    model: "auto", encrypted: true}
│                              │   ───────────────────────────────────►
└──────────────────────────────┘
                                  ◄── 200 {chat_id: "..." } ────────────
                                  (server creates row in state.db,
                                   subject to 7-day TTL)

Browser composes:  https://vectoryz.de/?id=<chat_id>#k=<key_b64u>
User copies, sends to friend.


When someone opens a shared URL  https://vectoryz.de/?id=X#k=Y:

┌─ Browser ────────────────────┐   GET /api/chat/X
│ Parses id from query         │   ───────────────────────────────────►
│ Parses key from #k= fragment │
│                              │   ◄── {messages: [{ct_b64, iv_b64, ts}]}
│ Decrypts each message        │
│ Renders the conversation     │
│                              │
│ User can continue turn       │   POST /api/chat/X/turn-shared
│ (or fork into private chat)  │   ───────────────────────────────────►
└──────────────────────────────┘
```

---

## 4. File-by-file delta

### 4.1 Wrapper (`benchmark_cc/wrapper_cc.py`)

**New endpoint:**

```
POST /api/chat/stream
  Body: {plaintext_history, user_message, engine, options}
  Behavior: process turn (LLM call, classifiers, tribunal, factampel),
            stream response via SSE, NO database writes
  Response: SSE stream like /api/chat/new today, minus chat_id events
```

**New endpoint:**

```
POST /api/chat/share
  Body: {chat_contents, chat_iv, model, encrypted: true}
  Behavior: create_chat() + append_message() in single transaction,
            no further work (no streaming, no LLM call — pure persistence)
  Response: {chat_id: <generated>}
```

**Modified endpoint:**

```
POST /api/chat/{id}/turn   →   becomes  POST /api/chat/{id}/turn-shared
  Body: same as today
  Behavior: ONLY for shared chats (where id exists in DB).
            Reads encrypted history from DB, processes turn,
            persists assistant response (same as today's /persist-assistant flow).
            Effectively a "fork" path: shared chat continues server-side
            for the original creator's session, or branches for visitors.
```

**Deprecated endpoint** (kept working for in-flight chats during transition):

```
POST /api/chat/new            (existing — auto-creates chat row)
POST /api/chat/{id}/turn      (existing — continues)
POST /api/chat/{id}/persist-assistant  (existing — stores assistant blob)
POST /api/chat/{id}/rollback  (existing — undo)
```

These stay alive for ~30 days post-cutover so any in-the-wild bookmarked
shared URLs continue to work. After 7 days post-cutover, all old-flow
chats will have aged out anyway (per TTL).

**No schema changes needed.** The state.db schema works for shared
chats as-is. The change is *behavioral*: chats only get written when
user opts in.

### 4.2 Frontend (`static-www-vectoryz-v1/index.html`)

**New module: client-side chat persistence**

Adds an IndexedDB-backed chat history that mirrors what state.db
previously held server-side, but for the user's own browser. Schema
roughly:

```javascript
// IndexedDB store: vectoryz-local-chats
{
  id: "client-uuid-...",       // generated browser-side
  created_at: 1779480000,
  model: "auto",
  messages: [
    {role: "user", content: "...", ts: ...},
    {role: "assistant", content: "...", ts: ..., factampel: {...}},
    ...
  ]
}
```

The chat-id is client-generated; never reaches the server unless the
user clicks Share. On page reload, the most-recent chat is restored
from IndexedDB. User can browse local history.

**Turn-send flow change:**

- Today: `POST /api/chat/new` (first turn) or `/api/chat/{id}/turn` (subsequent)
- After A: `POST /api/chat/stream` always, with `plaintext_history` populated
  from IndexedDB. Server doesn't care about chat-id during turn-processing.

**Share-button flow (new):**

```javascript
async function shareCurrentChat() {
  const key = generateAESKey();                    // 32 random bytes
  const ct  = await encrypt(currentHistory, key);  // existing crypto code reused
  const r = await fetch('/api/chat/share', {
    method: 'POST', body: JSON.stringify({
      chat_contents: ct.b64, chat_iv: ct.iv_b64,
      model: currentModel, encrypted: true
    })
  });
  const {chat_id} = await r.json();
  const shareUrl = `${location.origin}/?id=${chat_id}#k=${exportKey(key)}`;
  // copy to clipboard + show modal "Link in Zwischenablage — gültig 7 Tage"
}
```

**Bookmark modal rewrite:**

The current `nc-modal` ("Aktuellen Chat als Lesezeichen speichern?") is
about preserving the URL+#k= for cross-session retrieval. After Option A,
this gets:

- Repurposed for the SHARED case (when user has a `?id=` URL): same behavior
- Or removed entirely if user is on a transient chat: just clear-history + new
- New 🔗 Share button next to + neu

**Storage in IndexedDB explicitly disclosed:**
Datenschutz §4 rewrite (see §8 below) covers this — local browser storage,
never transmitted, user can clear via browser settings.

### 4.3 Datenschutz §4 rewrite

See §8 below for full text. Inverted principle: server stores nothing
by default; only shared chats are persisted (with the existing 7-day TTL).

### 4.4 default_prophylactic_debroeslar.js

No changes — still sweeps any cookies, still ALARMs if found. The
doctrine extends naturally: server-storage minimization + cookie
elimination + audit-open-door = same doctrine, three surfaces.

### 4.5 systemd-timer (vectoryz-chat-vault-ttl)

No changes — still daily 7-day eviction. Just applies to a much smaller
set (only shared chats remain in state.db).

### 4.6 Documentation

- `docs/ARCHITECTURE.md` — update with Option A diagrams
- `docs/DOCTRINES.md` — add "default-no-server-persistence" entry
- This file moves from `docs/architecture/option_a_*.md` (draft) to
  `docs/architecture/v002_client_side_default.md` (canonical, post-impl)

---

## 5. Migration + coexistence strategy

**Phase 0 — current state (pre-cutover):**
- All chats auto-persist (current behavior)
- 330 active chats in state.db, all subject to 7-day TTL

**Phase 1 — additive deployment (no user-visible change):**
- Add `/api/chat/stream` endpoint (parallel, doesn't replace anything)
- Add `/api/chat/share` endpoint (parallel)
- Frontend gets `localStorage`/IndexedDB chat-history scaffolding
  but doesn't use it yet (feature-flag-off)
- Existing endpoints all keep working
- Deploy + verify nothing breaks
- Risk: low (purely additive)

**Phase 2 — frontend cutover (visible to new users):**
- Frontend feature-flag flipped: new chats use `/api/chat/stream`
  + IndexedDB by default
- Frontend feature-flag check: if URL has `?id=...#k=...`, use shared-chat path
- Add 🔗 Share button to chat UI
- Risk: medium (UX change — existing user-bookmarks must keep working)

**Phase 3 — backend cleanup (after ~14 days):**
- Remove `/api/chat/new` (auto-persist path)
- Remove `/api/chat/{id}/persist-assistant` (replaced by share-on-demand)
- Keep `/api/chat/{id}` (read) for shared chats
- Keep `/api/chat/{id}/turn-shared` for continuing shared chats
- Risk: low (all old-flow chats have aged out by then)

**Phase 4 — datenschutz + announcement:**
- Datenschutz §4 rewrite goes live
- Mastodon post: "vectoryz now stores nothing server-side by default"
- This becomes the launch-story differentiator

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| IndexedDB quota exceeded for heavy users | low | low | warn at 80% quota, allow export-and-clear |
| User loses chat by closing browser before sharing | medium | low | UX expectation; the doctrine IS "ephemeral by default"; consider auto-save-warning before unload |
| Wrapper performance regression (every turn carries history) | low | low | history is small; same approach already used for encrypted chats today |
| Shared URLs break during cutover | low | high | Phase 3 only after 14d, all old chats aged out |
| User on second device can't see history | by design | n/a | not a regression — was true today; document clearly |
| CCC-folks ask "but you COULD persist!" | medium | low | docs + DOCTRINES.md make it explicit + checkable; default_prophylactic_debroeslar pattern (active enforcement) shows we mean it |
| Frontend bug: IndexedDB write fails silently | low | high | wrap all writes in try/catch + log + offer fallback in-memory mode |
| Multiple tabs collide on IndexedDB writes | medium | low | use serializable transactions; last-write-wins is fine for chat append |

---

## 7. Test plan

### 7.1 Unit tests (server-side)

- `/api/chat/stream` with empty plaintext_history → first turn works
- `/api/chat/stream` with populated plaintext_history → continues correctly
- `/api/chat/stream` MUST NOT touch state.db (verify via row count before/after)
- `/api/chat/share` with valid ciphertext → creates chat row, returns id
- `/api/chat/share` with bad ciphertext → rejects with 400
- `/api/chat/{id}` for shared chat → returns ciphertext
- `/api/chat/{id}/turn-shared` → continues correctly

### 7.2 Integration tests (browser)

- Open chat → ask question → response received → close browser → reopen
  → IndexedDB restores chat history
- Open chat → ask question → click Share → URL appears with `#k=` →
  open URL in incognito → chat content restored after decrypt
- Open chat → ask question → leave page → wait 1 hour → return →
  IndexedDB still has chat; state.db has nothing
- Open shared URL with bad `#k=` → existing error UI shows ("not_decryptable")
- Open shared URL → continue conversation → forked chat appears in IndexedDB

### 7.3 Acceptance tests (CCC-class scrutiny)

- `sqlite3 state.db "SELECT COUNT(*) FROM chats"` after 20 anon turn-asks:
  expect 0 new rows (was 20 under current architecture)
- Network tab during a chat: only `/api/chat/stream` POSTs visible
- After clicking Share: ONE `/api/chat/share` POST visible
- Browser dev-tools → Application → IndexedDB → chat history visible
- After clear-site-data: all chat history gone (verifies no hidden persistence)

---

## 8. Datenschutz §4 rewrite (draft)

```html
<h2 id="chat">4. Chat-Daten (vectoryz Chat-System)</h2>

<p>
  vectoryz behandelt Chat-Inhalte nach dem Prinzip
  <strong>Default-No-Server-Persistence</strong> (Datenminimierung
  per Architektur, nicht nur per Versprechen).
</p>

<h3>4.1 Standard-Fall: lokaler Chat</h3>
<p>
  Solange ein Chat <em>nicht explizit geteilt</em> wird:
</p>
<ul>
  <li><strong>Serverseitig:</strong> es entsteht
      <em>keine</em> Persistenz. Während einer Anfrage hält der
      Wrapper den Verlauf nur im Arbeitsspeicher (für den
      LLM-Kontext); nach Abschluss der Antwort wird der gesamte
      Zustand verworfen. Der Server kennt nach 30 Sekunden nichts mehr
      vom Inhalt der Konversation.</li>
  <li><strong>Im Browser:</strong> der Verlauf wird in
      <code>IndexedDB</code> gespeichert (Schlüssel:
      <code>vectoryz-local-chats</code>). Diese Daten bleiben
      ausschließlich auf dem Gerät des Nutzers, werden niemals an
      einen Server übertragen, und können jederzeit über die
      Browser-Einstellungen (oder die in-App-Funktion "Lokalen
      Verlauf leeren") gelöscht werden.</li>
</ul>
<p>
  <strong>Rechtsgrundlage:</strong> keine, weil keine personenbezogene
  Daten serverseitig verarbeitet werden (außer den
  in §3 disclosed Server-Logs der Aufrufe selbst).
</p>

<h3>4.2 Geteilte Chats (opt-in)</h3>
<p>
  Wenn ein Nutzer <strong>aktiv auf "🔗 Teilen"</strong> klickt:
</p>
<ul>
  <li>der Browser erzeugt einen zufälligen AES-256-Schlüssel,
      verschlüsselt den gesamten Chat-Verlauf clientseitig
      (AES-256-GCM), und überträgt nur das Chiffrat an den Server</li>
  <li>der Server speichert das Chiffrat plus eine Chat-ID in
      <code>state.db</code> (Tabellen <code>chats</code> +
      <code>messages</code>)</li>
  <li>der AES-Schlüssel verlässt niemals den Browser — er wird in
      die geteilte URL als Fragment (<code>#k=...</code>) eingebettet
      und nur an Empfänger weitergegeben, denen der Nutzer
      vertraut</li>
  <li>der Anbieter kann das Chiffrat technisch
      <strong>nicht entschlüsseln</strong></li>
</ul>
<p>
  <strong>Speicherdauer:</strong> Geteilte Chat-Daten werden nach
  <strong>maximal 7 Tagen</strong> automatisch gelöscht
  (systemd-Timer <code>vectoryz-chat-vault-ttl.timer</code>,
  täglich). Der Chat-Link ist nach Ablauf inert.<br>
  <strong>Rechtsgrundlage:</strong> Art.&nbsp;6 Abs.&nbsp;1 lit.&nbsp;a
  DSGVO (explizite Einwilligung durch Klick auf "Teilen").
</p>

<h3>4.3 Hinweis zur End-zu-End-Verschlüsselung</h3>
<p>
  Da der Schlüssel ausschließlich beim Nutzer liegt, kann der
  Anbieter <em>keine</em> Auskunft über den Chat-Inhalt erteilen
  — weder gegenüber dem Nutzer noch gegenüber Behörden. Auf
  richterlichen Beschluss (§&nbsp;100g StPO) innerhalb der 7-Tage-Frist
  kann lediglich die Existenz eines geteilten Chat-Datensatzes
  (anonyme Chat-ID, Erstellungszeitpunkt) bestätigt werden;
  nicht jedoch sein Inhalt.
</p>

<h3>4.4 Recht auf Löschung</h3>
<p>
  Über das normale TTL hinaus können Nutzer die sofortige Löschung
  eines spezifischen geteilten Chats durch Mitteilung der Chat-ID per
  E-Mail an
  <a href="mailto:contact@vectoryz.de">contact@vectoryz.de</a>
  verlangen. Wegen der E2E-Verschlüsselung ist eine inhaltliche
  Identifikation des Chats durch den Anbieter nicht möglich; die
  Chat-ID muss vom Nutzer selbst mitgeteilt werden.
</p>
<p>
  Lokale (nicht geteilte) Chat-Daten unterliegen der Kontrolle des
  Nutzers und können jederzeit eigenständig über die
  Browser-Einstellungen gelöscht werden.
</p>
```

---

## 9. Open questions for operator decision

1. **IndexedDB or localStorage for client-side history?**
   - localStorage: simpler, 5MB-ish limit per origin, sync API
   - IndexedDB: async, ~50MB+ available, transactional
   - Recommendation: **IndexedDB** for chat history (could grow large);
     localStorage stays theme-only.

2. **"Auto-clear after N days" for IndexedDB?**
   - Some users will value "chat persists until I clear it"; others
     will want symmetry with the 7-day server policy.
   - Recommendation: **30-day client-side default** with prominent
     "Lokalen Verlauf leeren" button. Longer than server (7d) because
     user owns their device, but not infinite. Mention in §4.

3. **Multi-chat in IndexedDB?**
   - User has 5 different conversations on different topics — do they
     all live in IndexedDB as separate entries?
   - Recommendation: **yes**, with a list-view UI. Already partially
     supported via the `chatId` concept.

4. **What happens to existing in-flight chats during cutover?**
   - 330 chats currently in state.db, all bookmarked at various URLs
   - Recommendation: **keep them alive for 14 days post-Phase-3**, then
     they age out via TTL. New chats follow Option A from Phase 2.

5. **Migration of frontend users mid-conversation?**
   - User has a chat open in browser, we deploy Phase 2. Their next
     turn would now go via `/api/chat/stream` instead of `/api/chat/{id}/turn`.
   - Recommendation: **frontend detects deployed-version mismatch**
     via deploy-stamp; if mismatch + active chat, prompts user to
     refresh.

6. **Should we keep `parent_id` (fork-on-share semantics)?**
   - Currently `chats.parent_id` enables visitor-forks of shared chats
   - In Option A, "fork" only matters if user continues a shared chat
   - Recommendation: **keep schema**, simplify usage to only "shared
     chat continuation creates fork".

---

## 10. Time + effort estimate

| Phase | Effort | Calendar |
|---|---|---|
| Phase 1 (additive deploy) | 4-6h dev + 1h test | half-day |
| Phase 2 (frontend cutover) | 6-8h dev + 2h test | 1 day |
| Phase 3 (backend cleanup) | 1h | 30min after 14d wait |
| Phase 4 (datenschutz + Mastodon) | 1h | inline with launch |
| **Total active dev** | **~14h** | **~2 working days** |
| Wait time | 14d before Phase 3 | calendar-driven |

This fits comfortably within "before Mastodon launch + chaos.social
account creation" timeline, if operator wants to ship it as the
launch differentiator.

---

## 11. Decision tree

```
Operator decision points:
├─ Ship Option A before Mastodon launch?
│   ├─ Yes → frontend has the differentiator-headline ready
│   │       AND we don't need to re-do datenschutz §4 later
│   └─ No  → ship existing 7d-TTL doctrine, plan Option A as v0.2
│
└─ If yes: IndexedDB or localStorage for client?
    └─ Recommended: IndexedDB

└─ If yes: how long does local-history live?
    └─ Recommended: 30 days, user-clearable, prominent button
```

---

## 12a. Archive UX — "the chat IS already at home, make it easy"

Operator insight 2026-05-22 (after seeing the architecture sketch):
*"the chatcontent is saved already (oh my how much do i fzzl
copynpaste .. timewaste!) we do a nice section at users browser;
how to archive best?"*

The chat content lives in the user's DOM + IndexedDB. Archival should
be a first-class UX, not buried per-message-hover. Existing copy-buttons
(📋 answer, 💬 QA, 🧵 thread) at L2469-2472 stay but become supplementary.

### 12a.1 New "Archive ▼" dropdown in header

Sits next to **+ neu** and the theme-toggle (header right of brand):

```
┌─ vectoryz ─────────────────────────────────────────────────────┐
│  + neu     🌗     [Archive ▼]     Settings                     │
└─────────────────────────────────────────────────────────────────┘
                    ┌──────────────────────────┐
                    │ 📋 Als Markdown kopieren │   → clipboard, formatted
                    │ 📄 .md herunterladen     │   → file: <yyyymmdd>-vectoryz.md
                    │ 🌐 .html herunterladen   │   → self-contained, styled
                    │ 📑 Als PDF (Drucken…)    │   → window.print()
                    │ ─────────────────────── │
                    │ 💾 In Favoriten ablegen  │   → IndexedDB pin with name
                    │ ⭐ Favoriten anzeigen…   │   → list-view of pinned chats
                    │ ─────────────────────── │
                    │ 🔗 Teilen (Server, 7d)   │   → POST /api/chat/share
                    └──────────────────────────┘
```

### 12a.2 Format definitions

**Markdown export** (`<yyyymmdd-hhmm>-vectoryz-chat.md`):
```markdown
# vectoryz chat — 2026-05-22 21:34 CEST

**Modell:** auto · **Verlauf:** 4 Turns

---

## 🧑 user
> [question text...]

## 🤖 assistant
[response text...]

> Faktampel: [factfact: 3, quasifact: 1, maybefact: 0, ...]
> Tribunal: [witnesses summary]
> Quellen: [...]

---

## 🧑 user
> [...]
```

Includes factampel + tribunal-witness summary inline, since those are
the differentiated value vectoryz adds. User retains the audit-tags
in their archive.

**HTML export** (`<yyyymmdd-hhmm>-vectoryz-chat.html`):
Self-contained single file: inline CSS (copy of the chat-page styles),
inline content. Opens in any browser, looks ~identical to live UI,
**works offline**. ~10-50KB per chat.

**Markdown clipboard**:
Same as .md download but goes via `navigator.clipboard.writeText()`.
Operator's primary anti-fzzl path: one click, paste anywhere.

**Print / PDF**:
Uses `window.print()` with a `@media print` CSS block hiding the
composer + header + nav, keeping only the conversation thread.
User picks "Save as PDF" in the print dialog.

### 12a.3 Favorites (local-only pinning)

For chats the user wants to keep beyond IndexedDB's default 30-day
client-side TTL:

```
IndexedDB store: vectoryz-favorites
{
  id: "client-uuid-...",       // same as chat id
  pinned_name: "Recherche Steuerrecht 2026-05-20",
  starred_at: 1779480000,
  full_chat: { ...complete history... },
  expires: null               // user-cleared only, not TTL'd
}
```

Favorites get:
- Custom name (user-editable)
- Bypassed from the 30-day client-TTL (live until user clears)
- Listed in "⭐ Favoriten anzeigen" view

This is **server-zero** — no backend involvement at any point.
Pure client-side knowledge management.

### 12a.4 "Lokalen Verlauf"-Browser

Separate view (linked from header dropdown):

```
⭐ Favoriten (3)
─────────────────
📌 Recherche Steuerrecht 2026-05-20    [Open] [Export ▼] [Remove]
📌 Manowar Black Arrows discussion     [Open] [Export ▼] [Remove]
📌 Bröselfrei doctrine walkthrough    [Open] [Export ▼] [Remove]

Recente lokale Chats (12)
─────────────────────────
🕓 Today 14:32 — "wie installiere ich..."
🕓 Today 13:01 — "was ist der unterschied..."
🕓 Yesterday — "..."
🕓 ...

[Verlauf leeren] [Alles exportieren als .zip]
```

### 12a.5 First-time-user nudge

After the user's third or fourth chat session, a one-shot tooltip
near the Archive button:

> 💡 **Tipp**: Chats werden lokal in deinem Browser gespeichert
> (default 30 Tage). Mit "Archive ▼" kannst du sie als Markdown,
> HTML, oder PDF exportieren — Server-frei. Wertvolle Chats als
> ⭐ Favorit pinnen, dann bleiben sie bis du sie löschst.

Dismiss-able, never re-shown. Stored in localStorage flag.

### 12a.6 The doctrinal frame

The Archive-UX is the *positive expression* of the same doctrine:
- Server-default-storage was *paternalistic convenience*
- Server-share-on-demand + client-default-storage is *user sovereignty*
- One-click archive in 5 formats is **giving the user the tools they
  need to manage their own data** — which is what "user owns the data"
  actually means in practice.

Operator's fzzl-pain captures it perfectly: today the data IS at home,
but the takeaway-experience is painful. After Option A + Archive-UX,
the data is at home AND easy to take with you.

---

## 12b. Evolution arc (worth saving as memory)

Operator observation 2026-05-22:
*"i love the evo.. first sequence on git: data on server;; now evo
to privacy by design maximized;; chat is at home"*

The git history itself documents the doctrine deepening:
1. **v0.1** (2026-05-22 morning): bröselfrei = cookies only
2. **v0.1+** (this commit thread): bröselfrei + 7-day chat-TTL =
   storage gets a clock
3. **v0.2** (this plan): bröselfrei + default-no-server-storage =
   storage gets opt-in semantics
4. **v0.3** (future): bröselfrei + zero-knowledge + storage + ???

Each step applies the same structural argument to a wider surface.
That progression is itself the strongest CCC-class evidence that the
doctrine is *lived*, not *declared*. The git log will be one of the
first things CCC-folks check after the Mastodon post — and they'll
see the doctrine evolving on its own logic, not as
launch-marketing.

This is the right kind of evolution: doctrine → application →
discovery-of-deeper-application → re-application. Maxim:
**"each layer of the same principle exposes the next."**

---

## 12. Doctrinal anchor

Option A is the natural completion of the bröselfrei-2026-decree
applied to *all* server-side persistence, not just cookies. The
decree said: "the category of 'technically necessary cookies' is
obsolete in 2026 — for every historical use-case there is a
non-cookie alternative." Option A makes the same claim about
**server-side chat persistence**: "the category of
'technically-necessary-default-server-storage' is obsolete in 2026 —
the user's browser is the natural home of their conversation; the
server should only see what's explicitly shared."

Same structural argument. Same doctrine. Bigger surface.
