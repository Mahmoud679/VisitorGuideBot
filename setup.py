import subprocess
import sys

# רשימת כל הספריות שהפרויקט שלכם צריך
packages = [
    "google-genai",
    "opencv-python",
    "gTTS",
    "edge-tts",
    "pygame",
    "SpeechRecognition",
    "PyAudio",
    "flask",
    "requests",
    "pyserial"
]

print("🚀 מתחיל בהתקנת הספריות אוטומטית... אנא המתן.")

for package in packages:
    print(f"מתקין את {package}...")
    try:
        # פייתון מפעיל את כלי ההתקנה הפנימי שלו בעצמו
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])
        print(f"✅ {package} הותקן בהצלחה!\n")
    except Exception as e:
        print(f"❌ שגיאה בהתקנת {package}: {e}\n")
        
print("🎉 ההתקנה הסתיימה לחלוטין! אפשר לסגור את הקובץ הזה ולעבור לקוד השרת.")