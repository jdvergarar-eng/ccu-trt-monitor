"""Vista TV por centro — /centro/{site_slug} — optimizada 1920×1080"""
from datetime import datetime
from nicegui import ui
from core import get_config_manager, get_monitoring_service, AnalyticsService
from ..shared import site_slug
from ..theme import Colors

# ── Paleta ────────────────────────────────────────────────────────────────────
BG      = '#F4F6F8'
CARD    = '#FFFFFF'
HDR     = Colors.CCU_GREEN
HDR2    = Colors.CCU_GREEN_LIGHT
BORDER  = '#E2E8F0'
GREEN   = Colors.ACTION_GREEN
BLUE    = Colors.INFO
ORANGE  = '#F97316'
RED     = Colors.ERROR
YELLOW  = Colors.WARNING
TXT_P   = Colors.TEXT_PRIMARY
TXT_S   = Colors.TEXT_SECONDARY
TXT_MUT = Colors.TEXT_MUTED

CCU_LOGO = 'https://www.ccu.cl/wp-content/themes/ccu-cl/img/logo-color.png'

_JS_YAXIS = ('function(v){var h=Math.floor(v/60),m=Math.round(v%60);'
             'return(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);}')
_JS_MLINE = ('function(p){var v=p.value||0,h=Math.floor(v/60),m=Math.round(v%60);'
             'return"Umbral "+(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);}')
_JS_TIP   = ('function(params){if(!Array.isArray(params))params=[params];'
             'var s="<b>Día "+params[0].name+"</b><br/>";'
             'params.forEach(function(p){var v=p.value;if(v==null)return;'
             'if(p.seriesName=="Camiones"){s+=p.marker+"Camiones: "+v+"<br/>";return;}'
             'var h=Math.floor(v/60),m=Math.round(v%60);'
             'var t=(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
             's+=p.marker+p.seriesName+": "+t+"<br/>";});return s;}')

_MESES = {'January':'Enero','February':'Febrero','March':'Marzo','April':'Abril',
          'May':'Mayo','June':'Junio','July':'Julio','August':'Agosto',
          'September':'Septiembre','October':'Octubre','November':'Noviembre','December':'Diciembre'}
_DIAS  = {'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
          'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'}

def _hhmm(m):
    if not m: return '00:00'
    t = int(round(m)); return f'{t//60:02d}:{t%60:02d}'
def _month_year(dt):
    return f"{_MESES.get(dt.strftime('%B'), dt.strftime('%B'))} {dt.year}"
def _date_es(dt):
    return (f"{_DIAS.get(dt.strftime('%A'), dt.strftime('%A'))} "
            f"{dt.day} de {_MESES.get(dt.strftime('%B'), dt.strftime('%B'))} de {dt.year}")


# ── Helpers visuales ───────────────────────────────────────────────────────────
def _section_title(text: str):
    return ui.label(text).classes('w-full').style(
        f'font-size:0.72rem;font-weight:800;color:{TXT_MUT};'
        'text-transform:uppercase;letter-spacing:0.16em;text-align:center;'
    )


def _kpi(container, label: str, value: str, color: str):
    """Bloque KPI: retorna el label de valor para updates."""
    with container:
        with ui.column().style('gap:3px;'):
            ui.label(label).style(
                f'font-size:0.65rem;font-weight:700;color:{TXT_MUT};'
                'text-transform:uppercase;letter-spacing:0.12em;'
            )
            lbl = ui.label(value).style(
                f'font-size:3rem;font-weight:800;color:{color};'
                'line-height:1;font-variant-numeric:tabular-nums;'
            )
    return lbl


# ── Chart ──────────────────────────────────────────────────────────────────────
def _chart_opt(data, umbral, cl, cb):
    days = [str(d[0]) for d in data]
    avgs = [d[1] if d[2] > 0 else None for d in data]
    cnts = [d[2] for d in data]
    return {
        'backgroundColor': 'transparent',
        'tooltip': {'trigger': 'axis', 'backgroundColor': CARD,
                    'borderColor': BORDER, 'textStyle': {'color': TXT_P},
                    ':formatter': _JS_TIP},
        'legend': {'data': ['TRT Promedio', 'Camiones'],
                   'textStyle': {'color': TXT_S, 'fontSize': 12},
                   'bottom': 0, 'itemGap': 28},
        'grid': {'top': 36, 'bottom': 44, 'left': 72, 'right': 72},
        'xAxis': {'type': 'category', 'data': days,
                  'axisLabel': {'color': TXT_MUT, 'fontSize': 11},
                  'axisLine': {'lineStyle': {'color': BORDER}},
                  'axisTick': {'lineStyle': {'color': BORDER}}},
        'yAxis': [
            {'type': 'value', 'name': 'TRT',
             'nameTextStyle': {'color': cl, 'fontSize': 11},
             'axisLabel': {':formatter': _JS_YAXIS, 'color': cl, 'fontSize': 11},
             'splitLine': {'lineStyle': {'color': '#EDF2F7', 'type': 'dashed'}},
             'axisLine': {'show': False}, 'axisTick': {'show': False}},
            {'type': 'value', 'name': 'Camiones',
             'nameTextStyle': {'color': cb, 'fontSize': 11},
             'axisLabel': {'color': cb, 'fontSize': 11},
             'splitLine': {'show': False},
             'axisLine': {'show': False}, 'axisTick': {'show': False}},
        ],
        'series': [
            {'name': 'TRT Promedio', 'type': 'line',
             'yAxisIndex': 0, 'data': avgs,
             'smooth': True, 'connectNulls': False, 'symbolSize': 6,
             'lineStyle': {'color': cl, 'width': 3}, 'itemStyle': {'color': cl},
             'areaStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                 'colorStops': [{'offset': 0, 'color': cl + '40'},
                                {'offset': 1, 'color': cl + '05'}]}},
             'markLine': {
                 'silent': True, 'symbol': ['none', 'none'],
                 'lineStyle': {'color': RED, 'type': 'dashed', 'width': 2},
                 'data': [{'yAxis': umbral, 'name': 'Umbral'}],
                 'label': {':formatter': _JS_MLINE, 'color': RED,
                           'fontSize': 11, 'fontWeight': 'bold',
                           'position': 'insideEndTop'},
             }},
            {'name': 'Camiones', 'type': 'bar',
             'yAxisIndex': 1, 'data': cnts,
             'itemStyle': {'color': cb, 'borderRadius': [3, 3, 0, 0]},
             'barMaxWidth': 20, 'opacity': 0.65},
        ],
    }


# ── Dialog camiones ────────────────────────────────────────────────────────────
def _build_trucks_dialog():
    """Crea el dialog de camiones una vez. Retorna (dialog, open_fn)."""
    title_ref  = {'v': ''}
    rows_ref   = {'v': []}

    dlg = ui.dialog()
    with dlg, ui.card().style('min-width:680px;max-width:900px;border-radius:12px;'):
        @ui.refreshable
        def _content():
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(title_ref['v']).style(
                    f'font-size:1.1rem;font-weight:700;color:{TXT_P};'
                )
                ui.button(icon='close', on_click=dlg.close).props('flat round dense color=grey')
            columns = [
                {'name': 'estado',        'label': 'Estado',          'field': 'estado_label', 'align': 'left'},
                {'name': 'plate',         'label': 'Patente',         'field': 'plate',        'align': 'left'},
                {'name': 'company',       'label': 'Empresa',         'field': 'company',      'align': 'left'},
                {'name': 'entry_type',    'label': 'Tipo ingreso',    'field': 'entry_type',   'align': 'left'},
                {'name': 'time_in_plant', 'label': 'Tiempo en planta','field': 'time_in_plant','align': 'left', 'sortable': True},
            ]
            tbl = ui.table(columns=columns, rows=rows_ref['v'], row_key='plate'
                           ).classes('w-full').props('dense flat bordered')
            tbl.add_slot('body-cell-estado', r'''
                <q-td :props="props">
                  <span :style="{
                    background: props.row.status==='red' ? '#FEE2E2'
                              : props.row.status==='yellow' ? '#FEF9C3' : '#DCFCE7',
                    color: props.row.status==='red' ? '#DC2626'
                         : props.row.status==='yellow' ? '#D97706' : '#16A34A',
                    padding:'2px 10px', borderRadius:'10px',
                    fontWeight:'600', fontSize:'0.75rem'
                  }">{{ props.row.estado_label }}</span>
                </q-td>''')
        _content()

    def open_fn(center_name: str, trucks_list: list, thresholds: dict = None):
        if not thresholds:
            thresholds = {'lateral': 60, 'trasera': 60, 'interna': 60}

        def _thr(entry_type: str) -> int:
            et = (entry_type or '').upper()
            if 'INTERNA' in et: return thresholds.get('interna', 60)
            if 'TRASERA' in et: return thresholds.get('trasera', 60)
            return thresholds.get('lateral', 60)

        def _classify(minutes: int, thr: int):
            if thr <= 0: return 'green', 'Normal'
            r = minutes / thr
            if r >= 1.3: return 'red', 'Crítico'
            if r >= 0.8: return 'yellow', 'Precaución'
            return 'green', 'Normal'

        title_ref['v'] = f'Camiones en planta — {center_name}'
        rows = []
        for t in trucks_list:
            st, lbl = _classify(t.time_in_plant_minutes, _thr(t.entry_type))
            rows.append({'plate': t.plate,
                         'company': t.company[:35],
                         'entry_type': t.entry_type,
                         'time_in_plant': t.time_in_plant,
                         'status': st, 'estado_label': lbl})
        rows_ref['v'] = rows
        _content.refresh()
        dlg.open()

    return open_fn


# ── Acuerdos ───────────────────────────────────────────────────────────────────
def _acuerdo_dialog(slug, acuerdo, refresh_fn):
    from ..acuerdos import save_acuerdo
    data = acuerdo.copy() if acuerdo else {}
    with ui.dialog() as dlg, ui.card().style('min-width:520px;border-radius:12px;'):
        ui.label('Nuevo Acuerdo' if not acuerdo else 'Editar Acuerdo').style(
            f'font-size:1.05rem;font-weight:700;color:{TXT_P};')
        ui.separator()
        problema = ui.textarea('Problema',     value=data.get('problema', '')).classes('w-full')
        accion   = ui.textarea('Acción a tomar', value=data.get('accion', '')).classes('w-full')
        with ui.row().classes('w-full gap-3'):
            quien  = ui.input('Responsable', value=data.get('quien', '')).classes('flex-1')
            cuando = ui.input('Plazo',       value=data.get('cuando', '')).classes('flex-1').props('type=date')
        estado = ui.select(['En Proceso', 'Cerrado'], label='Estado',
                           value=data.get('estado', 'En Proceso')).classes('w-full')
        def _save():
            data.update(problema=problema.value, accion=accion.value,
                        quien=quien.value, cuando=cuando.value, estado=estado.value)
            save_acuerdo(slug, data); dlg.close(); refresh_fn()
        with ui.row().classes('w-full justify-end gap-2 mt-2'):
            ui.button('Cancelar', on_click=dlg.close).props('flat color=grey')
            ui.button('Guardar',  on_click=_save).props('color=green')
    dlg.open()


def _acuerdos_section(slug):
    from ..acuerdos import get_acuerdos
    with ui.card().classes('w-full').style(
        f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
        f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
    ) as card:
        def refresh():
            card.clear(); _fill_acuerdos(card, slug, refresh)
        _fill_acuerdos(card, slug, refresh)


def _fill_acuerdos(card, slug, refresh_fn):
    from ..acuerdos import get_acuerdos, delete_acuerdo
    with card:
        with ui.row().classes('w-full items-center justify-between').style('margin-bottom:10px;'):
            with ui.row().classes('items-center').style('gap:8px;'):
                ui.icon('handshake').style(f'color:{GREEN};font-size:1.1rem;')
                ui.label('Acuerdos del Área').style(
                    f'font-size:0.95rem;font-weight:700;color:{TXT_P};')
            ui.button('+ Nuevo', icon='add',
                      on_click=lambda: _acuerdo_dialog(slug, None, refresh_fn)
                      ).props('outline color=green size=sm')

        acuerdos = get_acuerdos(slug)
        if not acuerdos:
            with ui.column().classes('w-full items-center').style('padding:18px 0;gap:8px;'):
                ui.icon('assignment').style(f'color:{BORDER};font-size:2.5rem;')
                ui.label('Sin acuerdos registrados').style(
                    f'color:{TXT_MUT};font-style:italic;font-size:0.88rem;')
            return

        cols = '88px 1fr 1fr 140px 110px 72px'
        with ui.element('div').style(
            f'display:grid;grid-template-columns:{cols};gap:10px;'
            f'padding:0 6px 7px;border-bottom:2px solid {BORDER};'
        ):
            for h in ['Fecha', 'Problema', 'Acción', 'Responsable', 'Estado', '']:
                ui.label(h).style(
                    f'font-size:0.62rem;font-weight:700;color:{TXT_MUT};'
                    'text-transform:uppercase;letter-spacing:0.1em;')

        for a in acuerdos:
            st  = a.get('estado', '')
            bg  = Colors.WARNING_BG if st == 'En Proceso' else Colors.SUCCESS_BG
            col = YELLOW            if st == 'En Proceso' else GREEN
            with ui.element('div').style(
                f'display:grid;grid-template-columns:{cols};gap:10px;'
                f'padding:8px 6px;border-bottom:1px solid {BORDER};align-items:center;'
            ):
                ui.label(a.get('fecha', '')).style(f'color:{TXT_MUT};font-size:0.82rem;')
                ui.label(a.get('problema', '')).style(
                    f'color:{TXT_P};font-size:0.86rem;font-weight:500;'
                    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;')
                ui.label(a.get('accion', '')).style(
                    f'color:{TXT_S};font-size:0.82rem;'
                    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;')
                ui.label(a.get('quien', '')).style(f'color:{TXT_P};font-size:0.84rem;')
                ui.html(
                    f'<span style="padding:2px 10px;border-radius:20px;font-size:0.72rem;'
                    f'font-weight:700;background:{bg};color:{col};">{st}</span>')
                with ui.row().style('gap:2px;align-items:center;'):
                    ui.button(icon='edit',
                              on_click=lambda ac=a: _acuerdo_dialog(slug, ac, refresh_fn)
                              ).props('flat round dense color=grey-7 size=xs').tooltip('Editar')
                    ui.button(icon='delete',
                              on_click=lambda aid=a['id']: (delete_acuerdo(slug, aid), refresh_fn())
                              ).props('flat round dense color=red-7 size=xs').tooltip('Eliminar')


# ── Página ─────────────────────────────────────────────────────────────────────
def setup_centro_page():

    @ui.page('/centro/{slug}')
    def centro_page(slug: str):
        ui.add_head_html(f"""<style>
  body{{background:{BG}!important;margin:0;}}
  .q-page-container,.q-page{{background:{BG}!important;padding:0!important;min-height:100vh;}}
  .nicegui-content{{background:{BG}!important;padding:0!important;
    max-width:100%!important;width:100%!important;}}
  *{{box-sizing:border-box;}}
</style>""")

        config_manager = get_config_manager()
        monitoring     = get_monitoring_service()
        analytics      = AnalyticsService()

        site = next(
            (s for s in config_manager.config.sites if site_slug(s.name) == slug), None)

        if site is None:
            with ui.column().classes('items-center justify-center').style(
                f'height:100vh;background:{BG};gap:16px;'):
                ui.icon('tv_off').style(f'color:{BORDER};font-size:4rem;')
                ui.label(f'Centro no encontrado: "{slug}"').style(
                    f'color:{TXT_MUT};font-size:1.2rem;')
                ui.link('← Volver al inicio', '/').style(f'color:{BLUE};')
            return

        now    = datetime.now()
        refs   = {}
        u_lat  = site.umbral_minutes_lateral or site.umbral_minutes or 60
        u_tras = site.umbral_minutes_trasera or site.umbral_minutes or 60
        thr    = {'lateral': u_lat, 'trasera': u_tras,
                  'interna': site.umbral_minutes_interna or site.umbral_minutes or 60}

        # Dialog camiones (creado una vez fuera del layout)
        open_trucks = _build_trucks_dialog()

        # ── Layout principal ──────────────────────────────────────────────────
        with ui.column().classes('w-full').style(
            f'background:{BG};padding:16px 20px;gap:12px;min-height:100vh;'
        ):
            # ── HEADER (compacto) ─────────────────────────────────────────────
            with ui.card().classes('w-full').style(
                f'background:linear-gradient(135deg,{HDR} 0%,{HDR2} 100%);'
                f'border:none;border-radius:12px;'
                f'box-shadow:0 3px 16px rgba(0,92,53,0.4);padding:14px 28px;'
            ):
                with ui.row().classes('w-full items-center no-wrap').style('gap:0;'):
                    ui.image(CCU_LOGO).style(
                        'height:44px;width:auto;flex-shrink:0;'
                        'filter:brightness(0) invert(1);'
                    )
                    with ui.column().classes('items-center flex-1').style(
                        'gap:1px;padding:0 16px;'
                    ):
                        ui.label('Sistema de Alertas TRT').style(
                            'font-size:0.75rem;font-weight:600;'
                            'color:rgba(255,255,255,0.75);'
                            'text-transform:uppercase;letter-spacing:0.18em;'
                        )
                        ui.label(site.name).style(
                            'font-size:2.2rem;font-weight:800;color:#ffffff;'
                            'letter-spacing:-0.02em;line-height:1;text-align:center;'
                        )
                    with ui.column().classes('items-end').style(
                        'gap:1px;flex-shrink:0;'
                    ):
                        refs['time_lbl'] = ui.label(now.strftime('%H:%M:%S')).style(
                            'font-size:2rem;font-weight:700;color:#86efac;'
                            'font-variant-numeric:tabular-nums;'
                        )
                        refs['date_lbl'] = ui.label(_date_es(now)).style(
                            'font-size:0.8rem;color:rgba(255,255,255,0.7);'
                        )

            # ── FILA SUPERIOR: 2 tarjetas resumen ────────────────────────────
            _section_title('Resumen en Tiempo Real')

            centers_list = monitoring.get_centers_data() if monitoring else []
            live  = next((c for c in centers_list if c['name'] == site.name), {})
            kpis  = analytics.get_kpi_summary(site.name, days=30)
            pct   = kpis.get('pct_critical', 0)
            t_now = live.get('trucks_in_plant', 0)
            a_now = live.get('alerts', 0)
            trucks_cache = {'list': live.get('trucks_list', [])}

            with ui.row().classes('w-full').style('gap:12px;'):
                # Card: Ahora en planta
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('w-full items-center justify-between').style(
                        'margin-bottom:10px;'
                    ):
                        with ui.row().classes('items-center').style('gap:7px;'):
                            ui.icon('local_shipping').style(
                                f'color:#F57C00;font-size:1.1rem;')
                            ui.label('Ahora en Planta').style(
                                f'font-size:0.9rem;font-weight:700;color:{TXT_S};')
                        # Botón Ver camiones
                        refs['trucks_btn'] = ui.button(
                            'Ver camiones', icon='local_shipping',
                            on_click=lambda: open_trucks(
                                site.name, trucks_cache['list'], thr)
                        ).props('outline color=orange size=sm')
                        refs['trucks_btn'].set_visibility(bool(trucks_cache['list']))

                    with ui.row().style('gap:40px;align-items:flex-end;'):
                        refs['trucks_lbl'] = _kpi(
                            ui.element('span'), 'Camiones', str(t_now), TXT_P)
                        refs['alerts_lbl'] = _kpi(
                            ui.element('span'), 'Alertas Activas', str(a_now),
                            RED if a_now > 0 else GREEN)

                # Card: Histórico
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('items-center').style('gap:7px;margin-bottom:10px;'):
                        ui.icon('insights').style(f'color:{BLUE};font-size:1.1rem;')
                        ui.label('Histórico — Últimos 30 Días').style(
                            f'font-size:0.9rem;font-weight:700;color:{TXT_S};')
                    with ui.row().style('gap:40px;align-items:flex-end;'):
                        refs['avg_lbl']  = _kpi(ui.element('span'), 'TRT Promedio',
                                                _hhmm(kpis.get('avg_trt_min', 0)), BLUE)
                        refs['disp_lbl'] = _kpi(ui.element('span'), 'Despachos',
                                                str(kpis.get('total_dispatches', 0)), TXT_P)
                        refs['pct_lbl']  = _kpi(ui.element('span'), '% Críticos',
                                                f'{pct:.1f}%', RED if pct > 20 else GREEN)

            # ── FILA GRÁFICOS (lado a lado) ───────────────────────────────────
            refs['ind_lbl'] = _section_title(
                f'Indicadores Operacionales — {_month_year(now)}')

            lat_data  = analytics.get_monthly_trend_by_type(site.name, 'LATERAL')
            tras_data = analytics.get_monthly_trend_by_type(site.name, 'TRASERA')

            with ui.row().classes('w-full').style('gap:12px;'):
                # Chart LATERAL
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('w-full items-center justify-between').style(
                        'margin-bottom:8px;'
                    ):
                        with ui.row().classes('items-center').style('gap:8px;'):
                            ui.html(
                                '<div style="width:12px;height:12px;border-radius:3px;'
                                'background:#3B82F6;flex-shrink:0;"></div>')
                            ui.label('Botelleros — Carga Lateral').style(
                                f'font-size:1rem;font-weight:700;color:#2563EB;')
                        ui.html(
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'flex-shrink:0;">'
                            f'<svg width="26" height="10"><line x1="0" y1="5" x2="26" y2="5"'
                            f' stroke="{RED}" stroke-width="2.5"'
                            f' stroke-dasharray="7,4"/></svg>'
                            f'<span style="color:{RED};font-size:0.82rem;font-weight:700;">'
                            f'Umbral {_hhmm(u_lat)}</span></div>')
                    refs['chart_lat'] = ui.echart(
                        _chart_opt(lat_data, u_lat, '#3B82F6', '#93C5FD')
                    ).style('height:320px;width:100%;')

                # Chart TRASERA
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('w-full items-center justify-between').style(
                        'margin-bottom:8px;'
                    ):
                        with ui.row().classes('items-center').style('gap:8px;'):
                            ui.html(
                                '<div style="width:12px;height:12px;border-radius:3px;'
                                'background:#F97316;flex-shrink:0;"></div>')
                            ui.label('InterAndinos — Carga Trasera').style(
                                f'font-size:1rem;font-weight:700;color:#EA580C;')
                        ui.html(
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'flex-shrink:0;">'
                            f'<svg width="26" height="10"><line x1="0" y1="5" x2="26" y2="5"'
                            f' stroke="{RED}" stroke-width="2.5"'
                            f' stroke-dasharray="7,4"/></svg>'
                            f'<span style="color:{RED};font-size:0.82rem;font-weight:700;">'
                            f'Umbral {_hhmm(u_tras)}</span></div>')
                    refs['chart_tras'] = ui.echart(
                        _chart_opt(tras_data, u_tras, '#F97316', '#FED7AA')
                    ).style('height:320px;width:100%;')

            # ── ACUERDOS ──────────────────────────────────────────────────────
            _section_title('Acuerdos del Área')
            _acuerdos_section(slug)

            refs['footer_lbl'] = ui.label(
                f'Última actualización: {now.strftime("%H:%M:%S")} · CCU-TRT Monitor'
            ).classes('w-full').style(
                f'text-align:center;color:{TXT_MUT};font-size:0.7rem;'
                f'padding-top:10px;border-top:1px solid {BORDER};'
            )

        # ── Timers ─────────────────────────────────────────────────────────────
        def _tick():
            refs['time_lbl'].text = datetime.now().strftime('%H:%M:%S')
        ui.timer(1, _tick)

        def _live():
            n  = datetime.now()
            refs['date_lbl'].text = _date_es(n)
            cd = monitoring.get_centers_data() if monitoring else []
            lv = next((c for c in cd if c['name'] == site.name), {})
            t  = lv.get('trucks_in_plant', 0)
            a  = lv.get('alerts', 0)
            trucks_cache['list'] = lv.get('trucks_list', [])
            refs['trucks_btn'].set_visibility(bool(trucks_cache['list']))
            refs['trucks_lbl'].text = str(t)
            refs['alerts_lbl'].text = str(a)
            refs['alerts_lbl'].style(
                f'font-size:3rem;font-weight:800;line-height:1;'
                f'font-variant-numeric:tabular-nums;'
                f'color:{RED if a > 0 else GREEN};')
            refs['footer_lbl'].text = (
                f'Última actualización: {n.strftime("%H:%M:%S")} · CCU-TRT Monitor')
        ui.timer(10, _live)

        def _charts():
            k = analytics.get_kpi_summary(site.name, days=30)
            p = k.get('pct_critical', 0)
            refs['avg_lbl'].text  = _hhmm(k.get('avg_trt_min', 0))
            refs['disp_lbl'].text = str(k.get('total_dispatches', 0))
            refs['pct_lbl'].text  = f'{p:.1f}%'
            refs['pct_lbl'].style(
                f'font-size:3rem;font-weight:800;line-height:1;'
                f'font-variant-numeric:tabular-nums;'
                f'color:{RED if p > 20 else GREEN};')
            ld = analytics.get_monthly_trend_by_type(site.name, 'LATERAL')
            td = analytics.get_monthly_trend_by_type(site.name, 'TRASERA')
            refs['chart_lat'].run_chart_method(
                'setOption', _chart_opt(ld, u_lat, '#3B82F6', '#93C5FD'), True)
            refs['chart_tras'].run_chart_method(
                'setOption', _chart_opt(td, u_tras, '#F97316', '#FED7AA'), True)
            refs['ind_lbl'].text = (
                f'Indicadores Operacionales — {_month_year(datetime.now())}')
        ui.timer(300, _charts)
