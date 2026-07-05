<div align="center">

# 🎧 mcp-applemusic

### Give Claude the keys to your Apple Music.

Search your library, build playlists, run playback, manage everything — in plain language, straight from any MCP client. Changes sync to your iPhone.

**[Landing page](https://nodesaint.github.io/mcp-applemusic/) · [Install](#install) · [Tools](#the-14-tools) · [Security](#security)**

</div>

---

## What it is

An [MCP](https://modelcontextprotocol.io) server that connects Claude (or any MCP client) to the Music app on your Mac. Ask for *"a rainy-Sunday playlist from my library"* or *"skip this and turn it down"* and it happens — through 14 focused tools over AppleScript.

Anything it changes on your Mac — new playlists, edits, ratings, favorites — propagates to your iPhone and every other device through iCloud Music Library, usually within seconds.

This is a ground-up rework of [kennethreitz/mcp-applemusic](https://github.com/kennethreitz/mcp-applemusic) (credit to Kenneth Reitz for the original experiment). The rewrite adds a modular package, injection-safe AppleScript execution, persistent-ID track handling so nothing matches the wrong song, structured JSON results, and roughly triple the tool surface.

## Quick example

> **You:** Build me a 30-minute focus playlist from stuff I already have, no lyrics.
>
> **Claude:** *searches your library by genre, assembles instrumental tracks, creates the playlist* → **"Deep Focus" created with 9 tracks.** It's syncing to your iPhone now.

## Install

**Requirements:** macOS · the Music app · an Apple Music subscription · **Sync Library on** (Music → Settings → General → Sync Library) · [uv](https://docs.astral.sh/uv/).

**Claude Code**

```bash
claude mcp add applemusic -- uvx --from git+https://github.com/NodeSaint/mcp-applemusic mcp-applemusic
```

**Claude Desktop** — add to `claude_desktop_config.json`:

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

The first tool call may trigger a macOS **Automation** permission prompt — allow it (System Settings → Privacy & Security → Automation). That's macOS confirming you want this app to control Music.

## The 14 tools

**Playback**
| Tool | Does |
|---|---|
| `music_playback` | play · pause · toggle · next · previous |
| `music_now_playing` | current track, state, volume, shuffle, repeat |
| `music_set_options` | volume (0–100), shuffle, repeat (off/one/all) |
| `music_play` | play a track, a playlist, or an ad-hoc track list (DJ mode) |

**Library**
| Tool | Does |
|---|---|
| `music_search` | search by all / songs / artists / albums / genre — returns persistent IDs |
| `music_track_info` | genre, year, play count, rating, favorited, cloud status |
| `music_rate` | 0–5 stars, favorite, dislike |

**Playlists**
| Tool | Does |
|---|---|
| `music_playlists` | list every playlist with IDs and counts |
| `music_playlist_tracks` | tracks inside a playlist |
| `music_create_playlist` | create, optionally pre-filled — reports any IDs it couldn't add |
| `music_add_to_playlist` | add tracks |
| `music_remove_from_playlist` | remove tracks (library untouched) |
| `music_rename_playlist` | rename |
| `music_delete_playlist` | delete (tracks stay in your library) |

Every track operation uses Music's **persistent IDs** from `music_search` — no fragile name matching, no accidental wrong-song. Batch operations always report an `added`/`removed` count plus a `missing` list; nothing is silently dropped.

## Security

The whole server talks to Music through **one** gateway (`runner.py`). Every value you give it — a search term, a playlist name — is passed to `osascript` as a positional argument behind a `--` terminator, **never** concatenated into script source. That makes AppleScript injection structurally impossible: a track named `"; do shell script "rm -rf ~"` is just a string, never code. There is no `eval`, no `shell=True`, no `do shell script` anywhere in the codebase. See [`CHANGELOG.md`](CHANGELOG.md) for the hardening history.

It's a local, stdio server with no network surface — it can only reach the Music app on the machine it runs on.

## Roadmap

**Phase 1 — done & live-tested.** Everything above, over AppleScript. Works today, no developer account needed.

**Phase 2 — Apple Music Web API.** Full-catalog search and adding songs you don't own yet, plus native cloud playlists. Needs an Apple Developer membership and a MusicKit key; design is already specced in [`docs/superpowers/`](docs/superpowers/).

## Develop

```bash
uv run pytest                          # 38 unit tests, no Music.app needed
uv run python scripts/live_smoke.py    # end-to-end against the real Music app
```

Architecture, conventions, and the hard-won AppleScript gotchas live in [`PRIMER.md`](PRIMER.md).

## License

MIT — see [LICENSE](LICENSE). Original work © Kenneth Reitz. This fork © NodeSaint.
