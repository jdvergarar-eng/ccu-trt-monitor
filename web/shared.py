# Shared layout - Sidebar + Header reutilizable para todas las páginas
from datetime import datetime
from nicegui import ui, app
from pathlib import Path
from .theme import Colors


ASSETS_DIR = Path(__file__).parent.parent / "assets"


def get_datetime_spanish() -> str:
    """Fecha/hora en español"""
    dias = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    meses = {
        'January': 'enero', 'February': 'febrero', 'March': 'marzo',
        'April': 'abril', 'May': 'mayo', 'June': 'junio',
        'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
        'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
    }
    now = datetime.now()
    day_name = dias.get(now.strftime("%A"), now.strftime("%A"))
    month_name = meses.get(now.strftime("%B"), now.strftime("%B"))
    return f"{day_name}, {now.day} de {month_name} de {now.year} - {now.strftime('%H:%M')}"


def create_header(monitoring_service=None):
    """Crea el header con status badges y reloj"""
    with ui.header().classes('items-center justify-between').style(
        f'background-color: {Colors.CCU_GREEN}; padding: 0 16px; height: 60px;'
    ):
        with ui.row().classes('items-center gap-4'):
            # Status badges
            wa_dot = ui.html('<span class="status-dot status-dot-disconnected"></span>')
            wa_label = ui.label('WhatsApp: Desconectado').classes('text-white text-sm')

            mon_dot = ui.html('<span class="status-dot status-dot-disconnected"></span>')
            mon_label = ui.label('Monitor: Detenido').classes('text-white text-sm')

        datetime_label = ui.label(get_datetime_spanish()).classes('text-white text-sm')

        def update_header():
            datetime_label.text = get_datetime_spanish()
            if monitoring_service:
                # WhatsApp status
                if monitoring_service.bot_status == "connected":
                    wa_dot.content = '<span class="status-dot status-dot-connected"></span>'
                    wa_label.text = "WhatsApp: Conectado"
                elif monitoring_service.bot_status == "warning":
                    wa_dot.content = '<span class="status-dot status-dot-warning"></span>'
                    wa_label.text = "WhatsApp: Parcial"
                else:
                    wa_dot.content = '<span class="status-dot status-dot-disconnected"></span>'
                    wa_label.text = "WhatsApp: Desconectado"

                # Monitor status
                if monitoring_service.monitor_running:
                    mon_dot.content = '<span class="status-dot status-dot-connected"></span>'
                    mon_label.text = "Monitor: Activo"
                else:
                    mon_dot.content = '<span class="status-dot status-dot-disconnected"></span>'
                    mon_label.text = "Monitor: Detenido"

        ui.timer(5.0, update_header)


def create_sidebar():
    """Crea el sidebar de navegación"""
    with ui.left_drawer(value=True).classes('ccu-sidebar').style(
        f'background-color: {Colors.CCU_GREEN}; width: 220px; padding: 0;'
    ) as drawer:
        # Logo
        with ui.column().classes('items-center w-full').style('padding: 16px 0;'):
            logo_path = ASSETS_DIR / "Logo_CCU.png"
            if logo_path.exists():
                ui.image(str(logo_path)).classes('w-32')
            else:
                ui.label('CCU').classes('text-white text-3xl font-bold')
            ui.label('Monitor TRT v2.0').classes('text-white text-xs')

        ui.separator().style('background-color: #007A46; margin: 0;')

        # Navigation
        with ui.column().classes('w-full').style('padding: 8px;'):
            menu_dir = ASSETS_DIR / "Menu"

            nav_items = [
                ('/', 'Inicio', 'home'),
                ('/centers', 'Centros', 'business'),
                ('/analytics', 'Estadisticas', 'analytics'),
                ('/settings', 'Configuracion', 'settings'),
            ]

            for href, label, icon in nav_items:
                with ui.link(target=href).classes('no-underline w-full'):
                    with ui.row().classes(
                        'items-center gap-3 w-full rounded-lg cursor-pointer'
                    ).style(
                        'padding: 10px 12px; color: white; transition: background 0.2s;'
                    ).on('mouseenter', lambda e: e.sender.style('background-color: #007A46;')).on(
                        'mouseleave', lambda e: e.sender.style('background-color: transparent;')
                    ):
                        ui.icon(icon).classes('text-white')
                        ui.label(label).classes('text-white text-sm')

        ui.separator().style('background-color: #007A46; margin: 16px 0;')

        # Info section
        with ui.column().classes('w-full').style('padding: 0 16px 16px;'):
            with ui.card().classes('w-full').style(
                f'background-color: {Colors.CCU_GREEN_HOVER}; border: none;'
            ):
                with ui.column().classes('gap-1'):
                    # Avatar
                    with ui.row().classes('items-center gap-2'):
                        with ui.element('div').style(
                            f'background-color: {Colors.ACTION_GREEN}; '
                            'border-radius: 50%; width: 32px; height: 32px; '
                            'display: flex; align-items: center; justify-content: center;'
                        ):
                            ui.label('CCU').classes('text-white text-xs font-bold')

                    ui.label('CCU-TRT Monitor').classes('text-white text-sm font-bold')
                    ui.label('Monitoreando TRT').classes('text-white text-xs')

    return drawer


def page_layout(title: str, monitoring_service=None):
    """Configura el layout de la página con header y sidebar"""
    ui.page_title(f'{title} - CCU TRT Monitor')
    create_header(monitoring_service)
    create_sidebar()
