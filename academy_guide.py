import asyncio
import os
import sys
import time
import cv2

# Windows consoles often default to a non-UTF-8 codepage (e.g. cp1252), which
# can't encode the emoji used in status prints below and would crash the
# script the moment one of those lines runs.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import edge_tts
import serial
from google import genai
from google.genai import types
import pygame
import speech_recognition as sr

# Initialize the audio mixer, voice recognizer, and face detector
pygame.mixer.init()
recognizer = sr.Recognizer()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Read from the GEMINI_API_KEY environment variable (see .env.example)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEMINI_MODEL = "gemini-3.6-flash"

# Minimum detected face width (in pixels) before we consider a visitor "close enough" to greet
FACE_PROXIMITY_THRESHOLD = 130
# Pause after a session ends so the same visitor doesn't immediately re-trigger a new one
COOLDOWN_AFTER_SESSION = 5

# Male Hebrew neural voice, slowed slightly with a touch of lowered pitch for a more "robotic" cadence
ROBOT_VOICE = "he-IL-AvriNeural"
ROBOT_VOICE_RATE = "-8%"
ROBOT_VOICE_PITCH = "-10Hz"

# Must match the baud rate the robot's own serial listener (robot_listener.py,
# deployed on the Tonybot's onboard controller) is initialized with. Override
# with the ROBOT_COM_PORT environment variable if the robot enumerates on a
# different port than the default below.
ROBOT_COM_PORT = os.environ.get("ROBOT_COM_PORT", "COM3")
ROBOT_BAUD_RATE = 9600

# Whitelisted gesture commands -- must match the COMMANDS dict in robot_listener.py.
# Plain newline-terminated ASCII text; the robot maps these names to verified
# action-group IDs, so nothing here ever encodes a servo ID or angle.
GESTURE_COMMANDS = {"WAVE", "BOW", "STAND", "LEFT_KICK", "RIGHT_KICK", "SPREAD_HANDS"}

try:
    robot_serial = serial.Serial(ROBOT_COM_PORT, ROBOT_BAUD_RATE, timeout=1)
    print(f"✅ Connected to robot on {ROBOT_COM_PORT}")
except Exception as e:
    print(f"⚠️ Could not connect to the robot ({e}). Gestures will be skipped.")
    robot_serial = None

# Short knowledge-base prototype for menu testing, sourced from mta.ac.il.
# Each entry lists the spoken triggers Google's Hebrew STT tends to produce
# for that number (it often transcribes spoken numbers as words, not digits).
MENU_OPTIONS = [
    {
        "triggers": ["1", "אחד", "אחת"],
        "answer": (
            "במכללה האקדמית תל אביב יפו אפשר ללמוד מדעי המחשב, מערכות מידע, פסיכולוגיה, "
            "כלכלה וניהול, מדעי הסיעוד, וממשל וחברה, לתואר ראשון ושני."
        ),
    },
    {
        "triggers": ["2", "שתיים", "שתים"],
        "answer": (
            "שכר הלימוד במכללה האקדמית תל אביב יפו נקבע על ידי המועצה להשכלה גבוהה, "
            "וזהה לשכר הלימוד באוניברסיטאות."
        ),
    },
    {
        "triggers": ["3", "שלוש", "שלושה"],
        "answer": (
            "המכללה מציעה ארבעה סוגי מלגות: למצטיינים, לבעלי נתוני קבלה גבוהים, "
            "מלגות סיוע כלכלי, ומלגות לעידוד מעורבות חברתית."
        ),
    },
]
MENU_PROMPT = (
    "אמרו אחד עבור מסלולי לימוד, שתיים עבור שכר לימוד, או שלושה עבור מלגות. "
    "אפשר גם לשאול אותי כל שאלה אחרת."
)


# Gestures the robot has no persistent onboard listener for (see
# robot_listener.py's docstring) -- the only verified way to trigger these on
# demand is WonderCode's own Connect -> Python Coding -> Upload flow.
WONDERCODE_GESTURES = {
    "WAVE": "trigger_wave_via_wondercode",
    "BOW": "trigger_bow_via_wondercode",
}


def send_gesture(name):
    """Sends a whitelisted gesture command to the robot. No-op if not connected."""
    if name not in GESTURE_COMMANDS:
        raise ValueError(f"Unknown gesture command: {name}")

    if name in WONDERCODE_GESTURES:
        # WonderCode needs exclusive access to the port, so release the
        # direct connection first and reopen it afterward.
        global robot_serial
        if robot_serial is not None:
            robot_serial.close()
        try:
            import wave_via_wondercode
            trigger = getattr(wave_via_wondercode, WONDERCODE_GESTURES[name])
            trigger()
        except Exception as e:
            print(f"⚠️ Failed to trigger {name} via WonderCode: {e}")
        finally:
            try:
                robot_serial = serial.Serial(ROBOT_COM_PORT, ROBOT_BAUD_RATE, timeout=1)
            except Exception as e:
                print(f"⚠️ Could not reconnect to the robot ({e}).")
                robot_serial = None
        return



def wait_for_visitor(cap):
    """Blocks until a face large/close enough is seen on camera. Returns False if ESC was pressed."""
    print("\n📷 Watching for visitors... (press ESC on the camera window to shut down)")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        cv2.imshow("VisitorGuideBot Vision", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            return False

        if any(w > FACE_PROXIMITY_THRESHOLD for (_, _, w, _) in faces):
            return True

def listen_to_student():
    with sr.Microphone() as source:
        print("\n🎤 Listening... Speak your question now!")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("🧠 Processing your voice...")
            text = recognizer.recognize_google(audio, language="he-IL")
            print(f"You said: {text}")
            return text
        except sr.WaitTimeoutError:
            print("...Silence detected.")
            return None
        except sr.UnknownValueError:
            print("...Could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"...Voice service error: {e}")
            return None

def speak(text):
    try:
        filename = "temp_response.mp3"
        communicate = edge_tts.Communicate(text, voice=ROBOT_VOICE, rate=ROBOT_VOICE_RATE, pitch=ROBOT_VOICE_PITCH)
        asyncio.run(communicate.save(filename))

        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.music.unload()
    except Exception as e:
        print(f"\n[Audio Output Error: {e}]")

def ask_the_guide(user_question):
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_question,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "אתה המדריך הרובוטי הרשמי של יום הפתוח במכללה האקדמית תל אביב יפו. "
                    "אתה עוזר, חביב, ובעל ידע על הקמפוס ועל מסלולי הלימוד, ובמיוחד מערכות מידע. "
                    "ענה אך ורק בעברית. שמור על תשובות קצרות, ממוקדות ושיחתיות, "
                    "מכיוון שהן יישמעו בקול על ידי רובוט."
                )
            )
        )
        return response.text
    except Exception as e:
        return f"System Error: {e}"

def run_conversation_session():
    """Runs one voice Q&A session: waves and greets right away, then listens until an exit phrase."""
    print("👋 Visitor detected -- waving and greeting.")
    send_gesture("WAVE")

    greeting = (
        f"שלום! אני המדריך הדיגיטלי של המכללה האקדמית תל אביב יפו. {MENU_PROMPT}"
    )
    print(f"Tonybot Guide: {greeting}")
    speak(greeting)

    while True:
        question = listen_to_student()

        if question:
            # Clean up the spoken text to make matching reliable
            clean_question = question.lower().strip()

            # Check if the user is ending the session
            if "תודה בוט" in clean_question or clean_question in ['תודה', 'צא', 'exit', 'stop']:
                closing_phrase = "בשמחה! שיהיה לכם יום פתוח נעים במכללה. להתראות!"
                print(f"Tonybot Guide: {closing_phrase}")
                speak(closing_phrase)
                print("👋 Bowing to close the conversation.")
                send_gesture("BOW")
                print("Session ended.")
                return

            # Menu shortcut: numbered options answered directly from the knowledge base
            menu_match = next(
                (opt["answer"] for opt in MENU_OPTIONS if any(t in clean_question for t in opt["triggers"])),
                None,
            )
            answer = menu_match if menu_match else ask_the_guide(question)

            print(f"Tonybot Guide: {answer}")
            speak(answer)

if __name__ == "__main__":
    print("🤖 Face-Triggered Voice Guide is online!")
    print("Say 'תודה ' or 'exit' to end a session. Press ESC on the camera window to shut down.")

    cap = None
    for index in (1, 0):   # 1 = external BRIO, 0 = built-in fallback
        candidate = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if candidate.isOpened() and candidate.read()[0]:
            print(f"📷 Using camera index {index}")
            cap = candidate
            break
        candidate.release()

    if cap is None:
        print("❌ Could not open the camera. Check that it's connected and not in use by another app.")
    else:
        try:
            while True:
                visitor_present = wait_for_visitor(cap)
                if not visitor_present:
                    break

                run_conversation_session()
                print(f"⏳ Cooling down for {COOLDOWN_AFTER_SESSION}s before watching for the next visitor...")
                time.sleep(COOLDOWN_AFTER_SESSION)
        finally:
            cap.release()
            cv2.destroyAllWindows()
