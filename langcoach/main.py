"""
LangCoach — Entry Point
Lance l'application desktop
"""
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def main():
    try:
        from PyQt6.QtWidgets import QApplication, QDialog
        from PyQt6.QtGui import QFont

        app = QApplication(sys.argv)
        app.setApplicationName("Echo")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("Quantelys")

        _load_fonts()

        from config.theme import T
        app.setFont(QFont(T["font_body"], T["font_size_md"]))

        # ── Database + migration ───────────────────────────────
        from config.settings import DB_FILE, save_last_profile_id, migrate_if_needed
        from core.database import Database

        db = Database(DB_FILE)
        migrate_if_needed(db)

        # ── Profile selection ──────────────────────────────────
        from ui.profile_screen import ProfileScreen, ProfileWizard

        profiles = db.list_profiles()

        if not profiles:
            # No profiles yet → show wizard directly
            wizard = ProfileWizard(db)
            created_id = []
            wizard.profile_created.connect(lambda pid: created_id.append(pid))
            if wizard.exec() != QDialog.DialogCode.Accepted or not created_id:
                sys.exit(0)
            profile = db.get_profile(created_id[0])
        elif len(profiles) == 1:
            # Single profile → auto-select
            db.touch_profile(profiles[0]["id"])
            profile = profiles[0]
        else:
            # Multiple profiles → splash screen
            screen = ProfileScreen(db)
            if screen.exec() != QDialog.DialogCode.Accepted:
                sys.exit(0)
            profile = screen.selected_profile

        if not profile:
            sys.exit(0)

        save_last_profile_id(profile["id"])

        # ── Main window ────────────────────────────────────────
        from ui.main_window import MainWindow

        window = MainWindow(db=db, profile=profile)
        window.show()

        sys.exit(app.exec())

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nInstall dependencies:")
        print("  pip install PyQt6 ollama transformers sounddevice numpy")
        sys.exit(1)


def _load_fonts():
    from PyQt6.QtGui import QFontDatabase
    assets_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    if not os.path.exists(assets_dir):
        return
    loaded = 0
    for fname in os.listdir(assets_dir):
        if fname.endswith((".ttf", ".otf")):
            path = os.path.join(assets_dir, fname)
            if QFontDatabase.addApplicationFont(path) >= 0:
                loaded += 1
    if loaded:
        logging.getLogger(__name__).info(f"Loaded {loaded} custom font(s)")


if __name__ == "__main__":
    main()
