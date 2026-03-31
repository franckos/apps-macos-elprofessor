"""
LangCoach — Memory Manager
CRUD mémoires, sélection contextuelle, suggestions IA asynchrones
"""
import json
import logging
import re
import threading
from typing import Optional

from core.database import Database

logger = logging.getLogger(__name__)

SYSTEM_TAGS = [
    "perso", "famille", "enfants", "couple", "amis", "logement",
    "pro", "travail", "carrière", "business", "finance",
    "santé", "sport", "psycho", "bien-être",
    "loisirs", "voyage", "culture", "technologie", "gastronomie", "lecture",
    "apprentissage", "objectifs", "langue",
]

_MAX_IMPORTANT = 5
_BUDGET_TOKENS = 800
_CHARS_PER_TOKEN = 4   # rough approximation


class MemoryManager:
    def __init__(self, db: Database, llm=None):
        self._db = db
        self._llm = llm

    # ── Selection ─────────────────────────────────────────────

    def get_context_memories(self, profile_id: str) -> list:
        """Returns list of memory dicts to inject into system prompt.

        Rules:
        - Exclude memories tagged 'confidentiel'
        - Always include memories tagged 'important' (max 5)
        - Fill remaining budget (800 tokens) with others sorted by weight DESC, last_used DESC
        """
        all_memories = self._db.list_memories(profile_id)
        if not all_memories:
            return []

        confidential_ids = {
            m["id"] for m in all_memories if "confidentiel" in m["tags"]
        }

        important = [
            m for m in all_memories
            if "important" in m["tags"] and m["id"] not in confidential_ids
        ][:_MAX_IMPORTANT]
        selected_ids = {m["id"] for m in important}
        # Exclude ALL important-tagged items from rest (even overflow beyond cap)
        important_ids = {
            m["id"] for m in all_memories if "important" in m["tags"]
        }

        rest = sorted(
            [
                m for m in all_memories
                if m["id"] not in selected_ids
                and m["id"] not in confidential_ids
                and m["id"] not in important_ids
            ],
            key=lambda m: (-m["weight"], -(m["last_used"] or 0)),
        )

        selected = list(important)
        budget_chars = _BUDGET_TOKENS * _CHARS_PER_TOKEN
        used_chars = sum(len(m["content"]) + 12 for m in selected)

        for m in rest:
            line_len = len(m["content"]) + 12
            if used_chars + line_len > budget_chars:
                break
            selected.append(m)
            used_chars += line_len

        return selected

    def format_memory_block(self, memories: list) -> str:
        """Formats a list of memories for system prompt injection."""
        if not memories:
            return ""
        lines = []
        for m in memories:
            tags = m["tags"] if isinstance(m["tags"], list) else json.loads(m["tags"])
            first_tag = next(
                (t for t in tags if t not in ("important", "confidentiel")), "perso"
            )
            lines.append(f"- [{first_tag}] {m['content']}")
        return "## Ce que tu sais sur ton élève\n" + "\n".join(lines)

    # ── Topic suggestions ──────────────────────────────────────

    def get_topic_suggestions(self, profile_id: str, last_sessions: list) -> list:
        """Returns 0-3 topic suggestion strings from memories (no LLM)."""
        memories = self._db.list_memories(profile_id)
        if not memories:
            return []

        relevant = [
            m for m in memories
            if any(t in ("objectifs", "pro", "travail", "carrière") for t in m["tags"])
        ]

        suggestions = []
        for m in relevant[:3]:
            tags = m["tags"]
            content = m["content"]
            if "objectifs" in tags:
                suggestions.append(f"Continuer sur : {content}")
            else:
                suggestions.append(f"Parler de : {content}")

        return suggestions[:3]

    # ── AI extraction ──────────────────────────────────────────

    def extract_suggestions_async(
        self,
        profile_id: str,
        session_id: str,
        exchanges: list,
        on_done=None,
    ):
        """Launches background AI extraction. on_done(count: int) called when done."""
        if not self._llm or len(exchanges) < 3:
            return
        threading.Thread(
            target=self._extract,
            args=(profile_id, session_id, exchanges, on_done),
            daemon=True,
        ).start()

    def _extract(self, profile_id: str, session_id: str, exchanges: list, on_done):
        try:
            convo = "\n".join(
                f"Apprenant: {e['user_text']}\nCoach: {e['ai_response'][:150]}"
                for e in exchanges[:10]
            )
            system = (
                "Tu extrais des faits mémorables sur un apprenant de langue. "
                "Réponds uniquement en JSON valide."
            )
            user = (
                "Analyse cette conversation et extrais 1 à 3 faits mémorables sur l'utilisateur.\n"
                "Chaque fait doit être court (max 120 chars), factuel, et utile pour personnaliser "
                "les prochaines sessions.\n\n"
                "Format JSON strict :\n"
                '[{"content": "...", "tags": ["tag1"]}, ...]\n\n'
                "Retourne UNIQUEMENT le JSON, rien d'autre. Si rien de mémorable, retourne [].\n\n"
                f"Conversation :\n{convo[:1500]}"
            )
            response = self._llm.chat_oneshot(system, user)
            if not response:
                return
            suggestions = self._parse_suggestions(response)
            count = 0
            for s in suggestions:
                content = str(s.get("content", ""))[:120]
                tags = s.get("tags", [])
                if content:
                    self._db.create_memory_suggestion(profile_id, session_id, content, tags)
                    count += 1
            if on_done:
                on_done(count)
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            if on_done:
                on_done(0)

    def _parse_suggestions(self, text: str) -> list:
        """Extracts JSON array from LLM response (tolerant of surrounding text)."""
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    # ── Weight update ──────────────────────────────────────────

    def update_weights_after_injection(self, memories: list, ai_response: str):
        """Updates last_used for all injected memories; bumps weight if cited."""
        for m in memories:
            self._db.update_memory_last_used(m["id"])
            keywords = [w for w in m["content"].lower().split()[:4] if len(w) > 3]
            if keywords and all(kw in ai_response.lower() for kw in keywords[:2]):
                self._db.update_memory_weight(m["id"], increment=0.1)
