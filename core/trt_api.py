# TRT API Client - Obtiene datos del sistema TRT
import requests
import urllib3
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass
import re
import time
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# AUTENTICACION CCCSafe API
# =============================================================================

class AuthManager:
    """Gestiona el JWT de CCCSafe: login inicial y refresh automatico."""

    _AUTH_BASE = "https://www.cccsafe.cl/api/auth"
    ANON_KEY = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVrenNkeHhnZ3N4cnFqbmt0amJtIiwi"
        "cm9sZSI6ImFub24iLCJpYXQiOjE3NDU0NzQ0MDAsImV4cCI6MjA2MTA1MDQwMH0"
        ".KBjMBKwstZFBOjJ2KhHWqtGj_d5Z-znTUQfFDWRY0ao"
    )

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def _do_login(self) -> None:
        r = requests.post(
            f"{self._AUTH_BASE}/sign-in",
            json={"email": self.email, "password": self.password},
            timeout=15, verify=False,
        )
        r.raise_for_status()
        self._store(r.json())

    def _do_refresh(self) -> None:
        r = requests.post(
            f"{self._AUTH_BASE}/refresh",
            json={"refresh_token": self._refresh_token},
            timeout=15, verify=False,
        )
        if r.status_code >= 400:
            self._do_login()
            return
        self._store(r.json())

    def _store(self, data: dict) -> None:
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 120

    def get_token(self) -> str:
        with self._lock:
            if self._access_token is None:
                self._do_login()
            elif time.time() >= self._expires_at:
                self._do_refresh()
            return self._access_token

    def headers(self) -> dict:
        return {
            "apikey": self.ANON_KEY,
            "Authorization": f"Bearer {self.get_token()}",
            "accept-profile": "public",
        }


_API_DATA_URL = "https://www.cccsafe.cl/api/supabase/rest/v1/movimientos"
_SANTIAGO_TZ = ZoneInfo("America/Santiago")


def _ventana_utc():
    now_utc = datetime.now(timezone.utc)
    start = now_utc.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_utc.hour < 4:
        start -= timedelta(days=1)
    end = start + timedelta(hours=23, minutes=59, seconds=59, microseconds=999000)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
    )


@dataclass
class TRTCenter:
    """Informacion de un centro del TRT"""
    name: str
    referer_id: str
    db_name: str
    op_code: str
    cd_code: str


@dataclass
class TruckInPlant:
    """Camion en planta"""
    plate: str
    company: str
    arrival_time: str
    time_in_plant: str
    time_in_plant_minutes: int
    entry_type: str


def _find_plant_table(soup):
    """Localiza la tabla de 'Camiones en Planta' usando múltiples estrategias.

    Orden de búsqueda:
    1. Tabla con <caption> que contenga 'camiones en planta'
    2. Tabla cuya primera fila tiene una celda con colspan y el título
    3. Tabla precedida por un heading que contenga el título
    4. Tabla con columna <th> 'tiempo en planta' (fallback de columna)

    Retorna None si no se encuentra (el llamador debe usar todos los <td>).
    """
    search = "camiones en planta"

    for table in soup.find_all("table"):
        # Estrategia 1: <caption> dentro de la tabla
        caption = table.find("caption")
        if caption and search in caption.get_text(strip=True).lower():
            return table

        # Estrategia 2: primera fila con celda colspan que lleva el título de sección
        first_row = table.find("tr")
        if first_row:
            for cell in first_row.find_all(["th", "td"]):
                if cell.get("colspan") and search in cell.get_text(strip=True).lower():
                    return table

        # Estrategia 3: heading inmediatamente anterior a esta tabla
        prev = table.find_previous_sibling()
        while prev:
            if prev.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                if search in prev.get_text(strip=True).lower():
                    return table
                break  # Heading que no coincide → no seguir buscando hacia atrás
            if prev.name == "table":
                break  # Otra tabla antes → no es nuestro heading
            prev = prev.find_previous_sibling()

    # Estrategia 4: columna <th> con 'tiempo en planta' (detección anterior, último recurso)
    for table in soup.find_all("table"):
        ths_text = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("tiempo en planta" in t for t in ths_text):
            return table

    return None


class TRTClient:
    """Cliente para el sistema TRT"""

    def __init__(self, base_url: str = "http://192.168.55.79", auth: AuthManager = None):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def test_connection(self, verbose: bool = False) -> bool:
        """Prueba la conexion al servidor TRT

        Args:
            verbose: Si True, imprime mensajes de error en consola
        """
        try:
            # Aumentar timeout para redes corporativas lentas
            r = self.session.get(
                f"{self.base_url}/ces/home/",
                timeout=15,
                allow_redirects=True
            )
            return r.status_code == 200
        except requests.exceptions.Timeout:
            if verbose:
                print(f"Error en test_connection: Timeout al conectar a {self.base_url}")
            return False
        except requests.exceptions.ConnectionError as e:
            if verbose:
                print(f"Error en test_connection: No se puede conectar - {e}")
            return False
        except Exception as e:
            if verbose:
                print(f"Error en test_connection: {e}")
            return False

    def get_available_centers(self) -> List[TRTCenter]:
        """
        Obtiene la lista de centros disponibles desde la pagina del TRT.
        Busca links con formato /ces/home/registro/N donde N es el ID del centro.
        """
        centers = []
        found_ids = set()

        try:
            # Intentar obtener centros de la pagina principal
            r = self.session.get(f"{self.base_url}/ces/home/", timeout=15)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "lxml")

            # Buscar todos los links que contengan /ces/home/registro/
            # Pueden estar en diferentes formatos:
            # - href="/ces/home/registro/25"
            # - href="registro/25"
            # - onclick con URL

            # Metodo 1: Buscar en atributos href
            for link in soup.find_all("a"):
                href = link.get("href", "")
                # Buscar patron de registro
                match = re.search(r"registro/(\d+)", href)
                if match:
                    referer_id = match.group(1)
                    if referer_id not in found_ids:
                        name = link.get_text(strip=True)
                        if name:
                            found_ids.add(referer_id)
                            centers.append({
                                "referer_id": referer_id,
                                "name": name,
                            })

            # Metodo 2: Buscar en todo el HTML por patron de URL
            if not centers:
                html_text = r.text
                # Buscar todas las referencias a registro/N
                matches = re.findall(r'registro/(\d+)["\'\s>]', html_text)
                for referer_id in set(matches):
                    if referer_id not in found_ids:
                        found_ids.add(referer_id)
                        # Obtener nombre de la pagina del centro
                        name = self._get_center_name(referer_id)
                        if name:
                            centers.append({
                                "referer_id": referer_id,
                                "name": name,
                            })

            # Metodo 3: Probar IDs conocidos comunes (1-50)
            if not centers:
                # Búsqueda silenciosa por IDs conocidos
                for test_id in range(1, 51):
                    try:
                        url = f"{self.base_url}/ces/home/registro/{test_id}"
                        r = self.session.get(url, timeout=5)
                        if r.status_code == 200 and "registro" in r.text.lower():
                            name = self._get_center_name(str(test_id))
                            if name and str(test_id) not in found_ids:
                                found_ids.add(str(test_id))
                                centers.append({
                                    "referer_id": str(test_id),
                                    "name": name,
                                })
                    except Exception:
                        continue

            # Ahora obtener los datos de formulario para cada centro encontrado
            result_centers = []
            for center_info in centers:
                referer_id = center_info["referer_id"]
                name = center_info["name"]

                # Obtener db, op, cd de la pagina del centro
                form_data = self._get_center_form_data(referer_id)

                result_centers.append(TRTCenter(
                    name=name,
                    referer_id=referer_id,
                    db_name=form_data.get("db", "") if form_data else "",
                    op_code=form_data.get("op", "") if form_data else "",
                    cd_code=form_data.get("cd", "") if form_data else "",
                ))

            # Prints eliminados para reducir ruido en consola
            return result_centers

        except Exception as e:
            print(f"Error obteniendo centros: {e}")
            import traceback
            traceback.print_exc()

        return centers

    def _get_center_name(self, referer_id: str) -> Optional[str]:
        """Obtiene el nombre del centro desde su pagina"""
        try:
            url = f"{self.base_url}/ces/home/registro/{referer_id}"
            r = self.session.get(url, timeout=10)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, "lxml")

            # Buscar el titulo en diferentes lugares
            # 1. Tag title
            title = soup.find("title")
            if title:
                text = title.get_text(strip=True)
                # Limpiar texto comun
                text = re.sub(r"TRT\s*-?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"Sistema\s*de\s*", "", text, flags=re.IGNORECASE)
                if text and len(text) > 2:
                    return text.strip()

            # 2. H1 o H2
            for tag in ["h1", "h2", "h3"]:
                header = soup.find(tag)
                if header:
                    text = header.get_text(strip=True)
                    if text and len(text) > 2 and len(text) < 50:
                        return text

            # 3. Clase especifica de nombre
            for cls in ["titulo", "nombre", "center-name", "site-name"]:
                elem = soup.find(class_=re.compile(cls, re.IGNORECASE))
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 2:
                        return text

            # 4. Usar el ID como fallback
            return f"Centro {referer_id}"

        except Exception as e:
            print(f"Error obteniendo nombre del centro {referer_id}: {e}")
            return f"Centro {referer_id}"

    def _get_center_form_data(self, referer_id: str) -> Optional[Dict[str, str]]:
        """
        Obtiene los parametros del formulario para un centro especifico.

        Estructura esperada en la pagina:
        - db: viene del input hidden con id="aca_ent" (ej: aca_ent_stsur)
        - cd: esta en el JavaScript como cdsd = 'xxx' o cd:'xxx'
        - op: esta en el JavaScript como op:N (generalmente 1)
        """
        try:
            url = f"{self.base_url}/ces/home/registro/{referer_id}"
            r = self.session.get(url, timeout=10)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "lxml")
            html_text = r.text
            data = {}

            # Metodo 1: Buscar input hidden con id="aca_ent" o name="aca_ent" para db
            aca_ent_input = soup.find("input", id="aca_ent")
            if not aca_ent_input:
                aca_ent_input = soup.find("input", attrs={"name": "aca_ent"})

            if aca_ent_input:
                data["db"] = aca_ent_input.get("value", "")

            # Metodo 2: Buscar en JavaScript para cd y op
            # Patrones para cd: cdsd = 'xxx' o cd:'xxx' o cd: 'xxx'
            cd_patterns = [
                r'cdsd\s*=\s*["\']([^"\']+)["\']',  # cdsd = 'stsur'
                r'cd\s*:\s*["\']?([^"\'}\s,]+)["\']?',  # cd:'stsur' o cd: cdsd
                r'cd\s*=\s*["\']([^"\']+)["\']',  # cd = 'stsur'
            ]

            # Patrones para op: op:N o op: N
            op_patterns = [
                r'op\s*:\s*(\d+)',  # op:1 o op: 1
                r'op\s*=\s*(\d+)',  # op = 1
            ]

            for script in soup.find_all("script"):
                script_text = script.get_text()

                # Buscar cd
                if "cd" not in data:
                    for pattern in cd_patterns:
                        match = re.search(pattern, script_text)
                        if match:
                            value = match.group(1)
                            # Si el valor es "cdsd", buscar la variable cdsd
                            if value == "cdsd":
                                cdsd_match = re.search(r'cdsd\s*=\s*["\']([^"\']+)["\']', script_text)
                                if cdsd_match:
                                    value = cdsd_match.group(1)
                            if value and value != "cdsd":
                                data["cd"] = value
                                break

                # Buscar op
                if "op" not in data:
                    for pattern in op_patterns:
                        match = re.search(pattern, script_text)
                        if match:
                            data["op"] = match.group(1)
                            break

            # Metodo 3: Si no encontramos cd, intentar extraerlo del valor de db
            # Si db = "aca_ent_stsur", entonces cd probablemente es "stsur"
            if "db" in data and "cd" not in data:
                db_value = data["db"]
                if db_value.startswith("aca_ent_"):
                    data["cd"] = db_value.replace("aca_ent_", "")

            # Metodo 4: Si no encontramos op, asumir que es 1 (valor comun)
            if "op" not in data:
                data["op"] = "1"

            # Metodo 5: Buscar en todo el HTML como fallback
            if "db" not in data:
                # Buscar patron: id="aca_ent" value="xxx"
                match = re.search(r'id=["\']aca_ent["\'].*?value=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
                if match:
                    data["db"] = match.group(1)
                else:
                    # Buscar patron: value="xxx".*id="aca_ent"
                    match = re.search(r'value=["\']([^"\']+)["\'].*?id=["\']aca_ent["\']', html_text, re.IGNORECASE)
                    if match:
                        data["db"] = match.group(1)

            return data if data else None

        except Exception as e:
            print(f"Error obteniendo datos del centro {referer_id}: {e}")
            return None

    def _fetch_trucks_from_api(self, site_config: dict) -> List[TruckInPlant]:
        """Obtiene camiones en planta via API REST CCCSafe."""
        inicio, fin = _ventana_utc()
        params = [
            ("select", "id,placa,movement_type,gate_nombre,fecha_evento,"
                       "ac_travel_id,conductor_empresa"),
            ("fecha_evento", f"gte.{inicio}"),
            ("fecha_evento", f"lte.{fin}"),
            ("order", "fecha_evento.asc"),
            ("status", "eq.acarreo"),
            ("centro_id", f"eq.{site_config['centro_id']}"),
        ]
        r = requests.get(
            _API_DATA_URL, params=params, headers=self.auth.headers(), timeout=15, verify=False
        )
        r.raise_for_status()
        eventos = r.json()

        # Agrupar por patente — fuente de verdad para saber si el camion esta en planta.
        # Usar ac_travel_id causaba falsos positivos cuando el evento OUT tenia
        # un travel_id distinto (o null) al evento IN del mismo camion.
        por_placa: Dict[str, list] = {}
        for ev in eventos:
            por_placa.setdefault(ev["placa"], []).append(ev)

        ahora_utc = datetime.now(timezone.utc)
        trucks = []
        for placa, evs in por_placa.items():
            ultimo = evs[-1]  # eventos ya vienen ordenados asc
            mt = (ultimo.get("movement_type") or "").upper()
            if mt != "IN":
                continue

            fecha_ev = datetime.fromisoformat(ultimo["fecha_evento"])
            tiempo = ahora_utc - fecha_ev
            total_s = int(tiempo.total_seconds())
            total_m = total_s // 60
            dias, rem = divmod(total_s, 86400)
            hh, mm, ss = rem // 3600, (rem % 3600) // 60, rem % 60
            tiempo_str = f"{dias} dias {hh:02d}:{mm:02d}:{ss:02d}"

            try:
                fecha_utc = datetime.fromisoformat(ultimo["fecha_evento"])
                fecha_local = fecha_utc.astimezone(_SANTIAGO_TZ)
                arrival_display = fecha_local.strftime("%H:%M")
            except Exception:
                arrival_display = ""

            trucks.append(TruckInPlant(
                plate=placa,
                company=ultimo.get("conductor_empresa") or "",
                arrival_time=arrival_display,
                time_in_plant=tiempo_str,
                time_in_plant_minutes=total_m,
                entry_type=ultimo.get("conductor_empresa") or "",
            ))

        return trucks

    def get_trucks_in_plant(self, site_config: dict) -> List[TruckInPlant]:
        """
        Obtiene los camiones actualmente en planta para un sitio.
        Usa API CCCSafe si site_config tiene centro_id y el cliente tiene auth;
        de lo contrario usa scraping HTML del servidor interno.

        Args:
            site_config: Diccionario con db_name, op_code, cd_code, referer_id
                         y opcionalmente centro_id (activa API)
        """
        if self.auth and site_config.get("centro_id"):
            return self._fetch_trucks_from_api(site_config)

        trucks = []

        try:
            url = f"{self.base_url}/ces/home/inicio/"
            referer = f"{self.base_url}/ces/home/registro/{site_config['referer_id']}"

            # Actualizar headers para POST
            headers = {
                "Referer": referer,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            }

            post_data = {
                "db": site_config["db_name"],
                "op": site_config["op_code"],
                "cd": site_config["cd_code"]
            }

            r = self.session.post(
                url,
                data=post_data,
                headers=headers,
                timeout=10
            )
            r.raise_for_status()

            # Parsear la tabla
            trucks = self._parse_trucks_table(r.text)

        except Exception as e:
            print(f"Error obteniendo camiones en planta: {e}")

        return trucks

    def _parse_trucks_table(self, html: str) -> List[TruckInPlant]:
        """Parsea la tabla de camiones en planta.

        Aplana todos los <td> de la pagina y los divide en chunks del
        tamaño correcto. El numero de columnas se detecta contando los
        <th> del header, que son seguros porque no se mezclan con datos.

        Formatos conocidos:
        - 9 cols (estandar): N°, Patente, Empresa, Arribo, Tipo, Tiempo, Control, Destino, Salida
        - 10 cols (Cervecera): N°, Patente, N°viaje, Empresa, Arribo, Tipo, Tiempo, Control, Destino, Salida
        """
        trucks = []
        soup = BeautifulSoup(html, "lxml")

        # Identificar la tabla de "Camiones en planta" mediante múltiples estrategias
        # (caption, colspan de sección, heading previo, columna). Si no se encuentra,
        # se usa fallback al comportamiento original (página con una sola tabla).
        target_table = _find_plant_table(soup)

        if target_table:
            headers = target_table.find_all("th")
            all_tds = [td.get_text(" ", strip=True) for td in target_table.find_all("td")]
        else:
            # Fallback: comportamiento original (página con una sola tabla)
            headers = soup.find_all("th")
            all_tds = [td.get_text(" ", strip=True) for td in soup.find_all("td")]

        # Detectar formato por numero de <th> en el header de la tabla correcta
        ncols = 10 if len(headers) >= 10 else 9

        # Mapeo de columnas segun formato
        if ncols >= 10:
            col_plate, col_company, col_arrival, col_entry, col_time = 1, 3, 4, 5, 6
        else:
            col_plate, col_company, col_arrival, col_entry, col_time = 1, 2, 3, 4, 5

        if len(all_tds) < ncols:
            return trucks

        usable = (len(all_tds) // ncols) * ncols

        for i in range(0, usable, ncols):
            chunk = all_tds[i:i + ncols]
            if not any(chunk):
                continue

            plate = chunk[col_plate]
            if not plate:
                continue

            time_str_raw = chunk[col_time]
            time_minutes = self._parse_time_to_minutes(time_str_raw)
            time_display = self._format_time_hms(time_str_raw)

            trucks.append(TruckInPlant(
                plate=plate,
                company=chunk[col_company],
                arrival_time=chunk[col_arrival],
                time_in_plant=time_display,
                time_in_plant_minutes=time_minutes,
                entry_type=chunk[col_entry],
            ))

        return trucks

    def _format_time_hms(self, time_str: str) -> str:
        """Convierte 'X dias HH:MM:SS' a 'HH:MM:SS' acumulando dias en horas.
        Ej: '1 dias 02:30:00' -> '26:30:00'
        """
        try:
            match = re.search(r"(\d+)\s*d[ia]+s?\s*(\d{2}):(\d{2}):(\d{2})", time_str, re.IGNORECASE)
            if match:
                total_hours = int(match.group(1)) * 24 + int(match.group(2))
                return f"{total_hours:02d}:{match.group(3)}:{match.group(4)}"
            # Si ya es HH:MM:SS sin dias
            match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", time_str)
            if match:
                return f"{int(match.group(1)):02d}:{match.group(2)}:{match.group(3)}"
        except Exception:
            pass
        return time_str

    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Convierte tiempo formato '0 dias 01:23:45' a minutos"""
        try:
            match = re.search(r"(\d+)\s*d[ia]as?\s*(\d{2}):(\d{2}):(\d{2})", time_str, re.IGNORECASE)
            if match:
                days = int(match.group(1))
                hours = int(match.group(2))
                minutes = int(match.group(3))
                return days * 24 * 60 + hours * 60 + minutes
            # Intentar HH:MM:SS sin dias
            match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", time_str)
            if match:
                return int(match.group(1)) * 60 + int(match.group(2))
        except Exception:
            pass
        return 0

    def get_center_stats(self, site_config: dict) -> Dict:
        """
        Obtiene estadisticas del centro.

        Returns:
            Dict con total_trucks, avg_time_minutes, trucks_over_threshold
        """
        trucks = self.get_trucks_in_plant(site_config)

        if not trucks:
            return {
                "total_trucks": 0,
                "avg_time_minutes": 0,
                "max_time_minutes": 0,
                "trucks_over_threshold": 0,
            }

        times = [t.time_in_plant_minutes for t in trucks]

        return {
            "total_trucks": len(trucks),
            "avg_time_minutes": sum(times) // len(times) if times else 0,
            "max_time_minutes": max(times) if times else 0,
            "trucks": trucks,
        }


# Instancia global
_trt_client: Optional[TRTClient] = None


def get_trt_client(base_url: str = None, api_email: str = None, api_password: str = None) -> TRTClient:
    """Obtiene la instancia global del TRTClient.
    Si se pasan api_email y api_password, el cliente usará la API CCCSafe
    para sitios con centro_id configurado.
    """
    global _trt_client
    url = (base_url or "http://192.168.55.79").rstrip("/")
    needs_new = (
        _trt_client is None
        or _trt_client.base_url != url
        or (api_email and _trt_client.auth is None)
    )
    if needs_new:
        auth = AuthManager(api_email, api_password) if api_email and api_password else None
        _trt_client = TRTClient(url, auth=auth)
    return _trt_client
