# ============================================================
#  LangCoach — Theme Configuration
#  Modifier ce fichier pour changer tout le look de l'app
# ============================================================

THEME = {

    # ── Couleurs principales ─────────────────────────────────
    "bg_primary":       "#0F0F10",   # Fond principal (quasi-noir)
    "bg_secondary":     "#161618",   # Fond des panneaux
    "bg_card":          "#1C1C1F",   # Fond des cards / inputs
    "bg_hover":         "#242428",   # Hover state

    "accent":           "#CC785C",   # Accent principal (terracotta chaud)
    "accent_soft":      "#CC785C22", # Accent transparent (glow)
    "accent_hover":     "#D98B6F",   # Accent au survol

    "text_primary":     "#F0EDE8",   # Texte principal (blanc chaud)
    "text_secondary":   "#8A8480",   # Texte secondaire
    "text_muted":       "#4A4845",   # Texte désactivé

    "border":           "#2A2A2E",   # Bordures subtiles
    "border_active":    "#CC785C",   # Bordure active / focus

    "success":          "#5C9E6E",   # Vert doux
    "warning":          "#C4913A",   # Ambre
    "error":            "#9E5C5C",   # Rouge doux
    "info":             "#5C7E9E",   # Bleu ardoise

    # ── Bulles de conversation ───────────────────────────────
    "bubble_user_bg":   "#CC785C18",
    "bubble_user_border": "#CC785C55",
    "bubble_ai_bg":     "#1E1E22",
    "bubble_ai_border": "#2E2E34",

    # ── Typographie ──────────────────────────────────────────
    # Polices installées automatiquement depuis Google Fonts
    # Ou remplacer par n'importe quelle police système
    "font_display":     "DM Serif Display",   # Titres
    "font_body":        "DM Sans",            # Corps de texte
    "font_mono":        "JetBrains Mono",     # Code / timestamps

    "font_size_xs":     10,
    "font_size_sm":     12,
    "font_size_md":     14,
    "font_size_lg":     16,
    "font_size_xl":     20,
    "font_size_2xl":    28,
    "font_size_3xl":    36,

    # ── Géométrie ────────────────────────────────────────────
    "radius_sm":        6,
    "radius_md":        12,
    "radius_lg":        18,
    "radius_xl":        24,
    "radius_pill":      99,

    "spacing_xs":       4,
    "spacing_sm":       8,
    "spacing_md":       16,
    "spacing_lg":       24,
    "spacing_xl":       40,

    # ── Fenêtre ──────────────────────────────────────────────
    "window_width":     1100,
    "window_height":    750,
    "window_min_width": 800,
    "window_min_height": 600,
    "sidebar_width":    280,
    "bottom_bar_height": 44,

    # ── Animation ────────────────────────────────────────────
    "anim_fast":        150,   # ms
    "anim_normal":      250,   # ms
    "anim_slow":        400,   # ms

    # ── Effets ───────────────────────────────────────────────
    "shadow_sm":        "0 2px 8px rgba(0,0,0,0.4)",
    "shadow_md":        "0 4px 20px rgba(0,0,0,0.6)",
    "opacity_disabled": 0.4,
}

# ── Thèmes alternatifs ───────────────────────────────────────
# Décommenter pour switcher de thème

# THEME_LIGHT = { ...same keys with light values... }
# THEME_OCEAN = { ...deep blues... }

# Raccourci pratique
T = THEME
