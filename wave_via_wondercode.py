"""
Triggers a robot action group by driving the WonderCode GUI end-to-end:
kill any stale WonderCode instance -> launch fresh -> connect to the robot's
serial port -> type a small Python snippet in WonderCode's "Python Coding"
tab (tonybot.runActionGroup(<id>, 1)) -> Upload (runs it on the board) ->
close WonderCode.

This exists because the robot has no persistent onboard listener: Tonybot
only runs custom code when the Hiwonder Python Editor / WonderCode uploads
it, so there is no way to trigger an action from a plain serial write the
way tonybot_actions.py / robot_listener.py assumed. WonderCode's own
"Connect -> Python Coding -> Upload" flow is the documented, actually-working
mechanism for running an action group on demand from a PC (see the TonyBot
wiki's PC Software Action Control Course and Python Programming Projects
pages). This exact sequence was verified live against the physical robot.

It is slow (~24s per action) and the robot's serial port must be free --
nothing else (e.g. academy_guide.py's robot_serial) may hold it open while
this runs, since WonderCode needs exclusive access to connect.

Coordinates below are tuned for a WonderCode window opened at its default
launch size/position on a 1456x816-reference display and scaled to this
machine's real resolution below. If WonderCode's layout changes (a new
version, a moved/resized window), re-capture coordinates with a screenshot.
"""

import subprocess
import time
import pyautogui
import pygetwindow as gw

WONDERCODE_EXE = r"C:\wondercode\wondercode.exe"

# Verified action-group IDs (see tonybot_actions.py for the full, cross-checked list).
ACTION_GROUP_WAVE = 9
ACTION_GROUP_BOW = 10

# Coordinates below were captured from a 1456x816 screenshot, but pyautogui
# operates in real physical pixels. Scale every captured coordinate up by
# that ratio before clicking, or every click lands in the wrong place.
_CAPTURE_W, _CAPTURE_H = 1456, 816
_REAL_W, _REAL_H = pyautogui.size()
_SCALE_X = _REAL_W / _CAPTURE_W
_SCALE_Y = _REAL_H / _CAPTURE_H


def _scaled(x, y):
    return (round(x * _SCALE_X), round(y * _SCALE_Y))


# Coordinates captured on WonderCode's default launch window/layout
# (1456x816 reference), scaled to this machine's real resolution at import time.
CONNECT_DEVICE_MENU = _scaled(570, 56)
# The connect-device dropdown always shows a single entry -- whichever COM
# port the robot enumerates on -- at this position, so this click is
# port-name-agnostic (no need to hardcode "COM4"/"COM5" text).
PORT_OPTION = _scaled(569, 95)
PYTHON_CODING_TAB = _scaled(1104, 108)
CODE_EDITOR_FIRST_LINE = _scaled(1089, 141)
UPLOAD_BUTTON = _scaled(1334, 109)


def _activate_wondercode():
    # Windows can refuse to foreground a window opened by a background-spawned
    # process, even though it's visible on top -- clicks then land on whatever
    # window actually holds focus. Force it forward before every interaction.
    windows = gw.getWindowsWithTitle("WonderCode")
    if windows:
        win = windows[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
        except Exception:
            pass
    time.sleep(0.3)


def _kill_existing_wondercode():
    # A previous connection can leave a stale port handle inside one of
    # WonderCode's processes, making the next "Connect" silently fail
    # ("Connect failed") even though the port is free at the OS level.
    # Force-closing every instance guarantees a clean state.
    subprocess.run(
        ["taskkill", "/IM", "wondercode.exe", "/F"],
        capture_output=True,
    )
    time.sleep(0.5)


def trigger_action_via_wondercode(action_group_id, wait_ms=3000):
    """Runs a single verified action group on the robot via WonderCode's Python editor."""
    action_code = (
        "\n"
        "tonybot = Hiwonder.Tonybot()\n"
        f"tonybot.runActionGroup({action_group_id}, 1)\n"
        f"tonybot.waitForStop({wait_ms})"
    )

    _kill_existing_wondercode()
    subprocess.Popen([WONDERCODE_EXE])
    try:
        # The "Creating Project" splash screen alone can take ~10s.
        time.sleep(9)
        _activate_wondercode()

        # Connect to the robot over its serial port.
        pyautogui.click(*CONNECT_DEVICE_MENU)
        time.sleep(1)
        pyautogui.click(*PORT_OPTION)
        time.sleep(3)

        # Switch to the Python editor and append the action after the
        # pre-filled "import Hiwonder" line.
        _activate_wondercode()
        pyautogui.click(*PYTHON_CODING_TAB)
        time.sleep(0.5)
        pyautogui.click(*CODE_EDITOR_FIRST_LINE)
        pyautogui.press("end")
        pyautogui.write(action_code, interval=0.02)
        time.sleep(0.5)

        # Upload + run the program (board resets, then runs the action group).
        # This wait covers file transfer + reboot + the action's own
        # waitForStop(wait_ms) executing on the board -- do not trim it below
        # roughly wait_ms + 8s or WonderCode may get force-closed while the
        # gesture is still physically running.
        pyautogui.click(*UPLOAD_BUTTON)
        time.sleep(11)
    finally:
        _kill_existing_wondercode()
        time.sleep(0.5)


def trigger_wave_via_wondercode():
    trigger_action_via_wondercode(ACTION_GROUP_WAVE)


def trigger_bow_via_wondercode():
    trigger_action_via_wondercode(ACTION_GROUP_BOW)


if __name__ == "__main__":
    trigger_wave_via_wondercode()
