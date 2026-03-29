# LangCoach Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 9 bugs identified in code review that prevent correct operation of LangCoach (VAD broken, Spanish STT broken, conversation history reset on settings change, race conditions, error strings read aloud, keyboard shortcuts firing inside text input, housekeeping).

**Architecture:** All fixes are isolated to their respective files. No new files needed. No architectural changes. Each fix is independent and can be verified by running the app manually.

**Tech Stack:** Python 3.9+, PyQt6, transformers (Whisper), Kokoro TTS, pyttsx3, Ollama

> **Note on TDD:** This project has no test infrastructure. Each task includes a manual verification step instead of automated tests.

---

## Files Modified

- `langcoach/config/settings.py` — Fix VAD threshold (I3)
- `langcoach/core/stt.py` — Fix STT language (C2) + wire model from config (C1)
- `langcoach/core/llm.py` — Fix history cleared on settings change (I1) + error sentinel strings (I2)
- `langcoach/core/session.py` — Fix trim_history race condition (C4) + handle error responses from LLM (I2)
- `langcoach/core/tts.py` — Fix stop() state race (C3)
- `langcoach/ui/main_window.py` — Fix keyboard shortcuts firing in text input (M10)
- `langcoach/requirements.txt` — Remove pathlib2 (M5), pin version ranges (M8)
- `langcoach/main.py` — Fix font loading counter (M7)

---

## Task 1: Fix VAD threshold (I3)

**File:** `langcoach/config/settings.py:44`

The VAD loop compares microphone RMS values (typically 0.001–0.05 for speech) against `vad_threshold`. With the current value of `0.5`, VAD will never trigger because a real microphone never reaches that amplitude. The default in the VAD loop code (`0.02`) is the correct value — but it's never reached because the config always provides `0.5`.

- [ ] **Step 1: Fix the threshold in settings.py**

Change line 44 in `langcoach/config/settings.py`:

```python
# Before
"vad_threshold":    0.5,       # Sensibilité VAD (0.0 → 1.0)

# After
"vad_threshold":    0.02,      # Sensibilité VAD RMS (0.001 silencieux → 0.05 parole normale)
```

- [ ] **Step 2: Manual verification**

Run the app, press "Auto" (VAD mode), speak normally. The status orb should switch to "Listening" and the waveform should animate when speaking. Before the fix, nothing happens.

---

## Task 2: Fix STT language — Spanish support (C2)

**File:** `langcoach/core/stt.py:43-48`

The Whisper pipeline has `generate_kwargs={"language": "english"}` hardcoded. This must be derived from `settings["target_language"]`. The `STTEngine` receives `settings` in its constructor — we just need to read it at transcription time.

The `TARGET_LANGUAGES` dict in `settings.py` has a `"code"` key (`"en"`, `"es"`) — use that to set the Whisper language.

- [ ] **Step 1: Store language code on STTEngine and use it in initialize()**

Replace lines 43-48 in `langcoach/core/stt.py`:

```python
# Before
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=device,
                generate_kwargs={"language": "english"},
            )

# After
            from config.settings import TARGET_LANGUAGES
            target_lang_key = self.settings.get("target_language", "english")
            lang_info = TARGET_LANGUAGES.get(target_lang_key, TARGET_LANGUAGES["english"])
            # Whisper uses full language names: "english", "spanish", etc.
            whisper_lang = lang_info.get("label", "English 🇬🇧").split(" ")[0].lower()

            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=device,
                generate_kwargs={"language": whisper_lang},
            )
```

- [ ] **Step 2: Manual verification**

Change the language to Spanish in settings, press "Auto" or hold Space and speak Spanish. The transcript should now be in Spanish (not garbled English).

---

## Task 3: Fix STT model wiring from config (C1)

**File:** `langcoach/core/stt.py:37-38`

The model name is hardcoded as `"openai/whisper-small"` and the config `MODELS["stt"]` is ignored. We need to pass `MODELS["stt"]` to `STTEngine` and read it in `initialize()`.

Looking at `session.py:69`: `STTEngine(settings=self.settings, ...)` — `self.settings` is the user preferences dict (teacher style, level, etc.), NOT the model config. We need to also pass the model config. The cleanest fix without changing the session interface is to import `MODELS` directly inside `STTEngine.initialize()`.

- [ ] **Step 1: Read model name from MODELS config in STTEngine.initialize()**

Replace lines 37-38 in `langcoach/core/stt.py`:

```python
# Before
            model_name = "openai/whisper-small"  # Fallback stable
            # TODO: Remplacer par mistralai/Voxtral-Transcribe-Mini quand dispo sur HF

# After
            from config.settings import MODELS as _MODELS
            stt_cfg = _MODELS.get("stt", {})
            model_name = stt_cfg.get("fallback", "openai/whisper-small")
            # When Voxtral becomes available on HuggingFace, set MODELS["stt"]["name"]
            # and the code below will try it first:
            # primary = stt_cfg.get("name")
            # model_name = primary if primary and "Voxtral" not in primary else stt_cfg.get("fallback", "openai/whisper-small")
```

- [ ] **Step 2: Manual verification**

In `config/settings.py`, `MODELS["stt"]["fallback"]` is `"openai/whisper-small"`. After the change, the app should load exactly the same model as before. Check the log: `Loading STT model on mps...` then `STT model loaded ✓`.

---

## Task 4: Fix set_system_prompt clearing history (I1)

**File:** `langcoach/core/llm.py:29-31`

`set_system_prompt()` is called by `session.update_settings()` every time the user changes any setting. Currently it wipes `_conversation_history = []`, which resets the entire conversation. The history should only be cleared on explicit `reset_conversation()` calls.

- [ ] **Step 1: Remove history clear from set_system_prompt()**

Replace lines 29-31 in `langcoach/core/llm.py`:

```python
# Before
    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt
        self._conversation_history = []

# After
    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt
        # Do NOT clear history here — use reset_conversation() for explicit resets.
        # Settings changes (level, style, topic) update the prompt but preserve context.
```

- [ ] **Step 2: Manual verification**

Start the app, have a short conversation (2-3 exchanges), then open Settings and change the teacher style or level. The conversation history should still be visible and the AI should continue the conversation, not restart with a greeting.

---

## Task 5: Fix trim_history race condition (C4)

**File:** `langcoach/core/session.py:192-193`

`chat_async()` launches a thread, then `trim_history()` is called immediately after on the caller thread. This means trim can run while the LLM thread is still appending the assistant's response to `_conversation_history`, silently dropping messages.

Fix: move `trim_history()` into the `on_done` callback, so it runs after the assistant response has been fully appended.

- [ ] **Step 1: Move trim_history into on_done callback**

Replace lines 169-193 in `langcoach/core/session.py`:

```python
    def _get_ai_response(self, user_text: str, is_greeting: bool = False):
        """Appelle le LLM et joue la réponse TTS"""
        self._set_state(SessionState.PROCESSING)

        full_response = []

        def on_token(token: str):
            full_response.append(token)
            if self.on_assistant_token:
                self.on_assistant_token(token)

        def on_done(text: str):
            self._llm.trim_history(keep_last=30)
            if self.on_assistant_done:
                self.on_assistant_done(text)
            if self._reachy:
                self._reachy.send_transcript(text, role="assistant")
            self._speak(text)

        if is_greeting:
            prompt = "[Start the session with your opening greeting]"
        else:
            prompt = user_text

        self._llm.chat_async(prompt, on_token=on_token, on_done=on_done)
```

- [ ] **Step 2: Manual verification**

Have a long conversation (10+ exchanges). The AI should maintain context throughout. No messages should be dropped mid-response.

---

## Task 6: Fix TTS stop() state race (C3)

**File:** `langcoach/core/tts.py:84-106, 147-153`

Two issues:
1. `speak()` has no guard — if called while another thread holds the lock, the new thread waits silently, potentially queuing two TTS outputs.
2. `stop()` interrupts audio but can't be called from `_speak_sync` because the lock is held. After `sd.stop()`, `sd.wait()` returns immediately in `_speak_sync`, so `_speaking` IS set to False in `finally`. This is actually correct.

The real fix needed: add a `_stop_requested` flag so `stop()` can signal intent immediately, and check it before playing each Kokoro chunk. Also add a guard in `speak()` to skip queuing if already speaking and stop was just called.

- [ ] **Step 1: Add _stop_requested flag and guard in speak()**

Replace the `TTSEngine` class methods in `langcoach/core/tts.py`:

```python
    def __init__(self, config: dict):
        self.config = config
        self._pipeline = None
        self._fallback = None
        self._initialized = False
        self._provider = "none"
        self._speaking = False
        self._stop_requested = False
        self._lock = threading.Lock()

    def speak(
        self,
        text: str,
        on_start: Optional[Callable] = None,
        on_done: Optional[Callable] = None,
        blocking: bool = False,
    ):
        """Synthétise et joue le texte"""
        if not self._initialized:
            logger.warning("TTS not initialized")
            if on_done:
                on_done()
            return

        self._stop_requested = False

        if blocking:
            self._speak_sync(text, on_start, on_done)
        else:
            t = threading.Thread(
                target=self._speak_sync,
                args=(text, on_start, on_done),
                daemon=True,
            )
            t.start()

    def _speak_kokoro(self, text: str):
        import sounddevice as sd
        import numpy as np

        generator = self._pipeline(text, voice="af_heart", speed=self.config.get("speed", 1.0))
        for _, _, audio in generator:
            if self._stop_requested:
                break
            if audio is not None:
                sd.play(audio, samplerate=24000)
                sd.wait()

    def stop(self):
        """Interrompt la synthèse en cours"""
        self._stop_requested = True
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
```

- [ ] **Step 2: Manual verification**

While the AI is speaking, press Esc or click the stop button. Speech should stop immediately without a queued second response playing afterward.

---

## Task 7: Fix error strings being sent to TTS (I2)

**Files:** `langcoach/core/llm.py:127-138`, `langcoach/core/session.py:180-185`

Error messages like `"[LLM error: connection refused]"` are passed to `on_done` and then spoken aloud by TTS. Fix: use a tuple `(text, is_error)` or check for error sentinel in `on_done` in session.py.

The simplest fix: in `session.py._get_ai_response.on_done`, check if the text starts with `[` and ends with `]` (the current error format) and route to `on_error` instead of `_speak()`.

- [ ] **Step 1: Filter error responses in on_done callback**

Replace the `on_done` function inside `_get_ai_response` in `langcoach/core/session.py` (the full method was already shown in Task 5 — apply this change on top of Task 5's version):

```python
        def on_done(text: str):
            self._llm.trim_history(keep_last=30)
            # Detect error sentinel strings returned by LLMEngine
            is_error = text.startswith("[") and text.endswith("]")
            if is_error:
                logger.error(f"LLM returned error: {text}")
                self._set_state(SessionState.ERROR)
                if self.on_error:
                    self.on_error(text)
                return
            if self.on_assistant_done:
                self.on_assistant_done(text)
            if self._reachy:
                self._reachy.send_transcript(text, role="assistant")
            self._speak(text)
```

- [ ] **Step 2: Manual verification**

Stop Ollama (`pkill ollama`), then try to chat. The UI should show a toast error message. TTS should NOT speak the error string. Then restart Ollama and verify normal operation resumes.

---

## Task 8: Fix keyboard shortcuts firing inside text input (M10)

**File:** `langcoach/ui/main_window.py:465-469`

`QShortcut` for `R`, `S`, `A` keys fires even when the text input has focus. Typing "Reset" in the chat would trigger "New session" + "Settings". Fix: use `Qt.ShortcutContext.WidgetWithChildrenShortcut` or set the shortcut context to `ActiveWindow` and add focus checks.

The cleanest fix for PyQt6 is to use `Qt.ShortcutContext.WindowShortcut` (the default) with a focus check lambda that only fires when the text input does NOT have focus.

- [ ] **Step 1: Add focus guard to keyboard shortcuts**

Replace lines 465-469 in `langcoach/ui/main_window.py`:

```python
    def _setup_shortcuts(self):
        def _if_not_typing(action):
            """Only trigger shortcut when text input doesn't have focus"""
            if not self._text_input.hasFocus():
                action()

        QShortcut(QKeySequence("R"), self, lambda: _if_not_typing(self._on_reset))
        QShortcut(QKeySequence("S"), self, lambda: _if_not_typing(self._toggle_settings))
        QShortcut(QKeySequence("A"), self, lambda: _if_not_typing(self._btn_vad.click))
        QShortcut(QKeySequence("Escape"), self, self._on_stop)
```

- [ ] **Step 2: Manual verification**

Click into the text input and type "Reset session". The session should NOT reset. Click outside the text input and press `R` — the session SHOULD reset.

---

## Task 9: Housekeeping (M5, M7, M8)

### M5: Remove pathlib2 from requirements.txt

**File:** `langcoach/requirements.txt`

`pathlib2` is a Python 2 backport. Unused on Python 3.9+.

- [ ] **Step 1: Remove pathlib2**

Find and remove the line `pathlib2` from `langcoach/requirements.txt`.

### M7: Fix font loading counter

**File:** `langcoach/main.py`

`QFontDatabase.addApplicationFont` returns `-1` on failure, but the counter increments regardless. Fix: only count successful loads.

- [ ] **Step 2: Fix font counter**

Find the font loading loop in `langcoach/main.py` and change:

```python
# Before (approximate — read the exact lines before editing)
                QFontDatabase.addApplicationFont(path)
                loaded += 1

# After
                if QFontDatabase.addApplicationFont(path) >= 0:
                    loaded += 1
```

### M8: Add upper-bound version pins to requirements.txt

**File:** `langcoach/requirements.txt`

- [ ] **Step 3: Pin major version bounds on transformers and torch**

In `langcoach/requirements.txt`, find:
```
transformers>=4.40.0
torch>=2.2.0
```

Replace with:
```
transformers>=4.40.0,<5.0.0
torch>=2.2.0,<3.0.0
```

- [ ] **Step 4: Manual verification**

Run `pip install -r langcoach/requirements.txt` in a fresh venv. Verify it resolves without conflicts and the app starts normally.

---

## Summary Checklist

| Task | Bug | File | Impact |
|------|-----|------|--------|
| 1 | I3: VAD threshold 0.5 → 0.02 | config/settings.py | VAD mode completely broken |
| 2 | C2: STT language hardcoded English | core/stt.py | Spanish users get garbled transcripts |
| 3 | C1: STT model name from config | core/stt.py | Voxtral migration path broken |
| 4 | I1: set_system_prompt clears history | core/llm.py | Conversation reset on every settings change |
| 5 | C4: trim_history race condition | core/session.py | Messages dropped mid-response |
| 6 | C3: TTS stop() state | core/tts.py | Two voices can overlap |
| 7 | I2: Error strings read aloud | core/session.py | TTS speaks "[LLM error: ...]" |
| 8 | M10: Shortcuts fire in text input | ui/main_window.py | Typing R/S/A triggers actions |
| 9 | M5/M7/M8: Housekeeping | requirements.txt, main.py | Minor reliability |
