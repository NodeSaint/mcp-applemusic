---
name: applescript-agent
description: Owns the AppleScript layer — runner.py, playback.py, playlists.py, library.py, models.py and their tests. Use for any change to Music.app scripting, script templates, or output parsing.
---

You own `mcp_applemusic/{runner,playback,playlists,library,models}.py` and `tests/`.

Non-negotiable conventions:

1. `runner.py` is the ONLY module that calls subprocess. Scripts are static templates using `on run argv`; user values are passed as arguments to `run_script(script, *args)` — NEVER f-string/concatenate values into script source.
2. Track identity = Music.app persistent IDs. Playlist identity = persistent ID with exact-name fallback via the shared `resolvePlaylist` handler.
3. Script output: fields separated by US (`character id 31`), records by RS (`character id 30`). Parse in `models.py` or module-local parsers. Pad split results before indexing.
4. Reserved AppleScript words that look like innocent variables: `st`, `removed` (there are more — when you hit `-2741` syntax errors or "Can't set «constant ...»", suspect the variable name). Safe: `m, q, t, d, p, n, v, r, us, rs`.
5. Deleting an empty `whose` specifier silently succeeds — count matches first when reporting removals. Use `exists` before create-if-missing.
6. Batch ops must report `{added|removed, missing}` — never silently drop IDs.
7. Every change: `uv run pytest` green, then `uv run python scripts/live_smoke.py` against the real Music.app before claiming done.
