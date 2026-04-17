"""
debug_safecard.py — Script de diagnóstico CCCSafe API

Consulta la API de CCCSafe directamente y compara los resultados
con y sin el filtro status=acarreo, para entender discrepancias
entre lo que muestra la web y lo que reporta la app.

Uso:
    python scripts/debug_safecard.py
    python scripts/debug_safecard.py --placa LJDW14
"""

import sys
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Suprimir advertencias de certificado SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.txt"

_API_DATA_URL = "https://www.cccsafe.cl/api/supabase/rest/v1/movimientos"
_AUTH_BASE = "https://www.cccsafe.cl/api/auth"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVrenNkeHhnZ3N4cnFqbmt0amJtIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NDU0NzQ0MDAsImV4cCI6MjA2MTA1MDQwMH0"
    ".KBjMBKwstZFBOjJ2KhHWqtGj_d5Z-znTUQfFDWRY0ao"
)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def load_config():
    if not CONFIG_FILE.exists():
        print(f"ERROR: No se encontró {CONFIG_FILE}")
        sys.exit(1)

    config = {"api_email": "", "api_password": "", "sites": []}
    current_site = {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                if current_site.get("name"):
                    config["sites"].append(current_site)
                    current_site = {}
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if key == "API_EMAIL":
                    config["api_email"] = value
                elif key == "API_PASSWORD":
                    config["api_password"] = value
                elif key == "SITE_NAME":
                    current_site["name"] = value
                elif key == "CENTRO_ID":
                    current_site["centro_id"] = int(value)

    if current_site.get("name"):
        config["sites"].append(current_site)

    return config


def login(email, password):
    print(f"Autenticando como {email}...")
    r = requests.post(
        f"{_AUTH_BASE}/sign-in",
        json={"email": email, "password": password},
        timeout=15,
        verify=False,
    )
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    print("Login exitoso.\n")
    return token


def make_headers(token):
    return {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {token}",
        "accept-profile": "public",
    }


def ventana_utc():
    """Retorna (inicio, fin) del día operativo actual en UTC (04:00-03:59:59)."""
    now_utc = datetime.now(timezone.utc)
    start = now_utc.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_utc.hour < 4:
        start -= timedelta(days=1)
    end = start + timedelta(hours=23, minutes=59, seconds=59, microseconds=999000)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
    )


def query_api(centro_id, token, with_status_filter=True):
    """Consulta la API con o sin el filtro status=acarreo.
    Usa los mismos campos que solicita el sitio web de Safecard."""
    inicio, fin = ventana_utc()
    params = [
        # Mismos campos que el sitio web de Safecard
        ("select", "id,placa,license_plate,movement_type,gate_nombre,fecha_evento,"
                   "ac_travel_code,ac_travel_id,spreadsheet_number,"
                   "conductor_empresa,proveedor_nombre,centro_nombre,site_name,"
                   "conductor_id,status"),
        ("fecha_evento", f"gte.{inicio}"),
        ("fecha_evento", f"lte.{fin}"),
        ("order", "fecha_evento.asc"),
        ("centro_id", f"eq.{centro_id}"),
    ]
    if with_status_filter:
        params.append(("status", "eq.acarreo"))

    r = requests.get(
        _API_DATA_URL,
        params=params,
        headers=make_headers(token),
        timeout=15,
        verify=False,
    )
    r.raise_for_status()
    return r.json()


def group_by_placa(eventos):
    """Agrupa eventos por patente, devuelve {placa: [eventos ordenados asc]}."""
    por_placa = {}
    for ev in eventos:
        por_placa.setdefault(ev["placa"], []).append(ev)
    return por_placa


def last_event_status(evs):
    ultimo = evs[-1]
    return {
        "movement_type": (ultimo.get("movement_type") or "").upper(),
        "status":        ultimo.get("status") or "(null)",
        "fecha_evento":  ultimo.get("fecha_evento") or "",
        "empresa":       ultimo.get("conductor_empresa") or "",
    }


def compute_time_in_plant(fecha_evento_str):
    """Devuelve timedelta desde fecha_evento hasta ahora."""
    try:
        fe = datetime.fromisoformat(fecha_evento_str)
        ahora = datetime.now(timezone.utc)
        return ahora - fe
    except Exception as e:
        return None


def fmt_td(td):
    if td is None:
        return "?"
    total = int(td.total_seconds())
    if total < 0:
        return "negativo"
    h, r = divmod(total, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def print_section(title):
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def simulate_fix(eventos):
    """Simula el fix real: intersección de criterios por placa Y por ac_travel_id."""
    print_section("SIMULACIÓN DEL FIX (intersección placa ∩ ac_travel_id)")

    # Criterio 1: por placa
    por_placa = group_by_placa(eventos)
    in_plant_placa = {
        p for p, evs in por_placa.items()
        if (evs[-1].get("movement_type") or "").upper() == "IN"
    }

    # Criterio 2: por ac_travel_id
    por_travel: dict = {}
    for ev in eventos:
        tid = ev.get("ac_travel_id")
        if tid is None:
            continue
        por_travel.setdefault(tid, []).append(ev)

    in_plant_travel: set = set()
    for tid, evs in por_travel.items():
        ultimo = evs[-1]
        if (ultimo.get("movement_type") or "").upper() == "IN":
            p = (ultimo.get("placa") or "").strip()
            if p:
                in_plant_travel.add(p)

    # Intersección
    in_plant_fix = sorted(in_plant_placa & in_plant_travel)
    in_plant_old = sorted(in_plant_placa)

    print(f"  Lógica VIEJA (solo placa):          {len(in_plant_old)} → {in_plant_old}")
    print(f"  Lógica NUEVA (placa ∩ travel_id):   {len(in_plant_fix)} → {in_plant_fix}")

    removed = in_plant_placa - in_plant_travel
    if removed:
        print(f"\n  Falsos positivos eliminados: {sorted(removed)}")
        for p in sorted(removed):
            evs = por_placa.get(p, [])
            travel_id = evs[-1].get("ac_travel_id") if evs else None
            if travel_id and travel_id in por_travel:
                t_evs = por_travel[travel_id]
                ultimo_t = t_evs[-1]
                print(f"    {p} — travel_id={travel_id}  "
                      f"último del viaje: {ultimo_t.get('movement_type')!r}  "
                      f"placa={ultimo_t.get('placa')!r}  "
                      f"fecha={ultimo_t.get('fecha_evento','')}")
    else:
        print("\n  Sin cambios — ambas lógicas dan el mismo resultado.")
    print()


def analyze_in_plant_trucks(eventos, label=""):
    """Agrupa por placa, muestra solo los que tienen último evento IN, con todos sus campos."""
    por_placa = group_by_placa(eventos)
    in_plant = [(p, evs) for p, evs in por_placa.items()
                if (evs[-1].get("movement_type") or "").upper() == "IN"]

    if not in_plant:
        print(f"  {label}: 0 camiones en planta\n")
        return

    print(f"  {label}: {len(in_plant)} camiones en planta\n")
    for placa, evs in sorted(in_plant):
        ultimo = evs[-1]
        td = compute_time_in_plant(ultimo.get("fecha_evento", ""))
        print(f"  PATENTE: {placa}  ({len(evs)} evento(s)) — tiempo en planta: {fmt_td(td)}")
        for k, v in ultimo.items():
            if v is not None and v != "":
                print(f"    {k}: {v!r}")
        print()


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

def analyze(centro_id, token, placa_filter=None):
    inicio, fin = ventana_utc()
    print(f"\nVentana UTC: {inicio}  →  {fin}\n")

    # --- Query SIN filtro de status ---
    print_section("QUERY SIN FILTRO status (todos los eventos)")
    eventos_all = query_api(centro_id, token, with_status_filter=False)
    print(f"Eventos devueltos: {len(eventos_all)}\n")

    por_placa_all = group_by_placa(eventos_all)

    # Mostrar todos los status únicos encontrados
    statuses_all = sorted({ev.get("status") or "(null)" for ev in eventos_all})
    print(f"Valores únicos de 'status': {statuses_all}\n")

    print(f"{'PATENTE':<12} {'EVENTOS':>7}  {'ULTIMO MOV':>10}  {'STATUS':>15}  {'TIEMPO EN PLANTA':>18}  EMPRESA")
    print("-" * 90)
    for placa, evs in sorted(por_placa_all.items()):
        if placa_filter and placa.upper() != placa_filter.upper():
            continue
        info = last_event_status(evs)
        td = compute_time_in_plant(info["fecha_evento"]) if info["movement_type"] == "IN" else None
        in_plant = "SI" if info["movement_type"] == "IN" else "NO"
        print(
            f"{placa:<12} {len(evs):>7}  {in_plant:>10}  {info['status']:>15}  "
            f"{fmt_td(td):>18}  {info['empresa']}"
        )

    # --- Camiones "en planta" según query sin filtro ---
    en_planta_all = {p for p, evs in por_placa_all.items() if last_event_status(evs)["movement_type"] == "IN"}
    print(f"\nCamiones en planta (sin filtro): {len(en_planta_all)} → {sorted(en_planta_all)}")

    # --- Query CON filtro status=acarreo ---
    print()
    print_section("QUERY CON FILTRO status=eq.acarreo (como lo hace la app hoy)")
    eventos_fil = query_api(centro_id, token, with_status_filter=True)
    print(f"Eventos devueltos: {len(eventos_fil)}\n")

    por_placa_fil = group_by_placa(eventos_fil)

    print(f"{'PATENTE':<12} {'EVENTOS':>7}  {'ULTIMO MOV':>10}  {'STATUS':>15}  {'TIEMPO EN PLANTA':>18}  EMPRESA")
    print("-" * 90)
    for placa, evs in sorted(por_placa_fil.items()):
        if placa_filter and placa.upper() != placa_filter.upper():
            continue
        info = last_event_status(evs)
        td = compute_time_in_plant(info["fecha_evento"]) if info["movement_type"] == "IN" else None
        in_plant = "SI" if info["movement_type"] == "IN" else "NO"
        print(
            f"{placa:<12} {len(evs):>7}  {in_plant:>10}  {info['status']:>15}  "
            f"{fmt_td(td):>18}  {info['empresa']}"
        )

    en_planta_fil = {p for p, evs in por_placa_fil.items() if last_event_status(evs)["movement_type"] == "IN"}
    print(f"\nCamiones en planta (con filtro status=acarreo): {len(en_planta_fil)} → {sorted(en_planta_fil)}")

    # --- Comparación ---
    print()
    print_section("COMPARACIÓN")
    solo_sin_filtro = en_planta_all - en_planta_fil
    solo_con_filtro = en_planta_fil - en_planta_all
    ambos = en_planta_all & en_planta_fil

    print(f"En planta en AMBAS queries:                    {sorted(ambos)}")
    print(f"En planta SOLO sin filtro (el filtro los pierde): {sorted(solo_sin_filtro)}")
    print(f"En planta SOLO con filtro (raro):              {sorted(solo_con_filtro)}")

    if solo_sin_filtro:
        print()
        print("*** CAMIONES PERDIDOS POR EL FILTRO status=acarreo ***")
        for placa in sorted(solo_sin_filtro):
            evs_all = por_placa_all[placa]
            print(f"\n  Patente: {placa}")
            print(f"  Total eventos (sin filtro): {len(evs_all)}")
            for ev in evs_all:
                print(
                    f"    [{ev.get('fecha_evento','')}] "
                    f"movement_type={ev.get('movement_type')!r:<5}  "
                    f"status={ev.get('status')!r}"
                )

    if not solo_sin_filtro and not solo_con_filtro:
        print("\n  Ambas queries dan el MISMO resultado.")
        print("  El filtro status=acarreo NO está causando el problema.")
        print("  La discrepancia puede ser:")
        print("   - Estado en memoria desactualizado (reinicia monitor_alertas.py)")
        print("   - La app muestra datos del ciclo de polling anterior")
        print("   - Diferencia de zona horaria en fecha_evento")

    # --- Detalle de todos los eventos de la placa buscada ---
    if placa_filter:
        print()
        print_section(f"TODOS LOS EVENTOS DE {placa_filter.upper()}")
        if placa_filter.upper() in por_placa_all:
            for ev in por_placa_all[placa_filter.upper()]:
                print(
                    f"  [{ev.get('fecha_evento','')}] "
                    f"movement_type={ev.get('movement_type')!r:<5}  "
                    f"status={ev.get('status')!r}  "
                    f"travel_id={ev.get('ac_travel_id')!r}  "
                    f"empresa={ev.get('conductor_empresa')!r}"
                )
        else:
            print(f"  No se encontraron eventos para {placa_filter} en la ventana de hoy.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SUPABASE_BASE = "https://www.cccsafe.cl/api/supabase/rest/v1"

CANDIDATE_TABLES = [
    "camiones_en_planta",
    "trucks_in_plant",
    "estado_camiones",
    "presencia_camiones",
    "ingresos_activos",
    "viajes_activos",
    "viajes",
    "acarreos",
    "camiones",
    "camiones_planta",
    "registros_activos",
    "tracking",
    "planta",
    "ingreso_camiones",
    "trucks",
    "vehicles",
    "vehiculos",
    "ac_travels",
    "travels",
]


def discover_tables(token, centro_id):
    """Prueba endpoints comunes de Supabase para encontrar la tabla de 'en planta'."""
    print_section("BÚSQUEDA DE ENDPOINT ALTERNATIVO")
    print(f"Probando {len(CANDIDATE_TABLES)} tablas candidatas...\n")
    headers = make_headers(token)
    found = []

    for table in CANDIDATE_TABLES:
        url = f"{_SUPABASE_BASE}/{table}"
        try:
            # Limit=1 para no descargar datos innecesarios
            r = requests.get(
                url,
                params=[("limit", "3"), ("centro_id", f"eq.{centro_id}")],
                headers=headers,
                timeout=8,
                verify=False,
            )
            if r.status_code == 200:
                data = r.json()
                print(f"  [OK 200] {table}  ({len(data)} filas con centro_id={centro_id})")
                if data:
                    print(f"           Campos: {list(data[0].keys())}")
                found.append((table, data))
            elif r.status_code == 404:
                pass  # tabla no existe, ignorar
            else:
                # Otro error puede ser interesante
                print(f"  [{r.status_code}] {table}")
        except requests.exceptions.Timeout:
            print(f"  [timeout] {table}")
        except Exception as e:
            print(f"  [error]   {table}: {e}")

    # También probar sin filtro centro_id (por si la tabla no tiene esa columna)
    print("\nProbando sin filtro centro_id (primeras 3 tablas candidatas)...\n")
    for table in CANDIDATE_TABLES[:6]:
        url = f"{_SUPABASE_BASE}/{table}"
        try:
            r = requests.get(
                url,
                params=[("limit", "3")],
                headers=headers,
                timeout=8,
                verify=False,
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    print(f"  [OK 200] {table}  ({len(data)} filas sin filtro)")
                    print(f"           Campos: {list(data[0].keys())}")
        except Exception:
            pass

    if not found:
        print("\n  No se encontró ninguna tabla accesible.")
        print("  Siguiente paso: revisar las llamadas de red del sitio Safecard.")
        print("  → Abre https://www.cccsafe.cl/camiones-planta en Chrome")
        print("  → F12 → Pestaña Network → filtra por 'rest/v1'")
        print("  → Refresca la página y copia las URLs de las llamadas API")

    return found


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico CCCSafe API")
    parser.add_argument("--placa", help="Filtrar por patente específica (ej: LJDW14)")
    parser.add_argument("--travel", help="Mostrar todos los eventos de un ac_travel_id (ej: 23447)")
    parser.add_argument("--centro", help="Nombre del sitio (ej: 'Santiago Sur'). Por defecto usa el primero con CENTRO_ID.")
    parser.add_argument("--discover", action="store_true", help="Busca tablas alternativas en la API de Safecard")
    args = parser.parse_args()

    config = load_config()
    if not config["api_email"]:
        print("ERROR: No hay API_EMAIL en config.txt")
        sys.exit(1)

    # Seleccionar sitio
    sites_with_api = [s for s in config["sites"] if s.get("centro_id")]
    if not sites_with_api:
        print("ERROR: Ningún sitio tiene CENTRO_ID configurado.")
        sys.exit(1)

    if args.centro:
        site = next((s for s in sites_with_api if args.centro.lower() in s["name"].lower()), None)
        if not site:
            print(f"ERROR: No se encontró sitio con nombre '{args.centro}'.")
            print(f"Sitios disponibles: {[s['name'] for s in sites_with_api]}")
            sys.exit(1)
    else:
        site = sites_with_api[0]

    print(f"Sitio: {site['name']}  |  CENTRO_ID: {site['centro_id']}")

    token = login(config["api_email"], config["api_password"])

    if args.discover:
        discover_tables(token, site["centro_id"])
    elif args.travel:
        # Modo travel: muestra TODOS los eventos de un ac_travel_id (cualquier patente)
        travel_id = int(args.travel)
        inicio, fin = ventana_utc()
        headers = make_headers(token)
        params = [
            ("select", "id,placa,license_plate,movement_type,gate_nombre,fecha_evento,"
                       "ac_travel_code,ac_travel_id,spreadsheet_number,"
                       "conductor_empresa,status"),
            ("ac_travel_id", f"eq.{travel_id}"),
            ("order", "fecha_evento.asc"),
        ]
        r = requests.get(_API_DATA_URL, params=params, headers=headers, timeout=15, verify=False)
        r.raise_for_status()
        eventos = r.json()
        print(f"\nTodos los eventos con ac_travel_id={travel_id}: {len(eventos)} encontrado(s)\n")
        for i, ev in enumerate(eventos, 1):
            mt = (ev.get("movement_type") or "").upper()
            print(f"  Evento {i} — movement_type={mt!r}  placa={ev.get('placa')!r}")
            for k, v in ev.items():
                if k not in ("id",):
                    print(f"    {k}: {v!r}")
            print()
    elif args.placa:
        # Modo detalle: muestra todos los eventos de esa patente con campos completos
        eventos = query_api(site["centro_id"], token, with_status_filter=False)
        por_placa = group_by_placa(eventos)
        placa_upper = args.placa.upper()
        if placa_upper not in por_placa:
            print(f"\nNo se encontraron eventos para {placa_upper} en la ventana de hoy.")
        else:
            evs = por_placa[placa_upper]
            print(f"\n{'='*60}")
            print(f"  TODOS LOS EVENTOS DE {placa_upper} ({len(evs)} total)")
            print(f"{'='*60}")
            for i, ev in enumerate(evs, 1):
                mt = (ev.get("movement_type") or "").upper()
                print(f"\n  Evento {i} — movement_type={mt!r}")
                for k, v in ev.items():
                    print(f"    {k}: {v!r}")
    else:
        # Modo completo: comparación y detalle de camiones en planta
        print_section("CAMIONES EN PLANTA — DATOS COMPLETOS (mismo select que el sitio web)")
        eventos_fil = query_api(site["centro_id"], token, with_status_filter=True)
        simulate_fix(eventos_fil)
        analyze_in_plant_trucks(eventos_fil, label="Con filtro status=acarreo")
        analyze(site["centro_id"], token, placa_filter=args.placa)


if __name__ == "__main__":
    main()
