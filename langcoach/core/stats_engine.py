"""
LangCoach — Stats Engine
Parses correction markers from LLM responses, records exchanges/errors to DB,
triggers end-of-session LLM quality analysis.
"""
import json
import logging
import re
import threading
from typing import Optional

from core.database import Database

logger = logging.getLogger(__name__)

# Matches: [type: "original" → "corrected" | rule]
_ERROR_RE = re.compile(r'\[(\w+):\s*"([^"]+)"\s*→\s*"([^"]+)"\s*\|\s*([^\]]+)\]')

LESSON_CATALOG: dict = {
    ("tense", "simple past"): {
        "title": "Simple past — verbes irréguliers",
        "desc": "Les verbes irréguliers ne prennent pas -ed au prétérit.",
        "examples": ["go → went", "have → had", "see → saw", "do → did", "make → made"],
        "tip": "Mémorise les 30 verbes irréguliers les plus courants.",
    },
    ("tense", "present perfect"): {
        "title": "Present perfect vs Simple past",
        "desc": "Present perfect = lien avec le présent. Simple past = passé révolu.",
        "examples": ["I have seen this (still relevant)", "I saw this yesterday (fixed time)"],
        "tip": "Si tu peux dire 'yesterday/last week' → simple past. Sinon → present perfect.",
    },
    ("tense", "past continuous"): {
        "title": "Past continuous",
        "desc": "Action en cours dans le passé, souvent interrompue par une autre.",
        "examples": ["I was cooking when she called", "We were sleeping at midnight"],
        "tip": "Was/were + verb-ing. Donne le contexte (background) d'une action passée.",
    },
    ("grammar", "subject-verb agreement"): {
        "title": "Accord sujet-verbe",
        "desc": "He/she/it → verbe + s au présent simple.",
        "examples": ["She goes (not go)", "He likes (not like)"],
        "tip": "Au présent simple, ajoute toujours -s/-es pour he/she/it.",
    },
    ("grammar", "article"): {
        "title": "Articles : a / an / the",
        "desc": "A/an = première mention ou non-spécifique. The = chose définie.",
        "examples": ["I saw a dog. The dog was big.", "I play tennis (no article for sports)"],
        "tip": "Pas d'article avec les langues, sports, repas, institutions.",
    },
    ("grammar", "conditional"): {
        "title": "Conditionnel — If clauses",
        "desc": "Structures fixes selon le degré de réalité.",
        "examples": [
            "Type 1: If I study, I will pass",
            "Type 2: If I studied, I would pass",
            "Type 3: If I had studied, I would have passed",
        ],
        "tip": "Ne jamais mettre 'would' dans la clause avec 'if'.",
    },
    ("vocabulary", "false friends"): {
        "title": "Faux amis anglais/français",
        "desc": "Mots similaires mais de sens différents.",
        "examples": ["actually = en fait", "eventually = finalement", "sensible = raisonnable"],
        "tip": "Mémorise les 20 faux amis les plus courants.",
    },
    ("vocabulary", "preposition"): {
        "title": "Prépositions de temps et lieu",
        "desc": "In/on/at suivent des règles précises.",
        "examples": ["at 3pm, on Monday, in January", "at the corner, on the street, in the room"],
        "tip": "AT = moment/lieu précis. ON = jour/surface. IN = période/espace fermé.",
    },
    ("syntax", "word order"): {
        "title": "Ordre des mots",
        "desc": "Adverbes de fréquence avant le verbe principal.",
        "examples": ["I always go (not I go always)", "She never eats meat"],
        "tip": "always/never/often/usually → entre sujet et verbe principal.",
    },
    ("grammar", "irregular plural"): {
        "title": "Pluriels irréguliers",
        "desc": "Certains noms ont des pluriels irréguliers.",
        "examples": ["child → children", "person → people", "tooth → teeth", "foot → feet"],
        "tip": "Mémorise les pluriels irréguliers les plus courants.",
    },
}


class StatsEngine:
    def __init__(self, db: Database, llm):
        self._db = db
        self._llm = llm
        self._profile: Optional[dict] = None
        self._session_id: Optional[str] = None
        self._exchange_count = 0
        self._error_count = 0
        self._memory_manager = None

    def set_memory_manager(self, memory_manager):
        self._memory_manager = memory_manager

    def start_session(self, profile: dict, language: str, level: str, topic: str) -> str:
        self._profile = profile
        self._exchange_count = 0
        self._error_count = 0
        self._session_id = self._db.open_session(profile["id"], language, level, topic)
        return self._session_id

    def record_exchange(self, user_text: str, ai_response: str, duration_ms: int):
        if not self._session_id or not self._profile:
            return
        errors = self.parse_errors(ai_response)
        exchange_id = self._db.record_exchange(
            self._session_id, user_text, ai_response, len(errors), duration_ms
        )
        if errors:
            s = self._profile.get("settings", {})
            self._db.record_errors(
                exchange_id, self._session_id, self._profile["id"],
                errors,
                s.get("target_language", "english"),
                s.get("level", "B1"),
            )
        self._exchange_count += 1
        self._error_count += len(errors)
        # Auto-titre après le 1er vrai échange
        if self._exchange_count == 1 and self._llm and self._session_id:
            sid = self._session_id
            threading.Thread(
                target=self._generate_title_async,
                args=(sid, user_text, ai_response),
                daemon=True,
            ).start()

    @staticmethod
    def parse_errors(ai_response: str) -> list:
        """Extract structured correction markers from an AI response."""
        results = []
        for m in _ERROR_RE.finditer(ai_response):
            results.append({
                "error_type": m.group(1).strip().lower(),
                "original":   m.group(2).strip(),
                "corrected":  m.group(3).strip(),
                "rule":       m.group(4).strip().lower(),
            })
        return results

    def _generate_title_async(self, session_id: str, user_text: str, ai_response: str):
        try:
            system = "Tu génères des titres courts et descriptifs en français pour des séances de langue."
            user = (
                f"Génère un titre court (4 à 6 mots maximum) en français résumant cette conversation.\n"
                f"Message de l'apprenant : \"{user_text[:200]}\"\n"
                f"Réponse du coach : \"{ai_response[:200]}\"\n"
                f"Réponds UNIQUEMENT avec le titre, sans ponctuation finale, sans guillemets."
            )
            title = self._llm.chat_oneshot(system, user)
            if title:
                title = title.strip().strip('"\'').strip()[:80]
                self._db.update_session_title(session_id, title)
                logger.info(f"Titre de session généré : {title}")
        except Exception as e:
            logger.warning(f"Génération du titre échouée : {e}")

    def analyze_session_by_id(self, session_id: str, on_done):
        """Analyse à la demande d'une session spécifique. Appelle on_done(score, summary)."""
        if not self._llm:
            on_done(None, "LLM non disponible.")
            return

        def run():
            try:
                session = self._db.get_session(session_id)
                if not session:
                    on_done(None, "Session introuvable.")
                    return
                exchanges = self._db.get_session_exchanges(session_id)
                if not exchanges:
                    on_done(None, "Aucun échange à analyser.")
                    return
                convo = "\n".join(
                    f"Apprenant : {e['user_text']}\nCoach : {e['ai_response'][:200]}"
                    for e in exchanges[:10]
                )
                prompt = (
                    f"Analyse cette séance d'apprentissage. Réponds UNIQUEMENT avec un objet JSON valide.\n\n"
                    f"Séance :\n"
                    f"- Langue : {session['language']} ({session['level']})\n"
                    f"- Sujet : {session['topic']}\n"
                    f"- Échanges : {session['exchange_count']}\n"
                    f"- Erreurs : {session['error_count']}\n\n"
                    f"Résumé de la conversation :\n{convo[:1200]}\n\n"
                    f"Réponds avec UNIQUEMENT ce JSON (pas d'autre texte) :\n"
                    f'{{\"quality_score\": 0.75, \"summary\": \"2-3 phrases en français sur la qualité et les points à améliorer.\"}}\n\n'
                    f"quality_score : de 0.0 (très mauvais) à 1.0 (excellent). summary : en français, bienveillant."
                )
                response = self._llm.chat_oneshot(
                    "Tu es un coach de langue qui analyse des séances. Réponds toujours en JSON valide.",
                    prompt,
                )
                if response:
                    score, summary = self._parse_analysis_response(response)
                    self._db.update_session_summary(session_id, score, summary)
                    on_done(score, summary)
                else:
                    on_done(None, "Analyse non disponible.")
            except Exception as e:
                logger.error(f"Analyse à la demande échouée : {e}")
                on_done(None, f"Erreur : {e}")

        threading.Thread(target=run, daemon=True).start()

    def end_session(self, on_memory_suggestions=None):
        if not self._session_id:
            return
        session_id = self._session_id   # capture before reset
        exchange_count = self._exchange_count
        profile = self._profile
        self._db.close_session(session_id, quality_score=None, summary=None)
        # Launch background LLM analysis if enough data
        if exchange_count >= 3 and self._llm and profile:
            t = threading.Thread(
                target=self._analyze_session_async,
                args=(session_id,),
                daemon=True,
            )
            t.start()
        if self._memory_manager:
            exchanges = self._db.get_session_exchanges(session_id)
            self._memory_manager.extract_suggestions_async(
                profile["id"], session_id, exchanges,
                on_done=on_memory_suggestions,
            )
        self._session_id = None
        self._exchange_count = 0
        self._error_count = 0

    def analyze_and_extract_async(self, on_done):
        """Used by 'Finir et Analyser' button. Calls on_done(score, summary, suggestion_count)."""
        if not self._session_id:
            on_done(None, "Aucune session en cours.", 0)
            return

        session_id = self._session_id
        profile = self._profile
        exchange_count = self._exchange_count

        # Close the session
        self._db.close_session(session_id, quality_score=None, summary=None)
        self._session_id = None
        self._exchange_count = 0
        self._error_count = 0

        if not self._llm or not profile:
            on_done(None, "LLM non disponible.", 0)
            return

        suggestion_count_holder = [0]
        analysis_result = [None, None]
        done_events = [False, False]  # [analysis_done, extraction_done]

        def _check_both_done():
            if all(done_events):
                score, summary = analysis_result
                on_done(score, summary, suggestion_count_holder[0])

        def _on_analysis(score, summary):
            analysis_result[0] = score
            analysis_result[1] = summary
            done_events[0] = True
            _check_both_done()

        def _on_extraction(count):
            suggestion_count_holder[0] = count
            done_events[1] = True
            _check_both_done()

        self.analyze_session_by_id(session_id, _on_analysis)

        if self._memory_manager and exchange_count >= 3:
            exchanges = self._db.get_session_exchanges(session_id)
            self._memory_manager.extract_suggestions_async(
                profile["id"], session_id, exchanges,
                on_done=_on_extraction,
            )
        else:
            done_events[1] = True
            _check_both_done()

    def _analyze_session_async(self, session_id: str):
        session = self._db.get_session(session_id)
        if not session or not self._profile:
            return
        breakdown = self._db.get_error_breakdown(self._profile["id"])
        prompt = self._build_analysis_prompt(session, breakdown)
        try:
            response = self._llm.chat(prompt)
            if response:
                score, summary = self._parse_analysis_response(response)
                self._db.close_session(session_id, quality_score=score, summary=summary)
        except Exception as e:
            logger.error(f"Session analysis failed: {e}")

    def _build_analysis_prompt(self, session: dict, breakdown: list) -> str:
        lines = "\n".join(
            f"  - {e['error_type']}: {e['count']} errors" for e in breakdown[:5]
        ) or "  - No errors recorded"
        dur = round((session.get("ended_at", 0) - session.get("started_at", 0)) / 60000)
        return f"""Analyze this language learning session. Respond ONLY with a valid JSON object, no other text.

Session:
- Language: {session['language']} ({session['level']})
- Topic: {session['topic']}
- Duration: ~{dur} minutes
- Exchanges: {session['exchange_count']}
- Total errors: {session['error_count']}
- Error breakdown:
{lines}

Respond with ONLY this JSON (no extra text):
{{"quality_score": 0.75, "summary": "2-3 sentences in French about quality and main areas to improve."}}

quality_score: 0.0 (very poor) to 1.0 (excellent).
summary: Write in French. Be encouraging but honest."""

    @staticmethod
    def _parse_analysis_response(text: str) -> tuple:
        """Returns (score: float, analysis: dict) with full structured data."""
        empty = {"summary": "", "errors": [], "improvements": [], "vocabulary": []}
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                score = max(0.0, min(1.0, float(data.get("quality_score", 0.5))))
                analysis = {
                    "summary": str(data.get("summary", "")),
                    "errors": data.get("errors", []) if isinstance(data.get("errors"), list) else [],
                    "improvements": data.get("improvements", []) if isinstance(data.get("improvements"), list) else [],
                    "vocabulary": data.get("vocabulary", []) if isinstance(data.get("vocabulary"), list) else [],
                }
                return score, analysis
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return 0.5, empty

    def _build_full_analysis_prompt(self, session: dict, exchanges: list) -> str:
        """Builds the enriched analysis prompt used by 'Analyser' button."""
        convo = "\n".join(
            f"Apprenant : {e['user_text']}\nCoach : {e['ai_response'][:200]}"
            for e in exchanges[:10]
        )
        return (
            "Analyse cette séance d'apprentissage de langue. Réponds UNIQUEMENT avec un objet JSON valide.\n\n"
            f"Séance :\n"
            f"- Langue : {session['language']} ({session['level']})\n"
            f"- Sujet : {session['topic']}\n"
            f"- Échanges : {session['exchange_count']}\n"
            f"- Erreurs détectées : {session['error_count']}\n\n"
            f"Conversation :\n{convo[:2000]}\n\n"
            "Réponds avec UNIQUEMENT ce JSON (pas d'autre texte) :\n"
            '{"quality_score": 0.75, '
            '"summary": "2-3 phrases bienveillantes en français résumant la session.", '
            '"errors": [{"original": "phrase originale", "corrected": "phrase corrigée", "type": "grammar", "rule": "nom de la règle"}], '
            '"improvements": ["Axe d\'amélioration 1 en français", "Axe d\'amélioration 2 en français"], '
            '"vocabulary": [{"word": "mot_anglais", "translation": "traduction française", "example": "exemple en anglais."}]}\n\n'
            "Règles :\n"
            "- quality_score : 0.0 (très mauvais) à 1.0 (excellent)\n"
            "- summary : en français, bienveillant, 2-3 phrases\n"
            "- errors : toutes les erreurs réelles corrigées dans la conversation (max 8), ou [] si aucune\n"
            "- improvements : 2 à 4 axes d'amélioration concrets en français\n"
            "- vocabulary : 3 à 6 mots/expressions importants de la conversation, avec traduction et exemple"
        )

    def get_lesson_cards(self, profile_id: str, threshold: int = 5) -> list:
        """Returns lesson cards for error patterns at or above threshold, ordered by count."""
        patterns = self._db.get_top_patterns(profile_id)
        cards = []
        for p in patterns:
            if p["occurrence_count"] < threshold:
                break
            lesson = LESSON_CATALOG.get((p["error_type"], p["rule"]))
            if not lesson:
                # Partial match on rule keyword
                for (cat, rule_key), l in LESSON_CATALOG.items():
                    if cat == p["error_type"] and rule_key in p["rule"]:
                        lesson = l
                        break
            if lesson:
                cards.append({
                    "pattern": p,
                    "lesson": lesson,
                    "critical": p["occurrence_count"] >= 10,
                })
        return cards

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def exchange_count(self) -> int:
        return self._exchange_count

    @property
    def error_count(self) -> int:
        return self._error_count
