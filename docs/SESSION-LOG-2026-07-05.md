# Session Log — Building the Apple Music MCP Server

**Date:** 2026-07-05
**Repo:** [NodeSaint/mcp-applemusic](https://github.com/NodeSaint/mcp-applemusic) (fork of [kennethreitz/mcp-applemusic](https://github.com/kennethreitz/mcp-applemusic))
**Assistant:** Claude Code

> This is a faithful reconstruction of the working session that produced this project, saved before the Claude Desktop app was deleted. User messages are quoted verbatim; assistant work is recorded substantively (exact long-form replies are summarised, but all decisions, code, findings, commands, and outcomes are preserved).

---

## 1. Kick-off — "flesh this out"

**User:**
> https://github.com/kennethreitz/mcp-applemusic
> I want to flesh this out — it's limited, and not sure if it'll work. I want to make an mcp to allow claude to go into apple music, create playlists, etc. plan out how we can do it — on our own fork etc.

**What I did:**
- Ran the brainstorming skill. Reviewed the upstream repo: a single-file FastMCP server (`mcp_applemusic.py`), 9 tools (`itunes_*`), controlling Music.app via AppleScript. Key weaknesses: raw user strings interpolated straight into AppleScript source (injection-prone), exact-name track matching, comma-split playlist input, library-only, MIT licensed.
- Asked scoping questions.

**User's answers:**
- Integration approach: **AppleScript-deep** (no dev account needed initially).
- Apple Developer account: **Willing to get one** ($99/yr).
- Use cases: **Build playlists · DJ/playback control · Library management**.

**User (mid-brainstorm correction):**
> first off, we need to recheck something, this tool needs to be able to work with all apple music content, not just the local stuff. like, it should work on iphone, and it should work with anything in my library on my mac, even if it's not downloaded, and it should interact with playlists etc

**Resolution → Hybrid design (user approved):**
- **AppleScript** drives Music.app on the Mac for playback + the edit/delete operations Apple's public API can't do.
- **Apple Music Web API** (Phase 2) for full-catalog search and adding songs not yet owned.
- **iCloud Music Library sync** is the mechanism that carries changes to iPhone (no API can drive iPhone playback directly). "Sync Library" on the Mac makes the full cloud library visible even when tracks aren't downloaded.

Forked to `NodeSaint/mcp-applemusic`, cloned to `~/mcp-applemusic`, committed the design spec:
`docs/superpowers/specs/2026-07-05-hybrid-apple-music-mcp-design.md`.

---

## 2. "Plan deeply, critique, adjust, execute"

**User:**
> plan this deeply, then heavily critique it, and then adjust and execute. think like a startup, cracked top 1% developer, founder and strategist

**What I did:**
- Wrote a full implementation plan (`docs/superpowers/plans/2026-07-05-phase1-applescript-deep.md`), then **self-critiqued it** and fixed four bugs before writing any code:
  1. Root `mcp_applemusic.py` vs package `mcp_applemusic/` name collision → delete old file in task 1.
  2. `remove_tracks` counted not-found tracks as removed (deleting an empty `whose` specifier doesn't error) → count matches first.
  3. Queue-playlist create/clear could duplicate "Claude Queue" → use `exists user playlist`.
  4. `subprocess.TimeoutExpired` escaped uncaught → map to `AppleScriptError`.

**Then executed the plan task-by-task (TDD, frequent commits):**

Architecture (the package that replaced the single file):
- `runner.py` — the **only** module that calls `osascript`. Scripts are static templates run via `on run argv`; user values are passed as **argv arguments, never interpolated** into script source. This makes AppleScript injection structurally impossible.
- `models.py` — parses US (`\x1f`) / RS (`\x1e`) delimited records into dicts.
- `library.py` — search (native fast `search` verb; `whose` scan for genre), track info, rating, favorite/dislike.
- `playback.py` — play/pause/next/prev, now-playing, volume/shuffle/repeat, play track/playlist/ad-hoc list.
- `playlists.py` — list, get tracks, create, add, remove, rename, delete. Playlists resolved by persistent ID with exact-name fallback.
- `server.py` — thin FastMCP layer; 14 `music_*` tools; `_safe()` shapes errors to `{error, hint}`; server never raises to the client.

**Design principles enforced:** track identity = Music.app **persistent IDs** (no fragile name matching); batch ops report `{added|removed, missing}` (nothing silently dropped).

**Live testing caught two AppleScript reserved-word collisions** that no amount of static review would find:
- `st` — collides (stone weight unit) → renamed `stateText`.
- `removed` — collides (a Music dictionary constant) → renamed `removedCount`.

**Outcome:** 37 unit tests (no Music.app needed) + a live smoke script (`scripts/live_smoke.py`) that creates/populates/edits/deletes a scratch playlist against the real 2,804-track library. All operations 150–850 ms. Shipped as **v0.2.0**.

---

## 3. "Check for cyber flaws, make it secure and friendly"

**User:**
> check for cyber flaws, ensure it's fully secure and friendly for use

**Finding (high severity) — argument injection, found + fixed + verified:**
- `run_script` built `["osascript", "-e", script, *args]` with **no `--` terminator**. Any argument beginning with `-` was parsed by osascript as an *option*, not data. Proven live: a value of `-e` + `return "PWNED"` executed a **second attacker-controlled script** → via `do shell script` that's arbitrary code execution. A `-s` value was silently swallowed as a flag.
- **Fix:** insert a `--` terminator (`["osascript", "-e", script, "--", *args]`) so everything after is unconditionally argv data. Re-tested: the same payloads now land as inert data. Regression test added.

**Proactive hardening:**
- `.gitignore` extended to block `.env`, `*.p8`, `config.json`, secret dirs (ahead of Phase 2).
- `mcp` dependency floor bumped `>=1.2.1` → `>=1.28.1` (latest stable), relocked.

Shipped as **v0.2.1**.

---

## 4. "Better README + a 3D GitHub Pages landing page"

**User:**
> write a better read me, the original was crap. and lets make a gitio pages landing page for it — make it with 3D elements, think ultracreatively

**What I did (frontend-design skill):**
- **Rewrote `README.md`** — hero, quick conversational example, categorized tool tables (Playback / Library / Playlists), plain-English security section, roadmap.
- **Built a 3D landing page** (`site/index.html`): a three.js hero of a **rotating vinyl record** (grooved disc, gradient center label, glowing edge rim) orbited by an **audio-waveform particle field** (~1,700 points driven by a travelling sine so it reads as sound), lit with Apple Music's pink→coral→orange gradient, bloom post-processing, mouse parallax, scroll-driven drift. Plus a tool marquee, feature triptych, all 14 tools as glass cards, a Mac-in/iPhone-out sync section, a security section showing the real `--` terminator code, install blocks, roadmap, footer. Custom cursor, film grain, scroll reveals, Clash Display + General Sans + JetBrains Mono type. Graceful CSS fallback if WebGL/CDN unavailable; respects reduced-motion.
- **Verified headlessly** (Chrome/preview tools were unreachable in-session): inline three.js module is valid ES syntax with balanced brackets; all three.js + font CDN endpoints return 200; page serves 200.
- **Deployed** to a clean orphan `gh-pages` branch (`index.html` + `.nojekyll`), enabled GitHub Pages via `gh api`.

**Caveat noted honestly:** the Pages build sat in GitHub's queue (no error, correct config) and hadn't served 200 by end of turn; and I couldn't get a live browser render in-session, so the user was asked to eyeball the deployed page.

URL: <https://nodesaint.github.io/mcp-applemusic/>

---

## 5. "Is my tool downloadable?"

**User:**
> is my tool downloadable, rather than the original which wasnt much good and was incomplete

**Critical find:** the fork's **default branch (`main`) still held the original 9-tool single-file version** — all our work was on `dev`. So the README install command would have given people the *old* code.

**What I did:**
- Proved real installability: ran `uvx --from git+…@dev mcp-applemusic` end-to-end — it fetched, built the wheel, installed 35 packages, launched.
- **Fast-forward merged `dev` → `main`** (Phase 1 complete + live-tested = your rule for promoting to main). Verified the default-branch install now boots clean with the new version.

Branches: `main` = released/installable · `dev` = ongoing · `gh-pages` = landing page.

---

## 6. `/security-review` — "check thoroughly"

(The slash command needs a git repo as CWD; the session CWD wasn't one, so I ran the review directly against `~/mcp-applemusic`.)

**Verified clean:** one osascript gateway (no other subprocess/`eval`/`exec`), no network surface, no secrets, `--` terminator present, all values via argv.

**Two findings — both fixed:**
1. **Output field-injection via crafted metadata (low severity).** Proven live: a track title containing a raw US/RS control character shifts the parsed fields (`Song␟HACKED` → `name=Song, artist=HACKED`). Track metadata is influenceable by whoever publishes a track. **Fix:** a shared AppleScript `san()` handler strips those control chars from every emitted free-text field. Persistent IDs were already safe (system-generated, always first). Proven: `Song␟HACKED␞Phantom` → harmless `Song HACKED Phantom`.
2. **PATH-lookup surface (low).** `osascript` invoked by bare name → pinned to `/usr/bin/osascript`.

Shipped as **v0.2.2** (both branches).

---

## 7. `/security-best-practices` — "make it a safe tool" + OWASP pass

**User:**
> ensure these are enacted on, so this is a safe tool

**OWASP Top 10 pass** — most items N/A (no network, DB, auth, or web input). The two that applied:
- **A06 (vulnerable components):** dependency tree audited — no known vulnerabilities.
- **A01 / A04 (access control & insecure design):** added **`MUSIC_MCP_READONLY`**. When set, every state-changing tool (playback, set_options, play, rate, and all playlist create/add/remove/rename/delete) is refused *before it runs* — a hard stop against a prompt-injected model deleting or overwriting a playlist. Default (unset) keeps full functionality. 4 new tests; verified live.

Shipped as **v0.2.3**. (Test count → 42.)

---

## 8. Strategy — "what would 10x this project?"

**User:**
> what would 10x this project?

**My take (founder hat):** more tools won't 10x it — this is a thin-moat product (anyone can wrap AppleScript). Two orthogonal bets:
1. **Distribution (10x reach, cheap):** the bottleneck is *discovery*, not features. Get listed in the MCP registries with one-click install. Being first-and-best-listed under "apple music mcp" is a sticky default-choice advantage.
2. **Phase 2 + a taste layer (10x value, the real product):** the catalog API turns *librarian* → *DJ*; a curation engine that grounds picks in real acoustic + behavioural signal is the only durable moat.

Reframe: **the product isn't "control Apple Music" — it's "an AI music curator with taste." The MCP server is just the delivery mechanism.**

**User:** > yh

Decisions taken via follow-up question:
- Distribution: **publish to PyPI as `mcp-applemusic-nodesaint`** (upstream owns `mcp-applemusic` on PyPI; new name verified free).
- Then: **scope the taste-layer design**.

---

## 9. Distribution prep (shipped) + taste-layer design (scoped)

**Distribution — done, on `main`:**
- Renamed distributable → `mcp-applemusic-nodesaint`; console script renamed to match so `uvx mcp-applemusic-nodesaint` works. Added PyPI metadata (license, keywords, classifiers, URLs).
- `server.json` — official registry manifest, name `io.github.nodesaint/mcp-applemusic`, points at the PyPI package, declares `MUSIC_MCP_READONLY`.
- `<!-- mcp-name: io.github.nodesaint/mcp-applemusic -->` marker added to README (the registry's PyPI-ownership check).
- `PUBLISHING.md` — exact PyPI + `mcp-publisher` steps.
- GitHub repo description + 10 MCP topics set (so Glama / PulseMCP / mcp.so can auto-index).
- Verified: renamed package builds a wheel, new script boots, `server.json` version/name/marker all consistent, 42 tests green.

**Taste-layer design — scoped (no code):** `docs/superpowers/specs/2026-07-05-taste-layer-design.md`.
- Thesis: **LLM does semantics** (brief → energy/genre/BPM/mood intent); **an engine does grounding + sequencing** (filter by acoustic constraints, weight by the user's own history, order for *flow* — energy arc, Camelot-wheel key adjacency, BPM smoothness, no artist clustering).
- Five components: taste profile builder, feature store (SQLite cache), candidate selector, sequencer, tool surface (`music_taste_profile`, `music_recommend`, `music_similar`).
- **Verified live on the machine** (facts, not assumptions): Music.app exposes rich **behavioural** signal (play/skip count, rating, favorited) but **BPM returns 0 for cloud tracks** and **ISRC is NOT exposed** by AppleScript. So a v1 taste profile ships now with no new API; real *acoustic* sequencing needs Tier-1 enrichment (external audio features matched by fuzzy title+artist, or Phase 2's Apple API which does return ISRC).
- Phasing: v1 (profile + genre/behaviour flow, no API) → v2 (audio-feature enrichment) → v3 (learn from keep/skip — the compounding, defensible part).

---

## Current state at end of session

- **Branches:** `main` (released, installable, v0.2.3 + distribution prep) · `dev` (ongoing) · `gh-pages` (landing page).
- **Tools:** 14 `music_*` (playback, search, ratings, playlist CRUD) + `MUSIC_MCP_READONLY` safety switch.
- **Tests:** 42 unit (no Music.app) + live smoke script.
- **Security:** argv-only osascript gateway with `--` terminator + pinned path; field sanitizer; read-only mode; no network/secrets/eval.
- **Docs:** spec, plan (+critique log), taste-layer design, README, CHANGELOG, PRIMER, PUBLISHING, agent files.
- **Landing page:** deployed to GitHub Pages (build was queued at end of the earlier turn).

## Outstanding action items (need the user's accounts — can't be automated)

1. **Publish to PyPI:** `cd ~/mcp-applemusic && git checkout main && uv build && uv publish` (needs a PyPI account + token). Then `uvx mcp-applemusic-nodesaint` works for everyone.
2. **List on the MCP registry:** `brew install mcp-publisher`, then `mcp-publisher login github && mcp-publisher publish` from the repo root. (See `PUBLISHING.md`.)
3. **Apple Developer membership ($99/yr)** → MusicKit `.p8` key → unlocks **Phase 2** (catalog search, add-to-library, cloud playlists) per the hybrid spec.
4. **Confirm the landing page renders** at <https://nodesaint.github.io/mcp-applemusic/> and eyeball the 3D scene on real hardware.
5. When ready: **build taste-layer v1** (clean fit onto the existing AppleScript modules; needs no new API).

## Key files

| Path | What |
|---|---|
| `mcp_applemusic/runner.py` | Sole osascript gateway (argv-only, `--` terminator, `san()` handler, pinned path) |
| `mcp_applemusic/{library,playback,playlists,models}.py` | AppleScript modules + record parsing |
| `mcp_applemusic/server.py` | 14 `music_*` tools + `_safe()` + read-only guard |
| `server.json` | Official MCP registry manifest |
| `PUBLISHING.md` | PyPI + registry publish steps |
| `docs/superpowers/specs/2026-07-05-hybrid-apple-music-mcp-design.md` | Overall design (Phase 1 + Phase 2) |
| `docs/superpowers/plans/2026-07-05-phase1-applescript-deep.md` | Implementation plan + critique log |
| `docs/superpowers/specs/2026-07-05-taste-layer-design.md` | Taste-layer (the moat) design scope |
| `PRIMER.md` | Session-continuity notes + AppleScript gotchas |
| `site/index.html` | 3D landing page (deployed to `gh-pages`) |

## Hard-won gotchas (don't rediscover)

- AppleScript variable names `st` and `removed` are reserved inside `tell application "Music"` blocks. Safe: `m, q, t, d, p, n, v, r, us, rs`.
- Deleting an empty `whose` specifier does **not** error — count matches before deleting or your removal report lies.
- Use `exists user playlist X` rather than try/create, or you make duplicate playlists.
- `osascript` args need a `--` terminator or values starting with `-` are parsed as options (injection).
- Music.app: BPM is `0` for cloud tracks; ISRC isn't exposed to AppleScript; `loved` is gone (use `favorited`).
- Upstream owns `mcp-applemusic` on PyPI — this fork publishes as `mcp-applemusic-nodesaint`.
