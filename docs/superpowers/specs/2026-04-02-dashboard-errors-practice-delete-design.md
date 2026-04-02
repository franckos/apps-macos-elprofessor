# Dashboard Erreurs — Boutons Pratiquer & Supprimer

**Date:** 2026-04-02  
**Scope:** Onglet Erreurs du Dashboard — cartes "Lacunes récurrentes"

---

## Objectif

Ajouter deux actions sur chaque carte de lacune récurrente :

1. **Bouton "🎯 Pratiquer"** — démarre une nouvelle session focalisée sur cette erreur et supprime la lacune du dashboard.
2. **Bouton "🗑"** — supprime la lacune sans confirmation et retire la carte.

---

## Architecture

### 1. `core/database.py`

Nouvelle méthode :

```python
def delete_error_pattern(self, profile_id: str, error_type: str, rule: str) -> None
```

Supprime la ligne correspondante dans `error_patterns` (PK = `profile_id + error_type + rule`).

---

### 2. `ui/dashboard_panel.py`

**Nouveau callback public :**

```python
self.on_practice_pattern = None  # callable(error_type: str, rule: str)
```

Initialisé à `None` dans `__init__`, câblé depuis `MainWindow`.

**Modifications de `_pattern_card(p)`:**

- Ajouter un bouton "🎯 Pratiquer" (style accent, height 28) à droite de la carte.
- Ajouter un bouton "🗑" (style muted/transparent, 28×28) à droite du précédent.
- Les deux boutons utilisent une closure capturant `error_type`, `rule`, et le widget `w`.

**Nouveau handler `_practice_pattern(error_type, rule, card)`:**

1. Appelle `self._db.delete_error_pattern(profile_id, error_type, rule)`.
2. Masque et détruit la carte (`card.hide(); card.deleteLater()`).
3. Appelle `self.on_practice_pattern(error_type, rule)` si défini.

**Nouveau handler `_delete_pattern(error_type, rule, card)`:**

1. Appelle `self._db.delete_error_pattern(profile_id, error_type, rule)`.
2. Masque et détruit la carte.

---

### 3. `ui/main_window.py`

**Câblage :** Après création de `DashboardPanel`, ajouter :

```python
self._dashboard_panel.on_practice_pattern = self._on_practice_pattern
```

**Nouveau handler `_on_practice_pattern(error_type, rule)`:**

1. Vide le chat layout (comme `_on_analysis_new_session`).
2. Appelle `self.session.reset_session()`.
3. Appelle `self._refresh_topic_picker()`.
4. Bascule vers l'onglet Session (`self._switch_tab(0)`).
5. Injecte un message d'amorçage dans la session LLM via `self.session._llm` :

```
"Je veux pratiquer ce point : {rule} ({error_type}). 
Commence par m'expliquer la règle en contexte, puis propose-moi des exercices pratiques adaptés à mon niveau."
```

Ce message est envoyé comme premier échange utilisateur pour initier la conversation.

---

## Data flow

```
[Clic Pratiquer]
  → delete_error_pattern(db)
  → card.hide() + deleteLater()
  → on_practice_pattern(error_type, rule)          [DashboardPanel → MainWindow]
    → reset_session()
    → switch_tab(0)
    → inject practice message into LLM
    → session starts focused on the rule

[Clic Supprimer]
  → delete_error_pattern(db)
  → card.hide() + deleteLater()
```

---

## UI des boutons

Les boutons s'ajoutent dans le `row` (QHBoxLayout) de `_pattern_card`, après le badge `×N` :

- **Pratiquer** : `background: accent 20%; color: accent; border: 1px solid accent 40%; height: 28; width: 80; font xs bold`
- **Supprimer** : `background: transparent; color: text_muted; border: none; hover: color error + bg #2a1a1a; size: 28×28`

---

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `core/database.py` | + `delete_error_pattern()` |
| `ui/dashboard_panel.py` | + callback, boutons dans `_pattern_card`, 2 handlers |
| `ui/main_window.py` | + câblage + `_on_practice_pattern()` |
