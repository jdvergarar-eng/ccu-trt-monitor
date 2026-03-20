# TRT API Client - Obtiene datos del sistema TRT
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass
import re


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

    def __init__(self, base_url: str = "http://192.168.55.79"):
        self.base_url = base_url.rstrip("/")
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

    def get_trucks_in_plant(self, site_config: dict) -> List[TruckInPlant]:
        """
        Obtiene los camiones actualmente en planta para un sitio.

        Args:
            site_config: Diccionario con db_name, op_code, cd_code, referer_id
        """
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


def get_trt_client(base_url: str = None) -> TRTClient:
    """Obtiene la instancia global del TRTClient"""
    global _trt_client
    if _trt_client is None or (base_url and _trt_client.base_url != base_url.rstrip("/")):
        _trt_client = TRTClient(base_url or "http://192.168.55.79")
    return _trt_client
