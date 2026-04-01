# Design Spec — Rapport d'analyse post-session
**Date :** 2026-04-01  
**Branch :** feat/memory-system  

---

## Contexte & Problèmes à résoudre

1. **Bug DB** : "database disk image is malformed" — deux threads SQLite (analyse + extraction mémoires) partagent une seule connexion `sqlite3` sans verrou. Concurrent writes → corruption.
2. **UX cassée** : cliquer "Analyser" efface le chat et réinitialise la session *immédiatement*, avant que l'analyse soit terminée.
3. **Rapport trop pauvre** : le dialog actuel n'affiche qu'un score + 2-3 phrases. Pas assez de valeur pour l'utilisateur.

---

## Architecture générale

### Navigation (existante + extension)
```
_main_stack
  ├── index 0 : Session widget
  │     └── _session_stack
  │           ├── index 0 : topic picker
  │           ├── index 1 : chat area
  │           └── index 2 : AnalysisReportWidget  ← NOUVEAU
  └── index 1 : Dashboard
```

### Flow mis à jour
```
[Analyser] clic
  → désactiver bouton + spinner "Analyse en cours…"
  → NE PAS toucher au chat ni à la session
  → lancer analyze_and_extract_async()
  → quand done → _session_stack.setCurrentIndex(2) avec les données
  → [Nouvelle discussion] → clear chat + reset session + index 0
  → [Tableau de bord]    → main_stack index 1
```

---

## 1. Fix DB threading — `database.py`

Ajouter `self._lock = threading.Lock()` dans `Database.__init__`.  
Wrapper chaque méthode publique avec `with self._lock:` pour sérialiser tous les accès DB.  
Cela suffit pour éliminer les corruptions concurrent-write sur une connexion partagée.

---

## 2. Prompt LLM enrichi — `stats_engine.py`

### Nouveau schéma JSON attendu du LLM

```json
{
  "quality_score": 0.82,
  "summary": "2-3 phrases bienveillantes résumant la session.",
  "errors": [
    {
      "original": "I go yesterday",
      "corrected": "I went yesterday",
      "type": "tense",
      "rule": "simple past"
    }
  ],
  "improvements": [
    "Travailler la conjugaison du prétérit irrégulier",
    "Utiliser davantage de connecteurs logiques (however, although)"
  ],
  "vocabulary": [
    {
      "word": "commute",
      "translation": "trajet domicile-travail",
      "example": "My daily commute takes 30 minutes."
    }
  ]
}
```

### Signature de callback mise à jour

```
# Avant
on_done(score: float, summary: str, suggestion_count: int)

# Après
on_done(score: float, analysis: dict, suggestions: list[dict])
```

`analysis` = le JSON complet parsé du LLM (errors, improvements, vocabulary, summary).  
`suggestions` = liste de dicts suggestion depuis la DB (pas juste un count).

Le signal PyQt change de `_sig(object, object, int)` → `_sig(object, object, object)`.

---

## 3. Nouveau widget — `langcoach/ui/analysis_report.py`

**Classe :** `AnalysisReportWidget(QWidget)`

### Interface publique
```python
def load_report(self, score: float, analysis: dict, suggestions: list) -> None
    # Remplit toutes les sections avec les données

on_new_session: callable  # callback → main_window clear + topic picker
on_go_dashboard: callable # callback → main_window switch dashboard
```

### Layout vertical (scrollable)
```
┌─────────────────────────────────────────────┐
│  Score circulaire  │  "Rapport de session"   │  ← Header fixe
│      82 / 100      │  langue · niveau · sujet│
├─────────────────────────────────────────────┤
│ ScrollArea                                  │
│  ── Résumé ──────────────────────────────── │
│  Texte du résumé (2-3 phrases)              │
│                                             │
│  ── Erreurs corrigées (N) ───────────────── │
│  ┌──────────────────────────────────────┐   │
│  │ ❌ "I go yesterday"                  │   │
│  │ ✅ "I went yesterday"   [simple past]│   │
│  └──────────────────────────────────────┘   │
│  (une card par erreur, max 8 affichées)     │
│                                             │
│  ── Points à améliorer ──────────────────── │
│  • Travailler le prétérit irrégulier        │
│  • Utiliser davantage de connecteurs        │
│                                             │
│  ── Vocabulaire clé ─────────────────────── │
│  ┌─────────────┐ ┌─────────────┐           │
│  │  commute    │ │  despite    │           │
│  │  trajet     │ │  malgré     │           │
│  │ exemple...  │ │ exemple...  │           │
│  └─────────────┘ └─────────────┘           │
│                                             │
│  ── Mémoires suggérées (N) ──────────────── │
│  ┌──────────────────────────────────────┐   │
│  │ 💡 "Travaille dans la finance"       │   │
│  │           [Accepter]  [Ignorer]      │   │
│  └──────────────────────────────────────┘   │
├─────────────────────────────────────────────┤
│  [Tableau de bord]    [Nouvelle discussion] │  ← Footer fixe
└─────────────────────────────────────────────┘
```

### Comportement mémoires
- **Accepter** → `db.accept_memory_suggestion(id)` → card disparaît avec animation fade
- **Ignorer** → `db.delete_memory_suggestion(id)` → card disparaît
- Si plus aucune suggestion → section disparaît

### Score circulaire
Widget `ScoreCircle(QWidget)` dessiné avec `QPainter` :
- Arc coloré de 0° à N° selon le score (vert ≥ 75, orange ≥ 50, rouge < 50)
- Chiffre centré en gras
- Taille fixe 80×80px

---

## 4. Changements `main_window.py`

- Supprimer le clear chat + session reset de `_on_finir_analyser`
- Ajouter `_analysis_report = AnalysisReportWidget(...)` dans `_build_ui`, l'ajouter à `_session_stack` index 2
- Mettre à jour `_on_finir_result` pour recevoir `(score, analysis, suggestions)` et appeler `_analysis_report.load_report(...)`
- Mettre à jour le signal `done = _sig(object, object, object)`
- Brancher les callbacks `on_new_session` / `on_go_dashboard`

---

## 5. Gestion du cas d'erreur DB

Si l'analyse échoue (DB corrompue ou LLM indisponible) :
- `analysis = {"summary": "Analyse non disponible.", "errors": [], "improvements": [], "vocabulary": []}`
- `score = None`
- Le rapport s'affiche quand même avec les données partielles disponibles
- Les suggestions (si extraites) s'affichent normalement

---

## Fichiers impactés

| Fichier | Changement |
|---|---|
| `langcoach/core/database.py` | Ajouter threading.Lock |
| `langcoach/core/stats_engine.py` | Prompt enrichi + nouvelle signature callback |
| `langcoach/ui/analysis_report.py` | **NOUVEAU** — AnalysisReportWidget + ScoreCircle |
| `langcoach/ui/main_window.py` | Flow mis à jour, signal, intégration du nouveau widget |

---

## Hors scope

- Export PDF du rapport
- Historique des rapports accessibles depuis le dashboard
- Comparaison avec sessions précédentes
