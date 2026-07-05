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
    assert "crazy" not in script
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


def test_track_info_parses_full_record():
    fields = ["PID", "Name", "Artist", "Album", "185", "Electronic", "2019",
              "42", "80", "true", "false", "subscription"]
    fake = FakeRunner(US.join(fields))
    info = library.track_info("PID", runner=fake)
    assert info["rating_stars"] == 4.0
    assert info["favorited"] is True
    assert info["cloud_status"] == "subscription"
    assert info["year"] == 2019
