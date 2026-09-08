# VisitorGuideBot

An autonomous, Hebrew-speaking open-day visitor guide built on the [Hiwonder TonyBot](https://wiki.hiwonder.com/projects/Tonybot/en/latest/docs/1.getting_ready.html) humanoid robot, for the Tel Aviv-Yafo Academic College.

The robot watches a camera for an approaching visitor, waves and greets them out loud, answers their questions (from a small menu or Google Gemini), and bows when the conversation ends.

## How it works

1. **Face detection** — a webcam feed is scanned for a face; once it's close enough to the camera, a visitor is considered "detected."
2. **Wave + greeting** — the robot waves and immediately speaks a Hebrew greeting. No wake word needed.
3. **Conversation** — the visitor's speech is transcribed, matched against a small menu of common questions (study programs / tuition / scholarships) or answered by Gemini for anything else, then spoken back.
4. **Closing** — saying **"תודה"**, **"exit"**, or **"stop"** ends the session: the robot speaks a closing phrase and **bows**.
5. The script then goes back to watching for the next visitor.

### Why gestures go through WonderCode

TonyBot has no persistent onboard program listening for commands — it only runs code when Hiwonder's **WonderCode** app uploads it. So every gesture (wave, bow) is triggered by an automation ([`wave_via_wondercode.py`](wave_via_wondercode.py)) that:

1. Releases the main script's own connection to the robot (WonderCode needs exclusive access to the port).
2. Launches WonderCode, connects to the robot, types a one-line action-group command into its Python editor, and clicks Upload.
3. Closes WonderCode and hands the connection back.

This takes about **24 seconds per gesture** — expect a short pause after a face is detected (before the wave) and after saying "תודה" (before the bow).

## Requirements

- **Hardware:** TonyBot robot (powered on, connected via USB), a webcam, a microphone, a speaker.
- **Software:** Python 3.12, [WonderCode](https://wiki.hiwonder.com/projects/Tonybot/en/latest/docs/5.scratch_programming_projects.html) installed at `C:\wondercode\wondercode.exe`, a [Gemini API key](https://aistudio.google.com/apikey).

## Setup

1. Install dependencies:
   ```bash
   python setup.py
   ```
   `wave_via_wondercode.py` additionally needs:
   ```bash
   pip install pyautogui pygetwindow
   ```
2. Set your Gemini API key as an environment variable. The script reads it from the environment — it does **not** read `.env`:
   ```powershell
   $env:GEMINI_API_KEY = "your_key_here"
   ```
3. Connect the robot via USB and power it on. The script defaults to `COM3` — if it enumerates elsewhere, set:
   ```powershell
   $env:ROBOT_COM_PORT = "COM5"
   ```

## Running

```bash
python academy_guide.py
```

- The camera is chosen automatically: index 1 (external USB webcam) if present, otherwise index 0 (built-in).
- A camera preview window opens — stand in front of it to trigger a session.
- Say **"תודה"**, **"exit"**, or **"stop"** to end a session.
- Press **ESC** on the camera window to shut the whole program down.
- **Don't touch the mouse/keyboard while a wave or bow is running** — the WonderCode automation clicks on fixed screen positions, so anything that steals focus or moves the WonderCode window can make it miss.
- Close WonderCode before starting — it holds the robot's COM port.

## Files

| File | Purpose |
|---|---|
| [`academy_guide.py`](academy_guide.py) | Main program — camera, speech, Gemini Q&A, and gesture orchestration. |
| [`wave_via_wondercode.py`](wave_via_wondercode.py) | Drives WonderCode to run a wave or bow on the physical robot. |
| [`setup.py`](setup.py) | Dependency installer. |

## Notes

- Never commit a real API key — `.env` and `api-gemini.txt` are git-ignored; use `.env.example` as the template.
- `wave_via_wondercode.py`'s click coordinates are tuned for WonderCode's default launch window on a 1456x816-reference display. If WonderCode's layout ever changes (new version, resized window), those coordinates will need to be re-captured.
