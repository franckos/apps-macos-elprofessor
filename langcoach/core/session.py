"""
LangCoach — Session Manager
Orchestre le pipeline STT → LLM → TTS
"""

import logging
import threading
from enum import Enum, auto
from typing import Callable, Optional

from core.stt import STTEngine, AudioRecorder
from core.llm import LLMEngine
from core.tts import TTSEngine
from core.prompt_builder import build_system_prompt
from config.settings import MODELS, AUDIO, REACHY

logger = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = auto()
    LOADING = auto()
    READY = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


class SessionManager:
    """
    Gère le cycle de vie complet d'une session de conversation.
    Thread-safe, callbacks pour la UI.
    """

    def __init__(self):
        self.settings = {}
        self._state = SessionState.IDLE
        self._stt: Optional[STTEngine] = None
        self._llm: Optional[LLMEngine] = None
        self._tts: Optional[TTSEngine] = None
        self._recorder: Optional[AudioRecorder] = None
        self._reachy = None

        # Callbacks UI
        self.on_state_change: Optional[Callable[[SessionState], None]] = None
        self.on_user_transcript: Optional[Callable[[str], None]] = None
        self.on_assistant_token: Optional[Callable[[str], None]] = None
        self.on_assistant_done: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_models_ready: Optional[Callable[[dict], None]] = None

        self._ptt_active = False

    def initialize(self, settings: dict):
        """Lance l'initialisation des modèles en arrière-plan"""
        self.settings = settings
        self._set_state(SessionState.LOADING)

        t = threading.Thread(target=self._init_models, daemon=True)
        t.start()

    def _init_models(self):
        """Initialise STT, LLM, TTS"""
        status = {"stt": False, "llm": False, "tts": False}

        try:
            # STT
            self._stt = STTEngine(settings=self.settings, on_transcript=self._on_audio_transcribed)
            status["stt"] = self._stt.initialize()

            # LLM
            self._llm = LLMEngine(config=MODELS["llm"])
            self._llm.set_system_prompt(build_system_prompt(self.settings))
            status["llm"] = True  # Ollama est vérifiable au premier appel

            # TTS
            self._tts = TTSEngine(config=MODELS["tts"])
            status["tts"] = self._tts.initialize()

            # Recorder audio
            self._recorder = AudioRecorder(
                config=AUDIO,
                on_audio_ready=self._on_audio_captured,
            )

            # Reachy bridge
            from reachy.bridge import ReachyBridge
            self._reachy = ReachyBridge(config=REACHY)
            self._reachy.on_connected = lambda: logger.info("Reachy connected")
            self._reachy.start()

            # Démarre la session avec le greeting de l'IA
            self._set_state(SessionState.READY)
            if self.on_models_ready:
                self.on_models_ready(status)

            # Greeting automatique
            self._get_ai_response("", is_greeting=True)

        except Exception as e:
            logger.error(f"Init error: {e}")
            self._set_state(SessionState.ERROR)
            if self.on_error:
                self.on_error(str(e))

    def start_listening_vad(self):
        """Active le mode VAD"""
        if self._state not in (SessionState.READY, SessionState.IDLE):
            return
        if self._recorder and self._stt:
            self._recorder.start_vad(self._stt)
            self._set_state(SessionState.LISTENING)

    def stop_listening_vad(self):
        if self._recorder:
            self._recorder.stop_vad()
        if self._state == SessionState.LISTENING:
            self._set_state(SessionState.READY)

    def start_ptt(self):
        """Push-to-talk : début"""
        if self._state not in (SessionState.READY, SessionState.LISTENING):
            return
        self._ptt_active = True
        if self._recorder:
            self._recorder.start_recording()
        self._set_state(SessionState.LISTENING)

    def stop_ptt(self):
        """Push-to-talk : fin"""
        self._ptt_active = False
        if self._recorder:
            self._recorder.stop_recording()

    def send_text(self, text: str):
        """Envoie un message texte direct (sans audio)"""
        if not text.strip():
            return
        if self.on_user_transcript:
            self.on_user_transcript(text)
        self._get_ai_response(text)

    def _on_audio_captured(self, audio_array, sample_rate: int):
        """Callback quand de l'audio est capturé"""
        if not self._stt:
            return

        def transcribe():
            transcript = self._stt.transcribe_array(audio_array, sample_rate)
            if transcript:
                self._on_audio_transcribed(transcript)

        threading.Thread(target=transcribe, daemon=True).start()

    def _on_audio_transcribed(self, text: str):
        """Callback quand le texte est transcrit"""
        if not text.strip():
            return

        if self.on_user_transcript:
            self.on_user_transcript(text)

        if self._reachy:
            self._reachy.send_transcript(text, role="user")

        self._get_ai_response(text)

    def _get_ai_response(self, user_text: str, is_greeting: bool = False):
        """Appelle le LLM et joue la réponse TTS"""
        self._set_state(SessionState.PROCESSING)

        full_response = []

        def on_token(token: str):
            full_response.append(token)
            if self.on_assistant_token:
                self.on_assistant_token(token)

        def on_done(text: str):
            if self.on_assistant_done:
                self.on_assistant_done(text)
            if self._reachy:
                self._reachy.send_transcript(text, role="assistant")
            self._speak(text)

        if is_greeting:
            prompt = "[Start the session with your opening greeting]"
        else:
            prompt = user_text

        self._llm.chat_async(prompt, on_token=on_token, on_done=on_done)
        self._llm.trim_history(keep_last=30)

    def _speak(self, text: str):
        """Lance la synthèse vocale"""
        if not self._tts:
            self._set_state(SessionState.READY)
            return

        self._set_state(SessionState.SPEAKING)
        if self._reachy:
            self._reachy.send_speaking(True)

        def on_done():
            self._set_state(SessionState.READY)
            if self._reachy:
                self._reachy.send_speaking(False)

        self._tts.speak(text, on_done=on_done)

    def stop_speaking(self):
        if self._tts:
            self._tts.stop()
        self._set_state(SessionState.READY)

    def reset_session(self):
        """Repart de zéro dans la même session"""
        if self._llm:
            self._llm.reset_conversation()
        if self._tts:
            self._tts.stop()
        self._set_state(SessionState.READY)
        self._get_ai_response("", is_greeting=True)

    def update_settings(self, new_settings: dict):
        """Met à jour les paramètres et reconstruit le prompt"""
        self.settings = new_settings
        if self._llm:
            self._llm.set_system_prompt(build_system_prompt(new_settings))

    def shutdown(self):
        """Nettoyage propre"""
        try:
            if self._recorder:
                self._recorder.stop_vad()
            if self._tts:
                self._tts.stop()
            if self._reachy:
                self._reachy.send_session_stop()
                self._reachy.stop()
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

    def _set_state(self, state: SessionState):
        self._state = state
        if self.on_state_change:
            self.on_state_change(state)

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def tts_provider(self) -> str:
        return self._tts.provider if self._tts else "none"
