# Theme - Colores y estilos corporativos CCU para NiceGUI
# Migrado de gui/styles.py


class Colors:
    """Colores corporativos CCU"""
    # Institutional Green
    CCU_GREEN = "#005C35"
    CCU_GREEN_LIGHT = "#007A46"
    CCU_GREEN_HOVER = "#004D2C"

    # Action Green
    ACTION_GREEN = "#009F4D"
    ACTION_GREEN_HOVER = "#008A42"
    ACTION_GREEN_LIGHT = "#E6F5ED"

    # Backgrounds
    BG_PRIMARY = "#F4F6F8"
    BG_CARD = "#FFFFFF"
    BG_SIDEBAR = "#005C35"
    BG_HEADER = "#005C35"
    BG_HOVER = "#EDF2F7"

    # Text
    TEXT_PRIMARY = "#2D3748"
    TEXT_SECONDARY = "#4A5568"
    TEXT_MUTED = "#718096"
    TEXT_ON_GREEN = "#FFFFFF"

    # Status
    SUCCESS = "#009F4D"
    SUCCESS_BG = "#E6F5ED"
    WARNING = "#FCB500"
    WARNING_BG = "#FFF8E1"
    ERROR = "#D32F2F"
    ERROR_BG = "#FFEBEE"
    INFO = "#3B82F6"
    INFO_BG = "#EBF5FF"

    # Icons
    ICON_TRUCKS = "#F57C00"

    # Chart
    CHART_TODAY = "#009F4D"
    CHART_THRESHOLD = "#D32F2F"


# CSS personalizado para aplicar el tema CCU
CCU_CSS = """
:root {
    --ccu-green: #005C35;
    --ccu-green-light: #007A46;
    --ccu-action-green: #009F4D;
    --ccu-bg: #F4F6F8;
    --ccu-text: #2D3748;
    --ccu-text-muted: #718096;
}

/* Override Quasar primary color */
.q-btn--standard.bg-primary,
.bg-primary {
    background-color: var(--ccu-action-green) !important;
}

.text-primary {
    color: var(--ccu-action-green) !important;
}

/* Cards estilo CCU */
.ccu-card {
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    background: white;
}

/* Status badges */
.status-connected { color: #009F4D; }
.status-warning { color: #FCB500; }
.status-disconnected { color: #D32F2F; }

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}

.status-dot-connected { background-color: #009F4D; }
.status-dot-warning { background-color: #FCB500; }
.status-dot-disconnected { background-color: #D32F2F; }

/* Severity badges */
.severity-normal { background-color: #E6F5ED; color: #009F4D; }
.severity-warning { background-color: #FFF8E1; color: #F57C00; }
.severity-critical { background-color: #FFEBEE; color: #D32F2F; }

/* Sidebar styling */
.ccu-sidebar .q-item {
    border-radius: 8px;
    margin: 2px 8px;
}

.ccu-sidebar .q-item--active {
    background-color: var(--ccu-green-light) !important;
}

/* KPI Card */
.kpi-card {
    text-align: center;
    padding: 16px;
}

.kpi-value {
    font-size: 2rem;
    font-weight: bold;
    color: var(--ccu-text);
}

.kpi-label {
    font-size: 0.85rem;
    color: var(--ccu-text-muted);
}

/* Truck table rows */
.truck-green { background-color: #F0FFF4; }
.truck-yellow { background-color: #FFFDE7; }
.truck-red { background-color: #FFF5F5; }

/* Body background */
body {
    background-color: var(--ccu-bg) !important;
}
"""
