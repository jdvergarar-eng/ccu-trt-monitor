# Connecting page - Espera de conexión del bot de WhatsApp
# Verifica que el bot esté conectado antes de ir al dashboard.
# Si tarda mucho, ofrece desvincular y reconectar con QR.
import io
import base64
from nicegui import ui
from ..theme import Colors
from core import get_whatsapp_client

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

TIMEOUT_SECONDS = 25
POLL_SECONDS = 3


def setup_connecting_page():
    """Registra la página de conexión"""

    @ui.page('/connecting')
    def connecting_page():
        ui.page_title('Conectando - CCU TRT Monitor')
        wa_client = get_whatsapp_client()

        # State
        state = {
            'phase': 'waiting',  # waiting | timeout | qr | done
            'elapsed': 0,
            'timer_active': True,
        }

        with ui.column().classes('absolute-center items-center'):
            # Card principal
            with ui.card().classes('items-center').style(
                'padding: 50px 60px; border-radius: 16px; '
                'border: 1px solid #E2E8F0; border-top: 4px solid #005C35; '
                'min-width: 500px;'
            ):
                # Icono WhatsApp
                with ui.element('div').style(
                    f'background-color: {Colors.ACTION_GREEN_LIGHT}; '
                    'border-radius: 50%; width: 72px; height: 72px; '
                    'display: flex; align-items: center; justify-content: center;'
                ):
                    ui.icon('chat').style(
                        f'color: {Colors.ACTION_GREEN}; font-size: 36px;'
                    )

                ui.label('Conectando al Bot de WhatsApp').classes(
                    'text-2xl font-bold mt-4'
                ).style(f'color: {Colors.TEXT_PRIMARY};')

                status_label = ui.label('Iniciando...').classes('text-sm').style(
                    f'color: {Colors.TEXT_SECONDARY};'
                )

                progress = ui.linear_progress(value=None).style(
                    'width: 300px; margin-top: 16px;'
                ).props('color=green-7')

                # Status badge
                with ui.row().classes('items-center gap-2 mt-4'):
                    status_dot = ui.html(
                        '<span class="status-dot status-dot-disconnected"></span>'
                    )
                    badge_label = ui.label('Esperando bot...').classes('text-sm').style(
                        f'color: {Colors.TEXT_MUTED};'
                    )

                detail_label = ui.label('').classes('text-xs mt-1').style(
                    f'color: {Colors.TEXT_MUTED};'
                )

            # Timeout card (hidden initially)
            timeout_card = ui.card().style(
                f'border: 1px solid {Colors.WARNING}; border-radius: 12px; '
                'margin-top: 16px; min-width: 500px;'
            )
            timeout_card.set_visibility(False)
            with timeout_card:
                with ui.column().classes('items-center gap-2 p-4'):
                    with ui.element('div').style(
                        f'background-color: {Colors.WARNING_BG}; '
                        'border-radius: 50%; width: 36px; height: 36px; '
                        'display: flex; align-items: center; justify-content: center;'
                    ):
                        ui.icon('warning').style(
                            f'color: {Colors.WARNING}; font-size: 18px;'
                        )

                    ui.label('La conexion esta tardando mucho').classes(
                        'font-bold text-base'
                    ).style(f'color: {Colors.TEXT_PRIMARY};')

                    ui.label(
                        'Puedes desvincular la cuenta actual y reconectar\n'
                        'escaneando un nuevo codigo QR.'
                    ).classes('text-sm text-center').style(
                        f'color: {Colors.TEXT_MUTED};'
                    )

                    ui.button(
                        'Desvincular y reconectar con QR',
                        on_click=lambda: _do_logout(
                            state, wa_client, timeout_card, qr_card,
                            status_label, status_dot, badge_label, progress
                        ),
                        icon='link_off',
                    ).props('color=green-9')

            # QR card (hidden initially)
            qr_card = ui.card().style(
                'border: 1px solid #E2E8F0; border-radius: 12px; '
                'margin-top: 12px; min-width: 500px;'
            )
            qr_card.set_visibility(False)
            with qr_card:
                with ui.column().classes('items-center gap-3 p-4'):
                    ui.label('Escanea el codigo QR').classes(
                        'font-bold text-base'
                    ).style(f'color: {Colors.TEXT_PRIMARY};')

                    qr_container = ui.column().classes('items-center')
                    with qr_container:
                        ui.label('Generando QR...').classes('text-sm').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )

                    ui.label(
                        'Abre WhatsApp > Configuracion > Dispositivos vinculados\n'
                        '> Vincular dispositivo > Escanea el codigo QR'
                    ).classes('text-xs text-center').style(
                        f'color: {Colors.TEXT_MUTED};'
                    )

        # Polling timer
        def poll_status():
            if not state['timer_active']:
                return

            state['elapsed'] += POLL_SECONDS

            # Check timeout
            if (state['elapsed'] >= TIMEOUT_SECONDS
                    and state['phase'] == 'waiting'):
                state['phase'] = 'timeout'
                progress.set_value(0)
                timeout_card.set_visibility(True)

            if state['phase'] == 'done':
                return

            try:
                if state['phase'] == 'qr':
                    # QR mode: poll for QR
                    qr_data = wa_client.get_qr_status()
                    qr_status = qr_data.get('status', '')

                    if qr_status == 'connected':
                        _go_connected(
                            state, status_label, status_dot,
                            badge_label, progress
                        )
                        return
                    elif qr_status == 'waiting_scan':
                        qr_str = qr_data.get('qr', '')
                        if qr_str:
                            status_label.text = 'Escanea el codigo QR con WhatsApp'
                            _render_qr(qr_container, qr_str)
                    elif qr_status == 'initializing':
                        qr_container.clear()
                        with qr_container:
                            ui.label(
                                'Inicializando...\nEsto puede tomar unos segundos'
                            ).classes('text-sm text-center').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )
                    return

                # Normal polling
                if not wa_client.health_check():
                    status_label.text = 'Iniciando el bot...'
                    status_dot.content = '<span class="status-dot status-dot-disconnected"></span>'
                    badge_label.text = 'Bot no disponible'
                    detail_label.text = 'El bot de WhatsApp se esta iniciando'
                elif wa_client.is_whatsapp_connected():
                    _go_connected(
                        state, status_label, status_dot,
                        badge_label, progress
                    )
                else:
                    status_label.text = 'Esperando cuenta vinculada...'
                    status_dot.content = '<span class="status-dot status-dot-warning"></span>'
                    badge_label.text = 'Bot activo, WhatsApp no vinculado'
                    detail_label.text = ''

            except Exception:
                status_label.text = 'Conectando...'
                status_dot.content = '<span class="status-dot status-dot-disconnected"></span>'

        ui.timer(POLL_SECONDS, poll_status)


def _go_connected(state, status_label, status_dot, badge_label, progress):
    """Transición al dashboard"""
    state['phase'] = 'done'
    state['timer_active'] = False
    status_label.text = 'Conectado'
    status_dot.content = '<span class="status-dot status-dot-connected"></span>'
    badge_label.text = 'WhatsApp conectado'
    badge_label.style(f'color: {Colors.SUCCESS};')
    progress.set_value(1.0)
    ui.timer(0.8, lambda: ui.navigate.to('/'), once=True)


def _do_logout(state, wa_client, timeout_card, qr_card,
               status_label, status_dot, badge_label, progress):
    """Desvincular WhatsApp y mostrar QR"""
    state['phase'] = 'qr'
    timeout_card.set_visibility(False)
    qr_card.set_visibility(True)
    status_label.text = 'Desvinculando cuenta...'
    status_dot.content = '<span class="status-dot status-dot-disconnected"></span>'
    badge_label.text = 'Desvinculando...'
    progress.set_value(None)  # indeterminate

    try:
        wa_client.logout()
    except Exception:
        pass


def _render_qr(container, qr_string: str):
    """Genera y muestra la imagen del QR como base64"""
    if not QR_AVAILABLE:
        container.clear()
        with container:
            ui.code(qr_string).classes('text-xs')
        return

    try:
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(qr_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((220, 220))

        # Convert to base64 for display in browser
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        b64 = base64.b64encode(buffer.getvalue()).decode()

        container.clear()
        with container:
            ui.html(
                f'<img src="data:image/png;base64,{b64}" '
                f'style="width: 220px; height: 220px;" />'
            )
    except Exception:
        container.clear()
        with container:
            ui.label('Error generando QR').style(f'color: {Colors.ERROR};')
