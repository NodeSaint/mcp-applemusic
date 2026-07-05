# Phase 1: AppleScript-Deep Apple Music MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile single-file server with a modular, injection-safe, persistent-ID-based AppleScript MCP server covering playback, library search, and full playlist CRUD.

**Architecture:** A Python package where `runner.py` is the sole `osascript` gateway (all user values passed via `argv`, never interpolated), AppleScript emits records using ASCII unit/record separators that `models.py` parses into dataclasses, and `server.py` registers thin FastMCP tools that shape module results into JSON with `{error, hint}` on failure.

**Tech Stack:** Python 3.13, FastMCP (`mcp>=1.2.1`), uv, pytest. macOS 26 Music.app 1.6.3 (verified live: `search` verb, `favorited`, `cloud status`, argv passing all work).

## Global Constraints

- `requires-python = ">=3.13"`; dependencies stay exactly `["mcp>=1.2.1"]` (pytest is dev-only).
- No user-provided value is EVER concatenated or f-stringed into AppleScript source. Values travel via `osascript -e <script> <arg1> <arg2>` into `on run argv`. `runner.py` is the only module that calls `subprocess`.
- All track identity via Music.app `persistent ID`; playlist identity via persistent ID with name fallback.
- Field/record delimiters: US = `"\x1f"` (`character id 31`), RS = `"\x1e"` (`character id 30`).
- Every MCP tool returns JSON-serializable dicts/lists; failures return `{"error": str, "hint": str|None}` — the server never raises to the client.
- Commits: author NodeSaint only, NO Claude co-author lines. Work on `dev`.
- Tool names use `music_` prefix (upstream `itunes_*` names are retired; no compat promise).

---

### Task 1: Package scaffold + injection-safe runner

**Files:**
- Create: `mcp_applemusic/__init__.py`, `mcp_applemusic/runner.py`
- Create: `tests/test_runner.py`
- Modify: `pyproject.toml` (entry point → `mcp_applemusic.server:main`, add dev group)
- Delete: `mcp_applemusic.py` — MUST happen in this task: a root module and package sharing the name `mcp_applemusic` is an import-resolution hazard (critique fix #1)

**Interfaces:**
- Produces: `run_script(script: str, *args: str) -> str` (raises `AppleScriptError`), `AppleScriptError(Exception)` with `.hint: str | None`, constants `US = "\x1f"`, `RS = "\x1e"`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_runner.py
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from mcp_applemusic.runner import run_script, AppleScriptError


def _completed(returncode=0, stdout="", stderr=""):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode, m.stdout, m.stderr = returncode, stdout, stderr
    return m


def test_args_passed_as_argv_not_interpolated():
    with patch("mcp_applemusic.runner.subprocess.run", return_value=_completed(stdout="ok\n")) as run:
        run_script("on run argv\nreturn item 1 of argv\nend run", 'evil " quote', "two")
    cmd = run.call_args[0][0]
    assert cmd[:2] == ["osascript", "-e"]
    assert cmd[3:] == ['evil " quote', "two"]  # data, not source
    assert 'evil' not in cmd[2]


def test_output_stripped_of_trailing_newline():
    with patch("mcp_applemusic.runner.subprocess.run", return_value=_completed(stdout="hello\n")):
        assert run_script("s") == "hello"


def test_error_raises_with_hint_for_not_running():
    err = _completed(1, stderr="execution error: Music got an error (-600)")
    with patch("mcp_applemusic.runner.subprocess.run", return_value=err):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert "not running" in ei.value.hint.lower()


def test_error_raises_with_hint_for_permission():
    err = _completed(1, stderr="execution error: Not authorized to send Apple events (-1743)")
    with patch("mcp_applemusic.runner.subprocess.run", return_value=err):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert "automation" in ei.value.hint.lower()


def test_error_not_found_hint():
    err = _completed(1, stderr="execution error: Music got an error: Can't get track. (-1728)")
    with patch("mcp_applemusic.runner.subprocess.run", return_value=err):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert "not found" in ei.value.hint.lower()


def test_timeout_maps_to_applescript_error():
    with patch("mcp_applemusic.runner.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=120)):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert "timed out" in str(ei.value).lower()


def test_error_without_known_code_has_no_hint():
    err = _completed(1, stderr="execution error: something odd (-999)")
    with patch("mcp_applemusic.runner.subprocess.run", return_value=err):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert ei.value.hint is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/mcp-applemusic && uv run pytest tests/test_runner.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: mcp_applemusic.runner`

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/__init__.py
```

```python
# mcp_applemusic/runner.py
"""Sole osascript gateway. User values travel via argv — never into script source."""
import subprocess

US = "\x1f"  # unit separator: between fields of a record
RS = "\x1e"  # record separator: between records

_HINTS = {
    "-600": "Music.app is not running. Open the Music app and try again.",
    "-609": "Music.app is not running. Open the Music app and try again.",
    "-1743": "Automation permission denied. Allow this app to control Music in System Settings > Privacy & Security > Automation.",
    "-1728": "The requested item was not found in the Music library.",
    "-1712": "Music.app timed out. It may be busy or showing a dialog.",
}


class AppleScriptError(Exception):
    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


def run_script(script: str, *args: str) -> str:
    cmd = ["osascript", "-e", script, *[str(a) for a in args]]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise AppleScriptError(
            "AppleScript timed out after 120s.",
            "Music.app may be busy or showing a dialog. Check the app and retry.",
        ) from None
    if result.returncode != 0:
        stderr = result.stderr.strip() or "AppleScript execution failed"
        hint = next((h for code, h in _HINTS.items() if f"({code})" in stderr), None)
        raise AppleScriptError(stderr, hint)
    return result.stdout.rstrip("\n")
```

```toml
# pyproject.toml (full replacement)
[project]
name = "mcp-applemusic"
version = "0.2.0"
description = "An MCP server for Apple Music: playback, library search, and playlist management"
readme = "README.md"
requires-python = ">=3.13"
dependencies = ["mcp>=1.2.1"]

[project.scripts]
mcp-applemusic = "mcp_applemusic.server:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["mcp_applemusic"]
```

Note: entry point targets `server:main` which doesn't exist until Task 6 — the package still imports fine for tests; the console script just can't run until then.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_runner.py -v` — Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add mcp_applemusic/ tests/ pyproject.toml uv.lock
git commit -m "feat: package scaffold with injection-safe AppleScript runner"
```

---

### Task 2: Track/playlist models + record parsing

**Files:**
- Create: `mcp_applemusic/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `US`, `RS` from `runner.py`.
- Produces: `Track` dataclass (`id, name, artist, album, duration_seconds: int|None, extra: dict`), `Playlist` dataclass (`id, name, track_count: int|None, smart: bool`), `parse_tracks(output: str) -> list[dict]`, `parse_playlists(output: str) -> list[dict]` (dicts via `asdict`, `extra` merged flat).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
from mcp_applemusic.models import parse_tracks, parse_playlists
from mcp_applemusic.runner import US, RS


def test_parse_tracks_basic():
    out = f"PID1{US}Song, with comma{US}Artist{US}Album{US}240{RS}PID2{US}B{US}C{US}D{US}"
    tracks = parse_tracks(out)
    assert tracks[0] == {
        "id": "PID1", "name": "Song, with comma", "artist": "Artist",
        "album": "Album", "duration_seconds": 240,
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
```

- [ ] **Step 2: Run** `uv run pytest tests/test_models.py -v` — Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/models.py
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
```

(Design note: dataclasses dropped — plain dicts are what FastMCP serializes anyway. YAGNI.)

- [ ] **Step 4: Run** `uv run pytest tests/test_models.py -v` — Expected: 3 passed
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: US/RS record parsing for tracks and playlists"`

---

### Task 3: Library module — search, track info, rating/favorite

**Files:**
- Create: `mcp_applemusic/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `run_script`, `parse_tracks`.
- Produces: `search(query: str, by: str = "all", limit: int = 25) -> list[dict]`; `track_info(track_id: str) -> dict`; `set_rating(track_id: str, stars: float) -> str`; `set_favorited(track_id: str, value: bool) -> str`; `set_disliked(track_id: str, value: bool) -> str`. All raise `ValueError` on bad params, `AppleScriptError` upward.
- All modules take an injectable `runner=run_script` kwarg for testing.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_library.py
import pytest
from mcp_applemusic import library
from mcp_applemusic.runner import US, RS


class FakeRunner:
    def __init__(self, output=""):
        self.output = output
        self.calls = []

    def __call__(self, script, *args):
        self.calls.append((script, args))
        return self.output


def test_search_passes_query_as_arg_not_in_script():
    fake = FakeRunner(f"P1{US}N{US}A{US}Al{US}100{RS}")
    result = library.search('crazy "query"', by="songs", limit=10, runner=fake)
    script, args = fake.calls[0]
    assert 'crazy' not in script
    assert args == ('crazy "query"', "songs", "10")
    assert result[0]["id"] == "P1"


def test_search_rejects_bad_field():
    with pytest.raises(ValueError):
        library.search("x", by="composer", runner=FakeRunner())


def test_search_genre_uses_whose_script():
    fake = FakeRunner("")
    library.search("jazz", by="genre", runner=fake)
    script, args = fake.calls[0]
    assert "genre contains" in script
    assert args == ("jazz", "25")


def test_set_rating_converts_stars_to_100_scale():
    fake = FakeRunner("ok")
    library.set_rating("PID", 4.5, runner=fake)
    assert fake.calls[0][1] == ("PID", "90")


def test_set_rating_rejects_out_of_range():
    with pytest.raises(ValueError):
        library.set_rating("PID", 6, runner=FakeRunner())


def test_set_favorited_passes_bool_string():
    fake = FakeRunner("ok")
    library.set_favorited("PID", True, runner=fake)
    assert fake.calls[0][1] == ("PID", "true")
```

- [ ] **Step 2: Run** `uv run pytest tests/test_library.py -v` — Expected: FAIL

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/library.py
"""Library search and track metadata. All values via argv."""
from .models import parse_tracks
from .runner import run_script

_TRACK_EMIT = '''
on emitTrack(t)
    tell application "Music"
        set US to character id 31
        set d to ""
        try
            set d to ((duration of t) as integer) as text
        end try
        return (persistent ID of t) & US & (name of t) & US & (artist of t) & US & (album of t) & US & d
    end tell
end emitTrack
'''

_SEARCH_AREAS = {"all": "all", "songs": "songs", "artists": "artists", "albums": "albums"}

_SEARCH_SCRIPT = _TRACK_EMIT + '''
on run argv
    set q to item 1 of argv
    set area to item 2 of argv
    set maxN to (item 3 of argv) as integer
    set RS to character id 30
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
        set out to out & (my emitTrack(t)) & RS
        set n to n + 1
    end repeat
    return out
end run
'''

_GENRE_SCRIPT = _TRACK_EMIT + '''
on run argv
    set q to item 1 of argv
    set maxN to (item 2 of argv) as integer
    set RS to character id 30
    tell application "Music"
        set found to (every track of library playlist 1 whose genre contains q)
    end tell
    set out to ""
    set n to 0
    repeat with t in found
        if n is greater than or equal to maxN then exit repeat
        set out to out & (my emitTrack(t)) & RS
        set n to n + 1
    end repeat
    return out
end run
'''

_INFO_SCRIPT = '''
on run argv
    set pid to item 1 of argv
    set US to character id 31
    tell application "Music"
        set t to first track of library playlist 1 whose persistent ID is pid
        set fields to (persistent ID of t) & US & (name of t) & US & (artist of t) & US & (album of t)
        try
            set fields to fields & US & ((duration of t) as integer)
        on error
            set fields to fields & US
        end try
        set fields to fields & US & (genre of t) & US & (year of t) & US & (played count of t) & US & (rating of t)
        try
            set fields to fields & US & (favorited of t) & US & (disliked of t)
        on error
            set fields to fields & US & "" & US & ""
        end try
        try
            set fields to fields & US & ((cloud status of t) as text)
        on error
            set fields to fields & US & ""
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
    return parse_tracks(runner(_SEARCH_SCRIPT, query, _SEARCH_AREAS[by], str(limit)))


def track_info(track_id: str, runner=run_script) -> dict:
    from .runner import US
    parts = runner(_INFO_SCRIPT, track_id).split(US)
    parts += [""] * (12 - len(parts))
    def _num(s):
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None
    return {
        "id": parts[0], "name": parts[1], "artist": parts[2], "album": parts[3],
        "duration_seconds": _num(parts[4]), "genre": parts[5], "year": _num(parts[6]),
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
```

- [ ] **Step 4: Run** `uv run pytest tests/test_library.py -v` — Expected: 6 passed
- [ ] **Step 5: Commit** `git commit -am "feat: library search, track info, rating and favorites"`

---

### Task 4: Playback module

**Files:**
- Create: `mcp_applemusic/playback.py`
- Test: `tests/test_playback.py`

**Interfaces:**
- Consumes: `run_script`, `US`.
- Produces: `control(action: str) -> str` (actions: play/pause/toggle/next/previous); `now_playing() -> dict`; `set_options(volume: int|None, shuffle: bool|None, repeat: str|None) -> dict`; `play_track(track_id) -> str`; `play_playlist(playlist) -> str`; `play_tracks(track_ids: list[str], queue_name: str = "Claude Queue") -> dict` (rebuilds a scratch playlist and plays it — this is how albums/ad-hoc DJ sets play).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_playback.py
import pytest
from mcp_applemusic import playback
from mcp_applemusic.runner import US


class FakeRunner:
    def __init__(self, output=""):
        self.output = output
        self.calls = []

    def __call__(self, script, *args):
        self.calls.append((script, args))
        return self.output


def test_control_valid_actions():
    for action in ("play", "pause", "toggle", "next", "previous"):
        fake = FakeRunner("ok")
        playback.control(action, runner=fake)
        assert len(fake.calls) == 1


def test_control_rejects_unknown_action():
    with pytest.raises(ValueError):
        playback.control("stop-hammer-time", runner=FakeRunner())


def test_now_playing_parses_stopped():
    fake = FakeRunner(f"stopped{US}{US}{US}{US}{US}{US}72{US}false{US}off")
    state = playback.now_playing(runner=fake)
    assert state["player_state"] == "stopped"
    assert state["track"] is None
    assert state["volume"] == 72


def test_now_playing_parses_playing():
    fake = FakeRunner(f"playing{US}PID{US}Song{US}Artist{US}Album{US}185{US}30{US}true{US}all")
    state = playback.now_playing(runner=fake)
    assert state["track"]["name"] == "Song"
    assert state["shuffle"] is True
    assert state["repeat"] == "all"


def test_set_options_volume_bounds():
    with pytest.raises(ValueError):
        playback.set_options(volume=150, runner=FakeRunner())


def test_set_options_repeat_validated():
    with pytest.raises(ValueError):
        playback.set_options(repeat="twice", runner=FakeRunner())


def test_play_tracks_passes_ids_as_args():
    fake = FakeRunner(f"2{US}")
    playback.play_tracks(["A", "B"], runner=fake)
    script, args = fake.calls[0]
    assert args == ("Claude Queue", "A", "B")
```

- [ ] **Step 2: Run** `uv run pytest tests/test_playback.py -v` — Expected: FAIL

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/playback.py
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
    set US to character id 31
    tell application "Music"
        set st to (player state) as text
        set trackPart to US & US & US & US & US
        if st is "playing" or st is "paused" then
            try
                set t to current track
                set d to ""
                try
                    set d to ((duration of t) as integer) as text
                end try
                set trackPart to US & (persistent ID of t) & US & (name of t) & US & (artist of t) & US & (album of t) & US & d
            end try
        end if
        return st & trackPart & US & (sound volume) & US & (shuffle enabled) & US & ((song repeat) as text)
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
    set US to character id 31
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
        return (added as text) & US & missing
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
    track = None
    if parts[1]:
        try:
            duration = int(float(parts[5]))
        except (ValueError, TypeError):
            duration = None
        track = {"id": parts[1], "name": parts[2], "artist": parts[3],
                 "album": parts[4], "duration_seconds": duration}
    try:
        volume = int(float(parts[6]))
    except (ValueError, TypeError):
        volume = None
    return {
        "player_state": parts[0],
        "track": track,
        "volume": volume,
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
```

- [ ] **Step 4: Run** `uv run pytest tests/test_playback.py -v` — Expected: 7 passed
- [ ] **Step 5: Commit** `git commit -am "feat: playback control, now-playing, options, queue-playlist playback"`

---

### Task 5: Playlists module — full CRUD

**Files:**
- Create: `mcp_applemusic/playlists.py`
- Test: `tests/test_playlists.py`

**Interfaces:**
- Consumes: `run_script`, `parse_tracks`, `parse_playlists`, `US`.
- Produces: `list_playlists() -> list[dict]`; `get_tracks(playlist: str, limit: int = 200) -> list[dict]`; `create(name: str, track_ids: list[str]) -> dict`; `add_tracks(playlist: str, track_ids: list[str]) -> dict`; `remove_tracks(playlist: str, track_ids: list[str]) -> dict`; `rename(playlist: str, new_name: str) -> str`; `delete(playlist: str) -> str`. Batch ops return `{"added"/"removed": int, "missing": [ids], "playlist": name}`.
- Playlist resolution: try persistent ID first, fall back to exact name (same pattern as playback).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_playlists.py
import pytest
from mcp_applemusic import playlists
from mcp_applemusic.runner import US, RS


class FakeRunner:
    def __init__(self, output=""):
        self.output = output
        self.calls = []

    def __call__(self, script, *args):
        self.calls.append((script, args))
        return self.output


def test_list_playlists_parses():
    fake = FakeRunner(f"P1{US}Chill{US}10{US}false{RS}")
    result = playlists.list_playlists(runner=fake)
    assert result == [{"id": "P1", "name": "Chill", "track_count": 10, "smart": False}]


def test_create_reports_added_and_missing():
    fake = FakeRunner(f"NEWPID{US}2{US}BADID,")
    result = playlists.create("Workout", ["A", "B", "BADID"], runner=fake)
    assert result == {"id": "NEWPID", "name": "Workout", "added": 2, "missing": ["BADID"]}
    script, args = fake.calls[0]
    assert args == ("Workout", "A", "B", "BADID")
    assert "Workout" not in script


def test_create_empty_tracks_ok():
    fake = FakeRunner(f"NEWPID{US}0{US}")
    result = playlists.create("Empty", [], runner=fake)
    assert result["added"] == 0 and result["missing"] == []


def test_add_tracks_requires_ids():
    with pytest.raises(ValueError):
        playlists.add_tracks("P", [], runner=FakeRunner())


def test_remove_tracks_reports():
    fake = FakeRunner(f"1{US}NOPE,")
    result = playlists.remove_tracks("P", ["X", "NOPE"], runner=fake)
    assert result == {"playlist": "P", "removed": 1, "missing": ["NOPE"]}


def test_rename_passes_args():
    fake = FakeRunner("ok")
    playlists.rename("Old", "New", runner=fake)
    assert fake.calls[0][1] == ("Old", "New")
```

- [ ] **Step 2: Run** `uv run pytest tests/test_playlists.py -v` — Expected: FAIL

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/playlists.py
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
    set US to character id 31
    set RS to character id 30
    tell application "Music"
        set out to ""
        repeat with p in (every user playlist)
            set sm to "false"
            try
                if smart of p then set sm to "true"
            end try
            set out to out & (persistent ID of p) & US & (name of p) & US & (count of tracks of p) & US & sm & RS
        end repeat
        return out
    end tell
end run
'''

_GET_TRACKS_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set maxN to (item 2 of argv) as integer
    set US to character id 31
    set RS to character id 30
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
            set out to out & (persistent ID of t) & US & (name of t) & US & (artist of t) & US & (album of t) & US & d & RS
            set n to n + 1
        end repeat
    end tell
    return out
end run
'''

_CREATE_SCRIPT = '''
on run argv
    set plName to item 1 of argv
    set US to character id 31
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
        return (persistent ID of p) & US & (added as text) & US & missing
    end tell
end run
'''

_ADD_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set US to character id 31
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
    return (added as text) & US & missing
end run
'''

_REMOVE_SCRIPT = _RESOLVE + '''
on run argv
    set q to item 1 of argv
    set US to character id 31
    set p to my resolvePlaylist(q)
    set removed to 0
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
                set removed to removed + 1
            end if
        end repeat
    end tell
    return (removed as text) & US & missing
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
    batch = _parse_batch(rest, "added")
    return {"id": pid, "name": name, **batch}


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
```

- [ ] **Step 4: Run** `uv run pytest tests/test_playlists.py -v` — Expected: 6 passed
- [ ] **Step 5: Commit** `git commit -am "feat: playlist CRUD with found/missing reporting"`

---

### Task 6: MCP server — tool registration + error shaping

**Files:**
- Create: `mcp_applemusic/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main()` entry point; 14 `music_*` tools; `_safe(fn)` wrapper mapping `AppleScriptError` → `{"error", "hint"}` and `ValueError` → `{"error"}`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_server.py
from mcp_applemusic.runner import AppleScriptError
from mcp_applemusic.server import _safe


def test_safe_passes_through_success():
    assert _safe(lambda: {"x": 1}) == {"x": 1}


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
```

- [ ] **Step 2: Run** `uv run pytest tests/test_server.py -v` — Expected: FAIL

- [ ] **Step 3: Implement**

```python
# mcp_applemusic/server.py
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
    list of tracks (track_ids — builds and plays the 'Claude Queue' playlist).
    Provide exactly one of the three."""
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
    Returns tracks with persistent IDs — use those IDs for all other tools."""
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
    """Remove tracks (persistent IDs) from a playlist. Does not delete from library."""
    return _safe(lambda: playlists.remove_tracks(playlist, track_ids))


@mcp.tool()
def music_rename_playlist(playlist: str, new_name: str) -> dict | str:
    """Rename a playlist (identified by persistent ID or exact current name)."""
    return _safe(lambda: playlists.rename(playlist, new_name))


@mcp.tool()
def music_delete_playlist(playlist: str) -> dict | str:
    """Delete a playlist (by persistent ID or exact name). Tracks stay in library."""
    return _safe(lambda: playlists.delete(playlist))


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full suite** `uv run pytest -v` — Expected: all pass (~25 tests)
- [ ] **Step 5: Verify server boots** `timeout 5 uv run mcp-applemusic <<< '' ; echo "exit ok"` — Expected: starts without traceback
- [ ] **Step 6: Commit** `git commit -am "feat: 14-tool MCP surface replacing single-file server"`

---

### Task 7: Live smoke test against real Music.app

**Files:**
- Create: `scripts/live_smoke.py`

**Interfaces:** Consumes all modules directly (bypasses MCP transport).

- [ ] **Step 1: Write the smoke script**

```python
# scripts/live_smoke.py
"""End-to-end exercise against the real Music.app. Run: uv run python scripts/live_smoke.py
Creates and deletes a scratch playlist named 'MCP Smoke Test'. Non-destructive otherwise."""
import sys
sys.path.insert(0, ".")

from mcp_applemusic import library, playback, playlists

SCRATCH = "MCP Smoke Test"


def check(label, fn):
    try:
        result = fn()
        print(f"  OK  {label}: {str(result)[:120]}")
        return result
    except Exception as e:
        print(f" FAIL {label}: {e}")
        raise SystemExit(1)


print("== read-only ==")
state = check("now_playing", playback.now_playing)
tracks = check("search 'a' (songs, limit 3)", lambda: library.search("a", "songs", 3))
assert tracks, "search returned nothing"
tid = tracks[0]["id"]
check("track_info", lambda: library.track_info(tid))
pls = check("list_playlists", playlists.list_playlists)

print("== playlist lifecycle ==")
created = check("create with 2 tracks + 1 bogus id",
                lambda: playlists.create(SCRATCH, [tracks[0]["id"], tracks[1]["id"], "BOGUSID000"]))
assert created["added"] == 2 and created["missing"] == ["BOGUSID000"], created
check("get_tracks", lambda: playlists.get_tracks(created["id"]))
check("add third track", lambda: playlists.add_tracks(created["id"], [tracks[2]["id"]]))
check("remove one", lambda: playlists.remove_tracks(created["id"], [tracks[0]["id"]]))
check("rename", lambda: playlists.rename(created["id"], SCRATCH + " Renamed"))
check("delete", lambda: playlists.delete(created["id"]))

print("== options round-trip ==")
orig_volume = state["volume"]
check("set volume", lambda: playback.set_options(volume=orig_volume))
print("\nAll smoke checks passed.")
```

- [ ] **Step 2: Run it** `cd ~/mcp-applemusic && uv run python scripts/live_smoke.py` — Expected: `All smoke checks passed.` Verify in Music.app that no scratch playlist remains.
- [ ] **Step 3: Commit** `git commit -am "test: live smoke script against real Music.app"`

---

### Task 8: Docs, project standards, MCP registration

**Files:**
- Modify: `README.md` (rewrite)
- Create: `CHANGELOG.md`, `PRIMER.md`, `.claude/agents/applescript-agent.md`, `.claude/agents/api-agent.md`

**Steps:**
- [ ] README: what it is (fork lineage + credit to kennethreitz), 14-tool table, install via `claude mcp add applemusic -- uvx --from git+https://github.com/NodeSaint/mcp-applemusic mcp-applemusic` plus Claude Desktop JSON snippet, Sync Library requirement, automation-permission first-run note, iPhone sync explanation, Phase 2 (API) roadmap.
- [ ] CHANGELOG.md: 0.2.0 entry (restructure, injection fix, persistent IDs, 14 tools).
- [ ] PRIMER.md: current state, spec/plan paths, what Phase 2 needs (dev account → MusicKit key → setup flow).
- [ ] Agent files: `applescript-agent.md` (owns `mcp_applemusic/{runner,playback,playlists,library}.py` — conventions: argv-only, US/RS, persistent IDs), `api-agent.md` (owns future `api/` — stub with Phase 2 pointers).
- [ ] Commit: `git commit -am "docs: README rewrite, changelog, primer, specialist agents"`
- [ ] Push `dev`: `git push -u origin dev`

---

## Critique log (pre-execution review — all fixes applied above)

**Bugs caught and fixed:**
1. Root `mcp_applemusic.py` module vs `mcp_applemusic/` package name collision across Tasks 1-5 → old file now deleted in Task 1.
2. `remove_tracks` counted not-in-playlist tracks as removed (deleting an empty `whose` specifier doesn't error) → now counts matches before deleting.
3. Queue-playlist try/create pattern could create a duplicate "Claude Queue" if the clear step errored → now uses `exists user playlist`.
4. `subprocess.TimeoutExpired` escaped the runner uncaught → now mapped to `AppleScriptError` with hint.

**Deliberate spec deviations (recorded, not accidents):**
- `reorder_playlist` cut: AppleScript `move` in modern Music.app unverified; lowest-value op. Revisit on demand.
- `recently_added` / `recently_played` cut: AppleScript can't sort; correct implementation needs vectorized date fetch + Python-side sort. Phase 2 backlog.
- Per-track property reads (O(n) Apple events) accepted for a 2,804-track library with `limit` caps; smoke test measures timings — vectorize `get {props} of every track` ONLY if measured slow.
- No PyPI publish (upstream owns the name); distribute via `uvx --from git+https://github.com/NodeSaint/mcp-applemusic`.

---

## Phase 2 (deferred — separate plan when dev account exists)

Apple Music Web API layer per spec §Auth: `api/auth.py` (ES256 dev JWT + Music User Token), `api/client.py`, catalog search, add-to-library, API playlist create/add, dual routing in `server.py`, `setup_flow/` localhost MusicKit JS token capture. **Do not build any of it in Phase 1.**
