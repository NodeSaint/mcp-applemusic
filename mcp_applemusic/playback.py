"""Playback control for Music.app on this Mac."""
from .runner import run_script, US

_ACTIONS = {
    "play": 'tell application "Music" to play',
    "pause": 'tell application "Music" to pause',
    "toggle": 'tell application "Music" to playpause',
    "next": 'tell application "Music" to next track',
    "previous": 'tell application "Music" to previous track',
}

_NOW_PLAYING_SCRIPT = '''
on run argv
    set us to character id 31
    tell application "Music"
        set stateText to (player state) as text
        set trackPart to us & us & us & us & us
        if stateText is "playing" or stateText is "paused" then
            try
                set t to current track
                set d to ""
                try
                    set d to ((duration of t) as integer) as text
                end try
                set trackPart to us & (persistent ID of t) & us & (name of t) & us & (artist of t) & us & (album of t) & us & d
            end try
        end if
        return stateText & trackPart & us & (sound volume) & us & (shuffle enabled) & us & ((song repeat) as text)
    end tell
end run
'''

_VOLUME_SCRIPT = '''
on run argv
    tell application "Music" to set sound volume to (item 1 of argv) as integer
    return "ok"
end run
'''

_SHUFFLE_SCRIPT = '''
on run argv
    tell application "Music" to set shuffle enabled to ((item 1 of argv) is "true")
    return "ok"
end run
'''

_REPEAT_SCRIPT = '''
on run argv
    set m to item 1 of argv
    tell application "Music"
        if m is "off" then
            set song repeat to off
        else if m is "one" then
            set song repeat to one
        else
            set song repeat to all
        end if
    end tell
    return "ok"
end run
'''

_PLAY_TRACK_SCRIPT = '''
on run argv
    set pid to item 1 of argv
    tell application "Music"
        play (first track of library playlist 1 whose persistent ID is pid)
        return "ok"
    end tell
end run
'''

_PLAY_PLAYLIST_SCRIPT = '''
on run argv
    set q to item 1 of argv
    tell application "Music"
        try
            set p to first user playlist whose persistent ID is q
        on error
            set p to first user playlist whose name is q
        end try
        play p
        return "ok"
    end tell
end run
'''

_PLAY_TRACKS_SCRIPT = '''
on run argv
    set qName to item 1 of argv
    set us to character id 31
    tell application "Music"
        if (exists user playlist qName) then
            set q to user playlist qName
            try
                delete every track of q
            end try
        else
            set q to make new user playlist with properties {name:qName}
        end if
        set added to 0
        set missing to ""
        repeat with i from 2 to count of argv
            set pid to item i of argv
            try
                duplicate (first track of library playlist 1 whose persistent ID is pid) to q
                set added to added + 1
            on error
                set missing to missing & pid & ","
            end try
        end repeat
        if added is greater than 0 then play q
        return (added as text) & us & missing
    end tell
end run
'''


def control(action: str, runner=run_script) -> str:
    if action not in _ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(_ACTIONS)} (got {action!r})")
    runner(_ACTIONS[action])
    return "ok"


def now_playing(runner=run_script) -> dict:
    parts = runner(_NOW_PLAYING_SCRIPT).split(US)
    parts += [""] * (9 - len(parts))

    def _num(s):
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None

    track = None
    if parts[1]:
        track = {
            "id": parts[1],
            "name": parts[2],
            "artist": parts[3],
            "album": parts[4],
            "duration_seconds": _num(parts[5]),
        }
    return {
        "player_state": parts[0],
        "track": track,
        "volume": _num(parts[6]),
        "shuffle": parts[7].strip().lower() == "true",
        "repeat": parts[8] or None,
    }


def set_options(volume: int | None = None, shuffle: bool | None = None,
                repeat: str | None = None, runner=run_script) -> dict:
    applied = {}
    if volume is not None:
        if not 0 <= int(volume) <= 100:
            raise ValueError("volume must be 0-100")
        runner(_VOLUME_SCRIPT, str(int(volume)))
        applied["volume"] = int(volume)
    if shuffle is not None:
        runner(_SHUFFLE_SCRIPT, "true" if shuffle else "false")
        applied["shuffle"] = bool(shuffle)
    if repeat is not None:
        if repeat not in ("off", "one", "all"):
            raise ValueError("repeat must be off, one, or all")
        runner(_REPEAT_SCRIPT, repeat)
        applied["repeat"] = repeat
    if not applied:
        raise ValueError("Provide at least one of volume, shuffle, repeat")
    return applied


def play_track(track_id: str, runner=run_script) -> str:
    return runner(_PLAY_TRACK_SCRIPT, track_id)


def play_playlist(playlist: str, runner=run_script) -> str:
    return runner(_PLAY_PLAYLIST_SCRIPT, playlist)


def play_tracks(track_ids: list[str], queue_name: str = "Claude Queue", runner=run_script) -> dict:
    if not track_ids:
        raise ValueError("track_ids must not be empty")
    out = runner(_PLAY_TRACKS_SCRIPT, queue_name, *track_ids)
    added_s, _, missing_s = out.partition(US)
    missing = [m for m in missing_s.split(",") if m]
    return {"queued": int(added_s or 0), "missing": missing, "playlist": queue_name}
