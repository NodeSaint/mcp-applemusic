"""Sole osascript gateway. User values travel via argv — never into script source."""
import subprocess

US = "\x1f"  # unit separator: between fields of a record
RS = "\x1e"  # record separator: between records

# Absolute path to the system binary — avoids any PATH-lookup / shim surface.
_OSASCRIPT = "/usr/bin/osascript"

# Shared AppleScript handler: strips the US/RS delimiter control characters out
# of a text value before it is emitted. Without this, a track whose title
# literally contained a US/RS char (metadata is influenceable by whoever
# publishes a track) could inject extra fields or a phantom record into the
# parsed output. Prepend to an emitting script and wrap free-text fields as
# `my san(name of t)`.
SANITIZE_HANDLER = '''
on san(v)
    set v to v as text
    repeat with sep in {character id 31, character id 30}
        set AppleScript's text item delimiters to sep
        set parts to text items of v
        set AppleScript's text item delimiters to " "
        set v to parts as text
    end repeat
    set AppleScript's text item delimiters to ""
    return v
end san
'''

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
    # The "--" terminator forces osascript to treat every following value as a
    # positional argv item. Without it, any user value beginning with "-"
    # (e.g. "-e <script>") is parsed as an osascript option — an injection
    # vector that can smuggle a second script and reach `do shell script`.
    cmd = [_OSASCRIPT, "-e", script, "--", *[str(a) for a in args]]
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
