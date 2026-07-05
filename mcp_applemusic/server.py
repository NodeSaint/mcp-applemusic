"""FastMCP tool surface. Thin: validate → call module → shape result."""
from mcp.server.fastmcp import FastMCP

from . import library, playback, playlists
from .runner import AppleScriptError

mcp = FastMCP("AppleMusic")


def _safe(fn):
    try:
        return fn()
    except AppleScriptError as e:
        return {"error": str(e), "hint": e.hint}
    except ValueError as e:
        return {"error": str(e), "hint": None}


@mcp.tool()
def music_playback(action: str) -> dict | str:
    """Control playback: action is one of play, pause, toggle, next, previous."""
    return _safe(lambda: playback.control(action))


@mcp.tool()
def music_now_playing() -> dict:
    """Get player state, current track, volume, shuffle and repeat settings."""
    return _safe(playback.now_playing)


@mcp.tool()
def music_set_options(volume: int | None = None, shuffle: bool | None = None,
                      repeat: str | None = None) -> dict:
    """Set volume (0-100), shuffle (true/false), and/or repeat (off/one/all)."""
    return _safe(lambda: playback.set_options(volume, shuffle, repeat))


@mcp.tool()
def music_play(track_id: str | None = None, playlist: str | None = None,
               track_ids: list[str] | None = None) -> dict | str:
    """Play a track (by persistent ID), a playlist (by ID or name), or an ad-hoc
    list of tracks (track_ids — builds and plays the 'Claude Queue' playlist;
    use this to play an album or a DJ set). Provide exactly one of the three."""
    given = [x for x in (track_id, playlist, track_ids) if x]
    if len(given) != 1:
        return {"error": "Provide exactly one of track_id, playlist, or track_ids", "hint": None}
    if track_id:
        return _safe(lambda: playback.play_track(track_id))
    if playlist:
        return _safe(lambda: playback.play_playlist(playlist))
    return _safe(lambda: playback.play_tracks(track_ids))


@mcp.tool()
def music_search(query: str, by: str = "all", limit: int = 25) -> list | dict:
    """Search the Music library (including non-downloaded cloud tracks).
    'by' scopes the search: all, songs, artists, albums, or genre.
    Returns tracks with persistent IDs — use those IDs with all other tools."""
    return _safe(lambda: library.search(query, by, limit))


@mcp.tool()
def music_track_info(track_id: str) -> dict:
    """Full metadata for one track: genre, year, play count, rating, favorited,
    disliked, cloud status."""
    return _safe(lambda: library.track_info(track_id))


@mcp.tool()
def music_rate(track_id: str, rating: float | None = None,
               favorited: bool | None = None, disliked: bool | None = None) -> dict | str:
    """Rate a track (0-5 stars) and/or set favorited / disliked flags."""
    def go():
        results = {}
        if rating is not None:
            library.set_rating(track_id, rating)
            results["rating"] = rating
        if favorited is not None:
            library.set_favorited(track_id, favorited)
            results["favorited"] = favorited
        if disliked is not None:
            library.set_disliked(track_id, disliked)
            results["disliked"] = disliked
        if not results:
            raise ValueError("Provide at least one of rating, favorited, disliked")
        return results
    return _safe(go)


@mcp.tool()
def music_playlists() -> list | dict:
    """List all user playlists with persistent IDs, track counts, smart flag."""
    return _safe(playlists.list_playlists)


@mcp.tool()
def music_playlist_tracks(playlist: str, limit: int = 200) -> list | dict:
    """List the tracks in a playlist (by persistent ID or exact name)."""
    return _safe(lambda: playlists.get_tracks(playlist, limit))


@mcp.tool()
def music_create_playlist(name: str, track_ids: list[str] | None = None) -> dict:
    """Create a playlist, optionally populated with tracks (persistent IDs from
    music_search). Syncs to iPhone via iCloud Music Library. Reports which IDs
    could not be added."""
    return _safe(lambda: playlists.create(name, track_ids))


@mcp.tool()
def music_add_to_playlist(playlist: str, track_ids: list[str]) -> dict:
    """Add tracks (persistent IDs) to an existing playlist."""
    return _safe(lambda: playlists.add_tracks(playlist, track_ids))


@mcp.tool()
def music_remove_from_playlist(playlist: str, track_ids: list[str]) -> dict:
    """Remove tracks (persistent IDs) from a playlist. Does not delete them from
    the library."""
    return _safe(lambda: playlists.remove_tracks(playlist, track_ids))


@mcp.tool()
def music_rename_playlist(playlist: str, new_name: str) -> dict | str:
    """Rename a playlist (identified by persistent ID or exact current name)."""
    return _safe(lambda: playlists.rename(playlist, new_name))


@mcp.tool()
def music_delete_playlist(playlist: str) -> dict | str:
    """Delete a playlist (by persistent ID or exact name). Tracks stay in the
    library."""
    return _safe(lambda: playlists.delete(playlist))


def main():
    mcp.run()


if __name__ == "__main__":
    main()
