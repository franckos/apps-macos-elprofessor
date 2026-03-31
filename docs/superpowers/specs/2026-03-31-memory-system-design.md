# Système de Mémoire — Design Spec

**Date:** 2026-03-31
**Project:** El Profesor / LangCoach (MacOS, PyQt6)
**Status:** Approved

---

## 1. Vue d'ensemble

Ajouter un système de mini-mémoires liées au profil utilisateur. Ces mémoires capturent des faits personnels et professionnels sur l'utilisateur pour personnaliser les sessions de coaching. Elles sont créées manuellement ou suggérées par l'IA après analyse des discussions. À chaque session, les mémoires pertinentes sont injectées dans le system prompt du LLM local de façon compacte et contrôlée en tokens.

---

## 2. Structure de données

### 2.1 Table `memories`

```sql
CREATE TABLE memories (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,              -- texte court, max 120 chars
    tags        TEXT NOT NULL DEFAULT '[]', -- JSON array ex: ["pro","objectifs"]
    source      TEXT NOT NULL DEFAULT 'manual', -- 'manual' | 'ai'
    weight      REAL NOT NULL DEFAULT 1.0,  -- score de priorité d'injection
    last_used   INTEGER,                    -- timestamp ms, mis à jour à chaque injection
    created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_profile ON memories(profile_id);
```

### 2.2 Table `memory_suggestions`

Stocke les suggestions IA en attente de validation par l'utilisateur.

```sql
CREATE TABLE memory_suggestions (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  INTEGER NOT NULL
);
```

### 2.3 Taxonomie des tags

**Tags système (22) :**

| Domaine | Tags |
|---------|------|
| Vie personnelle | `perso`, `famille`, `enfants`, `couple`, `amis`, `logement` |
| Vie professionnelle | `pro`, `travail`, `carrière`, `business`, `finance` |
| Santé & bien-être | `santé`, `sport`, `psycho`, `bien-être` |
| Centres d'intérêt | `loisirs`, `voyage`, `culture`, `technologie`, `gastronomie`, `lecture` |
| Apprentissage | `apprentissage`, `objectifs`, `langue` |

**Tags de comportement d'injection :**
- `important` — mémoire toujours injectée, quelle que soit la session (max 5)
- `confidentiel` — visible dans l'UI mais jamais injectée dans le prompt LLM

**Tags custom :** l'utilisateur peut ajouter des tags libres en complément.

---

## 3. Injection dans le prompt

### 3.1 Algorithme de sélection

`MemoryManager.get_context_memories(profile_id, topic, language) -> list[Memory]`

1. **Toujours incluses :** mémoires avec tag `important` (max 5)
2. **Exclues :** mémoires avec tag `confidentiel`
3. **Tri des restantes par priorité :** `weight DESC`, `last_used DESC`
4. **Budget dynamique :** on ajoute des mémoires jusqu'à atteindre 800 tokens restants dans le system prompt

### 3.2 Format d'injection

Ajouté au system prompt, après les instructions du coach :

```
## Ce que tu sais sur ton élève
- [famille] A deux enfants (Emma et Lucas)
- [pro] Travaille comme développeur backend chez une startup
- [objectifs] Prépare un entretien d'embauche en anglais
- [psycho] Timide à l'oral, a besoin d'encouragements
```

Chaque ligne = 1 mémoire. Format : `[tag principal] contenu`.

### 3.3 Mise à jour du weight

Après chaque injection, `last_used` est mis à jour. Le `weight` peut être incrémenté (+0.1) si la mémoire est citée dans la réponse du LLM (détection simple par mots-clés du contenu).

---

## 4. Extraction automatique par l'IA

### 4.1 Déclenchement

- **Automatique :** à la fin de chaque session avec ≥ 3 échanges (même thread background que l'analyse qualité)
- **Manuel :** bouton **"Finir et Analyser"** dans l'UI de session

### 4.2 Bouton "Finir et Analyser"

Remplace le simple reset. Déclenche en parallèle :
- Clôture propre de la session
- Analyse qualité (score + résumé)
- Extraction de mémoires

Un indicateur de chargement est affiché pendant l'analyse (~5-15 secondes selon le LLM local).

Une fois terminé, une modale récap s'affiche avec :
- Score qualité de la session
- Résumé de la discussion
- Mémoires suggérées à valider (si > 0)

L'UI conserve aussi un bouton **"Nouvelle session"** pour un reset rapide sans analyse.

### 4.3 Mini-prompt d'extraction

Envoyé au LLM après la session (non-bloquant, background thread) :

```
Analyse cette conversation et extrais 1 à 3 faits mémorables sur l'utilisateur.
Chaque fait doit être court (max 120 chars), factuel, et utile pour personnaliser
les prochaines sessions.

Format JSON strict :
[
  {"content": "Prépare un entretien chez Google en juin", "tags": ["pro", "objectifs"]},
  {"content": "A peur de faire des erreurs devant les autres", "tags": ["psycho"]}
]

Retourne UNIQUEMENT le JSON, rien d'autre. Si rien de mémorable, retourne [].
```

Les suggestions sont stockées dans `memory_suggestions` jusqu'à validation.

### 4.4 Notification et validation

- Notification discrète dans l'UI : "💡 2 nouvelles mémoires suggérées"
- Modale de validation : pour chaque suggestion → **Accepter** / **Éditer** / **Rejeter**
- Les mémoires acceptées sont insérées dans `memories` avec `source='ai'`
- Les suggestions rejetées sont supprimées de `memory_suggestions`

---

## 5. Écran de démarrage de session

Avant de démarrer une session, l'utilisateur voit un écran de choix de thème en deux blocs.

### 5.1 Bloc "Thèmes issus de la mémoire"

Affiché uniquement si des mémoires existent. Algorithme local (pas de LLM) :
- Croiser les mémoires récentes avec tags `objectifs` ou `pro`
- Croiser avec le topic des 2-3 dernières sessions
- Générer 2-3 suggestions de thèmes sous forme de phrases

Exemples :
- "Reprendre la préparation de ton entretien chez Google"
- "Parler de tes projets professionnels"

### 5.2 Bloc "Thèmes par défaut"

Liste fixe de thèmes génériques (Discussion libre, Actualités, Voyage, Travail…).

### 5.3 Comportement

- Cliquer sur un thème → topic pré-rempli, session démarre
- L'utilisateur peut toujours saisir un thème libre
- Si aucune mémoire → seul le bloc défaut est affiché

---

## 6. UI de gestion des mémoires

### 6.1 Onglet "Mémoires" dans le profil

Nouvel onglet dans le panneau settings du profil (`settings_panel.py`).

**Vue principale :**
- Mémoires groupées par tag principal (accordéon)
- Chaque mémoire : texte + badges tags + icône source (✍️ manuel / 🤖 IA) + bouton supprimer
- Badge `📌` pour tag `important`, badge `🔒` pour tag `confidentiel`

**Ajout manuel :**
- Bouton **"+ Ajouter une mémoire"** → formulaire inline
- Champ texte (max 120 chars, compteur affiché)
- Sélecteur de tags : chips cliquables (tags système) + saisie libre pour tags custom

**Suggestions en attente :**
- Bandeau en haut si suggestions IA en attente : "💡 3 mémoires suggérées — Valider"
- Clic → modale de validation (Accepter / Éditer / Rejeter)

---

## 7. Architecture

### 7.1 Nouveaux fichiers

| Fichier | Responsabilité |
|---------|---------------|
| `core/memory_manager.py` | CRUD mémoires, algorithme de sélection/filtrage, extraction des suggestions IA |
| `ui/memory_panel.py` | Onglet "Mémoires" dans les settings du profil |

### 7.2 Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `core/database.py` | Ajout tables `memories` et `memory_suggestions`, méthodes CRUD correspondantes |
| `core/prompt_builder.py` | Injection du bloc mémoire dans le system prompt |
| `core/stats_engine.py` | Appel `memory_manager.extract_suggestions()` en fin de session |
| `ui/settings_panel.py` | Ajout onglet "Mémoires" (`MemoryPanel`) |
| `ui/main_window.py` | Bouton "Finir et Analyser" + "Nouvelle session", écran de choix de thème |

### 7.3 Flux de données

```
[Démarrage session]
  → Écran thèmes : MemoryManager.get_topic_suggestions(profile_id)
  → Utilisateur choisit un thème → session démarre

[Pendant la session]
  → MemoryManager.get_context_memories(profile_id, topic)
  → Mémoires injectées dans system prompt via PromptBuilder

[Fin de session — bouton "Finir et Analyser" ou auto]
  → StatsEngine.end_session()
    → Analyse qualité (LLM, background)
    → MemoryManager.extract_suggestions(session_id, exchanges) (LLM, background)
      → Stockage dans memory_suggestions
      → Notification UI "💡 N mémoires suggérées"

[Validation mémoires]
  → Modale dans settings profil onglet "Mémoires"
  → Accepter → INSERT INTO memories
  → Rejeter → DELETE FROM memory_suggestions
```

---

## 8. Hors scope

- Recherche sémantique / embeddings dans les mémoires
- Synchronisation cloud des mémoires
- Export/import des mémoires
- Mémoires partagées entre profils

---

## 9. Questions résolues

| Question | Décision |
|----------|----------|
| Qui crée les mémoires ? | Les deux : manuel + suggestions IA à valider |
| Budget tokens | Dynamique, max 800 tokens, filtrage par pertinence |
| Extraction auto | Fin de session (≥ 3 échanges) + bouton "Finir et Analyser" |
| Validation suggestions | Modale Accepter / Éditer / Rejeter |
| UI admin | Onglet "Mémoires" dans le panneau profil |
| Tags | 22 tags système + custom, `important` (épinglé) et `confidentiel` (jamais injecté) |
| Démarrage session | Écran thèmes : bloc mémoire + bloc défauts |
