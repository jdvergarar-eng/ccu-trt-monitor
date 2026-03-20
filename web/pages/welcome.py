# Welcome page - Requisitos del sistema antes de configurar
from nicegui import ui
from ..theme import Colors


def setup_welcome_page():
    """Registra la página de bienvenida/requisitos"""

    @ui.page('/welcome')
    def welcome_page():
        ui.page_title('Bienvenido - CCU TRT Monitor')

        requirements = [
            {
                "icon": "smartphone",
                "title": "Telefono con WhatsApp",
                "description": (
                    "Recomendamos un telefono dedicado exclusivamente para el bot, "
                    "por temas de seguridad y estabilidad."
                ),
                "required": True,
            },
            {
                "icon": "computer",
                "title": "PC encendido permanentemente",
                "description": (
                    "El computador debe estar encendido 24/7. "
                    "Puedes usar WinToys para configurar que no entre en suspension."
                ),
                "required": True,
            },
            {
                "icon": "lan",
                "title": "Conexion a red CCU",
                "description": (
                    "El equipo debe estar conectado a la red local de CCU "
                    "para acceder al sistema TRT."
                ),
                "required": True,
            },
            {
                "icon": "group",
                "title": "Grupos de WhatsApp creados",
                "description": (
                    "Debes tener creados los grupos de WhatsApp donde se "
                    "enviaran las alertas de cada centro."
                ),
                "required": False,
            },
        ]

        with ui.column().classes('max-w-2xl mx-auto p-8 gap-6'):
            # Titulo
            ui.label('Bienvenido al Sistema de Alertas TRT').classes(
                'text-3xl font-bold'
            ).style(f'color: {Colors.TEXT_PRIMARY};')

            ui.label(
                'Antes de comenzar, asegurate de cumplir con los siguientes requisitos'
            ).classes('text-base').style(f'color: {Colors.TEXT_SECONDARY};')

            # Tarjetas de requisitos
            for req in requirements:
                border_color = '#D4EDDA' if req["required"] else '#E2E8F0'
                with ui.card().style(
                    f'border: 1px solid {border_color}; border-radius: 12px; width: 100%;'
                ):
                    with ui.row().classes('items-start gap-4 w-full'):
                        # Icono
                        bg = Colors.ACTION_GREEN_LIGHT if req["required"] else Colors.BG_PRIMARY
                        icon_color = Colors.ACTION_GREEN if req["required"] else Colors.TEXT_MUTED
                        with ui.element('div').style(
                            f'background-color: {bg}; border-radius: 12px; '
                            'width: 48px; height: 48px; min-width: 48px; '
                            'display: flex; align-items: center; justify-content: center;'
                        ):
                            ui.icon(req["icon"]).style(
                                f'color: {icon_color}; font-size: 24px;'
                            )

                        # Contenido
                        with ui.column().classes('gap-1 flex-1'):
                            with ui.row().classes('items-center gap-2'):
                                ui.label(req["title"]).classes(
                                    'text-base font-bold'
                                ).style(f'color: {Colors.TEXT_PRIMARY};')

                                if req["required"]:
                                    ui.badge('REQUERIDO').props('color=green-9').style(
                                        'font-size: 10px;'
                                    )

                            ui.label(req["description"]).classes('text-sm').style(
                                f'color: {Colors.TEXT_SECONDARY};'
                            )

            # Botones de navegacion
            with ui.row().classes('w-full justify-center gap-4 mt-4'):
                ui.button(
                    'Volver',
                    on_click=lambda: ui.navigate.to('/splash'),
                    icon='arrow_back',
                ).props('flat color=grey-7')

                ui.button(
                    'Tengo todo listo, continuar',
                    on_click=lambda: ui.navigate.to('/setup'),
                    icon='arrow_forward',
                ).props('color=green-9 size=lg')
