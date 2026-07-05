"""End-to-end exercise against the real Music.app.

Run: uv run python scripts/live_smoke.py
Creates and deletes a scratch playlist named 'MCP Smoke Test'. Non-destructive otherwise.
"""
import time

from mcp_applemusic import library, playback, playlists

SCRATCH = "MCP Smoke Test"


def check(label, fn):
    start = time.perf_counter()
    try:
        result = fn()
        ms = (time.perf_counter() - start) * 1000
        print(f"  OK  {label} [{ms:.0f}ms]: {str(result)[:110]}")
        return result
    except Exception as e:
        print(f" FAIL {label}: {e}")
        raise SystemExit(1)


print("== read-only ==")
state = check("now_playing", playback.now_playing)
tracks = check("search 'a' (songs, limit 3)", lambda: library.search("a", "songs", 3))
assert len(tracks) >= 3, f"search returned {len(tracks)} tracks"
tid = tracks[0]["id"]
check("track_info", lambda: library.track_info(tid))
check("list_playlists", playlists.list_playlists)

print("== playlist lifecycle ==")
created = check(
    "create with 2 tracks + 1 bogus id",
    lambda: playlists.create(SCRATCH, [tracks[0]["id"], tracks[1]["id"], "BOGUSID000"]),
)
assert created["added"] == 2 and created["missing"] == ["BOGUSID000"], created
got = check("get_tracks", lambda: playlists.get_tracks(created["id"]))
assert len(got) == 2, got
check("add third track", lambda: playlists.add_tracks(created["id"], [tracks[2]["id"]]))
removed = check("remove one + report bogus", lambda: playlists.remove_tracks(created["id"], [tracks[0]["id"], "BOGUSID000"]))
assert removed["removed"] == 1 and removed["missing"] == ["BOGUSID000"], removed
check("rename", lambda: playlists.rename(created["id"], SCRATCH + " Renamed"))
check("delete", lambda: playlists.delete(created["id"]))
leftover = [p for p in playlists.list_playlists() if p["name"].startswith(SCRATCH)]
assert not leftover, f"scratch playlist left behind: {leftover}"

print("== options round-trip ==")
if state["volume"] is not None:
    check("set volume (restore current)", lambda: playback.set_options(volume=state["volume"]))
check("set shuffle (restore current)", lambda: playback.set_options(shuffle=state["shuffle"]))

print("\nAll smoke checks passed.")
