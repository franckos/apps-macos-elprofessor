# Design — Installer LangCoach (macOS standalone)

**Date :** 2026-03-31
**Statut :** Approuvé

---

## Contexte

LangCoach est une app macOS Python (PyQt6) 100% locale. Elle dépend de :
- Ollama + Llama 3.1 8B (~4.7 GB)
- torch + transformers + Whisper (~2-3 GB)
- Kokoro TTS, PortAudio, PyQt6

L'objectif est de rendre l'installation accessible à des utilisateurs non-techniques sur MacBook Apple Silicon (M1/M2/M3), en distribuant via GitHub.

---

## Décisions clés

| Décision | Choix | Raison |
|----------|-------|--------|
| Format d'installation | `install.sh` (script shell) | Léger sur GitHub, versionnable, maintenable |
| Lancement | Icône `.app` dans `/Applications/` | Expérience double-clic native macOS |
| Création du `.app` | Structure native macOS (Info.plist + shell launcher) | Zéro dépendance externe, reproductible |
| Mises à jour | Bouton dans l'UI (check GitHub Releases) | UX fluide sans réinstallation complète |
| Architecture cible | Apple Silicon uniquement (M1/M2/M3) | Simplifie torch/Ollama, audience cohérente |
| Mode futur | Reachy Mini (WebSocket bridge) | Déjà anticipé dans le code, pas dans ce scope |

---

## Structure du repo

```
ElProfessor/MacOS/
├── langcoach/           # code existant (inchangé)
├── install.sh           # script d'installation principal
├── update.sh            # script de mise à jour (appelé par l'app)
├── assets/
│   └── LangCoach.icns   # icône macOS (.icns format)
├── version.txt          # ex: "1.0.0" — utilisé pour le check updates
└── docs/
    └── superpowers/specs/
```

Le `.app` est **généré** par `install.sh` dans `/Applications/LangCoach.app/` — il n'est pas versionné dans le repo.

---

## `install.sh` — Étapes

Le script se lance via :
```bash
curl -fsSL https://raw.githubusercontent.com/[repo]/main/install.sh | bash
```

**Étapes dans l'ordre :**

1. Vérifie macOS + Apple Silicon (`uname -m == arm64`)
2. Installe **Homebrew** si absent
3. Installe **PortAudio** via `brew install portaudio`
4. Installe **Ollama** via `brew install ollama`
5. Clone le repo dans `~/Applications/LangCoach/` (ou `git pull` si déjà présent)
6. Crée un venv Python et installe `requirements.txt` + Kokoro
7. Lance `ollama pull llama3.1:8b` (avec progression visible)
8. Crée le **`LangCoach.app`** dans `/Applications/`
9. Affiche : *"LangCoach est installé ! Cherche-le dans ton Launchpad."*

**Le script est idempotent** : relançable sans casser l'existant (chaque étape vérifie si déjà fait avant d'agir).

> Note : les modèles Whisper/HuggingFace sont téléchargés automatiquement au premier lancement de l'app (HuggingFace cache dans `~/.cache/huggingface/`).

---

## Structure du `.app` généré

```
/Applications/LangCoach.app/
└── Contents/
    ├── Info.plist          # metadata macOS (nom, bundle ID, icône)
    ├── MacOS/
    │   └── LangCoach       # script shell exécutable
    └── Resources/
        └── LangCoach.icns  # icône
```

**`Info.plist` :** définit `CFBundleName`, `CFBundleIdentifier` (`com.quantelys.langcoach`), `CFBundleIconFile`.

**`LangCoach` (shell launcher) :**
1. Active le venv Python (`~/Applications/LangCoach/.venv`)
2. Démarre Ollama en background si pas déjà actif
3. Lance `python main.py`

---

## `update.sh` — Mise à jour

Appelé par l'app quand l'utilisateur accepte une mise à jour :

1. `git pull` dans `~/Applications/LangCoach/`
2. `pip install -r requirements.txt` (dans le venv)
3. Régénère le `.app` si `install.sh` a changé
4. Relance l'app

Ne réinstalle **pas** Ollama, le modèle LLM, ni PortAudio.

---

## Check for updates dans l'UI

Bouton dans le panneau Settings ("Vérifier les mises à jour") :

1. Lit `version.txt` local
2. Interroge `https://api.github.com/repos/[repo]/releases/latest`
3. Compare les versions (semver simple)
4. Si nouvelle version → toast/dialog : *"Version X.X disponible — Mettre à jour"*
5. Clic "Mettre à jour" → ouvre Terminal et exécute `update.sh`

---

## Compatibilité Reachy Mini (futur)

Le mode Reachy est déjà anticipé dans le code (`reachy/bridge.py`, `REACHY` config désactivée). L'installer n'a pas besoin de le gérer : ce sera une feature activée via Settings dans une release future, sans changement d'architecture d'installation.

---

## Ce qui n'est PAS dans ce scope

- Signature de code Apple (notarization) — pas nécessaire pour distribution GitHub
- Auto-update silencieux en background — update manuel via bouton UI
- Support Intel Mac
- Mode Reachy Mini
