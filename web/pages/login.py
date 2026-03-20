# Login page - Inicio de sesión con Azure AD
from nicegui import ui
from pathlib import Path
from ..theme import Colors
from ..auth import AUTH_ENABLED


ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


def setup_login_page():
    """Registra la página de login"""

    @ui.page('/login')
    def login_page():
        ui.page_title('Iniciar Sesión - CCU TRT Monitor')

        with ui.column().classes('absolute-center items-center gap-6'):
            # Logo
            logo_path = ASSETS_DIR / "Logo_CCU.png"
            if logo_path.exists():
                ui.image(str(logo_path)).style('width: 200px;')

            ui.label('CCU-TRT Monitor').classes('text-2xl font-bold').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.label('Sistema de Alertas de Tiempo de Residencia en Planta').classes(
                'text-sm'
            ).style(f'color: {Colors.TEXT_MUTED};')

            ui.separator().style('width: 300px;')

            if AUTH_ENABLED:
                ui.button(
                    'Iniciar sesión con cuenta CCU',
                    on_click=lambda: ui.navigate.to('/auth/login'),
                    icon='login'
                ).props('color=green-9 size=lg').style('width: 300px;')

                ui.label('Usa tu cuenta @ccu.cl para ingresar').classes(
                    'text-xs'
                ).style(f'color: {Colors.TEXT_MUTED};')
            else:
                ui.button(
                    'Ingresar (sin autenticación)',
                    on_click=lambda: ui.navigate.to('/'),
                    icon='login'
                ).props('color=green-9 size=lg').style('width: 300px;')

                ui.label('Autenticación Azure AD no configurada').classes(
                    'text-xs'
                ).style(f'color: {Colors.WARNING};')

            ui.label('Desarrollado por Juan Vergara & Vicente Vergara').classes(
                'text-xs mt-8'
            ).style(f'color: {Colors.TEXT_MUTED};')
