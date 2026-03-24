"""Vista TV por centro — /centro/{site_slug} — optimizada 1920×1080"""
import base64
import json as _json
from datetime import datetime
from pathlib import Path
from nicegui import ui
from core import get_config_manager, get_monitoring_service, AnalyticsService
from ..shared import site_slug
from ..theme import Colors

# Logo como base64 para usarlo en CSS background-image (no depende de rutas HTTP)
def _load_logo_b64() -> str:
    logo = Path(__file__).parent.parent.parent / 'assets' / 'Logo_CCU.png'
    if logo.exists():
        return base64.b64encode(logo.read_bytes()).decode()
    return ''

_LOGO_B64 = _load_logo_b64()

# ── Paleta ────────────────────────────────────────────────────────────────────
BG      = '#F4F6F8'
CARD    = '#FFFFFF'
HDR     = Colors.CCU_GREEN
HDR2    = Colors.CCU_GREEN_LIGHT
BORDER  = '#E2E8F0'
GREEN   = Colors.ACTION_GREEN
BLUE    = Colors.INFO
RED     = Colors.ERROR
YELLOW  = Colors.WARNING
TXT_P   = Colors.TEXT_PRIMARY
TXT_S   = Colors.TEXT_SECONDARY
TXT_MUT = Colors.TEXT_MUTED

# Colores de series
LAT_LINE   = '#1D4ED8'
LAT_BAR    = '#3B82F6'
TRAS_LINE  = '#B91C1C'
TRAS_BAR   = '#EF4444'
INT_LINE   = '#7C3AED'
INT_BAR    = '#A78BFA'
UMBRAL_CLR = '#F59E0B'
OVER_CLR   = '#DC2626'   # color de barra cuando supera umbral

_MESES = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
    'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
    'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
    'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre',
}
_DIAS = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo',
}


def _hhmm(m):
    if not m:
        return '00:00'
    t = int(round(m))
    return f'{t // 60:02d}:{t % 60:02d}'


def _month_year(dt):
    return f"{_MESES.get(dt.strftime('%B'), dt.strftime('%B'))} {dt.year}"


def _date_es(dt):
    return (f"{_DIAS.get(dt.strftime('%A'), dt.strftime('%A'))} "
            f"{dt.day} de {_MESES.get(dt.strftime('%B'), dt.strftime('%B'))} de {dt.year}")


# ── Chart JS string ────────────────────────────────────────────────────────────
def _chart_js(data, umbral: float, cl: str, cb: str, label_umbral: str) -> str:
    """String de expresión JavaScript para run_chart_method(':setOption', js_str, True).

    - TRT = barras: color normal si ≤ umbral, rojo (#DC2626) si lo supera.
    - Camiones = línea (eje secundario).
    - Umbral line = ámbar si ninguna barra lo supera, negro si alguna lo supera.
    Usando ':setOption' el prefijo ':' hace que NiceGUI evalúe el arg como JS puro,
    preservando las funciones formatter (que JSON destruiría).
    """
    days = [str(d[0]) for d in data]
    avgs = [d[1] if d[2] > 0 else None for d in data]
    cnts = [d[2] for d in data]
    valid = [a for a in avgs if a is not None]
    raw_max = max(max(valid) if valid else 0, umbral) * 1.2
    y_max = round(raw_max) if raw_max > 0 else round(umbral * 1.2) or 120

    # Color de la línea de umbral: negro si algún valor supera el umbral
    any_over = any(a is not None and a > umbral for a in avgs)
    ml_color = '#111827' if any_over else UMBRAL_CLR

    safe_label = label_umbral.replace('"', '\\"').replace("'", "\\'")

    fmt_fn = ('function(v){'
              'var h=Math.floor(v/60),m=Math.round(v%60);'
              'if(m===60){h++;m=0;}'
              'return(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);}')

    tip_fn = ('function(params){'
              'if(!Array.isArray(params))params=[params];'
              'var s="<b>D\\u00eda "+params[0].name+"</b><br/>";'
              'params.forEach(function(p){'
              'var v=p.value;if(v==null)return;'
              'if(p.seriesName==="Camiones"){s+=p.marker+"Camiones: "+v+"<br/>";return;}'
              'var h=Math.floor(v/60),m=Math.round(v%60);if(m===60){h++;m=0;}'
              'var t=(h<10?"0"+h:h)+":"+(m<10?"0"+m:m);'
              's+=p.marker+p.seriesName+": "+t+"<br/>";'
              '});return s;}')

    # Función de color por barra (rojo si supera umbral)
    bar_color_fn = (
        f'function(params){{'
        f'if(params.value===null||params.value===undefined)return"transparent";'
        f'return params.value>{umbral}?"{OVER_CLR}":"{cl}";}}'
    )

    return (
        f'({{'
        f'backgroundColor:"transparent",'
        f'tooltip:{{trigger:"axis",backgroundColor:"{CARD}",borderColor:"{BORDER}",'
        f'textStyle:{{color:"{TXT_P}",fontSize:13}},formatter:{tip_fn}}},'
        f'legend:{{data:["TRT Promedio","Camiones"],'
        f'textStyle:{{color:"{TXT_S}",fontSize:13}},bottom:0,itemGap:28}},'
        f'grid:{{top:40,bottom:50,left:76,right:110}},'
        f'xAxis:{{type:"category",data:{_json.dumps(days)},'
        f'axisLabel:{{color:"{TXT_MUT}",fontSize:12}},'
        f'axisLine:{{lineStyle:{{color:"{BORDER}"}}}},'
        f'axisTick:{{lineStyle:{{color:"{BORDER}"}}}}}},'
        f'yAxis:['
        f'{{type:"value",name:"TRT",min:0,max:{y_max},'
        f'nameTextStyle:{{color:"{cl}",fontSize:12}},'
        f'axisLabel:{{formatter:{fmt_fn},color:"{cl}",fontSize:12}},'
        f'splitLine:{{lineStyle:{{color:"#EDF2F7",type:"dashed"}}}},'
        f'axisLine:{{show:false}},axisTick:{{show:false}}}},'
        f'{{type:"value",name:"Camiones",'
        f'nameTextStyle:{{color:"{cb}",fontSize:12}},'
        f'axisLabel:{{color:"{cb}",fontSize:12}},'
        f'splitLine:{{show:false}},axisLine:{{show:false}},axisTick:{{show:false}}}}'
        f'],'
        f'series:['
        # TRT → barras con color por valor
        f'{{name:"TRT Promedio",type:"bar",yAxisIndex:0,data:{_json.dumps(avgs)},'
        f'itemStyle:{{color:{bar_color_fn},borderRadius:[4,4,0,0]}},'
        f'barMaxWidth:40,'
        f'markLine:{{silent:true,symbol:["none","none"],'
        f'lineStyle:{{color:"{ml_color}",type:"dashed",width:3}},'
        f'data:[{{yAxis:{umbral},name:"{safe_label}",'
        f'label:{{formatter:"{safe_label}",color:"{ml_color}",'
        f'fontSize:13,fontWeight:"bold",position:"insideEndTop"}}}}]}}}},'
        # Camiones → línea suave
        f'{{name:"Camiones",type:"line",yAxisIndex:1,data:{_json.dumps(cnts)},'
        f'smooth:false,symbolSize:7,'
        f'lineStyle:{{color:"{cb}",width:2.5}},itemStyle:{{color:"{cb}"}}}}'
        f']}}'
        f')'
    )


# ── Helpers visuales ───────────────────────────────────────────────────────────
def _section_title(text: str):
    return ui.label(text).classes('w-full').style(
        f'font-size:1.05rem;font-weight:800;color:{TXT_MUT};'
        'text-transform:uppercase;letter-spacing:0.16em;text-align:center;padding:8px 0;'
    )


def _kpi(container, label: str, value: str, color: str):
    with container:
        with ui.column().style('gap:4px;'):
            ui.label(label).style(
                f'font-size:0.9rem;font-weight:700;color:{TXT_MUT};'
                'text-transform:uppercase;letter-spacing:0.1em;'
            )
            lbl = ui.label(value).style(
                f'font-size:3rem;font-weight:800;color:{color};'
                'line-height:1;font-variant-numeric:tabular-nums;'
            )
    return lbl


def _chart_header(title: str, title_color: str, dot_color: str, umbral_txt: str):
    with ui.row().classes('w-full items-center justify-between').style('margin-bottom:8px;'):
        with ui.row().classes('items-center').style('gap:8px;'):
            ui.html(
                f'<div style="width:14px;height:14px;border-radius:3px;'
                f'background:{dot_color};flex-shrink:0;"></div>'
            )
            ui.label(title).style(f'font-size:1.1rem;font-weight:700;color:{title_color};')
        ui.html(
            f'<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">'
            f'<svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5"'
            f' stroke="{UMBRAL_CLR}" stroke-width="3" stroke-dasharray="8,4"/></svg>'
            f'<span style="color:{UMBRAL_CLR};font-size:0.9rem;font-weight:700;">'
            f'Umbral {umbral_txt}</span></div>'
        )


# ── Dialog camiones ────────────────────────────────────────────────────────────
def _build_trucks_dialog():
    title_ref = {'v': ''}
    rows_ref  = {'v': []}
    dlg = ui.dialog()
    with dlg, ui.card().style('min-width:700px;max-width:960px;border-radius:12px;'):
        @ui.refreshable
        def _content():
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(title_ref['v']).style(
                    f'font-size:1.15rem;font-weight:700;color:{TXT_P};')
                ui.button(icon='close', on_click=dlg.close).props('flat round dense color=grey')
            columns = [
                {'name': 'estado',        'label': 'Estado',           'field': 'estado_label', 'align': 'left'},
                {'name': 'plate',         'label': 'Patente',          'field': 'plate',        'align': 'left'},
                {'name': 'company',       'label': 'Empresa',          'field': 'company',      'align': 'left'},
                {'name': 'entry_type',    'label': 'Tipo ingreso',     'field': 'entry_type',   'align': 'left'},
                {'name': 'time_in_plant', 'label': 'Tiempo en planta', 'field': 'time_in_plant','align': 'left', 'sortable': True},
            ]
            tbl = ui.table(columns=columns, rows=rows_ref['v'], row_key='plate'
                           ).classes('w-full').props('dense flat bordered')
            tbl.add_slot('body-cell-estado', r'''
                <q-td :props="props">
                  <span :style="{background:props.row.status==='red'?'#FEE2E2'
                    :props.row.status==='yellow'?'#FEF9C3':'#DCFCE7',
                    color:props.row.status==='red'?'#DC2626'
                    :props.row.status==='yellow'?'#D97706':'#16A34A',
                    padding:'3px 12px',borderRadius:'12px',
                    fontWeight:'600',fontSize:'0.82rem'}">
                    {{ props.row.estado_label }}
                  </span>
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

        def _classify(minutes, thr):
            if thr <= 0: return 'green', 'Normal'
            r = minutes / thr
            if r >= 1.3: return 'red', 'Crítico'
            if r >= 0.8: return 'yellow', 'Precaución'
            return 'green', 'Normal'

        title_ref['v'] = f'Camiones en planta — {center_name}'
        rows = []
        for t in trucks_list:
            st, lbl = _classify(t.time_in_plant_minutes, _thr(t.entry_type))
            rows.append({'plate': t.plate, 'company': t.company[:40],
                         'entry_type': t.entry_type, 'time_in_plant': t.time_in_plant,
                         'status': st, 'estado_label': lbl})
        rows_ref['v'] = rows
        _content.refresh()
        dlg.open()

    return open_fn


# ── Acuerdos ───────────────────────────────────────────────────────────────────
# Paleta inspirada en el tablero físico: header verde oscuro CCU, filas menta/blanco
_TBL_HDR_BG  = '#004D2C'   # verde CCU oscuro
_TBL_HDR_TXT = '#FFFFFF'
_TBL_ROW_ALT = '#E8F5EC'   # menta claro
_TBL_ROW_REG = '#FFFFFF'
_TBL_BORDER  = '#B2DFCC'   # verde suave


def _acuerdo_dialog(slug, acuerdo, refresh_fn):
    from ..acuerdos import save_acuerdo
    data = acuerdo.copy() if acuerdo else {}
    with ui.dialog() as dlg, ui.card().style(
        'min-width:640px;max-width:820px;border-radius:14px;'
        f'background:{CARD};padding:28px;'
    ):
        ui.label('Nuevo Acuerdo' if not acuerdo else 'Editar Acuerdo').style(
            f'font-size:1.3rem;font-weight:800;color:{TXT_P};margin-bottom:4px;'
        )
        ui.separator().style('margin-bottom:18px;')
        problema = ui.textarea('Problema',       value=data.get('problema', '')).classes('w-full').props('rows=3 outlined')
        accion   = ui.textarea('Acción a tomar', value=data.get('accion',   '')).classes('w-full').props('rows=3 outlined')
        with ui.row().classes('w-full').style('gap:16px;'):
            quien  = ui.input('Responsable', value=data.get('quien',  '')).classes('flex-1').props('outlined')
            cuando = ui.input('Plazo',       value=data.get('cuando', '')).classes('flex-1').props('type=date outlined')
        estado = ui.select(['En Proceso', 'Cerrado'], label='Estado',
                           value=data.get('estado', 'En Proceso')).classes('w-full').props('outlined')

        def _save():
            data.update(problema=problema.value, accion=accion.value,
                        quien=quien.value, cuando=cuando.value, estado=estado.value)
            save_acuerdo(slug, data)
            dlg.close()
            refresh_fn()

        with ui.row().classes('w-full justify-end').style('gap:12px;margin-top:20px;'):
            ui.button('Cancelar', on_click=dlg.close).props('flat color=grey')
            ui.button('Guardar', on_click=_save).props('color=green unelevated').style(
                'font-weight:700;padding:0 28px;')
    dlg.open()


def _acuerdos_section(slug):
    with ui.card().classes('w-full').style(
        f'background:{CARD};border:1px solid {_TBL_BORDER};border-radius:12px;'
        f'box-shadow:0 2px 10px rgba(0,77,44,0.12);overflow:hidden;'
    ) as card:
        def refresh():
            card.clear()
            _fill_acuerdos(card, slug, refresh)
        _fill_acuerdos(card, slug, refresh)


def _fill_acuerdos(card, slug, refresh_fn):
    from ..acuerdos import get_acuerdos, delete_acuerdo

    COLS = '120px 1.8fr 1.8fr 140px 110px 120px 80px'

    _cell = ('padding:13px 16px;font-size:0.95rem;'
             f'border-right:1px solid {_TBL_BORDER};')
    _hcell = (f'padding:14px 16px;font-size:0.82rem;font-weight:800;color:{_TBL_HDR_TXT};'
              'text-transform:uppercase;letter-spacing:0.09em;'
              f'border-right:1px solid rgba(255,255,255,0.15);')

    with card:
        # ── Cabecera de sección ───────────────────────────────────────────────
        with ui.row().classes('w-full items-center justify-between').style(
            f'padding:16px 20px 14px;border-bottom:3px solid {_TBL_BORDER};'
        ):
            with ui.row().classes('items-center').style('gap:10px;'):
                ui.icon('handshake').style(f'color:{GREEN};font-size:1.5rem;')
                ui.label('Acuerdos del Área').style(
                    f'font-size:1.2rem;font-weight:800;color:{TXT_P};')
            ui.button('+ Nuevo Acuerdo',
                      on_click=lambda: _acuerdo_dialog(slug, None, refresh_fn)
                      ).props('color=green unelevated').style('font-weight:700;font-size:0.95rem;')

        acuerdos = get_acuerdos(slug)

        if not acuerdos:
            with ui.column().classes('w-full items-center').style('padding:36px 0;gap:10px;'):
                ui.icon('assignment').style(f'color:{BORDER};font-size:3.5rem;')
                ui.label('Sin acuerdos registrados').style(
                    f'color:{TXT_MUT};font-style:italic;font-size:1.05rem;')
            return

        # ── Tabla completa ────────────────────────────────────────────────────
        with ui.column().classes('w-full').style('gap:0;'):

            # Fila de encabezados (verde CCU oscuro)
            with ui.element('div').style(
                f'display:grid;grid-template-columns:{COLS};'
                f'background:{_TBL_HDR_BG};width:100%;'
            ):
                for h in ['Fechas', 'Problema', 'Acción', 'Quién', 'Cuándo', 'Estado', '']:
                    ui.label(h).style(_hcell)

            # Filas de datos
            for i, a in enumerate(acuerdos):
                st = a.get('estado', '')
                en_proceso = st == 'En Proceso'
                badge_bg  = '#FEF3C7' if en_proceso else '#DCFCE7'
                badge_col = '#92400E' if en_proceso else '#14532D'
                row_bg = _TBL_ROW_ALT if i % 2 == 0 else _TBL_ROW_REG

                with ui.element('div').style(
                    f'display:grid;grid-template-columns:{COLS};'
                    f'background:{row_bg};width:100%;'
                    f'border-bottom:1px solid {_TBL_BORDER};align-items:center;'
                ):
                    # Fecha
                    ui.label(a.get('fecha', '')).style(
                        _cell + f'color:{TXT_MUT};font-size:0.9rem;font-weight:500;')

                    # Problema
                    ui.label(a.get('problema', '')).style(
                        _cell + f'color:{TXT_P};font-weight:600;'
                        'word-break:break-word;white-space:pre-wrap;line-height:1.4;')

                    # Acción
                    ui.label(a.get('accion', '')).style(
                        _cell + f'color:{TXT_S};'
                        'word-break:break-word;white-space:pre-wrap;line-height:1.4;')

                    # Quién
                    ui.label(a.get('quien', '')).style(
                        _cell + f'color:{TXT_P};font-weight:500;')

                    # Cuándo
                    ui.label(a.get('cuando', '')).style(
                        _cell + f'color:{TXT_P};font-weight:500;')

                    # Estado (badge pill)
                    with ui.element('div').style(_cell + 'border-right:none;'):
                        ui.html(
                            f'<span style="display:inline-block;padding:4px 12px;'
                            f'border-radius:20px;font-size:0.8rem;font-weight:800;'
                            f'background:{badge_bg};color:{badge_col};">{st}</span>'
                        )

                    # Acciones
                    with ui.row().style(
                        f'gap:2px;align-items:center;padding:8px;'
                        f'border-left:1px solid {_TBL_BORDER};'
                    ):
                        ui.button(icon='edit',
                                  on_click=lambda ac=a: _acuerdo_dialog(slug, ac, refresh_fn)
                                  ).props('flat round dense color=blue-8 size=sm').tooltip('Editar')
                        ui.button(icon='delete',
                                  on_click=lambda aid=a['id']: (delete_acuerdo(slug, aid), refresh_fn())
                                  ).props('flat round dense color=red-8 size=sm').tooltip('Eliminar')


# ── Página ─────────────────────────────────────────────────────────────────────
def setup_centro_page():

    @ui.page('/centro/{slug}')
    def centro_page(slug: str):
        _logo_css = ''
        if _LOGO_B64:
            _logo_css = (
                f'.ccu-logo-box{{background:url("data:image/png;base64,{_LOGO_B64}")'
                f' no-repeat center/contain;flex-shrink:0;'
                f'width:150px;height:56px;}}'
            )
        ui.add_head_html(f"""<style>
  body{{background:{BG}!important;margin:0;}}
  .q-page-container,.q-page{{background:{BG}!important;padding:0!important;min-height:100vh;}}
  .nicegui-content{{background:{BG}!important;padding:0!important;
    max-width:100%!important;width:100%!important;}}
  *{{box-sizing:border-box;}}
  {_logo_css}
</style>""")

        config_manager = get_config_manager()
        monitoring     = get_monitoring_service()
        analytics      = AnalyticsService()

        site = next(
            (s for s in config_manager.config.sites if site_slug(s.name) == slug), None)

        if site is None:
            with ui.column().classes('items-center justify-center').style(
                f'height:100vh;background:{BG};gap:16px;'
            ):
                ui.icon('tv_off').style(f'color:{BORDER};font-size:4rem;')
                ui.label(f'Centro no encontrado: "{slug}"').style(
                    f'color:{TXT_MUT};font-size:1.2rem;')
                ui.link('← Volver al inicio', '/').style(f'color:{BLUE};')
            return

        now    = datetime.now()
        refs   = {}
        u_lat  = site.umbral_minutes_lateral or site.umbral_minutes or 60
        u_tras = site.umbral_minutes_trasera or site.umbral_minutes or 0
        u_int  = site.umbral_minutes_interna or site.umbral_minutes or 0
        thr    = {'lateral': u_lat, 'trasera': u_tras or 60, 'interna': u_int or 60}

        show_tras  = u_tras > 0
        show_intra = u_int > 0

        open_trucks = _build_trucks_dialog()

        with ui.column().classes('w-full').style(
            f'background:{BG};padding:16px 20px;gap:12px;min-height:100vh;'
        ):
            # ── HEADER ────────────────────────────────────────────────────────
            with ui.card().classes('w-full').style(
                f'background:linear-gradient(135deg,{HDR} 0%,{HDR2} 100%);'
                f'border:none;border-radius:12px;'
                f'box-shadow:0 3px 16px rgba(0,92,53,0.4);padding:14px 28px;'
            ):
                with ui.row().classes('w-full items-center no-wrap').style('gap:0;'):
                    # Logo: clase CSS inyectada en <head> (evita el parser de NiceGUI)
                    if _LOGO_B64:
                        ui.element('div').classes('ccu-logo-box')
                    with ui.column().classes('items-center flex-1').style('gap:1px;padding:0 16px;'):
                        ui.label('Sistema de Alertas TRT').style(
                            'font-size:0.8rem;font-weight:600;'
                            'color:rgba(255,255,255,0.75);'
                            'text-transform:uppercase;letter-spacing:0.18em;'
                        )
                        ui.label(site.name).style(
                            'font-size:2.2rem;font-weight:800;color:#ffffff;'
                            'letter-spacing:-0.02em;line-height:1;text-align:center;'
                        )
                    with ui.column().classes('items-end').style('gap:1px;flex-shrink:0;'):
                        refs['time_lbl'] = ui.label(now.strftime('%H:%M:%S')).style(
                            'font-size:2rem;font-weight:700;color:#86efac;'
                            'font-variant-numeric:tabular-nums;'
                        )
                        refs['date_lbl'] = ui.label(_date_es(now)).style(
                            'font-size:0.85rem;color:rgba(255,255,255,0.7);'
                        )

            # ── RESUMEN TIEMPO REAL ───────────────────────────────────────────
            _section_title('Resumen en Tiempo Real')

            centers_list = monitoring.get_centers_data() if monitoring else []
            live  = next((c for c in centers_list if c['name'] == site.name), {})
            kpis  = analytics.get_kpi_summary(site.name, days=30)
            pct   = kpis.get('pct_critical', 0)
            t_now = live.get('trucks_in_plant', 0)
            a_now = live.get('alerts', 0)
            trucks_cache = {'list': live.get('trucks_list', [])}

            with ui.row().classes('w-full').style('gap:12px;'):
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('w-full items-center justify-between').style('margin-bottom:10px;'):
                        with ui.row().classes('items-center').style('gap:7px;'):
                            ui.icon('local_shipping').style(f'color:#F57C00;font-size:1.3rem;')
                            ui.label('Ahora en Planta').style(
                                f'font-size:1.1rem;font-weight:700;color:{TXT_S};')
                        refs['trucks_btn'] = ui.button(
                            'Ver camiones', icon='local_shipping',
                            on_click=lambda: open_trucks(site.name, trucks_cache['list'], thr)
                        ).props('outline color=orange size=sm')
                        refs['trucks_btn'].set_visibility(bool(trucks_cache['list']))
                    with ui.row().style('gap:40px;align-items:flex-end;'):
                        refs['trucks_lbl'] = _kpi(ui.element('span'), 'Camiones', str(t_now), TXT_P)
                        refs['alerts_lbl'] = _kpi(ui.element('span'), 'Alertas Activas', str(a_now),
                                                  RED if a_now > 0 else GREEN)

                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    with ui.row().classes('items-center').style('gap:7px;margin-bottom:10px;'):
                        ui.icon('insights').style(f'color:{BLUE};font-size:1.3rem;')
                        ui.label('Histórico — Últimos 30 Días').style(
                            f'font-size:1.1rem;font-weight:700;color:{TXT_S};')
                    with ui.row().style('gap:40px;align-items:flex-end;'):
                        refs['avg_lbl']  = _kpi(ui.element('span'), 'TRT Promedio',
                                                _hhmm(kpis.get('avg_trt_min', 0)), BLUE)
                        refs['disp_lbl'] = _kpi(ui.element('span'), 'Despachos',
                                                str(kpis.get('total_dispatches', 0)), TXT_P)
                        refs['pct_lbl']  = _kpi(ui.element('span'), '% Críticos',
                                                f'{pct:.1f}%', RED if pct > 20 else GREEN)

            # ── GRÁFICOS ──────────────────────────────────────────────────────
            refs['ind_lbl'] = _section_title(
                f'Indicadores Operacionales — {_month_year(now)}')

            lat_data  = analytics.get_monthly_trend_by_type(site.name, 'LATERAL')
            tras_data = analytics.get_monthly_trend_by_type(site.name, 'TRASERA') if show_tras  else []
            int_data  = analytics.get_monthly_trend_by_type(site.name, 'INTERNA') if show_intra else []

            with ui.row().classes('w-full').style('gap:12px;'):
                # LATERAL
                with ui.card().classes('flex-1').style(
                    f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                    f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                ):
                    _chart_header('Botelleros — Carga Lateral', LAT_LINE, LAT_LINE, _hhmm(u_lat))
                    refs['chart_lat'] = ui.echart({}).style('height:320px;width:100%;')
                    refs['chart_lat'].run_chart_method(
                        ':setOption',
                        _chart_js(lat_data, u_lat, LAT_LINE, LAT_BAR, f'Umbral {_hhmm(u_lat)}'),
                        True,
                    )

                # TRASERA
                if show_tras:
                    with ui.card().classes('flex-1').style(
                        f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                        f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                    ):
                        _chart_header('InterAndinos — Carga Trasera', TRAS_LINE, TRAS_LINE, _hhmm(u_tras))
                        refs['chart_tras'] = ui.echart({}).style('height:320px;width:100%;')
                        refs['chart_tras'].run_chart_method(
                            ':setOption',
                            _chart_js(tras_data, u_tras, TRAS_LINE, TRAS_BAR, f'Umbral {_hhmm(u_tras)}'),
                            True,
                        )

                # INTERNA
                if show_intra:
                    with ui.card().classes('flex-1').style(
                        f'background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                        f'box-shadow:0 1px 6px rgba(0,0,0,0.05);'
                    ):
                        _chart_header('Interna — Carga Interna', INT_LINE, INT_LINE, _hhmm(u_int))
                        refs['chart_int'] = ui.echart({}).style('height:320px;width:100%;')
                        refs['chart_int'].run_chart_method(
                            ':setOption',
                            _chart_js(int_data, u_int, INT_LINE, INT_BAR, f'Umbral {_hhmm(u_int)}'),
                            True,
                        )

            # ── ACUERDOS ──────────────────────────────────────────────────────
            _section_title('Acuerdos del Área')
            _acuerdos_section(slug)

            refs['footer_lbl'] = ui.label(
                f'Última actualización: {now.strftime("%H:%M:%S")} · CCU-TRT Monitor'
            ).classes('w-full').style(
                f'text-align:center;color:{TXT_MUT};font-size:0.78rem;'
                f'padding-top:12px;border-top:1px solid {BORDER};'
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
            refs['chart_lat'].run_chart_method(
                ':setOption',
                _chart_js(ld, u_lat, LAT_LINE, LAT_BAR, f'Umbral {_hhmm(u_lat)}'),
                True,
            )
            if show_tras:
                td = analytics.get_monthly_trend_by_type(site.name, 'TRASERA')
                refs['chart_tras'].run_chart_method(
                    ':setOption',
                    _chart_js(td, u_tras, TRAS_LINE, TRAS_BAR, f'Umbral {_hhmm(u_tras)}'),
                    True,
                )
            if show_intra:
                id_ = analytics.get_monthly_trend_by_type(site.name, 'INTERNA')
                refs['chart_int'].run_chart_method(
                    ':setOption',
                    _chart_js(id_, u_int, INT_LINE, INT_BAR, f'Umbral {_hhmm(u_int)}'),
                    True,
                )
            refs['ind_lbl'].text = f'Indicadores Operacionales — {_month_year(datetime.now())}'

        ui.timer(300, _charts)
