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


def test_remove_script_counts_matches_before_delete():
    # critique fix #2: deleting an empty specifier must not count as removed
    fake = FakeRunner(f"0{US}")
    playlists.remove_tracks("P", ["X"], runner=fake)
    script, _ = fake.calls[0]
    assert "count of matches" in script


def test_rename_passes_args():
    fake = FakeRunner("ok")
    playlists.rename("Old", "New", runner=fake)
    assert fake.calls[0][1] == ("Old", "New")
