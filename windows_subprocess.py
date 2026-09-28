"""Keep the Claude CLI from popping a console window on Windows.

When the bot runs windowless (pythonw, e.g. started at logon), every Claude
turn would otherwise flash a console window, and closing it kills the turn.
CREATE_NO_WINDOW stops the console being allocated. Call once, before
importing claude_agent_sdk. No-op off Windows.
"""
import sys

import anyio

_CREATE_NO_WINDOW = 0x08000000
_patched = False


def patch_for_no_window() -> None:
    global _patched
    if _patched or sys.platform != "win32":
        return
    _orig_open_process = anyio.open_process

    async def _open_process_hidden(*args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | _CREATE_NO_WINDOW
        return await _orig_open_process(*args, **kwargs)

    anyio.open_process = _open_process_hidden
    _patched = True
