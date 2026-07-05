from mcp_applemusic.models import parse_tracks, parse_playlists
from mcp_applemusic.runner import US, RS


def test_parse_tracks_basic():
    out = f"PID1{US}Song, with comma{US}Artist{US}Album{US}240{RS}PID2{US}B{US}C{US}D{US}"
    tracks = parse_tracks(out)
    assert tracks[0] == {
        "id": "PID1",
        "name": "Song, with comma",
        "artist": "Artist",
        "album": "Album",
        "duration_seconds": 240,
    }
    assert tracks[1]["duration_seconds"] is None


def test_parse_tracks_empty_output():
    assert parse_tracks("") == []
    assert parse_tracks(f"{RS}") == []


def test_parse_playlists():
    out = f"P1{US}Chill{US}12{US}false{RS}P2{US}Smart One{US}{US}true{RS}"
    pls = parse_playlists(out)
    assert pls[0] == {"id": "P1", "name": "Chill", "track_count": 12, "smart": False}
    assert pls[1]["smart"] is True and pls[1]["track_count"] is None
