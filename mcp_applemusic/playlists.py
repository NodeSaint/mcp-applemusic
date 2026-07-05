"""User playlist CRUD. Playlists resolved by persistent ID, falling back to exact name."""
from .models import parse_tracks, parse_playlists
from .runner import run_script, US

_RESOLVE = '''
on resolvePlaylist(q)
    tell application "Music"
        try
            return first user playlist whose persistent ID is q
        on error
            return first user playlist whose name is q
        end try
    end tell
end resolvePlaylist
'''

_LIST_SCRIPT = '''
on run argv
    set us to character id 31
    set rs to character id 30
    tell application "Music"
        set out to ""
        repeat with p in (every user playlist)
            set sm to "false"
            try
                if smart of p then set sm to "true"
            end try
            set out to out & (persistent ID of p) & us & (name of p) & us & (count of tracks of p) & us & sm & rs
        end repeat
        return out
    end tell
end run
'''

_GET_TRACKS_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set maxN to (item 2 of argv) as integer
    set us to character id 31
    set rs to character id 30
    set p to my resolvePlaylist(q)
    set out to ""
    set n to 0
    tell application "Music"
        repeat with t in (every track of p)
            if n is greater than or equal to maxN then exit repeat
            set d to ""
            try
                set d to ((duration of t) as integer) as text
            end try
            set out to out & (persistent ID of t) & us & (name of t) & us & (artist of t) & us & (album of t) & us & d & rs
            set n to n + 1
        end repeat
    end tell
    return out
end run
'''

_CREATE_SCRIPT = '''
on run argv
    set plName to item 1 of argv
    set us to character id 31
    tell application "Music"
        set p to make new user playlist with properties {name:plName}
        set added to 0
        set missing to ""
        repeat with i from 2 to count of argv
            set pid to item i of argv
            try
                duplicate (first track of library playlist 1 whose persistent ID is pid) to p
                set added to added + 1
            on error
                set missing to missing & pid & ","
            end try
        end repeat
        return (persistent ID of p) & us & (added as text) & us & missing
    end tell
end run
'''

_ADD_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set us to character id 31
    set p to my resolvePlaylist(q)
    set added to 0
    set missing to ""
    tell application "Music"
        repeat with i from 2 to count of argv
            set pid to item i of argv
            try
                duplicate (first track of library playlist 1 whose persistent ID is pid) to p
                set added to added + 1
            on error
                set missing to missing & pid & ","
            end try
        end repeat
    end tell
    return (added as text) & us & missing
end run
'''

_REMOVE_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set us to character id 31
    set p to my resolvePlaylist(q)
    set removedCount to 0
    set missing to ""
    tell application "Music"
        repeat with i from 2 to count of argv
            set pid to item i of argv
            set matches to (every track of p whose persistent ID is pid)
            if (count of matches) is 0 then
                set missing to missing & pid & ","
            else
                repeat with m in matches
                    delete m
                end repeat
                set removedCount to removedCount + 1
            end if
        end repeat
    end tell
    return (removedCount as text) & us & missing
end run
'''

_RENAME_SCRIPT = _RESOLVE + '''
on run argv
    set p to my resolvePlaylist(item 1 of argv)
    tell application "Music" to set name of p to (item 2 of argv)
    return "ok"
end run
'''

_DELETE_SCRIPT = _RESOLVE + '''
on run argv
    set p to my resolvePlaylist(item 1 of argv)
    tell application "Music" to delete p
    return "ok"
end run
'''


def _parse_batch(out: str, key: str) -> dict:
    count_s, _, missing_s = out.partition(US)
    return {key: int(count_s or 0), "missing": [m for m in missing_s.split(",") if m]}


def list_playlists(runner=run_script) -> list[dict]:
    return parse_playlists(runner(_LIST_SCRIPT))


def get_tracks(playlist: str, limit: int = 200, runner=run_script) -> list[dict]:
    limit = max(1, min(int(limit), 1000))
    return parse_tracks(runner(_GET_TRACKS_SCRIPT, playlist, str(limit)))


def create(name: str, track_ids: list[str] | None = None, runner=run_script) -> dict:
    out = runner(_CREATE_SCRIPT, name, *(track_ids or []))
    pid, _, rest = out.partition(US)
    return {"id": pid, "name": name, **_parse_batch(rest, "added")}


def add_tracks(playlist: str, track_ids: list[str], runner=run_script) -> dict:
    if not track_ids:
        raise ValueError("track_ids must not be empty")
    return {"playlist": playlist, **_parse_batch(runner(_ADD_SCRIPT, playlist, *track_ids), "added")}


def remove_tracks(playlist: str, track_ids: list[str], runner=run_script) -> dict:
    if not track_ids:
        raise ValueError("track_ids must not be empty")
    return {"playlist": playlist, **_parse_batch(runner(_REMOVE_SCRIPT, playlist, *track_ids), "removed")}


def rename(playlist: str, new_name: str, runner=run_script) -> str:
    return runner(_RENAME_SCRIPT, playlist, new_name)


def delete(playlist: str, runner=run_script) -> str:
    return runner(_DELETE_SCRIPT, playlist)
