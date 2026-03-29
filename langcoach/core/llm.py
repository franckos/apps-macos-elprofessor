"""
LangCoach — LLM Engine
Interface avec Ollama (local) ou Mistral API (fallback cloud)
"""

import logging
import threading
from typing import Callable, Optional, Generator

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    Gère les appels au LLM.
    Provider: "ollama" (local, gratuit) ou "mistral_api" (cloud, payant)
    """

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("provider", "ollama")
        self.model = config.get("model", "llama3.1:8b")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 300)
        self._conversation_history = []
        self._system_prompt = ""
        self._lock = threading.Lock()

    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt
        # Do NOT clear history here — use reset_conversation() for explicit resets.
        # Settings changes (level, style, topic) update the prompt but preserve context.

    def reset_conversation(self):
        self._conversation_history = []

    def chat(
        self,
        user_message: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Envoie un message et retourne la réponse.
        Si on_token est fourni, stream les tokens en temps réel.
        Si on_done est fourni, callback en fin de génération.
        """
        with self._lock:
            self._conversation_history.append({
                "role": "user",
                "content": user_message,
            })

        if self.provider == "ollama":
            return self._chat_ollama(on_token, on_done)
        elif self.provider == "mistral_api":
            return self._chat_mistral_api(on_token, on_done)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

    def chat_async(
        self,
        user_message: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
    ):
        """Version asynchrone (thread)"""
        t = threading.Thread(
            target=self.chat,
            args=(user_message, on_token, on_done),
            daemon=True,
        )
        t.start()

    def _chat_ollama(
        self,
        on_token: Optional[Callable[[str], None]],
        on_done: Optional[Callable[[str], None]],
    ) -> Optional[str]:
        try:
            import ollama

            messages = []
            if self._system_prompt:
                messages.append({"role": "system", "content": self._system_prompt})
            messages.extend(self._conversation_history)

            full_response = ""

            if on_token:
                # Mode streaming
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    options={
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                )
                for chunk in stream:
                    token = chunk["message"]["content"]
                    full_response += token
                    on_token(token)
            else:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                )
                full_response = response["message"]["content"]

            with self._lock:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": full_response,
                })

            if on_done:
                on_done(full_response)

            return full_response

        except ImportError:
            logger.error("ollama package not installed. Run: pip install ollama")
            msg = "[Ollama not installed. Run: pip install ollama]"
            if on_done:
                on_done(msg)
            return msg
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            msg = f"[LLM error: {str(e)}]"
            if on_done:
                on_done(msg)
            return msg

    def _chat_mistral_api(
        self,
        on_token: Optional[Callable[[str], None]],
        on_done: Optional[Callable[[str], None]],
    ) -> Optional[str]:
        """Fallback Mistral API cloud"""
        try:
            from mistralai import Mistral
            import os

            api_key = os.environ.get("MISTRAL_API_KEY", "")
            if not api_key:
                msg = "[MISTRAL_API_KEY not set]"
                if on_done:
                    on_done(msg)
                return msg

            client = Mistral(api_key=api_key)
            messages = []
            if self._system_prompt:
                messages.append({"role": "system", "content": self._system_prompt})
            messages.extend(self._conversation_history)

            response = client.chat.complete(
                model="mistral-small-latest",
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            full_response = response.choices[0].message.content

            with self._lock:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": full_response,
                })

            if on_done:
                on_done(full_response)
            return full_response

        except Exception as e:
            logger.error(f"Mistral API error: {e}")
            msg = f"[API error: {str(e)}]"
            if on_done:
                on_done(msg)
            return msg

    def get_history_length(self) -> int:
        return len(self._conversation_history)

    def trim_history(self, keep_last: int = 20):
        """Évite les context windows trop longs"""
        if len(self._conversation_history) > keep_last:
            self._conversation_history = self._conversation_history[-keep_last:]
