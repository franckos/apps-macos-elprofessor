# LangCoach 🎓

**AI language teacher. 100% local. 100% free to run.**

Conversation libre en anglais ou espagnol avec un prof IA vocal, personnalisable, sans coût d'API.

---

## Stack

| Rôle | Modèle | Notes |
|------|--------|-------|
| STT | Whisper Small (HuggingFace) | Remplacer par Voxtral Transcribe quand dispo |
| LLM | Llama 3.1 8B via Ollama | Tourne fluide sur M1 Pro |
| TTS | Kokoro (priorité) / pyttsx3 (fallback) | Remplacer par Voxtral TTS quand dispo |

---

## Installation

### 1. Prérequis système (macOS)

```bash
# Homebrew (si pas installé)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# PortAudio (requis pour sounddevice)
brew install portaudio

# Ollama
brew install ollama
```

### 2. Modèle LLM

```bash
# Démarrer Ollama
ollama serve

# Télécharger le modèle (une seule fois, ~4.7 GB)
ollama pull llama3.1:8b
```

### 3. Dépendances Python

```bash
# Crée un virtualenv (recommandé)
python3 -m venv .venv
source .venv/bin/activate

# Installe les dépendances
pip install -r requirements.txt

# TTS Kokoro (belle voix — recommandé)
pip install kokoro soundfile
```

### 4. Lancer l'app

```bash
cd langcoach
python main.py
```

---

## Mise à jour vers Voxtral

Quand Voxtral TTS et Voxtral Transcribe seront disponibles sur Hugging Face :

**STT** — dans `config/settings.py` :
```python
"stt": {
    "name": "mistralai/Voxtral-Transcribe-Mini",
}
```

**TTS** — dans `core/tts.py`, ligne ~35 :
```python
model_name = "mistralai/Voxtral-TTS"
```

---

## Raccourcis clavier

| Touche | Action |
|--------|--------|
| `Space` (hold) | Push-to-talk |
| `A` | Toggle auto-detect (VAD) |
| `R` | Reset session |
| `S` | Ouvrir/fermer settings |
| `Esc` | Arrêter la synthèse vocale |
| `Enter` | Envoyer message texte |

---

## Reachy Mini (futur)

Activer le bridge dans `config/settings.py` :
```python
REACHY = {
    "enabled": True,
    "host": "192.168.1.xxx",  # IP du Reachy
    "port": 8765,
}
```

Le bridge envoie en WebSocket :
- Transcriptions (user + assistant)
- État speaking (pour synchroniser les animations)
- Événements de session

---

## Personnalisation

### Thème visuel
Tout dans `config/theme.py` — couleurs, typos, tailles, espacements.

### Profils professeur
Dans `config/settings.py` → `TEACHER_STYLES` — ajouter autant de styles que voulu.

### Modèle LLM
Dans `config/settings.py` → `MODELS["llm"]` — changer `model` pour n'importe quel modèle Ollama.

---

## Architecture

```
langcoach/
├── main.py                  # Entry point
├── config/
│   ├── theme.py             # 🎨 Tout le look ici
│   └── settings.py          # ⚙️  Tout le comportement ici
├── core/
│   ├── session.py           # Orchestrateur principal
│   ├── stt.py               # Speech-to-Text
│   ├── llm.py               # LLM (Ollama / Mistral API)
│   ├── tts.py               # Text-to-Speech
│   └── prompt_builder.py    # Génération du system prompt
├── ui/
│   ├── main_window.py       # Fenêtre principale
│   ├── settings_panel.py    # Panneau settings
│   └── widgets.py           # Composants custom
└── reachy/
    └── bridge.py            # WebSocket Reachy (stub)
```
