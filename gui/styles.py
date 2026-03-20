# GUI styles - Colores corporativos CCU y configuracion de temas
# Tema claro corporativo - Sistema de control interno de logistica industrial


class Colors:
    """Colores corporativos CCU - Tema Claro Profesional"""
    # CCU Institutional Green (structural - sidebar, header, active items)
    CCU_GREEN = "#005C35"
    CCU_GREEN_LIGHT = "#007A46"
    CCU_GREEN_HOVER = "#004D2C"

    # CCU Action Green (operational - buttons, progress, positive states)
    ACTION_GREEN = "#009F4D"
    ACTION_GREEN_HOVER = "#008A42"
    ACTION_GREEN_LIGHT = "#E6F5ED"

    # Legacy brand colors (kept for compatibility)
    CCU_RED = "#005C35"       # Mapped to institutional green
    CCU_RED_DARK = "#004D2C"
    CCU_RED_LIGHT = "#007A46"
    CCU_GOLD = "#005C35"      # Mapped to green
    CCU_GOLD_LIGHT = "#007A46"

    # Light Theme Backgrounds
    BG_PRIMARY = "#F4F6F8"        # Main background - corporate, stable
    BG_CARD = "#FFFFFF"           # Card background - clean white
    BG_SIDEBAR = "#005C35"        # Sidebar - institutional green
    BG_HEADER = "#005C35"         # Header - institutional green
    BG_HOVER = "#EDF2F7"          # Hover state
    BG_ACTIVE = "#007A46"         # Active sidebar item

    # Legacy dark theme aliases (mapped to light theme)
    DARK_BG = "#F4F6F8"
    DARK_CARD = "#FFFFFF"
    DARK_CARD_HOVER = "#EDF2F7"
    DARK_BORDER = "#E2E8F0"

    # Text Colors - Professional hierarchy
    TEXT_PRIMARY = "#2D3748"       # Main text - dark blue-gray, never pure black
    TEXT_SECONDARY = "#4A5568"     # Secondary text
    TEXT_MUTED = "#718096"         # Labels, hints
    TEXT_LIGHT = "#272A2E"        # Very subtle text
    TEXT_ON_GREEN = "#FFFFFF"      # Text on green backgrounds
    TEXT_ON_DARK = "#FFFFFF"       # Text on dark backgrounds

    # Card styling
    CARD_BORDER = "#E2E8F0"       # Subtle gray border
    CARD_SHADOW = "#CBD5E0"       # Very light shadow color

    # Status Colors
    SUCCESS = "#009F4D"           # Action green for positive states
    SUCCESS_BG = "#E6F5ED"        # Light green background
    WARNING = "#FCB500"           # Yellow for alerts
    WARNING_BG = "#FFF8E1"        # Light yellow background
    ERROR = "#D32F2F"             # Red only for real problems
    ERROR_BG = "#FFEBEE"          # Light red background
    INFO = "#3B82F6"              # Blue for information
    INFO_BG = "#EBF5FF"           # Light blue background

    # Specific icon colors (for stat cards)
    ICON_WHATSAPP = "#009F4D"     # Action green
    ICON_MONITOR_STOPPED = "#D32F2F"  # Red when stopped
    ICON_MONITOR_ACTIVE = "#009F4D"   # Green when active
    ICON_ALERTS = "#FB5A2D"       # Yellow
    ICON_TRUCKS = "#F57C00"       # Orange

    # Chart colors
    CHART_TODAY = "#009F4D"       # Green for today's data
    CHART_YESTERDAY = "#A0AEC0"   # Gray for yesterday
    CHART_THRESHOLD = "#D32F2F"   # Red dashed for threshold
    CHART_GRID = "#EDF2F7"        # Very subtle grid
    CHART_BG = "#FFFFFF"          # White chart background

    # Pre-mixed colors for backgrounds (light theme)
    CCU_RED_ALPHA_15 = "#E6F5ED"      # Green tinted bg
    CCU_RED_ALPHA_30 = "#D4EDDA"      # Green tinted bg stronger
    CCU_GOLD_ALPHA_07 = "#F0FAF4"     # Very light green
    CCU_GOLD_ALPHA_15 = "#E6F5ED"     # Light green
    CCU_GOLD_ALPHA_20 = "#D4EDDA"     # Medium green
    CCU_GOLD_ALPHA_30 = "#C3E6CB"     # Stronger green
    WARNING_ALPHA_15 = "#FFF8E1"      # Light yellow
    DARK_CARD_ALPHA_80 = "#F7FAFC"    # Very light gray

    # Filter buttons
    FILTER_BG = "#FFFFFF"          # White background
    FILTER_BORDER = "#A5A8AD"      # Gray border
    FILTER_ACTIVE_BG = "#009F4D"   # Green when selected
    FILTER_ACTIVE_TEXT = "#FFFFFF"  # White text when selected


# Helper function to get alpha color
def get_alpha_bg(color: str) -> str:
    """Returns a pre-mixed background color for the given color"""
    alpha_map = {
        Colors.CCU_GREEN: Colors.ACTION_GREEN_LIGHT,
        Colors.ACTION_GREEN: Colors.ACTION_GREEN_LIGHT,
        Colors.CCU_GOLD: Colors.ACTION_GREEN_LIGHT,
        Colors.CCU_RED: Colors.ACTION_GREEN_LIGHT,
        Colors.WARNING: Colors.WARNING_BG,
        Colors.ICON_ALERTS: Colors.WARNING_BG,
        Colors.SUCCESS: Colors.SUCCESS_BG,
        Colors.ERROR: Colors.ERROR_BG,
        Colors.INFO: Colors.INFO_BG,
        Colors.ICON_TRUCKS: "#FFF3E0",  # Light orange bg
    }
    return alpha_map.get(color, Colors.BG_CARD)


class Fonts:
    """Configuracion de fuentes - tipografia limpia y profesional"""
    FAMILY = "Segoe UI"

    # Sizes
    TITLE_SIZE = 28
    HEADING_SIZE = 24
    SUBHEADING_SIZE = 18
    BODY_SIZE = 14
    SMALL_SIZE = 12
    TINY_SIZE = 10

    # Weights
    BOLD = "bold"
    NORMAL = "normal"


class Dimensions:
    """Dimensiones de la ventana y componentes"""
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 950
    WINDOW_MIN_WIDTH = 1200
    WINDOW_MIN_HEIGHT = 900

    SIDEBAR_WIDTH = 220
    SIDEBAR_COLLAPSED_WIDTH = 70

    CARD_PADDING = 20
    CARD_RADIUS = 8               # More subtle radius

    BUTTON_PADDING_X = 20
    BUTTON_PADDING_Y = 10
    BUTTON_RADIUS = 6             # Moderate radius - firm, not playful

    INPUT_PADDING = 12
    INPUT_RADIUS = 6


# Configuracion de CustomTkinter
def configure_customtkinter():
    """Configura el tema de CustomTkinter - Modo Claro Corporativo"""
    import customtkinter as ctk

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")
