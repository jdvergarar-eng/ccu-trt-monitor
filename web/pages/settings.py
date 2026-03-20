# Settings page - Configuración del sistema
from nicegui import ui
from ..shared import page_layout
from ..theme import Colors
from ..auth import require_auth
from core import get_config_manager, get_whatsapp_client, get_monitoring_service


def setup_settings_page():
    """Registra la página de configuración"""

    @ui.page('/settings')
    def settings_page():
        require_auth()
        monitoring = get_monitoring_service()
        config_manager = get_config_manager()
        config = config_manager.config
        page_layout('Configuración', monitoring)

        with ui.column().classes('w-full gap-4 p-4'):
            # Title
            ui.label('Configuración').classes('text-2xl font-bold').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.label('Ajustes generales del sistema').classes('text-sm').style(
                f'color: {Colors.TEXT_MUTED};'
            )

            # Connection settings
            with ui.card().classes('w-full ccu-card'):
                ui.label('Conexión').classes('font-bold text-lg mb-2').style(
                    f'color: {Colors.TEXT_PRIMARY};'
                )

                url_input = ui.input(
                    'URL del servidor TRT',
                    value=config.base_url
                ).classes('w-full')

                with ui.row().classes('w-full gap-4'):
                    poll_input = ui.number(
                        'Intervalo de consulta (segundos)',
                        value=config.poll_seconds,
                        min=5, max=300
                    ).classes('flex-1')

                    realert_input = ui.number(
                        'Reenvío de alertas (minutos)',
                        value=config.realert_minutes,
                        min=1, max=120
                    ).classes('flex-1')

                def save_connection():
                    config.base_url = url_input.value
                    config.poll_seconds = int(poll_input.value)
                    config.realert_minutes = int(realert_input.value)
                    config_manager.save(config)
                    ui.notify('Configuración de conexión guardada', type='positive')

                ui.button(
                    'Guardar configuración',
                    on_click=save_connection,
                    icon='save'
                ).props('color=green-7').classes('mt-2')

            # WhatsApp settings
            with ui.card().classes('w-full ccu-card'):
                ui.label('WhatsApp').classes('font-bold text-lg mb-2').style(
                    f'color: {Colors.TEXT_PRIMARY};'
                )

                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-0'):
                        ui.label('Estado de conexión').style(
                            f'color: {Colors.TEXT_PRIMARY};'
                        )
                        phone_text = monitoring.whatsapp_phone or 'No conectado'
                        ui.label(phone_text).classes('text-sm').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )

                    status_text = 'Conectado' if monitoring.bot_status == 'connected' else 'Desconectado'
                    status_color = Colors.SUCCESS if monitoring.bot_status == 'connected' else Colors.ERROR
                    with ui.row().classes('items-center gap-2'):
                        ui.html(
                            f'<span class="status-dot" style="background-color: {status_color};"></span>'
                        )
                        ui.label(status_text).style(f'color: {status_color};')

                def disconnect_whatsapp():
                    try:
                        wa_client = get_whatsapp_client()
                        success = wa_client.logout()
                        if success:
                            ui.notify('WhatsApp desvinculado correctamente', type='positive')
                            monitoring.bot_status = "disconnected"
                            monitoring.whatsapp_phone = None
                        else:
                            ui.notify('No se pudo desvincular WhatsApp', type='negative')
                    except Exception as e:
                        ui.notify(f'Error: {str(e)[:50]}', type='negative')

                def confirm_disconnect():
                    with ui.dialog() as dialog, ui.card():
                        ui.label('¿Desvincular WhatsApp?').classes('text-lg font-bold').style(
                            f'color: {Colors.ERROR};'
                        )
                        ui.label(
                            'Esta acción cerrará la sesión de WhatsApp. '
                            'Deberás escanear el QR nuevamente.'
                        ).classes('text-sm')
                        with ui.row().classes('w-full justify-end gap-2 mt-4'):
                            ui.button('Cancelar', on_click=dialog.close).props('flat')
                            ui.button('Desvincular', on_click=lambda: (
                                disconnect_whatsapp(), dialog.close()
                            )).props('color=red-7')
                    dialog.open()

                ui.button(
                    'Desvincular WhatsApp',
                    on_click=confirm_disconnect,
                    icon='link_off'
                ).props('outline color=grey-7')

            # Danger zone
            with ui.card().classes('w-full').style(
                'border: 1px solid #FFCDD2; border-radius: 8px;'
            ):
                ui.label('Zona de Peligro').classes('font-bold text-lg mb-2').style(
                    f'color: {Colors.ERROR};'
                )
                ui.label(
                    'Las siguientes acciones son irreversibles y eliminarán '
                    'toda la configuración del sistema.'
                ).classes('text-sm mb-4').style(f'color: {Colors.TEXT_MUTED};')

                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-0'):
                        ui.label('Borrar toda la configuración').style(
                            f'color: {Colors.TEXT_PRIMARY};'
                        )
                        ui.label(
                            'Elimina todos los centros configurados y reinicia el sistema'
                        ).classes('text-sm').style(f'color: {Colors.TEXT_MUTED};')

                    def confirm_reset():
                        with ui.dialog() as dialog, ui.card():
                            ui.label('¿Borrar toda la configuración?').classes(
                                'text-lg font-bold'
                            ).style(f'color: {Colors.ERROR};')
                            ui.label(
                                'Todos los centros, umbrales y configuraciones serán eliminados. '
                                'Esta acción no se puede deshacer.'
                            ).classes('text-sm')
                            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                                ui.button('Cancelar', on_click=dialog.close).props('flat')
                                ui.button('Borrar todo', on_click=lambda: (
                                    _reset_config(config_manager), dialog.close()
                                )).props('color=red-7')
                        dialog.open()

                    ui.button(
                        'Borrar Configuración',
                        on_click=confirm_reset,
                        icon='delete_forever'
                    ).props('color=red-7')


def _reset_config(config_manager):
    """Borra la configuración"""
    import os
    if config_manager.config_path.exists():
        os.remove(config_manager.config_path)
    ui.notify('Configuración eliminada. Recarga la página.', type='warning')
    ui.navigate.to('/setup')
