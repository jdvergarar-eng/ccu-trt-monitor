# Analytics page - Estadísticas y gráficos TRT
from nicegui import ui
from ..shared import page_layout
from ..theme import Colors
from ..auth import require_auth
from core import get_config_manager, get_monitoring_service, AnalyticsService

# ── Constantes de tabla heatmap ────────────────────────────────────────────────
_WEEKDAY_LABELS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
_BLOCK_LABELS   = ['00–02', '03–05', '06–08', '09–11', '12–14', '15–17', '18–20', '21–23']

# ── JS formatters reutilizables para ECharts (minutos → HH:MM) ────────────────
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
_JS_MARKLINE_FMT = (
    'function(params) { var v=params.value||0;'
    ' var h=Math.floor(v/60); var m=Math.round(v%60);'
    ' return "Umbral "+(h<10?"0"+h:h)+":"+(m<10?"0"+m:m); }'
)


# ── Helpers de formato ─────────────────────────────────────────────────────────

def _mins_to_hhmm(minutes: float) -> str:
    """Convierte minutos (float) a HH:MM."""
    if not minutes:
        return '00:00'
    total_m = int(round(minutes))
    return f'{total_m // 60:02d}:{total_m % 60:02d}'



def _delta(current: float, previous, lower_is_better: bool = False):
    """Calcula delta entre períodos. Retorna str con signo o None."""
    if previous is None or previous == 0:
        return None
    diff = current - previous
    sign = "+" if diff >= 0 else ""
    return f"{sign}{round(diff, 1)}"



# ── Página principal ───────────────────────────────────────────────────────────

def setup_analytics_page():
    """Registra la página de estadísticas"""

    @ui.page('/analytics')
    def analytics_page():
        require_auth()
        monitoring = get_monitoring_service()
        config_manager = get_config_manager()
        analytics_service = AnalyticsService()
        page_layout('Estadísticas', monitoring)

        config = config_manager.config

        with ui.column().classes('w-full gap-4 p-4'):
            # Title
            ui.label('Estadísticas TRT').classes('text-2xl font-bold').style(
                f'color: {Colors.TEXT_PRIMARY};'
            )
            ui.label('Análisis de rendimiento por centro').classes('text-sm').style(
                f'color: {Colors.TEXT_MUTED};'
            )

            if not config.sites:
                with ui.card().classes('w-full ccu-card items-center py-10'):
                    ui.label('No hay centros configurados').classes('text-lg font-bold').style(
                        f'color: {Colors.TEXT_PRIMARY};'
                    )
                    ui.label(
                        'Agrega centros en la sección de Configuración para ver estadísticas.'
                    ).classes('text-sm').style(f'color: {Colors.TEXT_MUTED};')
                return

            # State
            state = {
                'center': config.sites[0].name,
                'period': 30,
                'compare': False,
            }

            # Usamos un dict mutable para guardar referencias a los containers
            # que se crean DESPUÉS de renderizar los filtros (así los filtros
            # aparecen arriba en la UI y los datos abajo).
            containers = {}

            def load_data():
                """Carga datos y actualiza gráficos"""
                center = state['center']
                days = state['period']
                compare = state['compare']

                # Get threshold for this center
                threshold = 60
                for site in config.sites:
                    if site.name == center:
                        threshold = site.umbral_minutes_lateral or site.umbral_minutes or 60
                        break

                try:
                    kpi_curr = analytics_service.get_kpi_summary(center, days, 0)
                    daily_curr = analytics_service.get_daily_trend(center, days, 0)
                    hourly_curr = analytics_service.get_hourly_distribution(center, days, 0)
                    heatmap_curr = analytics_service.get_heatmap_v2(center, days, 0)

                    kpi_prev = daily_prev = hourly_prev = heatmap_prev = None
                    if compare:
                        kpi_prev     = analytics_service.get_kpi_summary(center, days, days)
                        daily_prev   = analytics_service.get_daily_trend(center, days, days)
                        hourly_prev  = analytics_service.get_hourly_distribution(center, days, days)
                        heatmap_prev = analytics_service.get_heatmap_v2(center, days, days)
                except Exception as e:
                    ui.notify(f'Error cargando datos: {e}', type='negative')
                    return

                # Update KPIs
                containers['kpi_row'].clear()
                with containers['kpi_row']:
                    _kpi_card(
                        'TRT Promedio',
                        _mins_to_hhmm(kpi_curr["avg_trt_min"]),
                        '',
                        'schedule',
                        Colors.ACTION_GREEN,
                        delta=_delta(
                            kpi_curr["avg_trt_min"],
                            kpi_prev["avg_trt_min"] if kpi_prev else None,
                            lower_is_better=True,
                        ),
                        lower_is_better=True,
                    )
                    _kpi_card(
                        'Total Despachos',
                        str(kpi_curr["total_dispatches"]),
                        '',
                        'local_shipping',
                        Colors.ICON_TRUCKS,
                        delta=_delta(
                            kpi_curr["total_dispatches"],
                            kpi_prev["total_dispatches"] if kpi_prev else None,
                        ),
                    )
                    _kpi_card(
                        '% Críticos',
                        f'{kpi_curr["pct_critical"]}%',
                        '',
                        'warning',
                        Colors.ERROR if kpi_curr["pct_critical"] > 20 else Colors.WARNING,
                        delta=_delta(
                            kpi_curr["pct_critical"],
                            kpi_prev["pct_critical"] if kpi_prev else None,
                            lower_is_better=True,
                        ),
                        lower_is_better=True,
                    )
                    _kpi_card(
                        'TRT Máximo',
                        _mins_to_hhmm(kpi_curr["max_trt_min"]),
                        '',
                        'timer',
                        Colors.ERROR,
                        delta=_delta(
                            kpi_curr["max_trt_min"],
                            kpi_prev["max_trt_min"] if kpi_prev else None,
                            lower_is_better=True,
                        ),
                        lower_is_better=True,
                    )

                # Update charts
                containers['charts'].clear()
                with containers['charts']:
                    _daily_trend_chart(daily_curr, daily_prev, threshold, days, compare)
                    _hourly_chart(hourly_curr, hourly_prev, threshold, compare)
                    _heatmap_v2(heatmap_curr, heatmap_prev, threshold, compare)

            # Filters — refreshable para actualizar estilos de botones
            @ui.refreshable
            def filters_row():
                with ui.row().classes('gap-4 items-end flex-wrap'):
                    # Center selector
                    center_names = [s.name for s in config.sites]
                    ui.select(
                        center_names,
                        value=state['center'],
                        label='Centro',
                        on_change=lambda e: _update_state(state, 'center', e.value, load_data)
                    ).style('min-width: 200px;')

                    # Period buttons
                    with ui.row().classes('gap-1'):
                        for days_opt, label in [(7, '7 días'), (15, '15 días'), (30, '30 días')]:
                            def _on_period(d=days_opt):
                                state['period'] = d
                                filters_row.refresh()
                                load_data()
                            btn = ui.button(label, on_click=_on_period)
                            if days_opt == state['period']:
                                btn.props('color=green-7')
                            else:
                                btn.props('outline color=grey-7')

                    # Botón comparación
                    compare_label = (
                        'Comparando período anterior'
                        if state['compare']
                        else 'Comparar con período anterior'
                    )
                    compare_props = (
                        'color=blue-7' if state['compare'] else 'outline color=grey-7'
                    )

                    def _toggle_compare():
                        state['compare'] = not state['compare']
                        filters_row.refresh()
                        load_data()

                    ui.button(
                        compare_label,
                        icon='compare_arrows',
                        on_click=_toggle_compare
                    ).props(compare_props)

            # Render: filtros primero (aparecen arriba), luego containers de datos
            filters_row()

            # Crear containers DESPUÉS de los filtros → aparecen debajo en la UI
            containers['kpi_row'] = ui.row().classes('w-full gap-4')
            containers['charts'] = ui.column().classes('w-full gap-4')

            # Initial load
            load_data()


def _update_state(state, key, value, callback):
    """Actualiza estado y recarga"""
    state[key] = value
    callback()


def _kpi_card(
    title: str,
    value: str,
    unit: str,
    icon: str,
    color: str,
    delta: str = None,
    lower_is_better: bool = False,
):
    """Crea una tarjeta KPI con delta opcional vs período anterior."""
    with ui.card().classes('ccu-card flex-1 min-w-40'):
        with ui.row().classes('items-center gap-3'):
            with ui.element('div').style(
                f'background-color: {color}20; border-radius: 12px; '
                'width: 48px; height: 48px; display: flex; '
                'align-items: center; justify-content: center;'
            ):
                ui.icon(icon).style(f'color: {color}; font-size: 24px;')

            with ui.column().classes('gap-0'):
                ui.label(title).classes('text-xs').style(f'color: {Colors.TEXT_MUTED};')
                with ui.row().classes('items-baseline gap-1'):
                    ui.label(value).classes('text-2xl font-bold').style(
                        f'color: {Colors.TEXT_PRIMARY};'
                    )
                    if unit:
                        ui.label(unit).classes('text-sm').style(
                            f'color: {Colors.TEXT_MUTED};'
                        )
                if delta is not None:
                    # Verde si mejoró, rojo si empeoró
                    is_negative = delta.startswith('-')
                    improved = is_negative if lower_is_better else not is_negative
                    delta_color = Colors.SUCCESS if improved else Colors.ERROR
                    ui.label(f'{delta} vs período ant.').classes('text-xs').style(
                        f'color: {delta_color};'
                    )


def _daily_trend_chart(
    current: list,
    previous,
    threshold: int,
    days: int,
    compare: bool,
):
    """Gráfico de tendencia diaria con ECharts. Soporta modo comparación dual."""
    with ui.card().classes('w-full ccu-card'):
        ui.label('Tendencia TRT Diario').classes('font-bold text-lg').style(
            f'color: {Colors.TEXT_PRIMARY};'
        )
        ui.label(f'Promedio TRT por día - Últimos {days} días').classes('text-sm').style(
            f'color: {Colors.TEXT_MUTED};'
        )

        x_labels = [str(i) for i in range(1, days + 1)]
        curr_vals = [d[1] for d in current]

        series = [
            {
                'name': 'Período actual',
                'type': 'line',
                'data': curr_vals,
                'smooth': True,
                'areaStyle': {'color': '#009F4D20'},
                'lineStyle': {'color': '#009F4D'},
                'itemStyle': {'color': '#009F4D'},
                'markLine': {
                    'data': [{'yAxis': threshold, 'name': 'Umbral'}],
                    'lineStyle': {'color': '#D32F2F', 'type': 'dashed'},
                    'label': {'formatter': f'Umbral: {_mins_to_hhmm(threshold)}'},
                },
            }
        ]

        if compare and previous:
            prev_vals = [d[1] for d in previous]
            series.append({
                'name': 'Período anterior',
                'type': 'line',
                'data': prev_vals,
                'smooth': True,
                'lineStyle': {'color': '#3B82F6', 'type': 'dashed'},
                'itemStyle': {'color': '#3B82F6'},
            })

        ui.echart({
            'tooltip': {'trigger': 'axis', ':formatter': _JS_TOOLTIP_FMT},
            'legend': {'show': compare},
            'xAxis': {
                'type': 'category',
                'data': x_labels,
                'name': 'Día',
                'axisLabel': {'rotate': 45},
            },
            'yAxis': {
                'type': 'value',
                'axisLabel': {':formatter': _JS_YAXIS_FMT},
            },
            'series': series,
        }).style('height: 350px;')


def _hourly_chart(current: dict, previous, threshold: int, compare: bool):
    """Gráfico de distribución por hora. Barras agrupadas en modo comparación."""
    with ui.card().classes('w-full ccu-card'):
        ui.label('Distribución por Hora de Llegada').classes('font-bold text-lg').style(
            f'color: {Colors.TEXT_PRIMARY};'
        )
        ui.label('TRT promedio según hora de ingreso a planta').classes('text-sm').style(
            f'color: {Colors.TEXT_MUTED};'
        )

        hours = [f'{h:02d}:00' for h in range(24)]
        curr_vals = [current.get(h, 0) for h in range(24)]

        if compare and previous:
            prev_vals = [previous.get(h, 0) for h in range(24)]
            series = [
                {
                    'name': 'Período anterior',
                    'type': 'bar',
                    'data': prev_vals,
                    'itemStyle': {'color': '#3B82F6'},
                    'barMaxWidth': 14,
                },
                {
                    'name': 'Período actual',
                    'type': 'bar',
                    'data': curr_vals,
                    'itemStyle': {'color': '#009F4D'},
                    'barMaxWidth': 14,
                    'markLine': {
                        'data': [{'yAxis': threshold}],
                        'lineStyle': {'color': '#D32F2F', 'type': 'dashed'},
                        'label': {':formatter': _JS_MARKLINE_FMT},
                    },
                },
            ]
            legend = {'show': True}
        else:
            bar_colors = ['#D32F2F' if v >= threshold else '#009F4D' for v in curr_vals]
            series = [
                {
                    'name': 'TRT Promedio',
                    'type': 'bar',
                    'data': [
                        {'value': v, 'itemStyle': {'color': c}}
                        for v, c in zip(curr_vals, bar_colors)
                    ],
                    'markLine': {
                        'data': [{'yAxis': threshold}],
                        'lineStyle': {'color': '#D32F2F', 'type': 'dashed'},
                        'label': {':formatter': _JS_MARKLINE_FMT},
                    },
                }
            ]
            legend = {'show': False}

        ui.echart({
            'tooltip': {'trigger': 'axis', ':formatter': _JS_TOOLTIP_FMT},
            'legend': legend,
            'xAxis': {
                'type': 'category',
                'data': hours,
            },
            'yAxis': {
                'type': 'value',
                'axisLabel': {':formatter': _JS_YAXIS_FMT},
            },
            'series': series,
        }).style('height: 350px;')


def _heatmap_v2(current: list, previous, threshold_min: int, compare: bool):
    """Mapa de calor ECharts: filas=días de semana, columnas=bloques de 3h."""

    _JS_HM_TOOLTIP = (
        'function(params){'
        ' var weekdays=["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"];'
        ' var blocks=["00-02","03-05","06-08","09-11","12-14","15-17","18-20","21-23"];'
        ' var v=params.value[2];'
        ' var day=weekdays[params.value[1]],blk=blocks[params.value[0]];'
        ' if(!v||v<=0) return day+" "+blk+"<br/>Sin datos";'
        ' var h=Math.floor(v/60),m=Math.round(v%60);'
        ' return day+" "+blk+"<br/>TRT: "+(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
        '}'
    )
    _JS_HM_LABEL = (
        'function(params){'
        ' var v=params.value[2];'
        ' if(!v||v<=0) return "";'
        ' var h=Math.floor(v/60),m=Math.round(v%60);'
        ' return (h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
        '}'
    )

    def _build_data(matrix):
        data = []
        for wd in range(7):
            for b in range(8):
                val_sec = matrix[wd][b] if wd < len(matrix) and b < len(matrix[wd]) else 0.0
                val_min = round(val_sec / 60, 1) if val_sec > 0 else 0
                data.append([b, wd, val_min])
        return data

    def _echart_option(data, title=''):
        max_val = max(round(threshold_min * 1.5), 30)
        opt = {
            'tooltip': {'position': 'top', ':formatter': _JS_HM_TOOLTIP},
            'grid': {'top': '20%', 'bottom': '8%', 'left': '13%', 'right': '3%'},
            'xAxis': {
                'type': 'category',
                'data': _BLOCK_LABELS,
                'splitArea': {'show': True},
                'axisLabel': {'fontSize': 11},
            },
            'yAxis': {
                'type': 'category',
                'data': _WEEKDAY_LABELS,
                'splitArea': {'show': True},
                'axisLabel': {'fontSize': 11},
            },
            'visualMap': {
                'min': 0,
                'max': max_val,
                'calculable': True,
                'orient': 'horizontal',
                'left': 'center',
                'top': '2%',
                'itemHeight': 100,
                'text': [_mins_to_hhmm(max_val), '00:00'],
                'inRange': {
                    'color': ['#F0FDF4', '#86EFAC', '#FEF08A', '#F97316', '#DC2626'],
                },
                'textStyle': {'fontSize': 10},
            },
            'series': [{
                'name': 'TRT (min)',
                'type': 'heatmap',
                'data': data,
                'label': {
                    'show': True,
                    ':formatter': _JS_HM_LABEL,
                    'fontSize': 10,
                },
                'emphasis': {
                    'itemStyle': {'shadowBlur': 8, 'shadowColor': 'rgba(0,0,0,0.4)'},
                },
            }],
        }
        if title:
            opt['title'] = {
                'text': title,
                'left': 'center',
                'top': '14%',
                'textStyle': {'fontSize': 12, 'fontWeight': 'normal', 'color': '#64748B'},
            }
        return opt

    with ui.card().classes('w-full ccu-card'):
        ui.label('Mapa de Calor TRT Día/Hora').classes('font-bold text-lg').style(
            f'color: {Colors.TEXT_PRIMARY};'
        )
        ui.label(
            'TRT promedio (HH:MM) por día de semana y bloque de 3 horas'
        ).classes('text-sm').style(f'color: {Colors.TEXT_MUTED};')

        curr_data = _build_data(current)
        if compare and previous:
            prev_data = _build_data(previous)
            with ui.row().classes('w-full gap-2'):
                with ui.column().classes('flex-1 min-w-0'):
                    ui.echart(_echart_option(curr_data, 'Período actual')).style(
                        'height: 360px; width: 100%;'
                    )
                with ui.column().classes('flex-1 min-w-0'):
                    ui.echart(_echart_option(prev_data, 'Período anterior')).style(
                        'height: 360px; width: 100%;'
                    )
        else:
            ui.echart(_echart_option(curr_data)).style('height: 360px; width: 100%;')
