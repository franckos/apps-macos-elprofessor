"""
LangCoach — Entry Point
Lance l'application desktop
"""

import sys
import os
import logging

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Apple Silicon MPS acceleration pour PyTorch
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# Résolution HiDPI
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def main():
    try:
        from PyQt6.QtWidgets import QApplication, QSplashScreen
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtGui import QFont, QFontDatabase, QColor

        app = QApplication(sys.argv)
        app.setApplicationName("LangCoach")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("LangCoach")

        # Charge les polices Google Fonts si disponibles localement
        # (Sinon fallback sur polices système)
        _load_fonts()

        # Font par défaut
        from config.theme import T
        default_font = QFont(T["font_body"], T["font_size_md"])
        app.setFont(default_font)

        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()

        sys.exit(app.exec())

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nInstall dependencies:")
        print("  pip install PyQt6 ollama transformers sounddevice numpy")
        print("  pip install kokoro  # (optional, better TTS)")
        print("  brew install portaudio  # (macOS, required for sounddevice)")
        sys.exit(1)


def _load_fonts():
    """Charge les polices depuis le dossier assets/ si présentes"""
    from PyQt6.QtGui import QFontDatabase
    import os

    assets_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    if not os.path.exists(assets_dir):
        return

    loaded = 0
    for fname in os.listdir(assets_dir):
        if fname.endswith((".ttf", ".otf")):
            path = os.path.join(assets_dir, fname)
            QFontDatabase.addApplicationFont(path)
            loaded += 1

    if loaded:
        logging.getLogger(__name__).info(f"Loaded {loaded} custom font(s)")


if __name__ == "__main__":
    main()
