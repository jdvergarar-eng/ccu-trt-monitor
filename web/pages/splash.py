# Splash page - Pantalla de inicio con logo CCU
from nicegui import ui
from pathlib import Path
from ..theme import Colors


ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


def setup_splash_page():
    """Registra la página de splash"""

    @ui.page('/splash')
    def splash_page():
        ui.page_title('CCU-TRT Monitor')

        with ui.column().classes('absolute-center items-center'):
            # Card principal
            with ui.card().classes('items-center').style(
                'padding: 50px 80px; border-radius: 16px; '
                'border: 1px solid #E2E8F0; border-top: 4px solid #005C35;'
            ):
                # Logo CCU
                logo_path = ASSETS_DIR / "Logo_CCU.png"
                if logo_path.exists():
                    ui.image(str(logo_path)).style('width: 240px;')

                ui.separator().style('width: 300px; margin: 12px 0;')

                # Titulo
                ui.label('Sistema de Alertas TRT').classes(
                    'text-4xl font-bold text-center'
                ).style(f'color: {Colors.TEXT_PRIMARY};')

                ui.label('Monitor de Tiempo de Residencia en Planta').classes(
                    'text-base text-center'
                ).style(f'color: {Colors.TEXT_SECONDARY};')

                # Badge de origen
                with ui.element('div').style(
                    f'background-color: {Colors.ACTION_GREEN_LIGHT}; '
                    f'border: 1px solid {Colors.ACTION_GREEN}; '
                    'border-radius: 20px; padding: 6px 20px; margin-top: 20px;'
                ):
                    ui.label('CD Santiago Sur').classes('text-sm font-bold').style(
                        f'color: {Colors.CCU_GREEN};'
                    )

                # Boton comenzar
                ui.button(
                    'Comenzar Configuracion',
                    on_click=lambda: ui.navigate.to('/welcome'),
                    icon='arrow_forward',
                ).props('color=green-9 size=lg').style(
                    'width: 320px; margin-top: 28px;'
                )

            # Creditos
            with ui.column().classes('items-center mt-7 gap-1'):
                ui.label('Desarrollado por Juan Vergara & Vicente Vergara').classes(
                    'text-xs'
                ).style(f'color: {Colors.TEXT_MUTED};')
                ui.label('Equipo de Operaciones - CCU').classes('text-xs').style(
                    f'color: {Colors.ACTION_GREEN};'
                )
