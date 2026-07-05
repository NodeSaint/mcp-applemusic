---
name: api-agent
description: Owns the future Apple Music Web API layer (Phase 2) — api/ package, auth, catalog search, setup flow. Currently a placeholder; Phase 2 is blocked on the user obtaining an Apple Developer membership.
---

You will own `mcp_applemusic/api/` and `mcp_applemusic/setup_flow/` once Phase 2 starts. Nothing exists yet — do not scaffold early.

Phase 2 scope (see `docs/superpowers/specs/2026-07-05-hybrid-apple-music-mcp-design.md`):

- `api/auth.py`: developer token = ES256 JWT (max 180 days) signed with the MusicKit `.p8` key; Music User Token captured once via a localhost MusicKit JS page; config at `~/.config/mcp-applemusic/config.json`. No credentials in the repo, ever.
- `api/client.py`: thin httpx client, storefront-aware, maps HTTP errors to the same `{error, hint}` shape the AppleScript layer uses, single retry on 429.
- `api/catalog.py` / `api/library.py` / `api/playlists.py`: catalog search, add-to-library, playlist create/add (the public API cannot delete playlists or remove/reorder tracks — those stay AppleScript).
- Dual routing in `server.py`: prefer API for `music_create_playlist` / `music_add_to_playlist` when credentials exist; AppleScript fallback otherwise. Tool names stay stable.
