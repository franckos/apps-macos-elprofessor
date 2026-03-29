"""
LangCoach — Speech-to-Text
Utilise Voxtral Transcribe (via transformers) avec fallback Whisper
"""

import threading
import queue
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class STTEngine:
    """
    Moteur STT avec deux modes :
    - push_to_talk : enregistre entre start() et stop()
    - vad : détection automatique du silence
    """

    def __init__(self, settings: dict, on_transcript: Callable[[str], None]):
        self.settings = settings
        self.on_transcript = on_transcript
        self._pipeline = None
        self._recording = False
        self._audio_queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._initialized = False

    def initialize(self):
        """Charge le modèle en arrière-plan"""
        try:
            import torch
            from transformers import pipeline

            model_name = "openai/whisper-small"  # Fallback stable
            # TODO: Remplacer par mistralai/Voxtral-Transcribe-Mini quand dispo sur HF

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            logger.info(f"Loading STT model on {device}...")

            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=device,
                generate_kwargs={"language": "english"},
            )
            self._initialized = True
            logger.info("STT model loaded ✓")
            return True

        except ImportError as e:
            logger.warning(f"transformers not installed: {e}. STT disabled.")
            return False
        except Exception as e:
            logger.error(f"STT init error: {e}")
            return False

    def transcribe_file(self, audio_path: str) -> str:
        """Transcrit un fichier audio"""
        if not self._initialized or not self._pipeline:
            return ""
        try:
            result = self._pipeline(audio_path)
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def transcribe_array(self, audio_array, sample_rate: int = 16000) -> str:
        """Transcrit un array numpy"""
        if not self._initialized or not self._pipeline:
            return ""
        try:
            result = self._pipeline({"array": audio_array, "sampling_rate": sample_rate})
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def is_ready(self) -> bool:
        return self._initialized


class AudioRecorder:
    """
    Enregistreur audio avec support VAD et push-to-talk
    Utilise sounddevice (léger, cross-platform)
    """

    def __init__(self, config: dict, on_audio_ready: Callable):
        self.config = config
        self.on_audio_ready = on_audio_ready
        self._recording = False
        self._frames = []
        self._vad_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_recording(self):
        """Push-to-talk : début enregistrement"""
        try:
            import sounddevice as sd
            import numpy as np

            self._frames = []
            self._recording = True
            sr = self.config.get("sample_rate", 16000)

            def callback(indata, frames, time_info, status):
                if self._recording:
                    self._frames.append(indata.copy())

            self._stream = sd.InputStream(
                samplerate=sr,
                channels=1,
                dtype="float32",
                callback=callback,
                blocksize=self.config.get("chunk_size", 1024),
            )
            self._stream.start()
        except Exception as e:
            logger.error(f"Recording start error: {e}")

    def stop_recording(self):
        """Push-to-talk : fin enregistrement, retourne audio"""
        try:
            import numpy as np

            self._recording = False
            if hasattr(self, "_stream"):
                self._stream.stop()
                self._stream.close()

            if self._frames:
                audio = np.concatenate(self._frames, axis=0).flatten()
                sr = self.config.get("sample_rate", 16000)
                min_sec = self.config.get("min_record_sec", 0.5)
                if len(audio) >= sr * min_sec:
                    self.on_audio_ready(audio, sr)
        except Exception as e:
            logger.error(f"Recording stop error: {e}")

    def start_vad(self, stt_engine: STTEngine):
        """Démarre la détection automatique de parole"""
        self._stop_event.clear()
        self._vad_thread = threading.Thread(
            target=self._vad_loop,
            args=(stt_engine,),
            daemon=True,
        )
        self._vad_thread.start()

    def stop_vad(self):
        self._stop_event.set()

    def _vad_loop(self, stt_engine: STTEngine):
        """Boucle VAD : détecte parole → enregistre → transcrit"""
        try:
            import sounddevice as sd
            import numpy as np

            sr = self.config.get("sample_rate", 16000)
            chunk = self.config.get("chunk_size", 1024)
            threshold = self.config.get("vad_threshold", 0.02)
            silence_dur = self.config.get("silence_duration", 1.2)
            max_sec = self.config.get("max_record_sec", 30)

            frames = []
            silence_start = None
            speaking = False

            with sd.InputStream(samplerate=sr, channels=1, dtype="float32", blocksize=chunk) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(chunk)
                    rms = float(np.sqrt(np.mean(data ** 2)))

                    if rms > threshold:
                        if not speaking:
                            speaking = True
                            frames = []
                        silence_start = None
                        frames.append(data.copy())
                    else:
                        if speaking:
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start >= silence_dur:
                                # Fin de parole détectée
                                audio = np.concatenate(frames, axis=0).flatten()
                                if len(audio) >= sr * self.config.get("min_record_sec", 0.5):
                                    self.on_audio_ready(audio, sr)
                                frames = []
                                speaking = False
                                silence_start = None

                    # Sécurité durée max
                    if speaking and len(frames) * chunk / sr > max_sec:
                        audio = np.concatenate(frames, axis=0).flatten()
                        self.on_audio_ready(audio, sr)
                        frames = []
                        speaking = False

        except Exception as e:
            logger.error(f"VAD loop error: {e}")
