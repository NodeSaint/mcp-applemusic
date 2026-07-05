# mcp-applemusic

An MCP server that lets Claude control Apple Music on macOS: playback, library search, and full playlist management. Playlist and library changes sync to your iPhone via iCloud Music Library.

Forked from [kennethreitz/mcp-applemusic](https://github.com/kennethreitz/mcp-applemusic) — credit to Kenneth Reitz for the original experiment. This fork restructures it into a modular package with injection-safe AppleScript execution, persistent-ID track handling, structured JSON results, and a much larger tool surface.

## Requirements

- macOS with the Music app and an Apple Music subscription
- **Sync Library enabled** (Music → Settings → General → Sync Library) — this is what makes your full cloud library visible and syncs playlist changes to your other devices
- [uv](https://docs.astral.sh/uv/) installed
- First tool call may trigger a macOS Automation permission prompt — allow it (System Settings → Privacy & Security → Automation)

## Install

Claude Code:

```bash
claude mcp add applemusic -- uvx --from git+https://github.com/NodeSaint/mcp-applemusic mcp-applemusic
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "applemusic": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/NodeSaint/mcp-applemusic", "mcp-applemusic"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `music_playback` | play / pause / toggle / next / previous |
| `music_now_playing` | Current track, player state, volume, shuffle, repeat |
| `music_set_options` | Volume (0–100), shuffle, repeat (off/one/all) |
| `music_play` | Play a track, a playlist, or an ad-hoc track list (DJ mode via a "Claude Queue" playlist) |
| `music_search` | Search your library — by all / songs / artists / albums / genre. Returns persistent IDs |
| `music_track_info` | Full metadata: genre, year, play count, rating, favorited, cloud status |
| `music_rate` | Star rating (0–5), favorite, dislike |
| `music_playlists` | List all playlists with IDs and counts |
| `music_playlist_tracks` | Tracks in a playlist |
| `music_create_playlist` | Create a playlist, optionally with tracks. Reports any IDs it couldn't add |
| `music_add_to_playlist` | Add tracks to a playlist |
| `music_remove_from_playlist` | Remove tracks from a playlist (library untouched) |
| `music_rename_playlist` | Rename a playlist |
| `music_delete_playlist` | Delete a playlist (tracks stay in library) |

All track operations use Music.app **persistent IDs** returned by `music_search` — no fragile name matching. Batch operations report `added`/`removed` counts plus a `missing` list; nothing is silently dropped.

## How changes reach your iPhone

This server drives Music.app on your Mac. With Sync Library on, playlist creations, edits, deletions, ratings, and favorites propagate to all your devices through iCloud Music Library — usually within seconds. (No API exists that can control playback *on* an iPhone; playback tools affect the Mac.)

## Limitations

- macOS only (AppleScript-based)
- Library content only — searching the full Apple Music catalog and adding songs you don't have yet arrives in Phase 2 (Apple Music Web API; needs an Apple Developer membership)
- No Up Next queue manipulation (Music.app doesn't expose it to AppleScript); `music_play` with `track_ids` approximates it via a queue playlist
- Smart playlists can be read but not edited

## Development

```bash
uv run pytest                          # unit tests (no Music.app needed)
uv run python scripts/live_smoke.py   # end-to-end against the real Music.app
```

Design docs live in `docs/superpowers/`. Architecture in short: `runner.py` is the sole `osascript` gateway — every user value is passed as an `argv` argument, never spliced into script source, making AppleScript injection structurally impossible.

## License

MIT — see [LICENSE](LICENSE). Original work © Kenneth Reitz.
