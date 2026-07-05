import mcp_applemusic.server as server
from mcp_applemusic.runner import AppleScriptError
from mcp_applemusic.server import _safe, mcp


def test_safe_passes_through_success():
    assert _safe(lambda: {"x": 1}) == {"x": 1}


def test_readonly_blocks_write_tool_without_calling_it(monkeypatch):
    monkeypatch.setenv("MUSIC_MCP_READONLY", "1")
    called = []
    result = _safe(lambda: called.append(True), write=True)
    assert called == []  # module was never invoked
    assert "read-only" in result["error"].lower()
    assert result["hint"]


def test_readonly_allows_read_tool(monkeypatch):
    monkeypatch.setenv("MUSIC_MCP_READONLY", "1")
    assert _safe(lambda: {"ok": 1}) == {"ok": 1}  # write defaults to False


def test_readonly_off_allows_write(monkeypatch):
    monkeypatch.delenv("MUSIC_MCP_READONLY", raising=False)
    assert _safe(lambda: {"done": 1}, write=True) == {"done": 1}


def test_delete_playlist_tool_blocked_in_readonly(monkeypatch):
    monkeypatch.setenv("MUSIC_MCP_READONLY", "yes")
    # patch the module fn so a leak would be observable, then confirm it's never reached
    monkeypatch.setattr(server.playlists, "delete", lambda *a, **k: (_ for _ in ()).throw(AssertionError("reached")))
    result = server.music_delete_playlist("Anything")
    assert "read-only" in result["error"].lower()


def test_safe_shapes_applescript_error():
    def boom():
        raise AppleScriptError("execution error (-600)", hint="Open Music.app")

    result = _safe(boom)
    assert result["error"].startswith("execution error")
    assert result["hint"] == "Open Music.app"


def test_safe_shapes_value_error():
    def bad():
        raise ValueError("volume must be 0-100")

    assert _safe(bad) == {"error": "volume must be 0-100", "hint": None}


def test_all_fourteen_tools_registered():
    import asyncio

    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "music_playback", "music_now_playing", "music_set_options", "music_play",
        "music_search", "music_track_info", "music_rate",
        "music_playlists", "music_playlist_tracks", "music_create_playlist",
        "music_add_to_playlist", "music_remove_from_playlist",
        "music_rename_playlist", "music_delete_playlist",
    }
