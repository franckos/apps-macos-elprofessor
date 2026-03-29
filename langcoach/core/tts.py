"""
LangCoach — Text-to-Speech
Voxtral TTS (via transformers) avec fallback pyttsx3
"""

import threading
import logging
import tempfile
import os
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Moteur TTS.
    Essaie Voxtral TTS, fallback sur pyttsx3 si indisponible.
    """

    def __init__(self, config: dict):
        self.config = config
        self._pipeline = None
        self._fallback = None
        self._initialized = False
        self._provider = "none"
        self._speaking = False
        self._lock = threading.Lock()

    def initialize(self) -> bool:
        """Charge le moteur TTS disponible"""

        # Tentative Voxtral TTS
        try:
            import torch
            from transformers import pipeline

            # TODO: Remplacer par mistralai/Voxtral-TTS quand disponible
            # model_name = "mistralai/Voxtral-TTS"
            model_name = None  # Placeholder — Voxtral TTS pas encore sur HF publiquement

            if model_name:
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                self._pipeline = pipeline("text-to-speech", model=model_name, device=device)
                self._provider = "voxtral"
                self._initialized = True
                logger.info("Voxtral TTS loaded ✓")
                return True
        except Exception as e:
            logger.debug(f"Voxtral TTS not available: {e}")

        # Fallback Kokoro TTS (belle voix, open source, tourne sur Apple Silicon)
        try:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code="a")  # 'a' = American English
            self._provider = "kokoro"
            self._initialized = True
            logger.info("Kokoro TTS loaded ✓")
            return True
        except Exception as e:
            logger.debug(f"Kokoro not available: {e}")

        # Fallback pyttsx3 (basique mais fiable)
        try:
            import pyttsx3
            self._fallback = pyttsx3.init()
            self._fallback.setProperty("rate", int(175 * self.config.get("speed", 1.0)))
            # Cherche une voix anglaise
            voices = self._fallback.getProperty("voices")
            for v in voices:
                if "en" in v.id.lower() or "english" in v.name.lower():
                    self._fallback.setProperty("voice", v.id)
                    break
            self._provider = "pyttsx3"
            self._initialized = True
            logger.info("pyttsx3 TTS loaded ✓")
            return True
        except Exception as e:
            logger.warning(f"pyttsx3 not available: {e}")

        logger.error("No TTS engine available")
        return False

    def speak(
        self,
        text: str,
        on_start: Optional[Callable] = None,
        on_done: Optional[Callable] = None,
        blocking: bool = False,
    ):
        """Synthétise et joue le texte"""
        if not self._initialized:
            logger.warning("TTS not initialized")
            if on_done:
                on_done()
            return

        if blocking:
            self._speak_sync(text, on_start, on_done)
        else:
            t = threading.Thread(
                target=self._speak_sync,
                args=(text, on_start, on_done),
                daemon=True,
            )
            t.start()

    def _speak_sync(self, text: str, on_start, on_done):
        with self._lock:
            self._speaking = True
            try:
                if on_start:
                    on_start()

                if self._provider == "kokoro":
                    self._speak_kokoro(text)
                elif self._provider == "voxtral":
                    self._speak_voxtral(text)
                elif self._provider == "pyttsx3":
                    self._speak_pyttsx3(text)

            except Exception as e:
                logger.error(f"TTS speak error: {e}")
            finally:
                self._speaking = False
                if on_done:
                    on_done()

    def _speak_kokoro(self, text: str):
        import sounddevice as sd
        import numpy as np

        generator = self._pipeline(text, voice="af_heart", speed=self.config.get("speed", 1.0))
        for _, _, audio in generator:
            if audio is not None:
                sd.play(audio, samplerate=24000)
                sd.wait()

    def _speak_voxtral(self, text: str):
        """Placeholder pour Voxtral TTS"""
        pass

    def _speak_pyttsx3(self, text: str):
        self._fallback.say(text)
        self._fallback.runAndWait()

    def stop(self):
        """Interrompt la synthèse en cours"""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def is_ready(self) -> bool:
        return self._initialized
