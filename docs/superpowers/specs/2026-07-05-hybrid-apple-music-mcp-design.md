# Hybrid Apple Music MCP Server — Design

**Date:** 2026-07-05
**Repo:** Fork of [kennethreitz/mcp-applemusic](https://github.com/kennethreitz/mcp-applemusic) at [NodeSaint/mcp-applemusic](https://github.com/NodeSaint/mcp-applemusic)
**Status:** Approved (user-approved in brainstorming session)

## Goal

Turn the experimental single-file AppleScript MCP server into a robust hybrid server that lets Claude work with **all** Apple Music content — the full catalog, the user's cloud library (including non-downloaded tracks), and playlists that sync to iPhone — plus playback control on the Mac.

## Requirements

1. **Build playlists** from any Apple Music content, including songs not in the user's library, and have them appear on iPhone.
2. **DJ / playback control** on the Mac: play/pause/skip, volume, shuffle/repeat, play a specific track/album/playlist.
3. **Library management**: search/browse the whole cloud library (downloaded or not), edit and delete playlists, rate/love tracks.
4. Changes must propagate to the user's iPhone (via iCloud Music Library sync — the only mechanism Apple provides; no API can drive iPhone playback directly).

## Why hybrid

Neither integration route covers everything:

| Capability | AppleScript (Music.app) | Apple Music Web API |
|---|---|---|
| Full catalog search / add catalog songs | ❌ | ✅ |
| Create playlist + add tracks | ✅ (library tracks only) | ✅ (catalog + library) |
| Delete playlist, remove/reorder tracks | ✅ | ❌ (public API gap) |
| Search cloud library incl. non-downloaded | ✅ (needs Sync Library on) | ✅ |
| Playback control | ✅ (Mac only) | ❌ |
| Ratings / love / dislike | ✅ | ✅ (love/dislike via ratings endpoint) |
| Syncs to iPhone | ✅ via iCloud Music Library | ✅ native |

The two halves cover each other's blind spots. The MCP server runs on the Mac anyway, so hybrid costs nothing operationally.

## Architecture

Restructure the fork from one file into a package. Keep Python + FastMCP + uv (the existing, working foundation).

```
mcp_applemusic/
  __init__.py
  server.py            # FastMCP app; tool registration ONLY — no logic
  models.py            # dataclasses: Track, Playlist, SearchResult
  applescript/
    runner.py          # THE single osascript entry point (see Security)
    playback.py        # play/pause/next/prev, volume, shuffle, repeat, current track,
                       # play by persistent ID / playlist / album / artist
    playlists.py       # list, get tracks, create, rename, delete, add, remove (by persistent ID)
    library.py         # search (name/artist/album/genre/any), track info, rating, love/dislike,
                       # recently added / recently played
  api/
    auth.py            # developer token (ES256 JWT from MusicKit .p8) + Music User Token storage
    client.py          # thin httpx client: base URL, auth headers, storefront, error mapping
    catalog.py         # catalog search, song/album/artist/playlist lookup
    library.py         # add to library, library search
    playlists.py       # create playlist, add tracks (catalog or library IDs)
  setup_flow/
    __init__.py        # `mcp-applemusic-setup` console script: generates dev JWT, serves a
                       # localhost MusicKit JS page, captures the Music User Token, stores config
tests/
  test_runner.py       # arg passing, escaping, error mapping (mock subprocess)
  test_playback.py     # generated AppleScript correctness (mock runner)
  test_playlists.py
  test_library.py
  test_api_*.py        # API modules against respx/httpx mocks
  integration/         # opt-in live smoke tests (real Music.app / real API), pytest -m live
```

The old `mcp_applemusic.py` is replaced by the package; `pyproject.toml` entry points updated. Existing tool names are superseded by the new surface (this fork does not promise upstream tool-name compatibility).

## Security: injection-safe AppleScript

Current upstream interpolates user strings directly into AppleScript source — any input containing `"` breaks or hijacks the script. Fix: **no user value is ever concatenated into script source.** All scripts are static templates invoked as:

```
osascript -e 'on run argv' -e '...' -e 'end run' -- arg1 arg2
```

Values arrive through `argv` as data, making injection structurally impossible. `runner.py` is the only module allowed to call `subprocess`; it enforces this contract and maps failures (Music.app not running, no such track, permission denied under macOS automation privacy settings) to typed errors with actionable messages.

## Track identity

Search results and all mutating operations use **Music.app persistent IDs** (AppleScript side) and **catalog/library IDs** (API side) — never name matching. This kills upstream's exact-name and comma-splitting fragility. Tools return structured JSON (id, name, artist, album, duration, kind) so Claude can chain search → select → act.

## Tool surface (~24 tools)

**Playback (AppleScript, Mac only) — 10:**
`play`, `pause`, `next`, `previous`, `now_playing`, `player_state`, `set_volume`, `set_shuffle`, `set_repeat`, `play_item` (track persistent ID / playlist name / album+artist).

**Playlists — 8:**
`list_playlists`, `get_playlist_tracks`, `create_playlist` (API when configured — supports catalog songs, syncs natively; AppleScript fallback for library-only), `add_to_playlist` (same dual routing), `rename_playlist` (AppleScript), `delete_playlist` (AppleScript), `remove_from_playlist` (AppleScript), `reorder_playlist` (AppleScript).

**Library & catalog — 6:**
`search_library` (field-scoped: name/artist/album/genre/any; limit param), `search_catalog` (API), `add_to_library` (API), `get_track_info`, `set_rating`, `love_track` / `dislike_track`.

**Dual-routing rule:** tools that both layers can serve (`create_playlist`, `add_to_playlist`) prefer the API when credentials are configured, else fall back to AppleScript and say so in the response ("library tracks only — run setup to enable catalog songs"). Tool names stay stable; capability upgrades transparently once auth exists.

**Playlist-build report:** batch operations return `{added: [...], not_found: [...], failed: [...]}` — never silently drop requested tracks.

## Auth & configuration (API layer)

- Requires Apple Developer Program membership ($99/yr — user has agreed to obtain).
- One-time setup: user creates a MusicKit key in the developer portal, downloads the `.p8`.
- `mcp-applemusic-setup` then: (1) generates the developer token — ES256 JWT, 180-day max validity, from key ID + team ID + `.p8` path; (2) serves a localhost page loading MusicKit JS where the user authorizes with their Apple ID; (3) captures the **Music User Token** and writes config to `~/.config/mcp-applemusic/config.json` (`.p8` path, key ID, team ID, user token, storefront).
- At server start: dev token regenerated from the `.p8` if expired; if the user token is rejected (401/403), API tools return a clear "re-run setup" error instead of failing cryptically. AppleScript tools are unaffected.
- No credentials in the repo; config path is user-local.

## Error handling

- AppleScript: typed errors from `runner.py`; every tool returns either structured data or `{error, hint}` (e.g. hint: "Open Music.app", "Enable Sync Library", "Grant automation permission in System Settings → Privacy").
- API: HTTP errors mapped to the same `{error, hint}` shape; 429 respected with a single retry.
- Server never crashes on a failed tool call.

## Known limitations (accepted)

- No iPhone playback control — impossible on the platform; playlists/library sync instead.
- No Up Next queue manipulation — Music.app's AppleScript dictionary doesn't expose it.
- API cannot delete/edit playlists — routed to AppleScript, which requires the Mac session.
- AppleScript library coverage requires Sync Library enabled in Music.app.

## Testing

- Unit tests: mock the runner / mock HTTP; assert generated scripts, arg passing, response shaping, dual-routing decisions.
- Integration: `pytest -m live` suite that exercises the real Music.app (create + populate + delete a scratch playlist, playback toggle) and, when configured, real API calls. Excluded from CI/default runs.
- Manual acceptance: from Claude, build a playlist including a catalog song, confirm it appears on iPhone.

## Delivery phases

1. **Phase 1 — AppleScript-deep (works day 1, no dev account):** package restructure, safe runner, persistent-ID tools, playback + playlist CRUD + library search, tests, README rewrite, CHANGELOG.md, PRIMER.md.
2. **Phase 2 — API layer:** auth + setup flow, catalog search, add-to-library, API-routed playlist create/add, dual routing.

Branching per user standard: work on `dev`, feature branches off `dev`, merge to `main` when stable. MIT license and upstream attribution preserved.
