# El Profesor — CLAUDE.md

Application d'apprentissage linguistique 100% locale pour macOS Apple Silicon.
Nom interne du repo : **LangCoach-MacOS**. Nom produit : **El Profesor**.
Version courante : `version.txt` (actuellement 1.2.0).

---

## Stack technique

| Rôle | Technologie | Notes |
|------|-------------|-------|
| UI | PyQt6 | App native macOS, dark theme |
| STT | Whisper (HuggingFace) ou Voxtral-Transcribe-Mini | Fallback Whisper si Voxtral pas dispo |
| LLM | Llama 3.1 8B via Ollama | Provider configurable : `ollama` ou `mistral_api` |
| TTS | Kokoro (priorité) / pyttsx3 (fallback) | Voxtral TTS prévu quand dispo |
| Audio I/O | PortAudio + sounddevice | VAD maison (seuil RMS) |
| Persistance | SQLite dans `~/.langcoach/` | Profils, sessions, stats |

Pas de cloud. Pas de clé API obligatoire. Tourne exclusivement sur Apple Silicon.

---

## Architecture du projet

```
LangCoach-MacOS/
├── CLAUDE.md
├── README.md
├── version.txt
├── install.sh              # Installeur one-shot
├── update.sh               # Updater incrémental (appelé par l'app)
├── assets/
│   └── LangCoach.icns
├── docs/
├── tests/
│   └── test_score_to_stars.py
└── langcoach/
    ├── main.py             # Point d'entrée
    ├── requirements.txt
    ├── config/
    │   ├── settings.py     # Toutes les constantes (MODELS, AUDIO, TEACHER_STYLES…)
    │   └── theme.py        # Couleurs, typos, espacements — tout le look ici
    ├── core/
    │   ├── session.py      # Orchestrateur principal (STT → LLM → TTS)
    │   ├── stt.py          # Speech-to-Text
    │   ├── llm.py          # LLM engine (Ollama / Mistral API)
    │   ├── tts.py          # Text-to-Speech
    │   ├── prompt_builder.py
    │   ├── memory_manager.py
    │   ├── stats_engine.py
    │   ├── database.py     # SQLite — toutes les données dans ~/.langcoach/
    │   └── updater.py      # Vérif mises à jour GitHub Releases
    ├── ui/
    │   ├── main_window.py
    │   ├── settings_panel.py
    │   ├── dashboard_panel.py
    │   ├── profile_screen.py
    │   ├── analysis_report.py
    │   ├── memory_panel.py
    │   └── widgets.py      # Composants custom réutilisables
    └── reachy/             # Bridge WebSocket Reachy Mini (stub, futur)
```

---

## Fichiers clés à connaître

- **`langcoach/config/settings.py`** — source de vérité pour tous les paramètres : modèles, audio, styles professeur, langues, topics. Modifier ici plutôt que dans le code métier.
- **`langcoach/config/theme.py`** — toutes les constantes visuelles (couleurs, polices, rayons). Ne pas mettre de valeurs cosmétiques en dur ailleurs.
- **`langcoach/core/session.py`** — orchestrateur central. C'est lui qui enchaîne STT → LLM → TTS et gère l'état de la session.
- **`langcoach/core/database.py`** — tout ce qui touche à la persistance passe ici.
- **`~/.langcoach/`** — données utilisateur en production (ne pas committer).

---

## Conventions de code

- **Python 3.11**, type hints recommandés sur les signatures publiques.
- Langue du code : **anglais** (variables, fonctions, commentaires inline).
- Langue des messages UI et des docstrings de haut niveau : **français** (l'app est pensée pour des francophones).
- Imports organisés : stdlib → third-party → modules internes.
- Pas de logique métier dans les fichiers UI ; les panneaux PyQt6 appellent `core/`.
- Les constantes configurables vont dans `config/settings.py`, jamais en dur dans `core/` ou `ui/`.

---

## Données utilisateur

Toutes les données vivent dans `~/.langcoach/` :

| Fichier | Contenu |
|---------|---------|
| `data.db` | Sessions, messages, stats (SQLite) |
| `profiles.json` | Profils apprenants |
| `settings.json` | Préférences utilisateur sauvegardées |
| `last_profile.json` | Dernier profil actif |

Ne jamais modifier ces fichiers directement dans les tests — utiliser une DB temporaire ou mocker `database.py`.

---

## Tests

```bash
cd langcoach
python -m pytest ../tests/
```

Les tests sont dans `tests/` à la racine. Un seul fichier actuellement : `test_score_to_stars.py`.
Avant d'ajouter une feature, vérifier s'il faut un test unitaire correspondant dans `tests/`.

---

## Lancer l'app en dev

```bash
# Depuis la racine du repo
source .venv/bin/activate  # ou langcoach/.venv selon l'install
cd langcoach
python main.py
```

Ollama doit tourner en arrière-plan (`ollama serve`).

---

## Roadmap / plans connus

- **Voxtral STT** (`mistralai/Voxtral-Transcribe-Mini`) — remplacera Whisper quand disponible sur HuggingFace. Paramètre dans `config/settings.py → MODELS["stt"]`.
- **Voxtral TTS** (`mistralai/Voxtral-TTS`) — remplacera Kokoro. Paramètre dans `core/tts.py`.
- **Reachy Mini bridge** — `langcoach/reachy/bridge.py` est un stub WebSocket pour synchroniser un robot physique avec l'app (animations lip-sync, état speaking).

---

## Ce que ce projet n'est pas

- Pas de serveur backend, pas d'API REST exposée.
- Pas de compte utilisateur, pas de telemetry, pas de réseau sortant (sauf `update.sh` pour les mises à jour GitHub).
- Pas de support Windows/Linux prévu.
