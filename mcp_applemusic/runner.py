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
