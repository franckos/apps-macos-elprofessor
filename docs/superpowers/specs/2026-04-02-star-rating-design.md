# Design : Affichage étoiles pour le score de qualité

**Date :** 2026-04-02  
**Statut :** Approuvé

## Contexte

L'app affiche un `quality_score` (float 0.0–1.0) généré par Claude après chaque session. Ce score est actuellement affiché en % à deux endroits :

1. **Header du rapport de session** (`AnalysisReportWidget`) — via le widget `ScoreCircle` (arc SVG + % au centre)
2. **Liste des sessions dans le dashboard** (`dashboard_panel.py`) — via un `QLabel` inline `"{pct}%"`

L'objectif est d'ajouter un affichage complémentaire en étoiles (note sur 5) dans les deux endroits, **sans remplacer** l'affichage % existant.

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Report header | Garder l'arc % + ajouter badge étoiles à droite | Double lecture : progression visuelle + note intuitive |
| Dashboard list | Garder le % + ajouter étoiles inline | Cohérence, pas de surcharge UI |
| Précision | Étoiles entières uniquement | Simple, robuste, PyQt6-natif (Unicode) |
| Conversion | `round(score × 5)` → 0–5 étoiles | Standard intuitif |

## Architecture

### Helper : `score_to_stars(score)`

Défini dans `langcoach/ui/analysis_report.py`, utilisé aux deux endroits.

```python
def score_to_stars(score: float | None) -> str:
    if score is None:
        return "☆☆☆☆☆"
    n = round(score * 5)
    return "★" * n + "☆" * (5 - n)
```

### Nouveau widget : `StarBadge(QFrame)`

Défini dans `langcoach/ui/analysis_report.py`.

- Layout horizontal : `QLabel` étoiles + `QLabel` `"N/5"`
- Style : fond semi-transparent gold (`#c8a84b18`), bordure gold (`#c8a84b44`), border-radius arrondi
- Méthode `set_score(score: float | None)` pour mise à jour dynamique
- Taille compacte, cohérente visuellement avec le style existant de l'app

### Modifications `analysis_report.py`

**`_build_header()` :** Ajouter `self._star_badge = StarBadge(self)` après la colonne info title/subtitle, avant le `addStretch()`.

```
[ScoreCircle] [title / subtitle] [StarBadge ★★★★☆ 4/5] <stretch>
```

**`load_report()` :** Après `self._score_circle.set_score(score)`, ajouter :
```python
self._star_badge.set_score(score)
```

### Modifications `dashboard_panel.py`

Après le bloc `QLabel("{pct}%")` existant (lignes 412–419), ajouter un `QLabel` stars inline :

```python
sl = QLabel(score_to_stars(q))
sl.setFont(QFont(T["font_mono"], T["font_size_sm"]))
sl.setStyleSheet("color:#c8a84b; border:none;")
top.addWidget(sl)
```

`score_to_stars` sera importé depuis `langcoach.ui.analysis_report` (ou extrait dans un module utilitaire partagé si nécessaire).

## Flux de données

```
quality_score (float 0–1)
  ├── ScoreCircle.set_score()    → arc % (inchangé)
  ├── StarBadge.set_score()      → ★★★★☆  4/5  (nouveau, report header)
  └── QLabel(score_to_stars(q)) → ★★★★☆       (nouveau, dashboard list)
```

## Contraintes et points d'attention

- `score_to_stars` doit gérer `None` (sessions sans score)
- Le `StarBadge` doit rester lisible à côté du `ScoreCircle` existant (80×80px) — badge compact, pas de grande étoile centrale
- L'import de `score_to_stars` dans `dashboard_panel.py` crée une dépendance ; si cela pose problème, déplacer la fonction dans `langcoach/ui/utils.py`
- Aucune modification de `ScoreCircle`, aucun QPainter custom

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `langcoach/ui/analysis_report.py` | Ajouter `score_to_stars()`, `StarBadge`, mise à jour `_build_header()` et `load_report()` |
| `langcoach/ui/dashboard_panel.py` | Ajouter `QLabel` stars après le label `%` existant |
