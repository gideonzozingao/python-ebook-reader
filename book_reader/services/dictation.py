"""Voice dictation for notes. Needs the optional packages:  pip install SpeechRecognition pyaudio
(the default engine sends the recording to Google's free web speech service, so it needs
an internet connection)."""
from importlib.util import find_spec


class DictationError(Exception):
    """A problem the user can act on (shown as-is)."""


def available() -> bool:
    return find_spec("speech_recognition") is not None


INSTALL_HINT = ("Dictation needs two extra packages:\n\n    pip install SpeechRecognition pyaudio\n\n"
                "On Windows you can also press Win + H in any text box to use the built-in dictation.")


def listen_once(language: str = "en-US", timeout: float = 8.0, limit: float = 45.0) -> str:
    """Record from the default microphone until you stop talking and return the text."""
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise DictationError(INSTALL_HINT) from exc
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=limit)
    except sr.WaitTimeoutError as exc:
        raise DictationError("I didn't hear anything. Try again closer to the microphone.") from exc
    except (OSError, AttributeError) as exc:
        raise DictationError("No microphone could be opened (is PyAudio installed and a "
                             "microphone connected?).") from exc
    try:
        return recognizer.recognize_google(audio, language=language).strip()
    except sr.UnknownValueError as exc:
        raise DictationError("I couldn't understand that. Please try again.") from exc
    except sr.RequestError as exc:
        raise DictationError("The speech service could not be reached (are you offline?).") from exc
