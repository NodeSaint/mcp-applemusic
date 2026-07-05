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
    assert "evil" not in cmd[2]


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
    with patch(
        "mcp_applemusic.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=120),
    ):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert "timed out" in str(ei.value).lower()


def test_error_without_known_code_has_no_hint():
    err = _completed(1, stderr="execution error: something odd (-999)")
    with patch("mcp_applemusic.runner.subprocess.run", return_value=err):
        with pytest.raises(AppleScriptError) as ei:
            run_script("s")
    assert ei.value.hint is None
