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


# Hints pyttsx3 par langue (fallback)
_PYTTSX3_LANG_HINTS = {
    "english": ["en"],
    "spanish": ["es", "spanish"],
}


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
        self._stop_requested = False
        self._lock = threading.Lock()
        self._kokoro_lang_code = "a"
        self._kokoro_voice = "af_heart"
        self._target_lang = "english"

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
            self._pipeline = KPipeline(lang_code=self._kokoro_lang_code)
            self._provider = "kokoro"
            self._initialized = True
            logger.info(f"Kokoro TTS loaded ✓ (lang={self._kokoro_lang_code})")
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

        self._stop_requested = False

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

        speed = self.config.get("speed", 1.0)
        chunks = []

        # Split on newlines as Kokoro recommends for long texts
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        for line in lines:
            if self._stop_requested:
                return
            # EspeakG2P (used for non-English langs) returns (phonemes_str, None).
            # KPipeline.__call__ doesn't unwrap this tuple, causing the model to receive
            # the tuple as input and produce ~6000 empty samples.
            # Fix: call g2p manually, unwrap if tuple, then use generate_from_tokens.
            ps_result = self._pipeline.g2p(line)
            if isinstance(ps_result, tuple):
                ps = ps_result[0]  # unwrap (phonemes, tokens) → phonemes string
            else:
                ps = ps_result
            if not ps:
                continue
            if len(ps) > 510:
                ps = ps[:510]
            for _, _, audio in self._pipeline.generate_from_tokens(ps, voice=self._kokoro_voice, speed=speed):
                if self._stop_requested:
                    return
                if audio is not None:
                    chunks.append(audio)

        if not chunks:
            # La voix demandée n'est pas disponible dans cette installation de Kokoro.
            # Fallback sur pyttsx3 (voix macOS native).
            logger.warning(
                f"Kokoro voice '{self._kokoro_voice}' (lang={self._kokoro_lang_code}) "
                f"produced no audio. Install: pip install kokoro[es] or similar. "
                f"Falling back to pyttsx3."
            )
            self._speak_pyttsx3_fallback(text)
            return

        if not self._stop_requested:
            full_audio = np.concatenate(chunks)
            kokoro_sr = 24000
            device_sr = int(sd.query_devices(kind="output")["default_samplerate"])
            if device_sr != kokoro_sr:
                n_samples = int(len(full_audio) * device_sr / kokoro_sr)
                full_audio = np.interp(
                    np.linspace(0, len(full_audio) - 1, n_samples),
                    np.arange(len(full_audio)),
                    full_audio,
                )
            sd.play(full_audio.astype(np.float32), samplerate=device_sr)
            sd.wait()

    def _speak_pyttsx3_fallback(self, text: str):
        """pyttsx3 à la volée — utilisé quand Kokoro ne supporte pas la voix demandée"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", int(175 * self.config.get("speed", 1.0)))
            # Cherche une voix dans la langue cible
            lang_hints = _PYTTSX3_LANG_HINTS.get(self._target_lang, ["en"])
            voices = engine.getProperty("voices")
            for v in voices:
                if any(h in v.id.lower() or h in v.name.lower() for h in lang_hints):
                    engine.setProperty("voice", v.id)
                    break
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 fallback error: {e}")

    def _speak_voxtral(self, text: str):
        """Placeholder pour Voxtral TTS"""
        pass

    def _speak_pyttsx3(self, text: str):
        self._fallback.say(text)
        self._fallback.runAndWait()

    def set_coach(self, coach_cfg: dict):
        """Change le coach — re-initialise Kokoro avec le bon lang_code et la bonne voix"""
        lang_code = coach_cfg.get("lang_code", "a")
        voice = coach_cfg.get("voice", "af_heart")
        target_lang_key = coach_cfg.get("_target_lang", "english")

        if lang_code == self._kokoro_lang_code and voice == self._kokoro_voice:
            return  # Pas de changement

        self._kokoro_lang_code = lang_code
        self._kokoro_voice = voice
        self._target_lang = target_lang_key

        if self._provider == "kokoro":
            try:
                from kokoro import KPipeline
                self._pipeline = KPipeline(lang_code=lang_code)
                logger.info(f"Kokoro re-initialized: lang={lang_code}, voice={voice}")
            except Exception as e:
                logger.error(f"Kokoro re-init error: {e}")
        elif self._provider == "pyttsx3" and self._fallback:
            lang_hints = _PYTTSX3_LANG_HINTS.get(target_lang_key, ["en"])
            voices = self._fallback.getProperty("voices")
            for v in voices:
                if any(h in v.id.lower() or h in v.name.lower() for h in lang_hints):
                    self._fallback.setProperty("voice", v.id)
                    logger.info(f"pyttsx3 voice changed: {v.name}")
                    break

    def stop(self):
        """Interrompt la synthèse en cours"""
        self._stop_requested = True
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
