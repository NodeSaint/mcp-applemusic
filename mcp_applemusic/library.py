"""Library search and track metadata. All values via argv."""
from .models import parse_tracks
from .runner import run_script, US

_TRACK_EMIT = '''
on emitTrack(t)
    tell application "Music"
        set us to character id 31
        set d to ""
        try
            set d to ((duration of t) as integer) as text
        end try
        return (persistent ID of t) & us & (name of t) & us & (artist of t) & us & (album of t) & us & d
    end tell
end emitTrack
'''

_SEARCH_AREAS = {"all", "songs", "artists", "albums"}

_SEARCH_SCRIPT = _TRACK_EMIT + '''
on run argv
    set q to item 1 of argv
    set area to item 2 of argv
    set maxN to (item 3 of argv) as integer
    set rs to character id 30
    tell application "Music"
        if area is "songs" then
            set found to (search library playlist 1 for q only songs)
        else if area is "artists" then
            set found to (search library playlist 1 for q only artists)
        else if area is "albums" then
            set found to (search library playlist 1 for q only albums)
        else
            set found to (search library playlist 1 for q only all)
        end if
    end tell
    set out to ""
    set n to 0
    repeat with t in found
        if n is greater than or equal to maxN then exit repeat
        set out to out & (my emitTrack(t)) & rs
        set n to n + 1
    end repeat
    return out
end run
'''

_GENRE_SCRIPT = _TRACK_EMIT + '''
on run argv
    set q to item 1 of argv
    set maxN to (item 2 of argv) as integer
    set rs to character id 30
    tell application "Music"
        set found to (every track of library playlist 1 whose genre contains q)
    end tell
    set out to ""
    set n to 0
    repeat with t in found
        if n is greater than or equal to maxN then exit repeat
        set out to out & (my emitTrack(t)) & rs
        set n to n + 1
    end repeat
    return out
end run
'''

_INFO_SCRIPT = '''
on run argv
    set pid to item 1 of argv
    set us to character id 31
    tell application "Music"
        set t to first track of library playlist 1 whose persistent ID is pid
        set fields to (persistent ID of t) & us & (name of t) & us & (artist of t) & us & (album of t)
        try
            set fields to fields & us & ((duration of t) as integer)
        on error
            set fields to fields & us
        end try
        set fields to fields & us & (genre of t) & us & (year of t) & us & (played count of t) & us & (rating of t)
        try
            set fields to fields & us & (favorited of t) & us & (disliked of t)
        on error
            set fields to fields & us & "" & us & ""
        end try
        try
            set fields to fields & us & ((cloud status of t) as text)
        on error
            set fields to fields & us & ""
        end try
        return fields
    end tell
end run
'''

_RATING_SCRIPT = '''
on run argv
    set pid to item 1 of argv
    set r to (item 2 of argv) as integer
    tell application "Music"
        set t to first track of library playlist 1 whose persistent ID is pid
        set rating of t to r
        return "ok"
    end tell
end run
'''

_FAVORITED_SCRIPT = '''
on run argv
    set pid to item 1 of argv
    set v to (item 2 of argv) is "true"
    tell application "Music"
        set t to first track of library playlist 1 whose persistent ID is pid
        set favorited of t to v
        return "ok"
    end tell
end run
'''

_DISLIKED_SCRIPT = _FAVORITED_SCRIPT.replace("favorited", "disliked")


def search(query: str, by: str = "all", limit: int = 25, runner=run_script) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    if by == "genre":
        return parse_tracks(runner(_GENRE_SCRIPT, query, str(limit)))
    if by not in _SEARCH_AREAS:
        raise ValueError(f"'by' must be one of: all, songs, artists, albums, genre (got {by!r})")
    return parse_tracks(runner(_SEARCH_SCRIPT, query, by, str(limit)))


def _num(s):
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def track_info(track_id: str, runner=run_script) -> dict:
    parts = runner(_INFO_SCRIPT, track_id).split(US)
    parts += [""] * (12 - len(parts))
    return {
        "id": parts[0],
        "name": parts[1],
        "artist": parts[2],
        "album": parts[3],
        "duration_seconds": _num(parts[4]),
        "genre": parts[5],
        "year": _num(parts[6]),
        "played_count": _num(parts[7]),
        "rating_stars": (_num(parts[8]) or 0) / 20,
        "favorited": parts[9].strip().lower() == "true",
        "disliked": parts[10].strip().lower() == "true",
        "cloud_status": parts[11] or None,
    }


def set_rating(track_id: str, stars: float, runner=run_script) -> str:
    if not 0 <= stars <= 5:
        raise ValueError("rating must be between 0 and 5 stars")
    return runner(_RATING_SCRIPT, track_id, str(int(stars * 20)))


def set_favorited(track_id: str, value: bool, runner=run_script) -> str:
    return runner(_FAVORITED_SCRIPT, track_id, "true" if value else "false")


def set_disliked(track_id: str, value: bool, runner=run_script) -> str:
    return runner(_DISLIKED_SCRIPT, track_id, "true" if value else "false")
