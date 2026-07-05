"""Parse US/RS-delimited AppleScript output into plain dicts."""
from .runner import US, RS


def _int_or_none(value: str) -> int | None:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def parse_tracks(output: str) -> list[dict]:
    tracks = []
    for record in output.split(RS):
        if not record.strip():
            continue
        parts = record.split(US)
        parts += [""] * (5 - len(parts))
        tracks.append({
            "id": parts[0],
            "name": parts[1],
            "artist": parts[2],
            "album": parts[3],
            "duration_seconds": _int_or_none(parts[4]),
        })
    return tracks


def parse_playlists(output: str) -> list[dict]:
    playlists = []
    for record in output.split(RS):
        if not record.strip():
            continue
        parts = record.split(US)
        parts += [""] * (4 - len(parts))
        playlists.append({
            "id": parts[0],
            "name": parts[1],
            "track_count": _int_or_none(parts[2]),
            "smart": parts[3].strip().lower() == "true",
        })
    return playlists
