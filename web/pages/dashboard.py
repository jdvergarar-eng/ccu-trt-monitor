# Dashboard / Home page - Panel principal
from datetime import datetime
from nicegui import ui
from ..shared import page_layout, site_slug
from ..theme import Colors
from ..auth import require_auth
from core import get_monitoring_service, get_config_manager
from core.analytics import AnalyticsService

HOUR_LABELS = [f'{h:02d}h' for h in range(24)]

# ── JS formatters reutilizables para ECharts ──────────────────────────────────
_JS_YAXIS_FMT = (
    'function(value) { var h=Math.floor(value/60); var m=Math.round(value%60);'
    ' return (h<10?"0"+h:h)+":"+(m<10?"0"+m:m); }'
)
_JS_TOOLTIP_FMT = (
    'function(params) { if(!Array.isArray(params)) params=[params];'
    ' var s=params[0].name+"<br/>";'
    ' params.forEach(function(p){ var v=p.value||0;'
    ' var h=Math.floor(v/60); var m=Math.round(v%60);'
    ' var t=(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
    ' s+=p.marker+p.seriesName+": "+t+"<br/>"; });'
    ' return s; }'
)
_JS_TOOLTIP_MINI = (
    'function(params) { if(!Array.isArray(params)) params=[params];'
    ' var v=params[0]&&params[0].value||0;'
    ' var h=Math.floor(v/60); var m=Math.round(v%60);'
    ' var t=(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
    ' return params[0].name+": "+t; }'
)


def setup_dashboard_page():
    """Registra la pagina del dashboard"""

    @ui.page('/')
    def dashboard_page():
        require_auth()
        config_manager = get_config_manager()

        if not config_manager.exists() or not config_manager.config.sites:
            ui.navigate.to('/splash')
            return

        monitoring = get_monitoring_service()
        page_layout('Panel de Control', monitoring)

        # Auto-arrancar el monitor apenas se carga la página
        if not monitoring.monitor_running:
            monitoring.start()

        # ── Trucks dialog ──────────────────────────────────────────────────
        trucks_dialog = ui.dialog().props('maximized=false')
        trucks_dialog_title = {'value': ''}
        trucks_dialog_rows = {'value': []}

        with trucks_dialog, ui.card().classes('min-w-[600px]'):
            @ui.refreshable
            def trucks_dialog_content():
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label(trucks_dialog_title['value']).classes('font-bold text-lg').style(
                        f'color: {Colors.TEXT_PRIMARY};'
                    )
                    ui.button(icon='close', on_click=trucks_dialog.close).props('flat round dense')
                columns = [
                    {'name': 'estado', 'label': 'Estado', 'field': 'estado_label', 'align': 'left'},
                    {'name': 'plate', 'label': 'Patente', 'field': 'plate', 'align': 'left'},
                    {'name': 'company', 'label': 'Empresa', 'field': 'company', 'align': 'left'},
                    {'name': 'entry_type', 'label': 'Tipo', 'field': 'entry_type', 'align': 'left'},
                    {'name': 'time_in_plant', 'label': 'Tiempo en planta', 'field': 'time_in_plant',
                     'align': 'left', 'sortable': True},
                ]
                table = ui.table(
                    columns=columns, rows=trucks_dialog_rows['value'], row_key='plate'
                ).classes('w-full').props('dense flat bordered')
                table.add_slot('body-cell-estado', r'''
                    <q-td :props="props">
                        <span :style="{
                            background: props.row.status === 'red' ? '#FEE2E2'
                                      : props.row.status === 'yellow' ? '#FEF9C3' : '#DCFCE7',
                            color: props.row.status === 'red' ? '#DC2626'
                                 : props.row.status === 'yellow' ? '#D97706' : '#16A34A',
                            padding: '2px 8px', borderRadius: '10px',
                            fontWeight: '600', fontSize: '0.75rem',
                        }">{{ props.row.estado_label }}</span>
                    </q-td>
                ''')
                table.props(
                    ''':row-class="row => row.status === 'red' ? 'bg-red-1' '''
                    ''': row.status === 'yellow' ? 'bg-amber-1' : ''"'''
                )

            trucks_dialog_content()

        def open_trucks_dialog(center_name: str, trucks_list: list, thresholds: dict = None):
            if thresholds is None:
                thresholds = {'lateral': 60, 'trasera': 60, 'interna': 60}

            def _get_threshold(entry_type: str) -> int:
                et = (entry_type or '').upper()
                if 'INTERNA' in et:
                    return thresholds['interna']
                if 'TRASERA' in et:
                    return thresholds['trasera']
                return thresholds['lateral']

            def _classify(minutes: int, threshold: int):
                if threshold <= 0:
                    return 'green', 'Normal'
                ratio = minutes / threshold
                if ratio >= 1.3:
                    return 'red', 'Crítico'
                if ratio >= 0.8:
                    return 'yellow', 'Precaución'
                return 'green', 'Normal'

            trucks_dialog_title['value'] = f'Camiones en planta — {center_name}'
            rows = []
            for t in trucks_list:
                thr = _get_threshold(t.entry_type)
                status, label = _classify(t.time_in_plant_minutes, thr)
                rows.append({
                    'plate': t.plate,
                    'company': t.company[:30] if len(t.company) > 30 else t.company,
                    'entry_type': t.entry_type,
                    'time_in_plant': t.time_in_plant,
                    'status': status,
                    'estado_label': label,
                })
            trucks_dialog_rows['value'] = rows
            trucks_dialog_content.refresh()
            trucks_dialog.open()

        # ── Status + control cards (simple, refreshable) ───────────────────

        @ui.refreshable
        def status_cards():
            with ui.row().classes('w-full gap-4'):
                _status_card(
                    'WhatsApp',
                    'Conectado' if monitoring.bot_status == 'connected' else 'Desconectado',
                    monitoring.bot_status == 'connected',
                    'chat',
                )
                _status_card(
                    'Alertas WhatsApp',
                    'Activas' if monitoring.alerts_enabled else 'Pausadas',
                    monitoring.alerts_enabled and monitoring.bot_status == 'connected',
                    'notifications',
                )
                centers_data = monitoring.get_centers_data()
                _stat_card(
                    'Alertas activas',
                    str(sum(c["alerts"] for c in centers_data)),
                    'warning', Colors.WARNING,
                )
                _stat_card(
                    'Camiones en centros',
                    str(sum(c["trucks_in_plant"] for c in centers_data)),
                    'local_shipping', Colors.ICON_TRUCKS,
                )

        @ui.refreshable
        def control_card():
            with ui.card().classes('w-full ccu-card'):
                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-0'):
                        ui.label('Control del Monitor').classes('font-bold text-lg').style(
                            f'color: {Colors.TEXT_PRIMARY};'
                        )
                        if monitoring.last_update:
                            s = (datetime.now() - monitoring.last_update).seconds
                            ui.label(f'Ultima actualizacion: hace {s}s').classes('text-sm').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )
                        else:
                            ui.label('Ultima actualizacion: iniciando...').classes('text-sm').style(
                                f'color: {Colors.TEXT_MUTED};'
                            )
                    # Botón principal: activar/pausar alertas WhatsApp
                    if not monitoring.alerts_enabled:
                        ui.button(
                            'Activar alertas WhatsApp', icon='notifications',
                            on_click=lambda: (
                                monitoring.enable_alerts(),
                                control_card.refresh(),
                            )
                        ).props('color=green-7')
                    else:
                        ui.button(
                            'Pausar alertas WhatsApp', icon='notifications_off',
                            on_click=lambda: (
                                monitoring.disable_alerts(),
                                control_card.refresh(),
                            )
                        ).props('color=green-7 outline')

                # Banner de advertencia: alertas activas pero bot con problemas
                if monitoring.alerts_enabled:
                    if monitoring.bot_status == 'disconnected':
                        with ui.row().classes('w-full items-center gap-2 mt-2 p-2').style(
                            f'background:{Colors.ERROR_BG};border-radius:8px;'
                        ):
                            ui.icon('warning').style(f'color:{Colors.ERROR};font-size:18px;')
                            ui.label(
                                'El bot de WhatsApp no está disponible — '
                                'las alertas están bloqueadas hasta que el bot inicie.'
                            ).classes('text-sm flex-1').style(f'color:{Colors.ERROR};')
                    elif monitoring.bot_status == 'warning':
                        with ui.row().classes('w-full items-center gap-2 mt-2 p-2').style(
                            f'background:{Colors.WARNING_BG};border-radius:8px;'
                        ):
                            ui.icon('link_off').style(f'color:{Colors.ICON_TRUCKS};font-size:18px;')
                            ui.label(
                                'WhatsApp no está vinculado — '
                                'las alertas se enviarán en cuanto vincules tu cuenta.'
                            ).classes('text-sm flex-1').style(f'color:{Colors.ICON_TRUCKS};')
                            ui.button(
                                'Vincular', icon='qr_code',
                                on_click=lambda: ui.navigate.to('/settings'),
                            ).props('flat dense color=orange-7 size=sm')

        # ── Global historical charts (120s, refreshable) ──────────────────

        @ui.refreshable
        def global_charts():
            _global_charts()

        # ── Center cards (created ONCE, updated in-place) ─────────────────
        analytics_svc = AnalyticsService()
        sites = config_manager.config.sites
        initial_centers = {c['name']: c for c in monitoring.get_centers_data()}
        center_refs = {}  # site_name -> refs dict for in-place updates

        with ui.column().classes('w-full gap-4 p-4'):
            ui.label('Panel de Control').classes('text-2xl font-bold').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.label('Vista general del sistema de alertas TRT').classes('text-sm').style(
                f'color: {Colors.TEXT_MUTED};'
            )

            status_cards()
            control_card()
            global_charts()

            if sites:
                # Accesos directos Vista TV
                with ui.card().classes('w-full ccu-card'):
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('tv').style(f'color:{Colors.ACTION_GREEN};font-size:1.2rem;')
                            ui.label('Vista TV por Centro').style(
                                f'font-size:0.95rem;font-weight:700;color:{Colors.TEXT_PRIMARY};'
                            )
                        with ui.row().classes('gap-2 flex-wrap'):
                            for s in sites:
                                ui.button(
                                    s.name, icon='open_in_new',
                                    on_click=lambda sl=site_slug(s.name): ui.navigate.to(
                                        f'/centro/{sl}', new_tab=True)
                                ).props('outline color=green-7 size=sm')

                with ui.column().classes('w-full gap-4'):
                    for site in sites:
                        center = initial_centers.get(site.name, {
                            'name': site.name,
                            'trucks_in_plant': 0,
                            'alerts': 0,
                            'status': 'normal',
                            'threshold': site.umbral_minutes_lateral or 60,
                            'trucks_list': [],
                        })
                        today = analytics_svc.get_today_summary(site.name)
                        hourly = analytics_svc.get_today_hourly_data(site.name)
                        refs = _build_center_card(
                            center, today, hourly, monitoring, open_trucks_dialog
                        )
                        center_refs[site.name] = refs
            else:
                ui.label('No hay centros configurados.').classes('text-sm py-6').style(
                    f'color: {Colors.TEXT_MUTED};'
                )


        # ── Timer: 10s live updates ────────────────────────────────────────

        def refresh_dashboard():
            # Fast sections (just icon/label changes)
            status_cards.refresh()
            control_card.refresh()

            # Center cards: update data IN-PLACE without recreating anything
            centers_map = {c['name']: c for c in monitoring.get_centers_data()}

            for site_name, refs in center_refs.items():
                center = centers_map.get(site_name, {
                    'trucks_in_plant': 0, 'alerts': 0,
                    'status': 'normal', 'threshold': 60, 'trucks_list': [],
                })
                threshold = center.get('threshold', 60)

                # Live stats (in-place)
                refs['camiones'].set_text(str(center['trucks_in_plant']))

                alert_count = center['alerts']
                alert_color = Colors.ERROR if alert_count > 0 else Colors.SUCCESS
                refs['alertas'].set_content(
                    f'<span style="font-size:1.25rem;font-weight:700;color:{alert_color};">'
                    f'{alert_count}</span>'
                )

                sev_style, sev_text = _severity_info(center['status'])
                refs['severity_badge'].set_content(
                    f'<span style="{sev_style}padding:2px 10px;border-radius:12px;'
                    f'font-size:0.75rem;font-weight:bold;">{sev_text}</span>'
                )

                trucks_list = center.get('trucks_list', [])
                refs['trucks_cache']['trucks'] = trucks_list
                refs['trucks_btn'].set_visibility(bool(trucks_list))

                # Today summary (file read)
                today = analytics_svc.get_today_summary(site_name)
                refs['hoy_despachos'].set_text(str(today['total_dispatches']))

                trt_color = Colors.ERROR if today['avg_trt_min'] > threshold else Colors.TEXT_PRIMARY
                refs['hoy_trt'].set_content(
                    f'<span style="font-size:1.1rem;font-weight:700;color:{trt_color};">'
                    f'{_fmt_hhmm(today["avg_trt_min"])}</span>'
                )

                crit_color = Colors.ERROR if today['critical'] > 0 else Colors.SUCCESS
                refs['hoy_criticos'].set_content(
                    f'<span style="font-size:1.25rem;font-weight:700;color:{crit_color};">'
                    f'{today["critical"]}</span>'
                )

                # Mini-charts: in-place data update via ECharts setOption
                hourly = analytics_svc.get_today_hourly_data(site_name)
                counts = [hourly[h]['count'] for h in range(24)]
                avg_trts_m = [round(hourly[h]['avg_trt'], 1) for h in range(24)]

                refs['chart_trucks'].run_chart_method('setOption', {
                    'series': [{'data': counts}]
                })
                refs['chart_trt'].run_chart_method('setOption', {
                    'series': [
                        {'data': avg_trts_m},
                        {'data': [threshold] * 24},
                    ]
                })

        ui.timer(10.0, refresh_dashboard)

        # Global historical charts refresh independently (they show daily data)
        ui.timer(120.0, global_charts.refresh)


# ── Card builder (creates DOM once, returns refs for in-place updates) ────────

def _build_center_card(
    center: dict,
    today: dict,
    hourly: dict,
    monitoring=None,
    open_trucks_fn=None,
) -> dict:
    """Construye la tarjeta de un centro y retorna refs para actualizacion in-place."""
    refs = {}
    site_name = center['name']
    threshold = center.get('threshold', 60)
    alert_count = center['alerts']
    alert_color = Colors.ERROR if alert_count > 0 else Colors.SUCCESS
    sev_style, sev_text = _severity_info(center['status'])

    counts = [hourly[h]['count'] for h in range(24)]
    avg_trts_m = [round(hourly[h]['avg_trt'], 1) for h in range(24)]
    trt_color = Colors.ERROR if today['avg_trt_min'] > threshold else Colors.TEXT_PRIMARY
    crit_color = Colors.ERROR if today['critical'] > 0 else Colors.SUCCESS

    trucks_cache = {'trucks': center.get('trucks_list', [])}
    refs['trucks_cache'] = trucks_cache

    with ui.card().classes('ccu-card w-full'):
        # ── Header ────────────────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between'):
            ui.label(site_name).classes('font-bold text-lg').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            with ui.row().classes('items-center gap-2'):
                ui.button(
                    icon='tv',
                    on_click=lambda s=site_name: ui.navigate.to(
                        f'/centro/{site_slug(s)}', new_tab=True
                    ),
                ).props('flat round dense color=blue-7').tooltip('Abrir vista TV')
                if monitoring:
                    ui.button(
                        icon='send',
                        on_click=lambda s=site_name: _force_send(monitoring, s),
                    ).props('flat round dense color=green-7').tooltip('Forzar envio')
                refs['severity_badge'] = ui.html(
                    f'<span style="{sev_style}padding:2px 10px;border-radius:12px;'
                    f'font-size:0.75rem;font-weight:bold;">{sev_text}</span>'
                )

        ui.separator()

        # ── Two data sections ─────────────────────────────────────────────
        with ui.row().classes('w-full gap-3 mt-1'):

            # Left: Ahora en planta (live from MonitoringService)
            with ui.column().classes('flex-1 gap-1').style('min-width: 0;'):
                ui.label('Ahora en planta').classes('text-xs font-bold').style(
                    f'color: {Colors.TEXT_MUTED};text-transform:uppercase;letter-spacing:0.05em;'
                )
                with ui.row().classes('gap-4 mt-1 items-end').style('flex-wrap: nowrap;'):
                    with ui.column().classes('gap-0'):
                        ui.label('Camiones').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        refs['camiones'] = ui.label(
                            str(center['trucks_in_plant'])
                        ).classes('text-xl font-bold').style(f'color: {Colors.TEXT_PRIMARY};')

                    with ui.column().classes('gap-0'):
                        ui.label('Alertas activas').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        refs['alertas'] = ui.html(
                            f'<span style="font-size:1.25rem;font-weight:700;color:{alert_color};">'
                            f'{alert_count}</span>'
                        )

                _thr = {
                    'lateral': center.get('threshold_lateral', center.get('threshold', 60)),
                    'trasera': center.get('threshold_trasera', center.get('threshold', 60)),
                    'interna': center.get('threshold_interna', center.get('threshold', 60)),
                }
                refs['trucks_btn'] = ui.button(
                    'Ver camiones', icon='local_shipping',
                    on_click=lambda thr=_thr: open_trucks_fn(
                        site_name, trucks_cache['trucks'], thr
                    ) if open_trucks_fn else None,
                ).props('flat dense color=green-7').classes('mt-1')
                refs['trucks_btn'].set_visibility(bool(trucks_cache['trucks']))

            ui.separator().props('vertical')

            # Right: Hoy (from daily_data written by monitor_alertas.py)
            with ui.column().classes('flex-1 gap-1').style('min-width: 0;'):
                ui.label('Hoy').classes('text-xs font-bold').style(
                    f'color: {Colors.TEXT_MUTED};text-transform:uppercase;letter-spacing:0.05em;'
                )
                # Row 1: Despachos + Criticos (compact numbers)
                with ui.row().classes('gap-4 mt-1 items-end').style('flex-wrap: nowrap;'):
                    with ui.column().classes('gap-0'):
                        ui.label('Despachos').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        refs['hoy_despachos'] = ui.label(
                            str(today['total_dispatches'])
                        ).classes('text-xl font-bold').style(f'color: {Colors.TEXT_PRIMARY};')

                    with ui.column().classes('gap-0'):
                        ui.label('Criticos').classes('text-xs').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                        refs['hoy_criticos'] = ui.html(
                            f'<span style="font-size:1.25rem;font-weight:700;color:{crit_color};">'
                            f'{today["critical"]}</span>'
                        )

                # Row 2: TRT Prom (takes full width, no overflow)
                with ui.column().classes('gap-0 mt-1'):
                    ui.label('TRT Prom').classes('text-xs').style(
                        f'color: {Colors.TEXT_MUTED};'
                    )
                    refs['hoy_trt'] = ui.html(
                        f'<span style="font-size:1.1rem;font-weight:700;color:{trt_color};">'
                        f'{_fmt_hhmm(today["avg_trt_min"])}</span>'
                    )

        # ── Mini-charts (today by hour, created once, data updated in-place) ─
        with ui.row().classes('w-full gap-2 mt-2'):

            # Chart 1: Camiones despachados por hora
            with ui.column().classes('flex-1 gap-0').style('min-width: 0;'):
                ui.label('Camiones/hora (hoy)').classes('text-xs').style(
                    f'color: {Colors.TEXT_MUTED};font-weight:600;'
                )
                refs['chart_trucks'] = ui.echart({
                    'animation': True,
                    'grid': {'top': 4, 'bottom': 22, 'left': 24, 'right': 4},
                    'xAxis': {
                        'type': 'category',
                        'data': HOUR_LABELS,
                        'axisLabel': {'fontSize': 8, 'color': Colors.TEXT_MUTED, 'interval': 3},
                        'axisLine': {'show': False},
                        'axisTick': {'show': False},
                    },
                    'yAxis': {
                        'type': 'value',
                        'show': True,
                        'minInterval': 1,
                        'axisLabel': {'fontSize': 8, 'color': Colors.TEXT_MUTED},
                        'splitLine': {'lineStyle': {'color': '#f0f0f0'}},
                    },
                    'series': [{
                        'type': 'bar',
                        'data': counts,
                        'itemStyle': {'color': Colors.CHART_TODAY, 'borderRadius': [2, 2, 0, 0]},
                        'barMaxWidth': 12,
                    }],
                    'tooltip': {
                        'trigger': 'axis',
                        'formatter': '{b}: {c} camiones',
                        'textStyle': {'fontSize': 11},
                    },
                }).style('height: 130px;')

            # Chart 2: TRT promedio por hora (valores en minutos)
            with ui.column().classes('flex-1 gap-0').style('min-width: 0;'):
                ui.label('TRT por hora (hoy)').classes('text-xs').style(
                    f'color: {Colors.TEXT_MUTED};font-weight:600;'
                )
                refs['chart_trt'] = ui.echart({
                    'animation': True,
                    'grid': {'top': 4, 'bottom': 22, 'left': 48, 'right': 4},
                    'xAxis': {
                        'type': 'category',
                        'data': HOUR_LABELS,
                        'axisLabel': {'fontSize': 8, 'color': Colors.TEXT_MUTED, 'interval': 3},
                        'axisLine': {'show': False},
                        'axisTick': {'show': False},
                    },
                    'yAxis': {
                        'type': 'value',
                        'show': True,
                        'axisLabel': {
                            'fontSize': 8,
                            'color': Colors.TEXT_MUTED,
                            ':formatter': _JS_YAXIS_FMT,
                        },
                        'splitLine': {'lineStyle': {'color': '#f0f0f0'}},
                    },
                    'series': [
                        {
                            'type': 'line',
                            'data': avg_trts_m,
                            'smooth': True,
                            'symbol': 'circle',
                            'symbolSize': 3,
                            'lineStyle': {'width': 2, 'color': Colors.CHART_TODAY},
                            'itemStyle': {'color': Colors.CHART_TODAY},
                            'areaStyle': {'color': f'{Colors.CHART_TODAY}20'},
                        },
                        {
                            'type': 'line',
                            'data': [threshold] * 24,
                            'symbol': 'none',
                            'lineStyle': {
                                'width': 1, 'type': 'dashed', 'color': Colors.CHART_THRESHOLD
                            },
                        },
                    ],
                    'tooltip': {
                        'trigger': 'axis',
                        ':formatter': _JS_TOOLTIP_MINI,
                        'textStyle': {'fontSize': 11},
                    },
                }).style('height: 130px;')

    return refs


# ── Shared helpers ────────────────────────────────────────────────────────────

def _fmt_hhmm(minutes: float) -> str:
    """Convierte minutos (float) a HH:MM."""
    if not minutes:
        return "00:00"
    total_m = int(round(minutes))
    return f"{total_m // 60:02d}:{total_m % 60:02d}"


def _severity_info(status: str):
    """Retorna (style_str, label_str) para el badge de severidad."""
    severity_styles = {
        "critical": f'background-color:{Colors.ERROR_BG};color:{Colors.ERROR};',
        "warning":  f'background-color:{Colors.WARNING_BG};color:{Colors.ICON_TRUCKS};',
        "normal":   f'background-color:{Colors.SUCCESS_BG};color:{Colors.SUCCESS};',
    }
    severity_text = {"critical": "CRITICO", "warning": "ALERTA", "normal": "NORMAL"}
    return severity_styles.get(status, severity_styles["normal"]), severity_text.get(status, "NORMAL")


def _force_send(monitoring, site_name: str):
    monitoring.force_send_banner(site_name)
    ui.notify(f'Forzando envio: {site_name}...', type='info')


def _global_charts():
    """Graficos globales de los ultimos 7 dias (todos los centros)"""
    analytics = AnalyticsService()
    trend = analytics.get_aggregated_daily_trend(days=7)

    dates = [d['date_str'] for d in trend]
    trucks = [d['total_trucks'] for d in trend]
    criticals = [d['total_critical'] for d in trend]
    avg_trts = [round(d['avg_trt_min'], 1) for d in trend]  # en minutos

    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('ccu-card flex-1'):
            ui.label('Despachos y Alertas (7 dias)').classes('font-bold text-sm').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.echart({
                'tooltip': {'trigger': 'axis'},
                'legend': {
                    'data': ['Despachos', 'Criticos'], 'bottom': 0,
                    'textStyle': {'fontSize': 11},
                },
                'grid': {'top': 20, 'bottom': 40, 'left': 40, 'right': 20},
                'xAxis': {'type': 'category', 'data': dates},
                'yAxis': {'type': 'value', 'name': 'Cantidad'},
                'series': [
                    {
                        'name': 'Despachos',
                        'type': 'bar',
                        'data': trucks,
                        'itemStyle': {'color': Colors.CHART_TODAY, 'borderRadius': [4, 4, 0, 0]},
                    },
                    {
                        'name': 'Criticos',
                        'type': 'line',
                        'data': criticals,
                        'lineStyle': {'color': Colors.CHART_THRESHOLD, 'width': 2},
                        'itemStyle': {'color': Colors.CHART_THRESHOLD},
                    },
                ],
            }).style('height: 220px;')

        with ui.card().classes('ccu-card flex-1'):
            ui.label('TRT Promedio (7 dias)').classes('font-bold text-sm').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.echart({
                'tooltip': {'trigger': 'axis', ':formatter': _JS_TOOLTIP_FMT},
                'grid': {'top': 20, 'bottom': 20, 'left': 56, 'right': 20},
                'xAxis': {'type': 'category', 'data': dates},
                'yAxis': {'type': 'value', 'axisLabel': {':formatter': _JS_YAXIS_FMT}},
                'series': [{
                    'name': 'TRT Prom',
                    'type': 'line',
                    'data': avg_trts,
                    'smooth': True,
                    'lineStyle': {'color': Colors.CHART_TODAY, 'width': 2},
                    'itemStyle': {'color': Colors.CHART_TODAY},
                    'areaStyle': {'color': f'{Colors.CHART_TODAY}25'},
                }],
            }).style('height: 220px;')


def _status_card(title: str, value: str, is_ok: bool, icon: str):
    with ui.card().classes('ccu-card flex-1 min-w-48'):
        with ui.row().classes('items-center gap-3'):
            bg_color = Colors.SUCCESS_BG if is_ok else Colors.ERROR_BG
            icon_color = Colors.SUCCESS if is_ok else Colors.ERROR
            with ui.element('div').style(
                f'background-color:{bg_color};border-radius:12px;'
                'width:52px;height:52px;display:flex;align-items:center;justify-content:center;'
            ):
                ui.icon(icon).style(f'color:{icon_color};font-size:24px;')
            with ui.column().classes('gap-0'):
                ui.label(title).classes('text-xs').style(f'color:{Colors.TEXT_MUTED};')
                status_color = Colors.SUCCESS if is_ok else Colors.ERROR
                with ui.row().classes('items-center gap-1'):
                    ui.html(f'<span class="status-dot" style="background-color:{status_color};"></span>')
                    ui.label(value).classes('text-sm font-bold').style(f'color:{status_color};')


def _stat_card(title: str, value: str, icon: str, color: str):
    with ui.card().classes('ccu-card flex-1 min-w-48'):
        with ui.row().classes('items-center gap-3'):
            with ui.element('div').style(
                f'background-color:{color}20;border-radius:12px;'
                'width:52px;height:52px;display:flex;align-items:center;justify-content:center;'
            ):
                ui.icon(icon).style(f'color:{color};font-size:24px;')
            with ui.column().classes('gap-0'):
                ui.label(title).classes('text-xs').style(f'color:{Colors.TEXT_MUTED};')
                ui.label(value).classes('text-2xl font-bold').style(f'color:{color};')
