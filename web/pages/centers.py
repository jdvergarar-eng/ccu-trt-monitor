# Centers page - Gestión de centros de distribución
import asyncio
from nicegui import ui
from ..shared import page_layout, site_slug
from ..theme import Colors
from ..auth import require_auth
from core import (
    get_config_manager, get_trt_client, get_whatsapp_client,
    SiteConfig, get_monitoring_service
)


def _fmt_min(m: int) -> str:
    """Convierte minutos enteros a HH:MM. Retorna '—' si 0 o None."""
    if not m:
        return '—'
    return f'{m // 60:02d}:{m % 60:02d}'


def setup_centers_page():
    """Registra la página de centros"""

    @ui.page('/centers')
    def centers_page():
        require_auth()
        monitoring = get_monitoring_service()
        config_manager = get_config_manager()
        page_layout('Centros de Distribución', monitoring)

        with ui.column().classes('w-full gap-4 p-4'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('gap-0'):
                    ui.label('Centros de Distribución').classes('text-2xl font-bold').style(
                        f'color: {Colors.TEXT_PRIMARY};'
                    )
                    ui.label('Administra los centros monitoreados').classes('text-sm').style(
                        f'color: {Colors.TEXT_MUTED};'
                    )

                async def open_add():
                    loop = asyncio.get_event_loop()
                    available_centers, whatsapp_groups = await _fetch_dialog_data(
                        loop, config_manager.config.base_url
                    )
                    _show_center_dialog(
                        config_manager=config_manager,
                        refresh_fn=centers_list_view.refresh,
                        available_centers=available_centers,
                        whatsapp_groups=whatsapp_groups,
                    )

                ui.button(
                    'Agregar Centro', on_click=open_add, icon='add'
                ).props('color=green-7')

            @ui.refreshable
            def centers_list_view():
                config = config_manager.config
                if not config.sites:
                    ui.label(
                        'No hay centros configurados. '
                        'Usa el botón "Agregar Centro" para comenzar.'
                    ).classes('text-sm py-10').style(f'color: {Colors.TEXT_MUTED};')
                    return
                for site in config.sites:
                    _center_row(site, config_manager, centers_list_view.refresh)

            centers_list_view()


def _center_row(site: SiteConfig, config_manager, refresh_fn):
    """Fila de un centro con acciones"""
    with ui.card().classes('w-full ccu-card'):
        with ui.row().classes('w-full items-start justify-between'):
            # Info
            with ui.column().classes('gap-2 flex-1'):
                ui.label(site.name).classes('text-lg font-bold').style(
                    f'color: {Colors.TEXT_PRIMARY};'
                )
                with ui.row().classes('gap-6'):
                    for label, value in [
                        ('Umbral Lateral', site.umbral_minutes_lateral),
                        ('Umbral Trasera', site.umbral_minutes_trasera),
                        ('Umbral Interna', site.umbral_minutes_interna),
                    ]:
                        with ui.column().classes('gap-0'):
                            ui.label(label).classes('text-xs').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )
                            val_text = _fmt_min(value)
                            val_color = Colors.TEXT_PRIMARY if value else Colors.TEXT_MUTED
                            ui.label(val_text).classes('text-base font-bold').style(
                                f'color: {val_color};'
                            )
                    with ui.column().classes('gap-0'):
                        ui.label('Re-alerta').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        ui.label(_fmt_min(site.realert_minutes)).classes('text-base font-bold').style(
                            f'color: {Colors.TEXT_PRIMARY};'
                        )

                group = site.whatsapp_group_id or site.group_id or 'No configurado'
                with ui.row().classes('items-center gap-2'):
                    ui.label('Grupo:').classes('text-sm').style(f'color: {Colors.TEXT_MUTED};')
                    ui.label(group).classes('text-sm font-bold').style(
                        f'color: {Colors.ACTION_GREEN};'
                    )

                with ui.row().classes('items-center gap-1 mt-1'):
                    if site.alerts_enabled:
                        ui.icon('notifications').style(f'color: {Colors.SUCCESS}; font-size: 16px;')
                        ui.label('Alertas activas').classes('text-xs font-bold').style(
                            f'color: {Colors.SUCCESS};'
                        )
                    else:
                        ui.icon('notifications_off').style(f'color: {Colors.TEXT_MUTED}; font-size: 16px;')
                        ui.label('Alertas desactivadas').classes('text-xs font-bold').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )

            # Actions
            with ui.row().classes('gap-2'):
                async def edit_center(s=site):
                    loop = asyncio.get_event_loop()
                    _, whatsapp_groups = await _fetch_dialog_data(loop, None)
                    _show_center_dialog(
                        config_manager=config_manager,
                        refresh_fn=refresh_fn,
                        existing_site=s,
                        whatsapp_groups=whatsapp_groups,
                    )

                ui.button(
                    'TV', icon='tv',
                    on_click=lambda s=site: ui.navigate.to(
                        f'/centro/{site_slug(s.name)}', new_tab=True
                    )
                ).props('outline color=blue-7 size=sm').tooltip('Abrir vista TV en nueva pestaña')

                ui.button(
                    'Editar', icon='edit', on_click=edit_center
                ).props('outline color=green-7 size=sm')

                ui.button(
                    'Eliminar', icon='delete',
                    on_click=lambda s=site: _confirm_delete(s, config_manager, refresh_fn)
                ).props('outline color=red-7 size=sm')


async def _fetch_dialog_data(loop, base_url):
    """Obtiene centros TRT y grupos WhatsApp en background threads (no bloquea el event loop)."""
    available_centers = []
    whatsapp_groups = []

    if base_url:
        try:
            trt_client = get_trt_client(base_url)
            centers = await loop.run_in_executor(None, trt_client.get_available_centers)
            available_centers = [
                {'name': c.name, 'referer_id': c.referer_id, 'db_name': c.db_name,
                 'op_code': c.op_code, 'cd_code': c.cd_code}
                for c in centers
            ]
        except Exception:
            pass

    try:
        wa_client = get_whatsapp_client()
        groups = await loop.run_in_executor(None, wa_client.get_groups)
        whatsapp_groups = [{'id': g.id, 'name': g.name} for g in groups]
    except Exception:
        pass

    return available_centers, whatsapp_groups


def _show_center_dialog(config_manager, refresh_fn=None,
                        existing_site=None,
                        available_centers=None, whatsapp_groups=None):
    """Diálogo unificado para agregar o editar un centro."""
    if available_centers is None:
        available_centers = []
    if whatsapp_groups is None:
        whatsapp_groups = []

    is_edit = existing_site is not None
    title = f'Editar: {existing_site.name}' if is_edit else 'Agregar Centro'

    sel = {
        'center': None,
        'wa_id': existing_site.whatsapp_group_id if is_edit else '',
    }
    if is_edit:
        sel['center'] = {
            'referer_id': existing_site.referer_id,
            'db_name': existing_site.db_name,
            'op_code': existing_site.op_code,
            'cd_code': existing_site.cd_code,
        }

    save_btn = [None]

    def _check():
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

        # ── Centro ────────────────────────────────────────────────────────────
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

        # ── WhatsApp ──────────────────────────────────────────────────────────
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
                'No se encontraron grupos. Verifica que el bot esté conectado.'
            ).classes('text-sm').style(f'color: {Colors.WARNING};')

        # ── Umbrales ──────────────────────────────────────────────────────────
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

        # ── Alertas WhatsApp ──────────────────────────────────────────────────
        ui.separator()
        alerts_enabled_inp = ui.switch(
            'Enviar alertas a WhatsApp',
            value=existing_site.alerts_enabled if is_edit else True,
        )
        ui.label(
            'Si está desactivado, este centro no recibirá alertas aunque las alertas globales estén activas.'
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
                    alerts_enabled=alerts_enabled_inp.value,
                )

                if is_edit:
                    config_manager.update_site(existing_site.name, site)
                    ui.notify(f'Centro "{n}" actualizado', type='positive')
                else:
                    config_manager.add_site(site)
                    ui.notify(f'Centro "{n}" agregado', type='positive')

                dialog.close()
                if refresh_fn:
                    refresh_fn()
                else:
                    ui.navigate.to('/centers')

            save_btn[0] = ui.button(
                'Guardar' if is_edit else 'Agregar', on_click=save
            ).props('color=green-7')
            save_btn[0].disable()
            _check()  # habilita si edit y campos ya válidos

    dialog.open()


def _confirm_delete(site: SiteConfig, config_manager, refresh_fn):
    """Confirma la eliminación de un centro"""
    with ui.dialog() as dialog, ui.card().style('width: 400px;'):
        ui.label('¿Eliminar centro?').classes('text-xl font-bold').style(
            f'color: {Colors.ERROR};'
        )
        ui.label(
            f'¿Estás seguro de eliminar "{site.name}"? Esta acción no se puede deshacer.'
        ).classes('text-sm').style(f'color: {Colors.TEXT_SECONDARY};')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancelar', on_click=dialog.close).props('flat')
            ui.button('Eliminar', on_click=lambda: _do_delete(
                config_manager, dialog, site.name, refresh_fn
            )).props('color=red-7')

    dialog.open()


def _do_delete(config_manager, dialog, site_name, refresh_fn):
    """Ejecuta la eliminación"""
    config_manager.remove_site(site_name)
    dialog.close()
    ui.notify(f'Centro "{site_name}" eliminado', type='warning')
    refresh_fn()
