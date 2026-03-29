"""
LangCoach — Configuration générale
Toutes les constantes modifiables de l'app
"""

import json
import os
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────
APP_DIR = Path(__file__).parent.parent
CONFIG_DIR = APP_DIR / "config"
DATA_DIR = Path.home() / ".langcoach"
PROFILES_FILE = DATA_DIR / "profiles.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# ── Modèles ──────────────────────────────────────────────────
MODELS = {
    "stt": {
        "name": "mistralai/Voxtral-Transcribe-Mini",
        "fallback": "openai/whisper-small",   # Si Voxtral pas dispo
        "language": "auto",
    },
    "llm": {
        "provider": "ollama",                  # "ollama" | "mistral_api"
        "model": "llama3.1:8b",
        "temperature": 0.7,
        "max_tokens": 300,
        "context_window": 4096,
    },
    "tts": {
        "name": "mistralai/Voxtral-TTS",
        "fallback": "pyttsx3",                # TTS local sans IA
        "speed": 1.0,                          # 0.5 → 2.0
        "voice_sample": None,                  # Path vers fichier audio pour voice cloning
    },
}

# ── Audio ─────────────────────────────────────────────────────
AUDIO = {
    "sample_rate":      16000,
    "channels":         1,
    "chunk_size":       1024,
    "vad_threshold":    0.5,       # Sensibilité VAD (0.0 → 1.0)
    "silence_duration": 1.2,       # Secondes de silence avant envoi
    "max_record_sec":   30,        # Durée max d'un enregistrement
    "min_record_sec":   0.5,       # Durée min (évite les faux déclenchements)
}

# ── Profils prof ──────────────────────────────────────────────
TEACHER_STYLES = {
    "bienveillant": {
        "label": "Bienveillant",
        "emoji": "😊",
        "description": "Encourageant, patient, corrections douces",
        "system_hint": "Be warm, encouraging and patient. Gently correct mistakes by reformulating naturally.",
    },
    "natif": {
        "label": "Natif décontracté",
        "emoji": "🤙",
        "description": "Parle comme un vrai natif, argot inclus",
        "system_hint": "Speak naturally like a native speaker. Use idioms, contractions, and casual language.",
    },
    "academique": {
        "label": "Académique",
        "emoji": "🎓",
        "description": "Formel, précis, axé grammaire",
        "system_hint": "Use formal, precise language. Explicitly correct grammar mistakes and explain rules briefly.",
    },
    "strict": {
        "label": "Strict",
        "emoji": "📐",
        "description": "Correction systématique, exigence élevée",
        "system_hint": "Correct every mistake immediately and firmly. Demand proper grammar and vocabulary at all times.",
    },
    "socratique": {
        "label": "Socratique",
        "emoji": "🤔",
        "description": "Guide par questions, fait réfléchir",
        "system_hint": "Guide the student through questions rather than giving direct answers. Make them think.",
    },
}

# ── Niveaux ───────────────────────────────────────────────────
LEVELS = {
    "A1": {"label": "A1 — Débutant", "desc": "Vocabulaire de base, phrases simples"},
    "A2": {"label": "A2 — Élémentaire", "desc": "Communication basique du quotidien"},
    "B1": {"label": "B1 — Intermédiaire", "desc": "Conversations courantes"},
    "B2": {"label": "B2 — Intermédiaire+", "desc": "Discussions complexes, nuances"},
    "C1": {"label": "C1 — Avancé", "desc": "Maîtrise fluide et précise"},
    "C2": {"label": "C2 — Maîtrise", "desc": "Niveau natif, style élaboré"},
}

# ── Langues cibles ────────────────────────────────────────────
TARGET_LANGUAGES = {
    "english": {"label": "English 🇬🇧", "code": "en", "tts_lang": "en-US"},
    "spanish": {"label": "Español 🇪🇸", "code": "es", "tts_lang": "es-ES"},
}

# ── Langues maternelles ───────────────────────────────────────
NATIVE_LANGUAGES = {
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "zh": "中文",
    "ar": "العربية",
    "ru": "Русский",
    "ja": "日本語",
    "other": "Autre",
}

# ── Thèmes de conversation ────────────────────────────────────
CONVERSATION_TOPICS = [
    "Conversation libre",
    "Se présenter",
    "Voyage & Vacances",
    "Travail & Carrière",
    "Culture & Cinéma",
    "Actualités",
    "Sport & Loisirs",
    "Gastronomie",
    "Technologie & IA",
    "Débat / Opinion",
    "Entretien d'embauche",
    "Négociation business",
]

# ── Reachy Bridge (stub) ──────────────────────────────────────
REACHY = {
    "enabled": False,             # Activer quand Reachy connecté
    "host": "192.168.1.100",
    "port": 8765,
    "reconnect_interval": 5,      # secondes
}

# ── Paramètres par défaut ─────────────────────────────────────
DEFAULT_SETTINGS = {
    "teacher_style": "bienveillant",
    "level": "B1",
    "topic": "Conversation libre",
    "target_language": "english",
    "native_language": "fr",
    "input_mode": "vad",          # "vad" | "push_to_talk" | "both"
    "show_transcript": True,
    "show_corrections": True,
    "auto_send": True,
}


def load_settings() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
            return {**DEFAULT_SETTINGS, **saved}
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
