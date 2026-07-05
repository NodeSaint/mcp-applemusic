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


def test_play_tracks_reports_missing():
    fake = FakeRunner(f"1{US}BAD,")
    result = playback.play_tracks(["A", "BAD"], runner=fake)
    assert result == {"queued": 1, "missing": ["BAD"], "playlist": "Claude Queue"}


def test_play_tracks_rejects_empty():
    with pytest.raises(ValueError):
        playback.play_tracks([], runner=FakeRunner())
