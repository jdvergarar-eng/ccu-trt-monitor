# Analytics service - Lee datos historicos de daily_data/ para graficos
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    TIMEZONE = ZoneInfo("America/Santiago")
except Exception:
    TIMEZONE = None


class AnalyticsService:
    """Lee archivos JSON de daily_data/ y calcula metricas para graficos"""

    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "daily_data"
        self.data_dir = data_dir

    def _get_safe_name(self, site_name: str) -> str:
        return site_name.lower().replace(" ", "_")

    def _find_files_for_site(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> list:
        """Encuentra archivos JSON para un sitio en el rango de dias.

        start_offset_days: desplazamiento desde hoy hacia atrás para el inicio del período.
        Con start_offset_days=0 el período es [hoy-days+1, hoy].
        Con start_offset_days=days el período es [hoy-2*days+1, hoy-days].
        """
        safe_name = self._get_safe_name(site_name)
        files = []

        # Buscar archivos con patron datado: daily_data_{name}_{YYYY-MM-DD}.json
        today = datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()
        for i in range(days):
            date = today - timedelta(days=start_offset_days + i)
            date_str = date.strftime("%Y-%m-%d")
            path = self.data_dir / f"daily_data_{safe_name}_{date_str}.json"
            if path.exists():
                files.append((date, path))

        # Tambien buscar archivo sin fecha (formato legacy)
        legacy_path = self.data_dir / f"daily_data_{safe_name}.json"
        if legacy_path.exists():
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                period_start = data.get("period_start", "")
                if period_start:
                    dt = datetime.fromisoformat(period_start)
                    file_date = dt.date()
                    # Solo incluir si esta dentro del rango y no duplica
                    days_ago = (today - file_date).days
                    if start_offset_days <= days_ago < start_offset_days + days:
                        if not any(d == file_date for d, _ in files):
                            files.append((file_date, legacy_path))
            except Exception:
                pass

        files.sort(key=lambda x: x[0])
        return files

    def _load_file(self, path: Path) -> dict:
        """Carga un archivo JSON de datos diarios"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error leyendo {path}: {e}")
            return {"dispatches": []}

    def _get_all_dispatches(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> list:
        """Obtiene todos los despachos de un sitio en el rango de dias"""
        files = self._find_files_for_site(site_name, days, start_offset_days)
        all_dispatches = []
        for date, path in files:
            data = self._load_file(path)
            for d in data.get("dispatches", []):
                d["_file_date"] = date
                all_dispatches.append(d)
        return all_dispatches

    def get_kpi_summary(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> dict:
        """KPIs generales: promedio TRT, total despachos, % criticos, TRT maximo"""
        dispatches = self._get_all_dispatches(site_name, days, start_offset_days)

        if not dispatches:
            return {
                "avg_trt_min": 0,
                "total_dispatches": 0,
                "pct_critical": 0,
                "max_trt_min": 0,
            }

        trts = [d["trt_seconds"] for d in dispatches]
        criticos = sum(1 for d in dispatches if d.get("fue_critico", False))

        return {
            "avg_trt_min": round(sum(trts) / len(trts) / 60, 1),
            "total_dispatches": len(dispatches),
            "pct_critical": round(criticos / len(dispatches) * 100, 1) if dispatches else 0,
            "max_trt_min": round(max(trts) / 60, 1),
        }

    def get_daily_trend(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> list:
        """Tendencia diaria: lista de (day_index, avg_trt_min, count, critical_count).

        day_index va de 1 (más antiguo) a days (más reciente), lo que permite
        alinear correctamente ambos períodos al comparar.
        """
        dispatches = self._get_all_dispatches(site_name, days, start_offset_days)

        # Agrupar por fecha del archivo
        by_date = defaultdict(list)
        for d in dispatches:
            by_date[d["_file_date"]].append(d)

        result = []
        today = datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()
        reference_date = today - timedelta(days=start_offset_days)
        for i in range(days - 1, -1, -1):
            date = reference_date - timedelta(days=i)
            day_dispatches = by_date.get(date, [])
            if day_dispatches:
                trts = [x["trt_seconds"] for x in day_dispatches]
                avg = sum(trts) / len(trts) / 60
                count = len(day_dispatches)
                critical = sum(1 for x in day_dispatches if x.get("fue_critico", False))
            else:
                avg = 0
                count = 0
                critical = 0
            result.append((days - i, round(avg, 1), count, critical))

        return result

    def get_aggregated_daily_trend(self, days: int = 7) -> list:
        """Tendencia diaria agregada de todos los sitios.

        Retorna lista de dicts con:
        - date_str: fecha "DD/MM"
        - total_trucks: total despachos del dia
        - total_critical: total criticos
        - avg_trt_min: promedio ponderado de TRT (weighted by dispatch count)
        """
        from .config import ConfigManager
        try:
            cm = ConfigManager()
            sites = cm.config.sites
        except Exception:
            return []

        today = datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()

        # Accumulate per-date
        # date -> {trt_sum_seconds, count, critical}
        by_date = defaultdict(lambda: {'trt_sum': 0, 'count': 0, 'critical': 0})

        for site in sites:
            dispatches = self._get_all_dispatches(site.name, days)
            for d in dispatches:
                file_date = d["_file_date"]
                by_date[file_date]['trt_sum'] += d.get("trt_seconds", 0)
                by_date[file_date]['count'] += 1
                if d.get("fue_critico", False):
                    by_date[file_date]['critical'] += 1

        result = []
        for i in range(days - 1, -1, -1):
            date = today - timedelta(days=i)
            data = by_date.get(date, {'trt_sum': 0, 'count': 0, 'critical': 0})
            avg_trt = round(data['trt_sum'] / data['count'] / 60, 1) if data['count'] > 0 else 0
            result.append({
                'date_str': date.strftime("%d/%m"),
                'total_trucks': data['count'],
                'total_critical': data['critical'],
                'avg_trt_min': avg_trt,
            })

        return result

    def get_hourly_distribution(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> dict:
        """Distribucion por hora de llegada: dict {hora: avg_trt_min}"""
        dispatches = self._get_all_dispatches(site_name, days, start_offset_days)

        by_hour = defaultdict(list)
        for d in dispatches:
            hora_despacho = d.get("hora_despacho", "")
            trt_seconds = d.get("trt_seconds", 0)
            if not hora_despacho:
                continue
            try:
                dt_despacho = datetime.fromisoformat(hora_despacho)
                # Hora de llegada = hora de despacho - TRT
                dt_llegada = dt_despacho - timedelta(seconds=trt_seconds)
                hour = dt_llegada.hour
                by_hour[hour].append(trt_seconds / 60)
            except Exception:
                continue

        result = {}
        for h in range(24):
            values = by_hour.get(h, [])
            result[h] = round(sum(values) / len(values), 1) if values else 0

        return result

    def get_today_summary(self, site_name: str) -> dict:
        """Resumen del dia actual: total despachos, TRT promedio y criticos.
        Lee el archivo daily_data con la fecha de HOY (periodo que termina hoy a las 23:30).
        """
        today = datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()
        date_str = today.strftime("%Y-%m-%d")
        safe_name = self._get_safe_name(site_name)
        path = self.data_dir / f"daily_data_{safe_name}_{date_str}.json"

        if not path.exists():
            return {'total_dispatches': 0, 'avg_trt_min': 0, 'critical': 0}

        data = self._load_file(path)
        dispatches = data.get("dispatches", [])

        if not dispatches:
            return {'total_dispatches': 0, 'avg_trt_min': 0, 'critical': 0}

        trts = [d.get("trt_seconds", 0) for d in dispatches]
        criticos = sum(1 for d in dispatches if d.get("fue_critico", False))

        return {
            'total_dispatches': len(dispatches),
            'avg_trt_min': round(sum(trts) / len(trts) / 60, 1) if trts else 0,
            'critical': criticos,
        }

    def get_today_hourly_data(self, site_name: str) -> dict:
        """Datos por hora del dia actual: {hora: {'count': N, 'avg_trt': M}}.
        Agrupa por hora de despacho (hora_despacho). Retorna las 24 horas.
        """
        today = datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()
        date_str = today.strftime("%Y-%m-%d")
        safe_name = self._get_safe_name(site_name)
        path = self.data_dir / f"daily_data_{safe_name}_{date_str}.json"

        by_hour = defaultdict(list)

        if path.exists():
            data = self._load_file(path)
            for d in data.get("dispatches", []):
                hora_despacho = d.get("hora_despacho", "")
                trt_seconds = d.get("trt_seconds", 0)
                if not hora_despacho:
                    continue
                try:
                    hour = datetime.fromisoformat(hora_despacho).hour
                    by_hour[hour].append(trt_seconds / 60)
                except Exception:
                    continue

        result = {}
        for h in range(24):
            values = by_hour.get(h, [])
            result[h] = {
                'count': len(values),
                'avg_trt': round(sum(values) / len(values), 1) if values else 0,
            }
        return result

    def get_heatmap_data(self, site_name: str, days: int = 30) -> list:
        """Heatmap hora x dia de semana: matrix[hora][dia_semana] con avg TRT en min

        Retorna lista de 24 listas (una por hora), cada una con 7 valores (Lun-Dom).
        """
        dispatches = self._get_all_dispatches(site_name, days)

        # matrix[hora][dia_semana] = lista de TRT values
        matrix = [[[] for _ in range(7)] for _ in range(24)]

        for d in dispatches:
            hora_despacho = d.get("hora_despacho", "")
            trt_seconds = d.get("trt_seconds", 0)
            if not hora_despacho:
                continue
            try:
                dt_despacho = datetime.fromisoformat(hora_despacho)
                dt_llegada = dt_despacho - timedelta(seconds=trt_seconds)
                hour = dt_llegada.hour
                weekday = dt_llegada.weekday()  # 0=Lunes, 6=Domingo
                matrix[hour][weekday].append(trt_seconds / 60)
            except Exception:
                continue

        # Calcular promedios
        result = []
        for h in range(24):
            row = []
            for wd in range(7):
                values = matrix[h][wd]
                row.append(round(sum(values) / len(values), 1) if values else 0)
            result.append(row)

        return result

    def get_heatmap_v2(self, site_name: str, days: int = 30, start_offset_days: int = 0) -> list:
        """Heatmap 7×8: matrix[display_weekday][block] = avg TRT en segundos.

        display_weekday: 0=Domingo, 1=Lunes, ..., 6=Sábado
          (Python weekday() Mon=0..Sun=6 → display: (weekday+1)%7)
        block: 0=00-02h, 1=03-05h, ..., 7=21-23h  (block = arrival_hour // 3)
        Retorna 0.0 para celdas sin datos.
        """
        dispatches = self._get_all_dispatches(site_name, days, start_offset_days)
        matrix = [[[] for _ in range(8)] for _ in range(7)]
        for d in dispatches:
            hora_despacho = d.get("hora_despacho", "")
            trt_seconds = d.get("trt_seconds", 0)
            if not hora_despacho:
                continue
            try:
                dt_despacho = datetime.fromisoformat(hora_despacho)
                dt_llegada = dt_despacho - timedelta(seconds=trt_seconds)
                display_weekday = (dt_llegada.weekday() + 1) % 7  # Sun=0..Sat=6
                block = dt_llegada.hour // 3                       # 0..7
                matrix[display_weekday][block].append(trt_seconds)
            except Exception:
                continue
        return [
            [round(sum(matrix[wd][b]) / len(matrix[wd][b]), 1) if matrix[wd][b] else 0.0
             for b in range(8)]
            for wd in range(7)
        ]
