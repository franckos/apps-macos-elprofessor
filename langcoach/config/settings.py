"""
LangCoach — Configuration générale
Toutes les constantes modifiables de l'app
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

# ── Chemins ──────────────────────────────────────────────────
APP_DIR = Path(__file__).parent.parent
CONFIG_DIR = APP_DIR / "config"
DATA_DIR = Path.home() / ".langcoach"
PROFILES_FILE = DATA_DIR / "profiles.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "data.db"
LAST_PROFILE_FILE = DATA_DIR / "last_profile.json"

# ── Modèles ──────────────────────────────────────────────────
MODELS = {
    "stt": {
        "name": "mistralai/Voxtral-Transcribe-Mini",
        "fallback": "openai/whisper-small",  # Si Voxtral pas dispo
        "language": "auto",
    },
    "llm": {
        "provider": "ollama",  # "ollama" | "mistral_api"
        "model": "llama3.1:8b",
        "temperature": 0.7,
        "max_tokens": 500,
        "context_window": 4096,
    },
    "tts": {
        "name": "mistralai/Voxtral-TTS",
        "fallback": "pyttsx3",  # TTS local sans IA
        "speed": 1.0,  # 0.5 → 2.0
        "voice_sample": None,  # Path vers fichier audio pour voice cloning
    },
}

# ── Audio ─────────────────────────────────────────────────────
AUDIO = {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "vad_threshold": 0.02,  # Sensibilité VAD RMS (0.001 silencieux → 0.05 parole normale)
    "silence_duration": 1.2,  # Secondes de silence avant envoi
    "max_record_sec": 30,  # Durée max d'un enregistrement
    "min_record_sec": 0.5,  # Durée min (évite les faux déclenchements)
}

# ── Profils prof ──────────────────────────────────────────────
TEACHER_STYLES = {
    "bienveillant": {
        "label": "Bienveillant",
        "emoji": "😊",
        "description": "Encourageant, patient, corrections douces",
        "system_hint": "Be warm, encouraging and patient. Focus on building the student's confidence. Gently correct mistakes by reformulating naturally.",
    },
    "natif": {
        "label": "Natif décontracté",
        "emoji": "🤙",
        "description": "Parle comme un vrai natif, argot inclus",
        "system_hint": "Speak naturally like a native speaker. Use idioms, contractions, and casual language. Speak naturally like a native speaker in the target language. Use common oral fillers (like 'eh', 'pues', 'you know'), local idioms, and casual contractions. Adopt a relaxed, street-smart tone while staying conversational.",
    },
    "academique": {
        "label": "Académique",
        "emoji": "🎓",
        "description": "Formel, précis, axé grammaire, correction systématique, exigence élevée",
        "system_hint": "Use formal, precise language. Explicitly correct grammar and vocabulary mistakes and explain rules briefly.",
    },
    "socratique": {
        "label": "Socratique",
        "emoji": "🤔",
        "description": "Guide par questions, fait réfléchir",
        "system_hint": "Guide the student through questions rather than giving direct answers. Make them think.",
    },
    "business": {
        "label": "Business & Pro",
        "emoji": "💼",
        "description": "Professionnel, pragmatique, vocabulaire corporate",
        "system_hint": "Maintain a professional and efficient tone. Use industry-standard terminology and corporate etiquette appropriate for the target language (e.g., using 'usted' in Spanish or professional phrasal verbs in English). Focus on clarity and leadership.",
    },
    "elegant": {
        "label": "Élégant",
        "emoji": "✦",
        "description": "Distingué, luxueux, vocabulaire raffiné et profond",
        "system_hint": "Speak with sophistication and elegance. Use refined, precise vocabulary. Favour nuance, depth and stylistic flourish. Correct errors with grace, never harshness. Avoid common or bland words; prefer poetic or rare synonyms.",
    },
}

# ── Niveaux ───────────────────────────────────────────────────
LEVELS = {
    "A1": {
        "label": "A1 — Débutant",
        "desc": "Vocabulaire de base, phrases simples.",
        "instructions": "Utilise uniquement le présent. Phrases très courtes (Sujet-Verbe-Complément). Limite le vocabulaire aux objets du quotidien et propose des mots adaptés. Aide le à se présenter ou à décrire son travail, des lieux ou des personnes.",
    },
    "A2": {
        "label": "A2 — Élémentaire",
        "desc": "Communication basique du quotidien.",
        "instructions": "Utilise principalement le présent et le passé composé. Fais des phrases simples mais complètes. Pose une seule question à la fois. Introduis 1 ou 2 nouveaux mots de vocabulaire avec leur traduction dans son langage naturel et encourage le à utiliser ces mots dans les phrases suivantes.",
    },
    "B1": {
        "label": "B1 — Intermédiaire",
        "desc": "Conversations courantes.",
        "instructions": "Adopte un ton naturel mais reste clair. Utilise le futur et l'imparfait en plus des autres temps. Encourage l'élève à donner son opinion. Suggère des reformulations, de synonymes pour en améliorer la clarté.",
    },
    "B2": {
        "label": "B2 — Intermédiaire+",
        "desc": "Discussions complexes, nuances.",
        "instructions": "Parle comme un ami natif. Utilise des expressions idiomatiques courantes et des connecteurs logiques. Propose des sujets de débat. Corrige les erreurs de syntaxe subtiles et suggère des synonymes plus précis.",
    },
    "C1": {
        "label": "C1 — Avancé",
        "desc": "Maîtrise fluide et précise.",
        "instructions": "Utilise un langage soutenu et des structures grammaticales complexes (subjonctif, inversion). Sois exigeant sur la précision des mots. Challenge l'élève sur des nuances culturelles ou des concepts abstraits.",
    },
    "C2": {
        "label": "C2 — Maîtrise",
        "desc": "Niveau natif, style élaboré.",
        "instructions": "Comporte-toi comme un partenaire de discussion intellectuel. Utilise des figures de style, de l'ironie ou des références littéraires. Analyse les nuances de registre (familier vs formel) dans les réponses de l'élève.",
    },
}

# ── Langues cibles ────────────────────────────────────────────
TARGET_LANGUAGES = {
    "english": {"label": "English 🇬🇧", "code": "en", "tts_lang": "en-US"},
    "spanish": {"label": "Español 🇪🇸", "code": "es", "tts_lang": "es-ES"},
}

# ── Coaches ───────────────────────────────────────────────────
# lang_code : codes Kokoro — a=américain, b=britannique, e=espagnol
COACHES = {
    "english": {
        "angela": {
            "name": "Angela",
            "gender": "female",
            "flag": "🇬🇧",
            "lang_code": "b",  # British English
            "voice": "bf_emma",
        },
        "georges": {
            "name": "Georges",
            "gender": "male",
            "flag": "🇺🇸",
            "lang_code": "a",  # American English
            "voice": "am_adam",
        },
    },
    "spanish": {
        "aitanita": {
            "name": "Aitanita",
            "gender": "female",
            "flag": "🇪🇸",
            "lang_code": "e",
            "voice": "ef_dora",
        },
        "javier": {
            "name": "Javier",
            "gender": "male",
            "flag": "🇪🇸",
            "lang_code": "e",
            "voice": "em_alex",
        },
    },
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
    "enabled": False,  # Activer quand Reachy connecté
    "host": "192.168.1.100",
    "port": 8765,
    "reconnect_interval": 5,  # secondes
}

# ── Paramètres par défaut ─────────────────────────────────────
DEFAULT_SETTINGS = {
    "teacher_style": "bienveillant",
    "level": "B1",
    "topic": "Conversation libre",
    "target_language": "english",
    "coach": "angela",
    "native_language": "fr",
    "input_mode": "vad",  # "vad" | "push_to_talk" | "both"
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


def load_last_profile_id() -> Optional[str]:
    """Returns the last-used profile ID, or None."""
    if LAST_PROFILE_FILE.exists():
        try:
            with open(LAST_PROFILE_FILE) as f:
                return json.load(f).get("profile_id")
        except Exception:
            pass
    return None


def save_last_profile_id(profile_id: str):
    DATA_DIR.mkdir(exist_ok=True)
    with open(LAST_PROFILE_FILE, "w") as f:
        json.dump({"profile_id": profile_id}, f)


def migrate_if_needed(db) -> bool:
    """
    If no profiles exist in DB but old settings.json exists, create a default profile.
    Returns True if migration happened.
    """
    if db.list_profiles():
        return False
    if not SETTINGS_FILE.exists():
        return False
    try:
        with open(SETTINGS_FILE) as f:
            old_settings = {**DEFAULT_SETTINGS, **json.load(f)}
        profile = db.create_profile("Moi", "🧑", old_settings)
        save_last_profile_id(profile["id"])
        SETTINGS_FILE.rename(SETTINGS_FILE.with_suffix(".json.migrated"))
        logging.getLogger(__name__).info("Migrated old settings.json to profile")
        return True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Migration failed: {e}")
        return False
