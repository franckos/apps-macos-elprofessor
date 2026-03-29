"""
LangCoach — Reachy Mini Bridge
Stub désactivé par défaut. Activé quand REACHY["enabled"] = True dans settings.py

Protocol:
  → {"type": "transcript", "text": "...", "role": "user"|"assistant"}
  → {"type": "speaking", "active": true|false}
  → {"type": "session", "action": "start"|"stop", "settings": {...}}
"""

import json
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ReachyBridge:
    """
    WebSocket bridge vers Reachy Mini.
    Envoie les transcriptions et états audio pour synchroniser
    les animations et comportements du robot.
    """

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self._ws = None
        self._connected = False
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None

    def start(self):
        if not self.enabled:
            logger.info("Reachy bridge disabled (set REACHY['enabled']=True to activate)")
            return

        self._stop_event.clear()
        self._reconnect_thread = threading.Thread(
            target=self._connect_loop, daemon=True
        )
        self._reconnect_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def send_transcript(self, text: str, role: str = "assistant"):
        self._send({"type": "transcript", "text": text, "role": role})

    def send_speaking(self, active: bool):
        self._send({"type": "speaking", "active": active})

    def send_session_start(self, settings: dict):
        self._send({"type": "session", "action": "start", "settings": settings})

    def send_session_stop(self):
        self._send({"type": "session", "action": "stop"})

    def _send(self, payload: dict):
        if not self.enabled or not self._connected or not self._ws:
            return
        try:
            self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.warning(f"Reachy send error: {e}")
            self._connected = False

    def _connect_loop(self):
        import time
        interval = self.config.get("reconnect_interval", 5)

        while not self._stop_event.is_set():
            try:
                import websocket

                host = self.config.get("host", "localhost")
                port = self.config.get("port", 8765)
                url = f"ws://{host}:{port}"

                logger.info(f"Connecting to Reachy at {url}...")
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_close=self._on_close,
                    on_error=self._on_error,
                )
                self._ws.run_forever()

            except ImportError:
                logger.warning("websocket-client not installed. pip install websocket-client")
                break
            except Exception as e:
                logger.warning(f"Reachy connection failed: {e}")

            if not self._stop_event.is_set():
                logger.info(f"Retrying in {interval}s...")
                time.sleep(interval)

    def _on_open(self, ws):
        self._connected = True
        logger.info("Reachy connected ✓")
        if self.on_connected:
            self.on_connected()

    def _on_close(self, ws, code, msg):
        self._connected = False
        logger.info("Reachy disconnected")
        if self.on_disconnected:
            self.on_disconnected()

    def _on_error(self, ws, error):
        logger.warning(f"Reachy WS error: {error}")
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.enabled
