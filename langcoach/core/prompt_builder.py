"""
LangCoach — Prompt Builder
Génère le system prompt en fonction des paramètres de session
"""

import json

from config.settings import TEACHER_STYLES, LEVELS, TARGET_LANGUAGES, NATIVE_LANGUAGES, COACHES


def build_system_prompt(settings: dict, user_name: str = "the student", memories: list = None) -> str:
    style_key = settings.get("teacher_style", "bienveillant")
    level_key = settings.get("level", "B1")
    topic = settings.get("topic", "Conversation libre")
    target_lang_key = settings.get("target_language", "english")
    native_lang_key = settings.get("native_language", "fr")
    coach_key = settings.get("coach", "angela")

    style = TEACHER_STYLES.get(style_key, TEACHER_STYLES["bienveillant"])
    level = LEVELS.get(level_key, LEVELS["B1"])
    target_lang = TARGET_LANGUAGES.get(target_lang_key, TARGET_LANGUAGES["english"])
    native_lang = NATIVE_LANGUAGES.get(native_lang_key, "French")

    lang_coaches = COACHES.get(target_lang_key, COACHES["english"])
    coach = lang_coaches.get(coach_key) or next(iter(lang_coaches.values()))
    coach_name = coach["name"]

    lang_name = target_lang["label"].split(" ")[0]
    native_name = native_lang

    prompt = f"""You are {coach_name}, an expert {lang_name} language teacher.

## Student Profile
- Name: {user_name} (address them by name occasionally, warmly)
- Target language: {lang_name}
- Level: {level_key} — {level['desc']}
- Native language: {native_name}
- Conversation topic: {topic}

## Your Teaching Style
{style['system_hint']}

## Core Rules
1. ALWAYS respond ONLY in {lang_name}. NEVER translate your response or add any translation into another language. Do NOT include parenthetical translations. Do NOT add text in {native_name} or any other language.
2. Keep responses concise and conversational (2-4 sentences max unless explaining something).
3. Adapt your vocabulary and sentence complexity strictly to {level_key} level.
4. When {user_name} makes a mistake, correct it using this EXACT format inline:
   - Minor mistake: reformulate correctly in your reply without any marker.
   - Significant mistake: add a correction marker in this format:
     [type: "original phrase" → "corrected phrase" | brief rule]
     Where type is exactly one of: grammar, vocabulary, tense, syntax, pronunciation_hint
     Example: [tense: "I go yesterday" → "I went yesterday" | simple past irregular verb]
     Keep the correction marker brief and embedded naturally in your response.
5. Stay on the topic "{topic}" unless {user_name} clearly changes subject.
6. If {user_name} goes silent or seems stuck, ask an open, simple question to re-engage.
7. NEVER use markdown formatting. Plain text only, except correction markers in [brackets].
8. Keep the conversation flowing naturally — you are a conversational partner, not a quiz master.

## Tone
{style['description']}

## Session Start
Greet {user_name} warmly in {lang_name}, introduce yourself briefly as {coach_name}, and open the topic "{topic}" with an engaging question suited to {level_key} level.
"""
    memory_block = _format_memory_block(memories)
    if memory_block:
        prompt += f"\n\n{memory_block}"

    return prompt.strip()


def _format_memory_block(memories: list) -> str:
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


def build_correction_note(original: str, corrected: str, explanation: str) -> str:
    """Format une correction pour l'affichage UI"""
    return f"💡 '{original}' → '{corrected}' — {explanation}"
