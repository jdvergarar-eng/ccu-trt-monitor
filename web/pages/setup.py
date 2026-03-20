# Setup wizard page - Configuracion inicial (primer uso)
import io
import base64
import asyncio
from nicegui import ui
from pathlib import Path
from ..theme import Colors
from ..auth import require_auth
from core import (
    get_config_manager, get_trt_client, get_whatsapp_client,
    AppConfig, SiteConfig
)

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


def setup_setup_page():
    """Registra la página del wizard de setup"""

    @ui.page('/setup')
    def setup_page():
        require_auth()
        config_manager = get_config_manager()

        if config_manager.exists() and config_manager.config.sites:
            ui.navigate.to('/')
            return

        ui.page_title('Configuración Inicial - CCU TRT Monitor')

        state = {
            'base_url': 'http://192.168.55.79',
            'poll_seconds': 10,
            'wa_connected': False,
            'trt_connected': False,
            'setup_sites': [],
            'whatsapp_groups': [],
            'timer_active': True,
        }

        btn_refs = {
            'next_wa': None,
            'next_trt': None,
            'next_centers': None,
        }

        with ui.column().classes('w-full max-w-4xl mx-auto gap-6 p-8'):
            logo_path = ASSETS_DIR / "Logo_CCU.png"
            if logo_path.exists():
                ui.image(str(logo_path)).classes('mx-auto').style('width: 160px;')

            ui.label('Configuración Inicial').classes(
                'text-3xl font-bold text-center w-full'
            ).style(f'color: {Colors.TEXT_PRIMARY};')
            ui.label('Configura el sistema de alertas TRT paso a paso').classes(
                'text-center w-full text-sm'
            ).style(f'color: {Colors.TEXT_MUTED};')

            with ui.stepper().props('vertical').classes('w-full') as stepper:

                # ============================================================
                # Paso 1: WhatsApp (obligatorio)
                # ============================================================
                with ui.step('WhatsApp'):
                    ui.label('Conecta el bot de WhatsApp').classes('font-bold text-base mb-1')
                    ui.label(
                        'Escanea el código QR con tu teléfono. '
                        'La conexión es obligatoria para continuar.'
                    ).classes('text-sm mb-4').style(f'color: {Colors.TEXT_MUTED};')

                    with ui.card().classes('w-full').style(
                        'border: 1px solid #E2E8F0; background: white;'
                    ):
                        with ui.column().classes('items-center gap-3 p-4 w-full'):
                            wa_status_row = ui.row().classes('items-center gap-2')
                            with wa_status_row:
                                wa_dot = ui.html(
                                    '<span class="status-dot status-dot-disconnected"></span>'
                                )
                                wa_status_lbl = ui.label('Iniciando bot...').classes(
                                    'text-sm font-medium'
                                ).style(f'color: {Colors.TEXT_MUTED};')

                            qr_container = ui.column().classes('items-center')
                            with qr_container:
                                ui.label('Esperando código QR...').classes('text-sm').style(
                                    f'color: {Colors.TEXT_MUTED};'
                                )

                            wa_hint = ui.label(
                                'Abre WhatsApp > Configuración > Dispositivos vinculados > Vincular dispositivo'
                            ).classes('text-xs text-center').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )

                    def poll_wa():
                        if not state['timer_active']:
                            return
                        try:
                            wa = get_whatsapp_client()
                            qr_data = wa.get_qr_status()
                            status = qr_data.get('status', '')

                            if status == 'connected':
                                state['wa_connected'] = True
                                state['timer_active'] = False
                                wa_dot.content = (
                                    '<span class="status-dot status-dot-connected"></span>'
                                )
                                wa_status_lbl.text = 'WhatsApp conectado'
                                wa_status_lbl.style(f'color: {Colors.SUCCESS};')
                                wa_hint.set_visibility(False)
                                qr_container.clear()
                                with qr_container:
                                    ui.icon('check_circle').style(
                                        f'color: {Colors.SUCCESS}; font-size: 48px;'
                                    )
                                if btn_refs['next_wa']:
                                    btn_refs['next_wa'].enable()
                                ui.notify('¡WhatsApp conectado!', type='positive')

                            elif status == 'waiting_scan':
                                qr_str = qr_data.get('qr', '')
                                if qr_str:
                                    wa_status_lbl.text = 'Escanea el código QR'
                                    wa_status_lbl.style(f'color: {Colors.WARNING};')
                                    wa_dot.content = (
                                        '<span class="status-dot status-dot-warning"></span>'
                                    )
                                    _render_qr_to(qr_container, qr_str)

                            elif status == 'initializing':
                                wa_status_lbl.text = 'Inicializando bot...'
                            else:
                                wa_status_lbl.text = f'Estado: {status}. Esperando...'

                        except Exception:
                            wa_status_lbl.text = 'Bot no disponible. Iniciando...'

                    state['wa_timer'] = ui.timer(3, poll_wa)

                    def go_next_wa():
                        state['timer_active'] = False
                        try:
                            state['wa_timer'].cancel()
                        except Exception:
                            pass
                        stepper.next()

                    with ui.stepper_navigation():
                        btn_refs['next_wa'] = ui.button(
                            'Siguiente', icon='arrow_forward',
                            on_click=go_next_wa
                        ).props('color=green-7')
                        btn_refs['next_wa'].disable()

                # ============================================================
                # Paso 2: Configuración TRT (obligatorio)
                # ============================================================
                with ui.step('Configuración'):
                    ui.label('Conexión al servidor TRT').classes('font-bold text-base mb-1')
                    ui.label(
                        'Ingresa la URL del servidor. '
                        'Debes probar la conexión exitosamente para continuar.'
                    ).classes('text-sm mb-4').style(f'color: {Colors.TEXT_MUTED};')

                    url_input = ui.input(
                        'URL del servidor TRT',
                        value=state['base_url']
                    ).classes('w-full')

                    poll_input = ui.number(
                        'Intervalo de consulta (segundos)',
                        value=state['poll_seconds'],
                        min=5, max=300
                    ).classes('w-full')

                    with ui.row().classes('items-center gap-3 mt-2'):
                        test_icon = ui.icon('circle').style(
                            f'color: {Colors.TEXT_MUTED}; font-size: 12px;'
                        )
                        test_lbl = ui.label('Sin probar').classes('text-sm').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )

                    def test_connection():
                        state['base_url'] = url_input.value or state['base_url']
                        state['poll_seconds'] = int(poll_input.value or 10)
                        test_lbl.text = 'Probando conexión...'
                        test_lbl.style(f'color: {Colors.TEXT_MUTED};')
                        try:
                            trt = get_trt_client(state['base_url'])
                            if trt.test_connection(verbose=True):
                                state['trt_connected'] = True
                                test_icon.style(f'color: {Colors.SUCCESS}; font-size: 12px;')
                                test_lbl.text = 'Conexión exitosa al servidor TRT'
                                test_lbl.style(f'color: {Colors.SUCCESS};')
                                if btn_refs['next_trt']:
                                    btn_refs['next_trt'].enable()
                                ui.notify('Conexión al servidor TRT exitosa', type='positive')
                            else:
                                state['trt_connected'] = False
                                test_icon.style(f'color: {Colors.ERROR}; font-size: 12px;')
                                test_lbl.text = 'No se pudo conectar al servidor'
                                test_lbl.style(f'color: {Colors.ERROR};')
                                if btn_refs['next_trt']:
                                    btn_refs['next_trt'].disable()
                        except Exception as e:
                            state['trt_connected'] = False
                            test_icon.style(f'color: {Colors.ERROR}; font-size: 12px;')
                            test_lbl.text = f'Error: {str(e)[:80]}'
                            test_lbl.style(f'color: {Colors.ERROR};')
                            if btn_refs['next_trt']:
                                btn_refs['next_trt'].disable()

                    ui.button(
                        'Probar conexión', on_click=test_connection, icon='wifi'
                    ).props('color=green-7').classes('mt-2')

                    with ui.stepper_navigation():
                        btn_refs['next_trt'] = ui.button(
                            'Siguiente', icon='arrow_forward',
                            on_click=stepper.next
                        ).props('color=green-7')
                        btn_refs['next_trt'].disable()
                        ui.button('Atrás', on_click=stepper.previous).props('flat')

                # ============================================================
                # Paso 3: Centros
                # ============================================================
                with ui.step('Centros'):
                    ui.label('Centros a monitorear').classes('font-bold text-base mb-1')
                    ui.label(
                        'Agrega al menos un centro de distribución. '
                        'Puedes agregar más después desde el menú de Centros.'
                    ).classes('text-sm mb-4').style(f'color: {Colors.TEXT_MUTED};')

                    @ui.refreshable
                    def centers_view():
                        if not state['setup_sites']:
                            with ui.card().classes('w-full').style(
                                'border: 2px dashed #E2E8F0; background: #FAFAFA;'
                            ):
                                ui.label(
                                    'Aún no hay centros. Usa el botón "+ Agregar Centro".'
                                ).classes('text-sm text-center py-8 w-full').style(
                                    f'color: {Colors.TEXT_MUTED};'
                                )
                        else:
                            for site in list(state['setup_sites']):
                                _setup_center_row(
                                    site, state,
                                    centers_view.refresh,
                                    btn_refs,
                                )

                    centers_view()

                    async def open_add():
                        loop = asyncio.get_event_loop()
                        available_centers = []
                        whatsapp_groups = []
                        try:
                            trt_client = get_trt_client(state['base_url'])
                            centers = await loop.run_in_executor(
                                None, trt_client.get_available_centers
                            )
                            available_centers = [
                                {'name': c.name, 'referer_id': c.referer_id,
                                 'db_name': c.db_name, 'op_code': c.op_code,
                                 'cd_code': c.cd_code}
                                for c in centers
                            ]
                        except Exception:
                            pass
                        try:
                            wa_client = get_whatsapp_client()
                            groups = await loop.run_in_executor(
                                None, wa_client.get_groups
                            )
                            whatsapp_groups = [{'id': g.id, 'name': g.name} for g in groups]
                            state['whatsapp_groups'] = whatsapp_groups
                        except Exception:
                            pass
                        _show_center_dialog(
                            state=state,
                            on_save=lambda s: _on_site_saved(
                                s, state, centers_view.refresh, btn_refs
                            ),
                            available_centers=available_centers,
                            whatsapp_groups=whatsapp_groups,
                        )

                    ui.button(
                        'Agregar Centro', on_click=open_add, icon='add'
                    ).props('color=green-7').classes('mt-2')

                    with ui.stepper_navigation():
                        btn_refs['next_centers'] = ui.button(
                            'Siguiente', icon='arrow_forward',
                            on_click=stepper.next
                        ).props('color=green-7')
                        btn_refs['next_centers'].disable()
                        ui.button('Atrás', on_click=stepper.previous).props('flat')

                # ============================================================
                # Paso 4: Finalizar
                # ============================================================
                with ui.step('Finalizar'):
                    ui.label('Resumen de configuración').classes('font-bold text-lg mb-4')

                    @ui.refreshable
                    def summary_view():
                        with ui.column().classes('w-full gap-3'):
                            with ui.card().classes('w-full p-4').style(
                                'border-left: 4px solid #E2E8F0;'
                            ):
                                ui.label('Conexión TRT').classes('text-xs font-bold').style(
                                    f'color: {Colors.TEXT_MUTED};'
                                )
                                ui.label(state['base_url']).classes('text-base font-medium')
                                ui.label(
                                    f'Consulta cada {state["poll_seconds"]}s'
                                ).classes('text-sm').style(f'color: {Colors.TEXT_MUTED};')

                            if state['setup_sites']:
                                ui.label(
                                    f'{len(state["setup_sites"])} centro(s) configurado(s)'
                                ).classes('text-sm font-bold').style(
                                    f'color: {Colors.TEXT_PRIMARY};'
                                )
                                for site in state['setup_sites']:
                                    with ui.card().classes('w-full p-3').style(
                                        f'border-left: 4px solid {Colors.ACTION_GREEN};'
                                    ):
                                        ui.label(site.name).classes('font-bold text-base')
                                        ui.label(
                                            f'Lateral: {site.umbral_minutes_lateral} min  |  '
                                            f'Trasera: {site.umbral_minutes_trasera} min  |  '
                                            f'Interna: {site.umbral_minutes_interna} min  |  '
                                            f'Re-alerta: {site.realert_minutes} min'
                                        ).classes('text-xs').style(
                                            f'color: {Colors.TEXT_MUTED};'
                                        )

                    summary_view()

                    def finish_setup():
                        if not state['setup_sites']:
                            ui.notify('Debes agregar al menos un centro', type='negative')
                            return
                        config = AppConfig(
                            base_url=state['base_url'],
                            poll_seconds=state['poll_seconds'],
                            realert_minutes=30,
                            sites=state['setup_sites'],
                        )
                        config_manager.save(config)
                        ui.notify('¡Configuración guardada exitosamente!', type='positive')
                        ui.navigate.to('/')

                    with ui.stepper_navigation():
                        ui.button(
                            'Guardar y comenzar', on_click=finish_setup, icon='check'
                        ).props('color=green-7')
                        ui.button('Atrás', on_click=lambda: (
                            summary_view.refresh(), stepper.previous()
                        )).props('flat')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _on_site_saved(site, state, refresh_fn, btn_refs):
    """Agrega o reemplaza un centro en el estado del setup"""
    state['setup_sites'] = [s for s in state['setup_sites'] if s.name != site.name]
    state['setup_sites'].append(site)
    refresh_fn()
    if state['setup_sites'] and btn_refs.get('next_centers'):
        btn_refs['next_centers'].enable()


def _setup_center_row(site, state, refresh_fn, btn_refs):
    """Tarjeta de un centro en el paso 3 del setup"""
    with ui.card().classes('w-full').style(
        f'border-left: 4px solid {Colors.ACTION_GREEN}; background: white;'
    ):
        with ui.row().classes('w-full items-center justify-between p-2'):
            with ui.column().classes('gap-1 flex-1'):
                ui.label(site.name).classes('font-bold text-base').style(
                    f'color: {Colors.TEXT_PRIMARY};'
                )
                with ui.row().classes('gap-4'):
                    for lbl, val in [
                        ('Lateral', site.umbral_minutes_lateral),
                        ('Trasera', site.umbral_minutes_trasera),
                        ('Interna', site.umbral_minutes_interna),
                    ]:
                        with ui.column().classes('gap-0'):
                            ui.label(lbl).classes('text-xs').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )
                            ui.label(f'{val} min').classes('text-sm font-bold').style(
                                f'color: {Colors.TEXT_PRIMARY};'
                            )
                    with ui.column().classes('gap-0'):
                        ui.label('Re-alerta').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        ui.label(f'{site.realert_minutes} min').classes('text-sm font-bold').style(
                            f'color: {Colors.TEXT_PRIMARY};'
                        )
                if site.whatsapp_group_id:
                    ui.label(f'Grupo: {site.whatsapp_group_id}').classes('text-xs').style(
                        f'color: {Colors.ACTION_GREEN};'
                    )

            with ui.row().classes('gap-1 items-center'):
                async def edit_site(s=site):
                    loop = asyncio.get_event_loop()
                    whatsapp_groups = []
                    try:
                        wa_client = get_whatsapp_client()
                        groups = await loop.run_in_executor(None, wa_client.get_groups)
                        whatsapp_groups = [{'id': g.id, 'name': g.name} for g in groups]
                        state['whatsapp_groups'] = whatsapp_groups
                    except Exception:
                        pass
                    _show_center_dialog(
                        state=state,
                        on_save=lambda new_s: _on_site_saved(new_s, state, refresh_fn, btn_refs),
                        existing_site=s,
                        whatsapp_groups=whatsapp_groups,
                    )

                ui.button(
                    '', icon='edit', on_click=edit_site
                ).props('flat color=green-7 size=sm round')

                def do_delete(name=site.name):
                    state['setup_sites'] = [
                        s for s in state['setup_sites'] if s.name != name
                    ]
                    refresh_fn()
                    if not state['setup_sites'] and btn_refs.get('next_centers'):
                        btn_refs['next_centers'].disable()

                ui.button(
                    '', icon='delete', on_click=do_delete
                ).props('flat color=red-7 size=sm round')


def _show_center_dialog(state, on_save, existing_site=None,
                        available_centers=None, whatsapp_groups=None):
    """Diálogo para agregar o editar un centro.
    Datos pre-fetched para no bloquear el event loop."""
    if available_centers is None:
        available_centers = []
    if whatsapp_groups is None:
        whatsapp_groups = state.get('whatsapp_groups', [])

    is_edit = existing_site is not None
    title = f'Editar: {existing_site.name}' if is_edit else 'Agregar Centro'

    # Estado interno: datos técnicos del centro seleccionado
    sel = {
        'center': None,   # dict con datos técnicos del centro TRT
        'wa_id': existing_site.whatsapp_group_id if is_edit else '',
    }
    if is_edit:
        # En edición los datos técnicos vienen del sitio existente
        sel['center'] = {
            'referer_id': existing_site.referer_id,
            'db_name': existing_site.db_name,
            'op_code': existing_site.op_code,
            'cd_code': existing_site.cd_code,
        }

    save_btn = [None]  # referencia mutable al botón

    def _check():
        """Habilita el botón solo si todos los campos obligatorios están completos."""
        if save_btn[0] is None:
            return
        name_ok = bool((name_inp.value or '').strip())
        center_ok = is_edit or (sel['center'] is not None)
        group_ok = bool(sel['wa_id'])
        lateral_ok = lat_inp.value is not None and float(lat_inp.value) > 0
        realert_ok = realert_inp.value is not None and float(realert_inp.value) > 0
        if name_ok and center_ok and group_ok and lateral_ok and realert_ok:
            save_btn[0].enable()
        else:
            save_btn[0].disable()

    with ui.dialog() as dialog, ui.card().style(
        'width: 560px; max-width: 92vw; max-height: 88vh; overflow-y: auto;'
    ):
        ui.label(title).classes('text-xl font-bold').style(
            f'color: {Colors.TEXT_PRIMARY};'
        )

        # ── Centro ──────────────────────────────────────────────────────────
        ui.label('Centro *').classes('text-sm font-bold mt-3').style(
            f'color: {Colors.TEXT_SECONDARY};'
        )
        if not is_edit:
            if available_centers:
                def on_center_select(e):
                    for c in available_centers:
                        if c['name'] == e.value:
                            sel['center'] = c
                            name_inp.value = c['name']
                            _check()
                            break

                ui.select(
                    [c['name'] for c in available_centers],
                    label='Buscar y seleccionar centro',
                    with_input=True,
                    on_change=on_center_select,
                ).classes('w-full')
            else:
                ui.label(
                    'No se encontraron centros en el servidor TRT.'
                ).classes('text-sm').style(f'color: {Colors.ERROR};')

        name_inp = ui.input(
            'Nombre del centro *',
            value=existing_site.name if is_edit else '',
            on_change=lambda e: _check(),
        ).classes('w-full')
        if not is_edit:
            ui.label(
                'Se completa al seleccionar arriba. Puedes editarlo si necesitas otro nombre.'
            ).classes('text-xs').style(f'color: {Colors.TEXT_MUTED};')

        # ── WhatsApp ─────────────────────────────────────────────────────────
        ui.separator()
        ui.label('Grupo WhatsApp *').classes('text-sm font-bold').style(
            f'color: {Colors.TEXT_SECONDARY};'
        )
        if whatsapp_groups:
            group_map = {g['name']: g['id'] for g in whatsapp_groups}
            current_group_name = next(
                (g['name'] for g in whatsapp_groups if g['id'] == sel['wa_id']),
                None,
            )

            def on_group_sel(e):
                sel['wa_id'] = group_map.get(e.value, '')
                _check()

            ui.select(
                list(group_map.keys()),
                value=current_group_name,
                label='Buscar y seleccionar grupo',
                with_input=True,
                on_change=on_group_sel,
            ).classes('w-full')
        else:
            ui.label(
                'No se encontraron grupos. Asegúrate de que el bot está conectado y tiene grupos.'
            ).classes('text-sm').style(f'color: {Colors.WARNING};')

        # ── Umbrales ─────────────────────────────────────────────────────────
        ui.separator()
        ui.label('Umbrales de tiempo (minutos)').classes('text-sm font-bold').style(
            f'color: {Colors.TEXT_SECONDARY};'
        )
        with ui.row().classes('w-full gap-4'):
            lat_val = existing_site.umbral_minutes_lateral if is_edit else None
            tra_val = existing_site.umbral_minutes_trasera if is_edit else None
            int_val = existing_site.umbral_minutes_interna if is_edit else None

            lat_inp = ui.number(
                'Lateral *', min=0, value=lat_val,
                on_change=lambda e: _check(),
            ).classes('flex-1')
            tra_inp = ui.number('Trasera', min=0, value=tra_val).classes('flex-1')
            int_inp = ui.number('Interna', min=0, value=int_val).classes('flex-1')

        ui.label(
            '* Lateral es obligatorio. Trasera e Interna son opcionales según el centro.'
        ).classes('text-xs').style(f'color: {Colors.TEXT_MUTED};')

        # ── Reenvío ───────────────────────────────────────────────────────────
        ui.separator()
        realert_val = existing_site.realert_minutes if is_edit else None
        realert_inp = ui.number(
            'Reenvío de alertas (minutos) *',
            min=1, max=480,
            value=realert_val,
            on_change=lambda e: _check(),
        ).classes('w-full')
        ui.label(
            'Tiempo mínimo entre alertas repetidas para este centro.'
        ).classes('text-xs').style(f'color: {Colors.TEXT_MUTED};')

        # ── Botones ───────────────────────────────────────────────────────────
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancelar', on_click=dialog.close).props('flat')

            def save():
                n = (name_inp.value or '').strip()
                if not n:
                    ui.notify('El nombre del centro es obligatorio', type='negative')
                    return
                if not sel['center']:
                    ui.notify('Debes seleccionar un centro de la lista', type='negative')
                    return
                if not sel['wa_id']:
                    ui.notify('Debes seleccionar un grupo de WhatsApp', type='negative')
                    return
                if not lat_inp.value or float(lat_inp.value) <= 0:
                    ui.notify('El umbral Lateral es obligatorio', type='negative')
                    return
                if not realert_inp.value or float(realert_inp.value) <= 0:
                    ui.notify('El reenvío de alertas es obligatorio', type='negative')
                    return

                c = sel['center']
                site = SiteConfig(
                    name=n,
                    referer_id=c['referer_id'],
                    db_name=c['db_name'],
                    op_code=str(c['op_code']),
                    cd_code=c.get('cd_code', ''),
                    whatsapp_group_id=sel['wa_id'],
                    umbral_minutes_lateral=int(lat_inp.value),
                    umbral_minutes_trasera=int(tra_inp.value or 0),
                    umbral_minutes_interna=int(int_inp.value or 0),
                    realert_minutes=int(realert_inp.value),
                )
                dialog.close()
                on_save(site)
                ui.notify(
                    f'Centro "{n}" {"actualizado" if is_edit else "agregado"}',
                    type='positive',
                )

            save_btn[0] = ui.button(
                'Guardar' if is_edit else 'Agregar', on_click=save
            ).props('color=green-7')
            save_btn[0].disable()
            # En edición: habilitar si los campos ya tienen valores válidos
            _check()

    dialog.open()


def _render_qr_to(container, qr_string: str):
    """Genera y muestra una imagen QR como base64 en un contenedor NiceGUI"""
    if not QR_AVAILABLE:
        container.clear()
        with container:
            ui.code(qr_string).classes('text-xs')
        return

    try:
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(qr_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img = img.resize((220, 220))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()

        container.clear()
        with container:
            ui.html(
                f'<img src="data:image/png;base64,{b64}" '
                f'style="width: 220px; height: 220px; border-radius: 8px;" />'
            )
    except Exception:
        container.clear()
        with container:
            ui.label('Error generando QR').style(f'color: {Colors.ERROR};')
