"""
Monitor de Alertas de Tiempo en Planta v4
Envia mensajes via API HTTP al bot de WhatsApp
Incluye sistema de resumen diario

IMPORTANTE: Para envíos automáticos, se usa WHATSAPP_GROUP_ID (formato: xxxxx@g.us)
en lugar de GROUP_ID (código de invitación). Esto evita timeouts porque el bot
no necesita buscar el grupo por código de invitación.
Si WHATSAPP_GROUP_ID no está configurado, se usa GROUP_ID como fallback.
"""

import time
import re
import requests
import urllib3
import json
import threading
import sys
import types
from bs4 import BeautifulSoup
from datetime import timedelta, datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple, Dict
import platform
import os
from zoneinfo import ZoneInfo
import logging
from logging.handlers import RotatingFileHandler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# CONFIGURACION DE LOGGING ROTATIVO
# =============================================================================

def setup_logging():
    """Configura logging con archivo rotativo"""
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "monitor_alertas.log"
    
    # Formato de log
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler rotativo: 5MB max, mantiene 3 backups
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Handler de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configurar logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# =============================================================================
# CONFIGURACION DE PUERTOS (desde ports.txt - independiente de config.txt)
# =============================================================================

def load_ports_config(ports_file="ports.txt"):
    """
    Carga configuracion de puertos desde ports.txt

    Este archivo es independiente de config.txt y permite cambiar
    los puertos sin afectar la configuracion principal.
    """
    ports_path = Path(__file__).resolve().parent / ports_file

    # Defaults
    ports = {
        "bot_port": 5050,
        "monitor_port": 5051,
        "web_port": 8080
    }

    if not ports_path.exists():
        return ports

    try:
        with open(ports_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip().upper(), value.strip()

                    if key == "BOT_PORT":
                        ports["bot_port"] = int(value)
                    elif key == "MONITOR_PORT":
                        ports["monitor_port"] = int(value)
                    elif key == "WEB_PORT":
                        ports["web_port"] = int(value)
    except Exception as e:
        logger.warning(f"Error leyendo ports.txt: {e}. Usando puertos por defecto.")

    return ports


# Cargar puertos
PORTS = load_ports_config()
BOT_URL = f"http://localhost:{PORTS['bot_port']}"
MONITOR_API_PORT = PORTS["monitor_port"]
TIMEZONE = ZoneInfo("America/Santiago")

logger.info(f"Puertos configurados: Bot={PORTS['bot_port']}, Monitor={PORTS['monitor_port']}")

# =============================================================================
# AUTENTICACION CCCSafe API
# =============================================================================

class AuthManager:
    """Gestiona el JWT de CCCSafe: login inicial y refresh automatico."""

    _AUTH_BASE = "https://www.cccsafe.cl/api/auth"
    # Clave anonima publica de Supabase — estatica, no caduca
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
        self._expires_at: float = 0.0  # epoch seconds
        self._lock = threading.Lock()

    def _do_login(self) -> None:
        r = requests.post(
            f"{self._AUTH_BASE}/sign-in",
            json={"email": self.email, "password": self.password},
            timeout=15,
            verify=False,
        )
        r.raise_for_status()
        self._store(r.json())
        logger.info("AuthManager: login exitoso")

    def _do_refresh(self) -> None:
        r = requests.post(
            f"{self._AUTH_BASE}/refresh",
            json={"refresh_token": self._refresh_token},
            timeout=15,
            verify=False,
        )
        if r.status_code >= 400:
            logger.warning("AuthManager: refresh fallido, re-login...")
            self._do_login()
            return
        self._store(r.json())
        logger.info("AuthManager: token refrescado")

    def _store(self, data: dict) -> None:
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 120  # 2 min de margen

    def get_token(self) -> str:
        """Devuelve access_token vigente, refrescando si esta por expirar."""
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


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class TruckInfo:
    plate: str
    time_in_plant: timedelta
    load_type: str
    empresa: str = ""
    umbral: timedelta = None
    tipo_ingreso: str = ""


@dataclass
class TrafficLight:
    green: int
    yellow: int
    red: int
    
    @property
    def total(self) -> int:
        return self.green + self.yellow + self.red


@dataclass
class CenterStatus:
    name: str
    traffic: TrafficLight
    worst_trucks: List[TruckInfo]
    time_limit: timedelta
    max_overrun: timedelta
    severity: str


@dataclass
class DispatchRecord:
    """Registro de un camion despachado"""
    patente: str
    empresa: str
    tipo_descarga: str
    trt_seconds: float
    hora_despacho: str
    turno: str
    fue_critico: bool = False  # Si supero el umbral


# =============================================================================
# CONFIGURACION DE BANNERS
# =============================================================================

SEVERITY_CONFIG = {
    "INFO": {
        "bg_primary": "#1B5E20", "bg_secondary": "#2E7D32", "bg_card": "#143D17",
        "accent": "#4CAF50", "text_primary": "#FFFFFF", "text_secondary": "#E8F5E9",
        "title": "INFO", "message": "SITUACION NORMAL"
    },
    "ALERTA": {
        "bg_primary": "#E65100", "bg_secondary": "#F57C00", "bg_card": "#7A2B00",
        "accent": "#FF9800", "text_primary": "#FFFFFF", "text_secondary": "#FFF3E0",
        "title": "ALERTA", "message": "FAVOR GESTIONAR ALERTA"
    },
    "CRITICA": {
        "bg_primary": "#B71C1C", "bg_secondary": "#C62828", "bg_card": "#4A0A0A",
        "accent": "#F44336", "text_primary": "#FFFFFF", "text_secondary": "#FFEBEE",
        "title": "ALERTA CRITICA", "message": "FAVOR GESTIONAR ALERTA"
    }
}

LIGHT_COLORS = {
    "green": "#4CAF50", "green_bg": "#0D3D14",
    "yellow": "#FF9800", "yellow_bg": "#3D2800",
    "red": "#F44336", "red_bg": "#3D0A0A"
}

BANNER_SIZE = (1080, 1080)
OVERRUN_GRAVE_MINUTES = 30


# =============================================================================
# SISTEMA DE RESUMEN DIARIO
# =============================================================================

class DailySummaryManager:
    """Gestiona el almacenamiento y calculo de resumenes diarios"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.data: Dict[str, dict] = {}
        self.lock = threading.Lock()
    
    def _get_file_path(self, site_name: str, period_start: datetime = None) -> Path:
        """Obtiene la ruta del archivo para un periodo especifico.
        El archivo se nombra con la fecha de FIN del periodo (no de inicio),
        para que los datos del turno nocturno queden en el dia que corresponde.
        Ej: periodo Feb-17 23:30 → Feb-18 23:30 → archivo 2026-02-18.
        """
        safe_name = site_name.lower().replace(" ", "_")
        if period_start is None:
            period_start, _ = self._get_current_period()
        # Usar fecha del fin del periodo (= inicio + 1 dia) como nombre del archivo
        period_end_date = (period_start + timedelta(days=1)).strftime("%Y-%m-%d")
        return self.data_dir / f"daily_data_{safe_name}_{period_end_date}.json"
    
    def _get_current_period(self) -> Tuple[datetime, datetime]:
        """
        Define el periodo operativo del dia: 23:30 a 23:30 del dia siguiente.
        El resumen automatico de las 8 AM cubre el periodo completo anterior (23:30 a 23:30).
        El resumen manual (@bot resumen) cubre desde las 23:30 hasta la hora actual.
        """
        now = datetime.now(TIMEZONE)
        today_2330 = now.replace(hour=23, minute=30, second=0, microsecond=0)
        
        if now >= today_2330:
            # Despues de las 23:30: nuevo periodo empieza hoy a las 23:30
            start = today_2330
            end = today_2330 + timedelta(days=1)
        else:
            # Antes de las 23:30: periodo empezo ayer a las 23:30
            start = today_2330 - timedelta(days=1)
            end = today_2330
        
        return start, end
    
    def _get_previous_period(self) -> Tuple[datetime, datetime]:
        """
        Obtiene el periodo anterior completo (23:30 a 23:30).
        Este es el periodo que se envia en el resumen automatico de las 8 AM.
        """
        current_start, _ = self._get_current_period()
        prev_start = current_start - timedelta(days=1)
        prev_end = current_start
        return prev_start, prev_end
    
    def _get_period_for_time(self, dt: datetime) -> Tuple[datetime, datetime]:
        """Obtiene el periodo operativo (23:30-23:30) que contiene la hora dada"""
        day_2330 = dt.replace(hour=23, minute=30, second=0, microsecond=0)
        if dt >= day_2330:
            return day_2330, day_2330 + timedelta(days=1)
        else:
            return day_2330 - timedelta(days=1), day_2330

    def _get_turno(self, hora: datetime) -> str:
        h = hora.hour
        m = hora.minute
        tiempo_minutos = h * 60 + m
        
        if 7 * 60 <= tiempo_minutos < 14 * 60 + 30:
            return "A"
        elif 14 * 60 + 30 <= tiempo_minutos < 23 * 60 + 30:
            return "B"
        else:
            return "C"
    
    def _load_data(self, site_name: str, period_start: datetime = None) -> dict:
        """Carga datos para un periodo especifico (por defecto el actual)"""
        if period_start is None:
            period_start, period_end = self._get_current_period()
        else:
            period_end = period_start + timedelta(days=1)
        
        file_path = self._get_file_path(site_name, period_start)
        now = datetime.now(TIMEZONE)
        
        default_data = {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "monitoring_start": now.isoformat(),
            "dispatches": [],
            "created_at": now.isoformat()
        }
        
        if not file_path.exists():
            return default_data
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "monitoring_start" not in data:
                data["monitoring_start"] = data.get("created_at", period_start.isoformat())
            
            return data
        except Exception as e:
            logger.error(f"Error cargando datos de {site_name}: {e}")
            return default_data
    
    def _load_previous_data(self, site_name: str) -> dict:
        """Carga datos del periodo anterior (para resumen de las 8 AM)"""
        prev_start, _ = self._get_previous_period()
        return self._load_data(site_name, prev_start)
    
    def _delete_previous_data(self, site_name: str):
        """Elimina el archivo de datos del periodo anterior"""
        prev_start, _ = self._get_previous_period()
        file_path = self._get_file_path(site_name, prev_start)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Archivo de periodo anterior eliminado: {file_path}")
        except Exception as e:
            logger.error(f"Error eliminando archivo anterior de {site_name}: {e}")

    def _clean_old_files(self, site_name: str, retention_days: int = 60):
        """Elimina archivos más antiguos que retention_days días."""
        safe_name = site_name.lower().replace(" ", "_")
        cutoff = datetime.now(TIMEZONE).date() - timedelta(days=retention_days)
        for f in self.data_dir.glob(f"daily_data_{safe_name}_*.json"):
            try:
                file_date = datetime.strptime(f.stem[-10:], "%Y-%m-%d").date()
                if file_date < cutoff:
                    f.unlink()
                    logger.info(f"[{site_name}] Archivo antiguo eliminado: {f.name}")
            except Exception as e:
                logger.warning(f"No se pudo parsear fecha de {f.name}: {e}")

    def clean_old_files(self, site_name: str, retention_days: int = 60):
        """Público thread-safe: limpia archivos más viejos que retention_days."""
        with self.lock:
            self._clean_old_files(site_name, retention_days)

    def _save_data(self, site_name: str, data: dict):
        period_start = datetime.fromisoformat(data["period_start"])
        file_path = self._get_file_path(site_name, period_start)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando datos de {site_name}: {e}")
    
    def register_dispatch(self, site_name: str, patente: str, empresa: str,
                         tipo_descarga: str, trt: timedelta, fue_critico: bool = False):
        with self.lock:
            now = datetime.now(TIMEZONE)
            # Calcular hora de ingreso REAL basada en TRT (hora_despacho - trt)
            hora_ingreso_real = now - trt

            record = DispatchRecord(
                patente=patente,
                empresa=empresa,
                tipo_descarga=tipo_descarga,
                trt_seconds=trt.total_seconds(),
                hora_despacho=now.isoformat(),
                turno=self._get_turno(hora_ingreso_real),
                fue_critico=fue_critico
            )

            # Determinar a que periodo pertenece segun hora de ingreso
            current_start, _ = self._get_current_period()
            ingreso_period_start, ingreso_period_end = self._get_period_for_time(hora_ingreso_real)

            if ingreso_period_start == current_start:
                # El camion pertenece al periodo actual
                if site_name not in self.data:
                    self.data[site_name] = self._load_data(site_name)
                self.data[site_name]["dispatches"].append(asdict(record))
                self._save_data(site_name, self.data[site_name])
            else:
                # El camion ingreso en un periodo diferente (anterior), registrar alla
                target_data = self._load_data(site_name, ingreso_period_start)
                target_data["dispatches"].append(asdict(record))
                self._save_data(site_name, target_data)
                logger.info(f"[{site_name}] Despacho registrado en periodo {ingreso_period_start.strftime('%d/%m %H:%M')}: {patente}")
    
    def get_general_summary(self, site_name: str) -> dict:
        with self.lock:
            if site_name not in self.data:
                self.data[site_name] = self._load_data(site_name)
            
            data = self.data[site_name]
            dispatches = data["dispatches"]
            
            # monitoring_start es cuando realmente comenzo el monitoreo
            monitoring_start = data.get("monitoring_start", data.get("created_at", data["period_start"]))
            
            if not dispatches:
                return {
                    "site_name": site_name,
                    "period_start": data["period_start"],
                    "period_end": data["period_end"],
                    "monitoring_start": monitoring_start,
                    "first_dispatch": None,
                    "last_dispatch": None,
                    "total_trucks": 0,
                    "total_criticos": 0,
                    "avg_trt_seconds": 0,
                    "has_data": False
                }
            
            total = len(dispatches)
            total_criticos = sum(1 for d in dispatches if d.get("fue_critico", False))
            avg_trt = sum(d["trt_seconds"] for d in dispatches) / total
            
            # Obtener primer y ultimo despacho real
            dispatch_times = [d["hora_despacho"] for d in dispatches]
            first_dispatch = min(dispatch_times)
            last_dispatch = max(dispatch_times)
            
            return {
                "site_name": site_name,
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "monitoring_start": monitoring_start,
                "first_dispatch": first_dispatch,
                "last_dispatch": last_dispatch,
                "total_trucks": total,
                "total_criticos": total_criticos,
                "avg_trt_seconds": avg_trt,
                "has_data": True
            }
    
    def get_full_summary(self, site_name: str) -> dict:
        with self.lock:
            if site_name not in self.data:
                self.data[site_name] = self._load_data(site_name)
            
            data = self.data[site_name]
            dispatches = data["dispatches"]
            
            # monitoring_start es cuando realmente comenzo el monitoreo
            monitoring_start = data.get("monitoring_start", data.get("created_at", data["period_start"]))
            
            result = {
                "site_name": site_name,
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "monitoring_start": monitoring_start,
                "first_dispatch": None,
                "last_dispatch": None,
                "general": {
                    "total_trucks": 0, 
                    "total_criticos": 0,
                    "avg_trt_seconds": 0
                },
                "turnos": {
                    "A": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0},
                    "B": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0},
                    "C": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0}
                },
                "has_data": len(dispatches) > 0
            }
            
            if not dispatches:
                return result
            
            # Obtener primer y ultimo despacho real
            dispatch_times = [d["hora_despacho"] for d in dispatches]
            result["first_dispatch"] = min(dispatch_times)
            result["last_dispatch"] = max(dispatch_times)
            
            # Estadisticas generales
            result["general"]["total_trucks"] = len(dispatches)
            result["general"]["total_criticos"] = sum(1 for d in dispatches if d.get("fue_critico", False))
            result["general"]["avg_trt_seconds"] = sum(d["trt_seconds"] for d in dispatches) / len(dispatches)
            
            # Estadisticas por turno
            for turno in ["A", "B", "C"]:
                turno_dispatches = [d for d in dispatches if d["turno"] == turno]
                if turno_dispatches:
                    trts = [d["trt_seconds"] for d in turno_dispatches]
                    criticos = sum(1 for d in turno_dispatches if d.get("fue_critico", False))
                    result["turnos"][turno] = {
                        "total": len(turno_dispatches),
                        "criticos": criticos,
                        "avg_trt": sum(trts) / len(trts),
                        "min_trt": min(trts),
                        "max_trt": max(trts)
                    }
            
            return result
    
    def reset_period(self, site_name: str):
        with self.lock:
            period_start, period_end = self._get_current_period()
            now = datetime.now(TIMEZONE)
            self.data[site_name] = {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "monitoring_start": now.isoformat(),
                "dispatches": [],
                "created_at": now.isoformat()
            }
            self._save_data(site_name, self.data[site_name])
    
    def check_and_reset_if_needed(self, site_name: str):
        with self.lock:
            if site_name not in self.data:
                self.data[site_name] = self._load_data(site_name)
            else:
                period_start, _ = self._get_current_period()
                stored_start = datetime.fromisoformat(self.data[site_name]["period_start"])
                
                if stored_start.date() != period_start.date() or stored_start.hour != period_start.hour:
                    self.data[site_name] = self._load_data(site_name)
    
    def get_previous_full_summary(self, site_name: str) -> dict:
        """
        Obtiene el resumen completo del periodo anterior (23:30 a 23:30).
        Se usa para el resumen automatico de las 8 AM.
        """
        with self.lock:
            data = self._load_previous_data(site_name)
            dispatches = data["dispatches"]
            
            monitoring_start = data.get("monitoring_start", data.get("created_at", data["period_start"]))
            
            result = {
                "site_name": site_name,
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "monitoring_start": monitoring_start,
                "first_dispatch": None,
                "last_dispatch": None,
                "general": {
                    "total_trucks": 0, 
                    "total_criticos": 0,
                    "avg_trt_seconds": 0
                },
                "turnos": {
                    "A": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0},
                    "B": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0},
                    "C": {"total": 0, "criticos": 0, "avg_trt": 0, "min_trt": 0, "max_trt": 0}
                },
                "has_data": len(dispatches) > 0
            }
            
            if not dispatches:
                return result
            
            dispatch_times = [d["hora_despacho"] for d in dispatches]
            result["first_dispatch"] = min(dispatch_times)
            result["last_dispatch"] = max(dispatch_times)
            
            result["general"]["total_trucks"] = len(dispatches)
            result["general"]["total_criticos"] = sum(1 for d in dispatches if d.get("fue_critico", False))
            result["general"]["avg_trt_seconds"] = sum(d["trt_seconds"] for d in dispatches) / len(dispatches)
            
            for turno in ["A", "B", "C"]:
                turno_dispatches = [d for d in dispatches if d["turno"] == turno]
                if turno_dispatches:
                    trts = [d["trt_seconds"] for d in turno_dispatches]
                    criticos = sum(1 for d in turno_dispatches if d.get("fue_critico", False))
                    result["turnos"][turno] = {
                        "total": len(turno_dispatches),
                        "criticos": criticos,
                        "avg_trt": sum(trts) / len(trts),
                        "min_trt": min(trts),
                        "max_trt": max(trts)
                    }
            
            return result
    
    def delete_previous_period(self, site_name: str):
        """Elimina los datos del periodo anterior despues de enviar el resumen"""
        with self.lock:
            self._delete_previous_data(site_name)


def format_seconds_to_hhmmss(seconds: float) -> str:
    total = int(seconds)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def format_general_summary_message(site_name: str, summary: dict, is_manual: bool = True) -> str:
    """
    Formatea el mensaje de resumen general.
    is_manual: True si se pidio con @bot resumen, False si es automatico de las 8 AM
    """
    now = datetime.now(TIMEZONE)
    period_start = datetime.fromisoformat(summary["period_start"])
    period_end = datetime.fromisoformat(summary["period_end"])
    monitoring_start = datetime.fromisoformat(summary.get("monitoring_start", summary["period_start"]))
    
    # Determinar el inicio efectivo de los datos
    # Es el maximo entre period_start (23:30) y monitoring_start (cuando inicio el script)
    effective_start = max(period_start, monitoring_start)
    
    if not summary["has_data"]:
        if is_manual:
            date_range = f"{effective_start.strftime('%d/%m/%Y %H:%M')} - {now.strftime('%H:%M')}"
        else:
            date_range = f"{effective_start.strftime('%d/%m/%Y %H:%M')} - {period_end.strftime('%d/%m/%Y %H:%M')}"
        return (
            f"*RESUMEN DEL DIA*\n"
            f"_{site_name}_\n"
            f"{date_range}\n\n"
            f"Sin despachos registrados aun"
        )
    
    if is_manual:
        # Para solicitud manual: desde inicio efectivo hasta ahora
        date_range = f"{effective_start.strftime('%d/%m/%Y %H:%M')} - {now.strftime('%H:%M')}"
    else:
        # Para resumen automatico: desde inicio efectivo hasta fin del periodo
        date_range = f"{effective_start.strftime('%d/%m/%Y %H:%M')} - {period_end.strftime('%d/%m/%Y %H:%M')}"
    
    avg_trt = format_seconds_to_hhmmss(summary["avg_trt_seconds"])
    total_trucks = summary['total_trucks']
    total_criticos = summary.get('total_criticos', 0)
    
    return (
        f"*RESUMEN DEL DIA*\n"
        f"_{site_name}_\n"
        f"{date_range}\n\n"
        f"Camiones despachados: *{total_trucks}*\n"
        f"Camiones criticos: *{total_criticos}*\n"
        f"TRT Promedio: *{avg_trt}*"
    )


def format_full_summary_message(site_name: str, summary: dict, is_manual: bool = False) -> str:
    """
    Formatea el mensaje de resumen completo.
    is_manual: True si se pidio con @bot resumen (hasta hora actual),
               False si es automatico de las 8 AM (periodo completo)
    """
    now = datetime.now(TIMEZONE)
    period_start = datetime.fromisoformat(summary["period_start"])
    period_end = datetime.fromisoformat(summary["period_end"])

    # monitoring_start es cuando realmente comenzo el monitoreo en este periodo
    monitoring_start = datetime.fromisoformat(summary.get("monitoring_start", summary["period_start"]))

    # El inicio real es el maximo entre period_start (23:30) y monitoring_start
    # Si el script se inicio despues de las 23:30, usamos monitoring_start
    # Si lleva mas de un dia corriendo, usamos period_start (23:30)
    display_start = max(period_start, monitoring_start)

    # Para resumen manual: hasta la hora actual
    # Para resumen automatico: hasta el fin del periodo
    if is_manual:
        display_end = now
    else:
        display_end = period_end

    # Formatear fechas - mostrar la fecha actual como referencia principal
    if is_manual:
        # Para resumen manual: "16/01/2026" con rango de horas debajo
        fecha_principal = now.strftime('%d/%m/%Y')
        # Mostrar hora de inicio y fin del periodo de datos
        fecha_rango = f"{display_start.strftime('%d/%m %H:%M')} - {display_end.strftime('%H:%M')}"
    else:
        # Para resumen automatico: mostrar rango completo
        fecha_principal = display_end.strftime('%d/%m/%Y')
        fecha_rango = f"{display_start.strftime('%d/%m %H:%M')} - {display_end.strftime('%d/%m %H:%M')}"

    if not summary["has_data"]:
        return (
            f"*RESUMEN OPERACION DIARIA*\n"
            f"_{site_name}_\n"
            f"{fecha_principal}\n"
            f"{fecha_rango}\n\n"
            f"Sin despachos registrados en este periodo"
        )

    # Calcular horas de monitoreo real
    hours_diff = (display_end - display_start).total_seconds() / 3600

    # Construir mensaje
    lines = [
        f"*RESUMEN OPERACION DIARIA*",
        f"_{site_name}_",
        f"{fecha_principal}",
        f"{fecha_rango}",
    ]

    # Mostrar horas de datos capturados si no es un periodo completo de 24h
    if hours_diff < 23.5:
        hours_int = int(hours_diff)
        mins_int = int((hours_diff - hours_int) * 60)
        if mins_int > 0:
            lines.append(f"_(Datos de {hours_int}h {mins_int}m)_")
        else:
            lines.append(f"_(Datos de {hours_int} horas)_")
    
    total_trucks = summary['general']['total_trucks']
    total_criticos = summary['general'].get('total_criticos', 0)
    avg_trt = format_seconds_to_hhmmss(summary['general']['avg_trt_seconds'])
    
    lines.extend([
        "",
        "*GENERAL*",
        f"Camiones: {total_trucks}",
        f"Criticos: {total_criticos}",
        f"TRT Promedio: {avg_trt}",
        "",
        "*POR TURNO*",
    ])
    
    turno_config = {
        "A": ("07:00", "14:30"),
        "B": ("14:30", "23:30"),
        "C": ("23:30", "07:00")
    }
    
    for turno, (inicio, fin) in turno_config.items():
        turno_data = summary["turnos"][turno]
        lines.append("")
        lines.append(f"*Turno {turno}* ({inicio} a {fin})")
        
        if turno_data["total"] > 0:
            criticos_turno = turno_data.get('criticos', 0)
            lines.append(f"  Camiones: {turno_data['total']} ({criticos_turno} crit.)")
            lines.append(f"  TRT Prom: {format_seconds_to_hhmmss(turno_data['avg_trt'])}")
            lines.append(f"  TRT Min: {format_seconds_to_hhmmss(turno_data['min_trt'])}")
            lines.append(f"  TRT Max: {format_seconds_to_hhmmss(turno_data['max_trt'])}")
        else:
            lines.append("  Sin despachos")
    
    return "\n".join(lines)


# =============================================================================
# CARGA DE CONFIGURACION
# =============================================================================

def load_config(config_file="config.txt"):
    """
    Carga la configuracion desde el archivo.
    Retorna None si el archivo no existe (en lugar de lanzar error).
    """
    config_path = Path(config_file)
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error leyendo config: {e}")
        return None

    config = {
        "base_url": None,
        "api_email": "",
        "api_password": "",
        "poll_seconds": None,
        "realert_minutes": None,
        "sites": []
    }
    current_site = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if current_site and "name" in current_site:
                config["sites"].append(current_site)
                current_site = {}
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()

            if key == "BASE_URL": config["base_url"] = value
            elif key == "API_EMAIL": config["api_email"] = value
            elif key == "API_PASSWORD": config["api_password"] = value
            elif key == "POLL_SECONDS": config["poll_seconds"] = int(value)
            elif key == "REALERT_MINUTES": config["realert_minutes"] = int(value)
            elif key == "SITE_NAME": current_site["name"] = value
            elif key == "GROUP_ID": current_site["group_id"] = value
            elif key == "WHATSAPP_GROUP_ID": current_site["whatsapp_group_id"] = value
            elif key == "CENTRO_ID": current_site["centro_id"] = int(value)
            elif key == "UMBRAL_MINUTES": current_site["umbral_minutes"] = int(value)
            elif key == "UMBRAL_MINUTES_LATERAL": current_site["umbral_minutes_lateral"] = int(value)
            elif key == "UMBRAL_MINUTES_TRASERA": current_site["umbral_minutes_trasera"] = int(value)
            elif key == "UMBRAL_MINUTES_INTERNA": current_site["umbral_minutes_interna"] = int(value)
            elif key == "DB_NAME": current_site["db_name"] = value
            elif key == "OP_CODE": current_site["op_code"] = value
            elif key == "CD_CODE": current_site["cd_code"] = value
            elif key == "REFERER_ID": current_site["referer_id"] = value

    if current_site and "name" in current_site:
        config["sites"].append(current_site)

    return config


# Cargar configuracion (si existe)
logger.info("Inicializando monitor...")
BASE_DIR = Path(__file__).resolve().parent
CONFIG = load_config(str(BASE_DIR / "config.txt"))

# Variables globales que se inicializaran cuando haya config
BASE_URL = None
POLL_SECONDS = None
REALERT_EVERY = None
SUMMARY_MANAGER = None

if CONFIG:
    BASE_URL = CONFIG["base_url"]
    POLL_SECONDS = CONFIG["poll_seconds"]
    REALERT_EVERY = timedelta(minutes=CONFIG["realert_minutes"])
    SUMMARY_MANAGER = DailySummaryManager(BASE_DIR / "daily_data")

    logger.info(f"URL Base: {BASE_URL}")
    logger.info(f"Intervalo: {POLL_SECONDS}s")
    logger.info(f"Re-alerta cada: {CONFIG['realert_minutes']} min")
    logger.info(f"Sitios: {len(CONFIG['sites'])}")
else:
    logger.warning("No se encontro archivo de configuracion. Esperando...")

# Instancia global de AuthManager para API CCCSafe (None si no hay credenciales)
auth = None
if CONFIG and CONFIG.get("api_email") and CONFIG.get("api_password"):
    auth = AuthManager(CONFIG["api_email"], CONFIG["api_password"])
    logger.info("Modo API CCCSafe activo para sitios con CENTRO_ID")


# =============================================================================
# HTTP SESSION
# =============================================================================

session = requests.Session()
session.headers.update({
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
})


# =============================================================================
# FUNCIONES DE PARSING
# =============================================================================

TIME_RE = re.compile(r"(\d+)\s*d[ia]as?\s*(\d{2}):(\d{2}):(\d{2})", re.IGNORECASE)


def get_tipo_descarga(empresa: str) -> str:
    if not empresa:
        return "LATERAL"
    empresa_upper = empresa.upper().strip()
    if "ROMANI" in empresa_upper or "LOGISTICA DEL NORTE" in empresa_upper:
        return "INTERNA"
    if "INTERANDINOS" in empresa_upper:
        return "TRASERA"
    return "LATERAL"


def get_tipo_descarga_for_site(empresa: str, umbral_trasera: int = 0, umbral_interna: int = 0) -> str:
    """Como get_tipo_descarga pero respeta la configuracion del centro.
    Si el centro no tiene configurado un tipo de carga (umbral=0), el camion es tratado como LATERAL."""
    tipo = get_tipo_descarga(empresa)
    if tipo == "INTERNA" and not umbral_interna:
        return "LATERAL"
    if tipo == "TRASERA" and not umbral_trasera:
        return "LATERAL"
    return tipo


def get_umbral_para_camion(site: dict, empresa: str) -> timedelta:
    if "umbral_minutes" in site:
        return timedelta(minutes=site["umbral_minutes"])
    tipo = get_tipo_descarga_for_site(
        empresa,
        site.get("umbral_minutes_trasera", 0),
        site.get("umbral_minutes_interna", 0),
    )
    if tipo == "INTERNA":
        return timedelta(minutes=site.get("umbral_minutes_interna", site["umbral_minutes_lateral"]))
    elif tipo == "TRASERA":
        return timedelta(minutes=site["umbral_minutes_trasera"])
    return timedelta(minutes=site["umbral_minutes_lateral"])


def get_umbral_general(site: dict) -> timedelta:
    if "umbral_minutes" in site:
        return timedelta(minutes=site["umbral_minutes"])
    return timedelta(minutes=max(
        site.get("umbral_minutes_lateral", 0),
        site.get("umbral_minutes_trasera", 0),
        site.get("umbral_minutes_interna", 0)
    ))


def parse_tiempo_en_planta(text: str) -> timedelta:
    m = TIME_RE.search(" ".join(text.split()))
    if not m:
        raise ValueError(f"No pude parsear: {text!r}")
    return timedelta(days=int(m.group(1)), hours=int(m.group(2)), 
                     minutes=int(m.group(3)), seconds=int(m.group(4)))


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


# =============================================================================
# FUENTE DE DATOS: API REST CCCSafe v2
# =============================================================================

_API_DATA_URL = "https://www.cccsafe.cl/api/supabase/rest/v1/movimientos"


def _ventana_utc() -> Tuple[str, str]:
    """
    Retorna (inicio, fin) ISO UTC para el dia operativo actual.
    Dia operativo: 04:00 UTC hoy -> 03:59:59 UTC manana.
    """
    now_utc = datetime.now(timezone.utc)
    start = now_utc.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_utc.hour < 4:
        start -= timedelta(days=1)
    end = start + timedelta(hours=23, minutes=59, seconds=59, microseconds=999000)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
    )


def fetch_camiones_en_planta(site: dict, auth: AuthManager) -> list:
    """
    Consulta la API REST de movimientos y devuelve lista de dicts con las
    mismas claves que usaba parse_table_rows, para compatibilidad downstream.

    Claves devueltas: "Patente", "Empresa", "Tipo de Ingreso", "Tiempo en Planta"
    """
    inicio, fin = _ventana_utc()
    params = [
        ("select", "id,placa,movement_type,fecha_evento,"
                   "ac_travel_id,conductor_empresa"),
        ("fecha_evento", f"gte.{inicio}"),
        ("fecha_evento", f"lte.{fin}"),
        ("order", "fecha_evento.asc"),
        ("status", "eq.acarreo"),
        ("centro_id", f"eq.{site['centro_id']}"),
    ]
    r = requests.get(_API_DATA_URL, params=params, headers=auth.headers(), timeout=15, verify=False)
    r.raise_for_status()
    eventos: list = r.json()

    # Agrupar por patente — fuente de verdad para saber si el camion esta en planta.
    # Usar ac_travel_id causaba falsos positivos cuando el evento OUT tenia
    # un travel_id distinto (o null) al evento IN del mismo camion.
    por_placa: Dict[str, list] = {}
    for ev in eventos:
        por_placa.setdefault(ev["placa"], []).append(ev)

    ahora_utc = datetime.now(timezone.utc)
    rows = []
    for placa, evs in por_placa.items():
        # Los eventos ya vienen ordenados asc; el ultimo es el mas reciente
        ultimo = evs[-1]
        mt = (ultimo.get("movement_type") or "").upper()
        if mt != "IN":
            continue  # ultimo movimiento fue salida -> no esta en planta

        fecha_ev = datetime.fromisoformat(ultimo["fecha_evento"])
        tiempo: timedelta = ahora_utc - fecha_ev

        total_s = int(tiempo.total_seconds())
        dias, rem = divmod(total_s, 86400)
        horas, rem = divmod(rem, 3600)
        mins, segs = divmod(rem, 60)
        tiempo_str = f"{dias} dias {horas:02d}:{mins:02d}:{segs:02d}"

        rows.append({
            "Patente":          placa,
            "Empresa":          ultimo.get("conductor_empresa") or "",
            "Tipo de Ingreso":  ultimo.get("conductor_empresa") or "",
            "Tiempo en Planta": tiempo_str,
        })

    return rows


# =============================================================================
# FUENTE DE DATOS: HTML scraping (servidor interno legacy)
# =============================================================================

def fetch_html_tabla(site: dict) -> str:
    url = f"{BASE_URL}/ces/home/inicio/"
    referer = f"{BASE_URL}/ces/home/registro/{site['referer_id']}"
    post_data = {"db": site["db_name"], "op": site["op_code"], "cd": site["cd_code"]}
    r = session.post(url, data=post_data, headers={"Referer": referer}, timeout=10)
    r.raise_for_status()
    return r.text


def parse_table_rows(html: str):
    """Parsea la tabla de camiones en planta.

    Aplana todos los <td> de la pagina y los divide en chunks del
    tamaño correcto (approach del original). El numero de columnas
    se detecta contando los <th> del header, que son seguros porque
    no se mezclan con los datos.

    Formatos conocidos:
    - 9 cols (estandar): N°, Patente, Empresa, Arribo, Tipo, Tiempo, Control, Destino, Salida
    - 10 cols (Cervecera): N°, Patente, N°viaje, Empresa, Arribo, Tipo, Tiempo, Control, Destino, Salida
    """
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
        return []

    usable = (len(all_tds) // ncols) * ncols
    rows = []

    for i in range(0, usable, ncols):
        chunk = all_tds[i:i + ncols]
        if not any(chunk):
            continue

        plate = chunk[col_plate]
        if not plate:
            continue

        rows.append({
            "Patente": plate,
            "Empresa": chunk[col_company],
            "Fecha de Arribo": chunk[col_arrival],
            "Tipo de Ingreso": chunk[col_entry],
            "Tiempo en Planta": chunk[col_time],
        })

    return rows


def fmt_td(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem = total // 86400, total % 86400
    hh, mm, ss = rem // 3600, (rem % 3600) // 60, rem % 60
    return f"{days}d {hh:02}:{mm:02}:{ss:02}" if days > 0 else f"{hh:02}:{mm:02}:{ss:02}"


def classify_truck(tiempo: timedelta, umbral: timedelta) -> str:
    umbral_80 = umbral * 0.8
    umbral_130 = umbral * 1.3
    if tiempo < umbral_80:
        return "green"
    elif tiempo < umbral_130:
        return "yellow"
    return "red"


# =============================================================================
# CLASIFICACION DE CENTRO
# =============================================================================

def calculate_center_severity(n_total, n_green, n_yellow, n_red, max_overrun, max_tiempo, umbral) -> str:
    if n_total == 0:
        return "INFO"
    
    overrun_grave = timedelta(minutes=OVERRUN_GRAVE_MINUTES)
    ratio_rojos = n_red / n_total if n_total > 0 else 0
    ratio_naranjos = n_yellow / n_total if n_total > 0 else 0
    umbral_80 = umbral * 0.8
    
    if n_red >= 2:
        return "CRITICA"
    if max_overrun >= overrun_grave:
        return "CRITICA"
    if ratio_rojos >= 0.20:
        return "CRITICA"
    
    if n_red == 0 and (n_yellow >= 2 or ratio_naranjos >= 0.30):
        return "ALERTA"
    
    if n_red == 0 and n_yellow <= 1 and max_tiempo < umbral_80:
        return "INFO"
    
    return "ALERTA"


def analyze_center_status(site: dict, rows: list) -> CenterStatus:
    site_name = site["name"]
    umbral_general = get_umbral_general(site)
    
    n_green, n_yellow, n_red = 0, 0, 0
    max_overrun, max_tiempo = timedelta(0), timedelta(0)
    all_trucks = []
    
    for row in rows:
        patente = (row.get("Patente") or "").strip()
        t_str = (row.get("Tiempo en Planta") or "").strip()
        if not patente or not t_str:
            continue
        try:
            tiempo = parse_tiempo_en_planta(t_str)
        except:
            continue
        
        empresa = (row.get("Empresa") or "").strip()
        umbral = get_umbral_para_camion(site, empresa)
        tipo_descarga = get_tipo_descarga_for_site(
            empresa,
            site.get("umbral_minutes_trasera", 0),
            site.get("umbral_minutes_interna", 0),
        )
        tipo_ingreso = (row.get("Tipo de Ingreso") or "").strip()
        
        if tiempo > max_tiempo:
            max_tiempo = tiempo
        
        status = classify_truck(tiempo, umbral)
        if status == "green":
            n_green += 1
        elif status == "yellow":
            n_yellow += 1
            overrun = tiempo - umbral
            if overrun > max_overrun:
                max_overrun = overrun
        else:
            n_red += 1
            overrun = tiempo - umbral
            if overrun > max_overrun:
                max_overrun = overrun
        
        all_trucks.append(TruckInfo(
            plate=patente, time_in_plant=tiempo, load_type=tipo_descarga,
            empresa=empresa, umbral=umbral, tipo_ingreso=tipo_ingreso
        ))
    
    all_trucks.sort(key=lambda t: t.time_in_plant, reverse=True)
    n_total = n_green + n_yellow + n_red
    severity = calculate_center_severity(
        n_total, n_green, n_yellow, n_red, max_overrun, max_tiempo, umbral_general
    )
    
    return CenterStatus(
        name=site_name, traffic=TrafficLight(n_green, n_yellow, n_red),
        worst_trucks=all_trucks, time_limit=umbral_general,
        max_overrun=max_overrun, severity=severity
    )


# =============================================================================
# FUNCIONES AUXILIARES PARA BANNERS
# =============================================================================

def format_timedelta_banner(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_delta_diff(td: timedelta) -> Optional[str]:
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"+{hours:02d}:{minutes:02d}:{seconds:02d}"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_candidates = []
    
    if platform.system() == "Windows":
        font_candidates = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    else:
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def draw_rounded_rect(draw: ImageDraw.Draw, xy: Tuple[int, int, int, int], radius: int, fill: str) -> None:
    x1, y1, x2, y2 = xy
    fill_rgb = hex_to_rgb(fill)
    
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill_rgb)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill_rgb)
    draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill_rgb)
    draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill_rgb)
    draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill_rgb)
    draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill_rgb)


def draw_text_centered(draw: ImageDraw.Draw, text: str, y: int, font: ImageFont.FreeTypeFont, 
                       fill: str, width: int = BANNER_SIZE[0]) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    draw.text((x, y), text, font=font, fill=hex_to_rgb(fill))
    return text_width


def draw_traffic_light_labeled(draw: ImageDraw.Draw, traffic: TrafficLight, center_x: int, y: int) -> None:
    """Dibuja el semaforo con conteos y etiquetas explicativas (ORIGINAL)"""
    light_width = 300
    light_height = 110
    spacing = 25
    total_width = 3 * light_width + 2 * spacing
    start_x = center_x - total_width // 2
    
    lights = [
        (traffic.green, "A TIEMPO", LIGHT_COLORS["green"], LIGHT_COLORS["green_bg"]),
        (traffic.yellow, "ATRASADO", LIGHT_COLORS["yellow"], LIGHT_COLORS["yellow_bg"]),
        (traffic.red, "CRITICO", LIGHT_COLORS["red"], LIGHT_COLORS["red_bg"]),
    ]
    
    for i, (count, label, color, bg_color) in enumerate(lights):
        x = start_x + i * (light_width + spacing)
        
        draw_rounded_rect(draw, (x, y, x + light_width, y + light_height), 12, bg_color)
        
        border_width = 3
        draw.rounded_rectangle(
            [x, y, x + light_width, y + light_height],
            radius=12,
            outline=hex_to_rgb(color),
            width=border_width
        )
        
        font_label = get_font(22, bold=True)
        label_bbox = draw.textbbox((0, 0), label, font=font_label)
        label_width = label_bbox[2] - label_bbox[0]
        draw.text(
            (x + (light_width - label_width) // 2, y + 10),
            label,
            font=font_label,
            fill=hex_to_rgb("#FFFFFF")
        )
        
        circle_radius = 22
        circle_x = x + 55
        circle_y = y + 72
        draw.ellipse(
            [circle_x - circle_radius, circle_y - circle_radius,
             circle_x + circle_radius, circle_y + circle_radius],
            fill=hex_to_rgb(color)
        )
        
        font_num = get_font(48, bold=True)
        num_text = str(count)
        bbox = draw.textbbox((0, 0), num_text, font=font_num)
        num_width = bbox[2] - bbox[0]
        draw.text(
            (x + light_width - 70 - num_width // 2, y + 48),
            num_text,
            font=font_num,
            fill=hex_to_rgb("#FFFFFF")
        )
        
        font_small = get_font(18, bold=False)
        cam_text = "camion" if count == 1 else "camiones"
        cam_bbox = draw.textbbox((0, 0), cam_text, font=font_small)
        cam_width = cam_bbox[2] - cam_bbox[0]
        draw.text(
            (x + light_width - 70 - cam_width // 2, y + 88),
            cam_text,
            font=font_small,
            fill=hex_to_rgb("#DDDDDD")
        )


# =============================================================================
# GENERACION DE BANNER (ORIGINAL)
# =============================================================================

def make_banner_png(status: CenterStatus) -> str:
    """Genera banner PNG de alerta operativa (DISEÑO ORIGINAL)"""
    config = SEVERITY_CONFIG[status.severity]
    
    img = Image.new('RGB', BANNER_SIZE, hex_to_rgb(config["bg_primary"]))
    draw = ImageDraw.Draw(img)
    
    width, height = BANNER_SIZE
    center_x = width // 2
    
    # HEADER
    header_height = 160
    draw.rectangle([0, 0, width, header_height], fill=hex_to_rgb(config["bg_secondary"]))
    draw.rectangle([0, header_height - 6, width, header_height], fill=hex_to_rgb(config["accent"]))
    
    font_title = get_font(64, bold=True)
    draw_text_centered(draw, config["title"], 45, font_title, config["text_primary"])
    
    # NOMBRE DEL CENTRO
    font_site = get_font(52, bold=True)
    draw_text_centered(draw, status.name.upper(), 190, font_site, config["text_primary"])
    
    line_y = 260
    draw.rectangle([center_x - 200, line_y, center_x + 200, line_y + 3], fill=hex_to_rgb(config["accent"]))
    
    # TOTAL EN PLANTA (CIRCULO GRANDE)
    circle_y = 370
    circle_radius = 95
    
    draw.ellipse(
        [center_x - circle_radius, circle_y - circle_radius,
         center_x + circle_radius, circle_y + circle_radius],
        fill=hex_to_rgb(config["accent"])
    )
    
    font_number = get_font(100, bold=True)
    num_text = str(status.traffic.total)
    bbox = draw.textbbox((0, 0), num_text, font=font_number)
    num_width = bbox[2] - bbox[0]
    num_height = bbox[3] - bbox[1]
    draw.text(
        (center_x - num_width // 2, circle_y - num_height // 2 - 15),
        num_text,
        font=font_number,
        fill=hex_to_rgb("#5C0000")
    )
    
    font_label = get_font(38, bold=True)
    draw_text_centered(draw, "CAMIONES EN PLANTA", 485, font_label, config["text_primary"])
    
    # SEMAFORO CON ETIQUETAS (ORIGINAL)
    traffic_y = 545
    draw_traffic_light_labeled(draw, status.traffic, center_x, traffic_y)
    
    # CAMION CON MAYOR TIEMPO EN PLANTA
    worst_y = 680
    worst_bg_height = 175
    
    if status.worst_trucks:
        worst_truck = status.worst_trucks[0]
        
        draw_rounded_rect(
            draw,
            (50, worst_y, width - 50, worst_y + worst_bg_height),
            15,
            config["bg_card"]
        )
        
        draw.rounded_rectangle(
            [50, worst_y, width - 50, worst_y + worst_bg_height],
            radius=15,
            outline=hex_to_rgb(config["accent"]),
            width=3
        )
        
        font_worst_label = get_font(26, bold=True)
        draw_text_centered(draw, "CAMION CON MAYOR TIEMPO EN PLANTA", worst_y + 12, font_worst_label, config["text_secondary"])
        
        col_left_x = 70
        col_left_center_x = 280
        col_right_center_x = 530
        col_right_x = 820
        content_y = worst_y + 55
        
        font_small_label = get_font(18, bold=False)
        font_value = get_font(32, bold=True)
        font_value_small = get_font(24, bold=True)
        
        # PATENTE
        draw.text((col_left_x, content_y), "PATENTE", font=font_small_label, fill=hex_to_rgb(config["text_secondary"]))
        
        plate_text = worst_truck.plate.upper()
        bbox = draw.textbbox((0, 0), plate_text, font=font_value)
        plate_width = bbox[2] - bbox[0]
        
        draw_rounded_rect(
            draw,
            (col_left_x - 10, content_y + 26, col_left_x + plate_width + 20, content_y + 68),
            8,
            config["accent"]
        )
        draw.text((col_left_x, content_y + 30), plate_text, font=font_value, fill=hex_to_rgb("#FFFFFF"))
        
        # TIPO CARGA
        draw.text((col_left_center_x, content_y), "TIPO CARGA", font=font_small_label, fill=hex_to_rgb(config["text_secondary"]))
        load_text = worst_truck.load_type.upper()
        draw.text((col_left_center_x, content_y + 30), load_text, font=font_value, fill=hex_to_rgb(config["text_primary"]))
        
        # TIPO INGRESO
        draw.text((col_right_center_x, content_y), "TIPO INGRESO", font=font_small_label, fill=hex_to_rgb(config["text_secondary"]))
        ingreso_text = worst_truck.tipo_ingreso.upper() if worst_truck.tipo_ingreso else "N/A"
        
        max_width = 250
        current_font = font_value_small
        bbox = draw.textbbox((0, 0), ingreso_text, font=current_font)
        text_width = bbox[2] - bbox[0]
        
        if text_width > max_width:
            while text_width > max_width and len(ingreso_text) > 3:
                ingreso_text = ingreso_text[:-4] + "..."
                bbox = draw.textbbox((0, 0), ingreso_text, font=current_font)
                text_width = bbox[2] - bbox[0]
        
        draw.text((col_right_center_x, content_y + 30), ingreso_text, font=current_font, fill=hex_to_rgb(config["text_primary"]))
        
        # TIEMPO
        draw.text((col_right_x, content_y), "TIEMPO", font=font_small_label, fill=hex_to_rgb(config["text_secondary"]))
        time_str = format_timedelta_banner(worst_truck.time_in_plant)
        draw.text((col_right_x, content_y + 30), time_str, font=font_value, fill=hex_to_rgb(config["text_primary"]))
        
        # ESTADO (DENTRO DEL LIMITE o EXCESO)
        umbral_camion = worst_truck.umbral if worst_truck.umbral else status.time_limit
        delta = worst_truck.time_in_plant - umbral_camion
        delta_str = format_delta_diff(delta)
        
        if delta_str:
            font_exceso = get_font(28, bold=True)
            exceso_text = f"EXCESO: {delta_str}"
            draw_text_centered(draw, exceso_text, content_y + 85, font_exceso, LIGHT_COLORS["red"])
        else:
            font_ok = get_font(28, bold=True)
            draw_text_centered(draw, "DENTRO DEL LIMITE", content_y + 85, font_ok, LIGHT_COLORS["green"])
    
    # LIMITE DE TIEMPO
    limit_y = 875
    font_limit = get_font(32, bold=True)
    if status.worst_trucks and status.worst_trucks[0].umbral:
        limite_mostrar = status.worst_trucks[0].umbral
        tipo_carga = status.worst_trucks[0].load_type
        limit_text = f"LIMITE PERMITIDO ({tipo_carga}): {format_timedelta_banner(limite_mostrar)}"
    else:
        limit_text = f"LIMITE PERMITIDO: {format_timedelta_banner(status.time_limit)}"
    draw_text_centered(draw, limit_text, limit_y, font_limit, config["text_secondary"])
    
    # FOOTER
    footer_height = 110
    footer_y = height - footer_height
    
    draw.rectangle([0, footer_y, width, height], fill=hex_to_rgb(config["bg_secondary"]))
    draw.rectangle([0, footer_y, width, footer_y + 6], fill=hex_to_rgb(config["accent"]))
    
    font_action = get_font(38, bold=True)
    draw_text_centered(draw, config["message"], footer_y + 38, font_action, config["text_primary"])
    
    # GUARDAR
    output_dir = Path("./banners")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alerta_{status.name.lower().replace(' ', '_')}_{timestamp}.png"
    output_path = output_dir / filename
    
    img.save(output_path, "PNG", optimize=True)
    
    return str(output_path)


# =============================================================================
# MENSAJE DE RESUMEN PARA WHATSAPP (ORIGINAL)
# =============================================================================

def format_banner_summary_message(status: CenterStatus) -> str:
    """Genera el mensaje de texto que acompana al banner (FORMATO ORIGINAL)"""
    now = datetime.now()
    fecha_hora = now.strftime("%d/%m/%Y - %H:%M:%S")
    
    lines = [
        f"*REPORTE DE ESTADO* - {status.name}",
        f"{fecha_hora}",
        "",
        f"En planta: {status.traffic.total} camiones",
        f"A tiempo: {status.traffic.green} | En riesgo: {status.traffic.yellow} | Criticos: {status.traffic.red}",
        "",
    ]
    
    # Top camiones atrasados
    trucks_to_show = [t for t in status.worst_trucks if t.umbral and classify_truck(t.time_in_plant, t.umbral) != "green"]
    
    if trucks_to_show:
        lines.append("*TOP CAMIONES ATRASADOS:*")
        tipo_map = {"LATERAL": "LAT", "TRASERA": "TRA", "INTERNA": "INT"}
        for i, truck in enumerate(trucks_to_show[:5], 1):
            tipo_corto = tipo_map.get(truck.load_type, truck.load_type[:3])
            ingreso_info = f" | {truck.tipo_ingreso}" if truck.tipo_ingreso else ""
            lines.append(f"{i}. {truck.plate} | {tipo_corto}{ingreso_info} | {fmt_td(truck.time_in_plant)}")
    else:
        lines.append("Sin camiones atrasados.")
    
    return "\n".join(lines)


def format_dispatch_alert(site_name: str, patente: str, trt: timedelta) -> str:
    """Formatea el mensaje de despacho"""
    now = datetime.now(TIMEZONE)
    fecha_hora = now.strftime("%d/%m/%Y - %H:%M:%S")
    msg = (
        f"*CAMION DESPACHADO* - {site_name}\n"
        f"{fecha_hora}\n"
        f"\n"
        f"*Patente:* {patente}\n"
        f"*Estado:* Camion con tiempo critico despachado\n"
        f"*TRT (Tiempo de Estadia Total):* {fmt_td(trt)}\n"
    )
    return msg


# =============================================================================
# ENVIO DE MENSAJES VIA HTTP
# =============================================================================

def send_text_to_group(group_id: str, message: str) -> bool:
    try:
        r = requests.post(f"{BOT_URL}/send/text", json={
            "groupId": group_id,
            "message": message
        }, timeout=10)
        return r.status_code == 200 and r.json().get("success", False)
    except Exception as e:
        logger.error(f"Error enviando texto: {e}")
        return False


def send_image_to_group(group_id: str, image_path: str, caption: str = "", delete_after: bool = True) -> bool:
    try:
        r = requests.post(f"{BOT_URL}/send/image-path", json={
            "groupId": group_id,
            "imagePath": os.path.abspath(image_path),
            "caption": caption,
            "deleteAfter": delete_after
        }, timeout=30)
        return r.status_code == 200 and r.json().get("success", False)
    except Exception as e:
        logger.error(f"Error enviando imagen: {e}")
        return False


def check_bot_connection(retries=5, delay=3) -> bool:
    for i in range(retries):
        try:
            r = requests.get(f"{BOT_URL}/health", timeout=5)
            data = r.json()
            if data.get("whatsapp") == "connected":
                return True
            logger.warning(f"Bot no listo, reintentando ({i+1}/{retries})...")
        except Exception as e:
            logger.warning(f"No se pudo conectar al bot, reintentando ({i+1}/{retries})...")
        time.sleep(delay)
    return False


# =============================================================================
# API HTTP PARA EL BOT (RESUMEN)
# =============================================================================

from flask import Flask, jsonify

api_app = Flask(__name__)

# Cache de camiones en planta actualizado por el loop principal
# {site_name: {patente: {empresa, tipo_descarga, minutos, tiempo_str}}}
_live_trucks: Dict[str, dict] = {}

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


@api_app.route('/resumen/<site_name>', methods=['GET'])
def get_resumen(site_name):
    if CONFIG is None or SUMMARY_MANAGER is None:
        return jsonify({"error": "Monitor aun no configurado. Esperando config.txt"}), 503

    site_found = None
    for site in CONFIG["sites"]:
        if site["name"].lower().replace(" ", "_") == site_name.lower().replace(" ", "_"):
            site_found = site
            break
        if site["name"].lower() == site_name.lower():
            site_found = site
            break

    if not site_found:
        return jsonify({"error": "Sitio no encontrado", "available": [s["name"] for s in CONFIG["sites"]]}), 404

    # Usar resumen completo (general + por turnos) igual que el de las 8 AM
    summary = SUMMARY_MANAGER.get_full_summary(site_found["name"])
    message = format_full_summary_message(site_found["name"], summary, is_manual=True)

    return jsonify({
        "success": True,
        "site_name": site_found["name"],
        "message": message,
        "data": summary
    })


@api_app.route('/resumen-completo/<site_name>', methods=['GET'])
def get_resumen_completo(site_name):
    if CONFIG is None or SUMMARY_MANAGER is None:
        return jsonify({"error": "Monitor aun no configurado. Esperando config.txt"}), 503

    site_found = None
    for site in CONFIG["sites"]:
        if site["name"].lower().replace(" ", "_") == site_name.lower().replace(" ", "_"):
            site_found = site
            break
        if site["name"].lower() == site_name.lower():
            site_found = site
            break

    if not site_found:
        return jsonify({"error": "Sitio no encontrado"}), 404

    summary = SUMMARY_MANAGER.get_full_summary(site_found["name"])
    message = format_full_summary_message(site_found["name"], summary)

    return jsonify({
        "success": True,
        "site_name": site_found["name"],
        "message": message,
        "data": summary
    })


@api_app.route('/sites', methods=['GET'])
def get_sites():
    if CONFIG is None:
        return jsonify({"error": "Monitor aun no configurado. Esperando config.txt", "sites": []}), 503

    return jsonify({
        "sites": [{"name": s["name"], "group_id": s.get("whatsapp_group_id") or s.get("group_id", "")} for s in CONFIG["sites"]]
    })


@api_app.route('/trucks-live/<path:site_name>', methods=['GET'])
def get_trucks_live(site_name):
    """Devuelve lista de camiones en planta (datos del último poll del monitor)"""
    # Normalizar nombre de sitio
    site_key = None
    for key in _live_trucks:
        if key.lower().replace(" ", "_") == site_name.lower().replace(" ", "_"):
            site_key = key
            break
        if key.lower() == site_name.lower():
            site_key = key
            break

    if site_key is None:
        return jsonify({"site": site_name, "trucks": [], "total": 0})

    trucks_list = [info for info in _live_trucks[site_key].values()]
    return jsonify({"site": site_key, "trucks": trucks_list, "total": len(trucks_list)})


def run_api_server():
    api_app.run(host='0.0.0.0', port=MONITOR_API_PORT, threaded=True, use_reloader=False)


# =============================================================================
# SCHEDULER PARA RESUMEN DE 8 AM
# =============================================================================

def check_and_send_daily_summary():
    if CONFIG is None or SUMMARY_MANAGER is None:
        return

    now = datetime.now(TIMEZONE)

    if now.hour == 8 and now.minute == 0:
        logger.info("Enviando resumenes diarios (periodo anterior 23:30-23:30)...")

        for site in CONFIG["sites"]:
            try:
                # Obtener resumen del periodo ANTERIOR (23:30 a 23:30 completo)
                summary = SUMMARY_MANAGER.get_previous_full_summary(site["name"])
                message = format_full_summary_message(site["name"], summary)
                
                # Usar WHATSAPP_GROUP_ID si esta disponible (mas rapido), sino GROUP_ID
                group_id = site.get("whatsapp_group_id") or site.get("group_id", "")
                if not group_id:
                    logger.warning(f"Sin group_id para {site['name']}, saltando resumen")
                    continue
                if send_text_to_group(group_id, message):
                    logger.info(f"Resumen {site['name']} enviado")
                    # Limpiar archivos más viejos que 60 días (retención)
                    SUMMARY_MANAGER.clean_old_files(site["name"], retention_days=60)
                else:
                    logger.error(f"Error enviando resumen {site['name']}")
            except Exception as e:
                logger.error(f"Error procesando resumen {site['name']}: {e}")
        
        return True
    return False


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def main():
    global CONFIG, BASE_URL, POLL_SECONDS, REALERT_EVERY, SUMMARY_MANAGER

    logger.info("=" * 50)
    logger.info("MONITOR DE ALERTAS v4")
    logger.info("Con sistema de resumen diario")
    logger.info("=" * 50)

    # Esperar hasta que exista configuracion
    while CONFIG is None:
        logger.info("Esperando archivo de configuracion (config.txt)...")
        time.sleep(5)
        CONFIG = load_config(str(BASE_DIR / "config.txt"))

    # Inicializar variables globales ahora que tenemos config
    BASE_URL = CONFIG["base_url"]
    POLL_SECONDS = CONFIG["poll_seconds"]
    REALERT_EVERY = timedelta(minutes=CONFIG["realert_minutes"])
    SUMMARY_MANAGER = DailySummaryManager(BASE_DIR / "daily_data")

    logger.info(f"Configuracion cargada!")
    logger.info(f"URL Base: {BASE_URL}")
    logger.info(f"Intervalo: {POLL_SECONDS}s")
    logger.info(f"Re-alerta cada: {CONFIG['realert_minutes']} min")
    logger.info(f"Sitios: {len(CONFIG['sites'])}")

    logger.info("Iniciando API de resumenes en puerto 5051...")
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    time.sleep(1)

    logger.info("Conectando con bot de WhatsApp...")
    if not check_bot_connection(retries=10, delay=3):
        logger.error("No se pudo conectar al bot de WhatsApp")
        logger.error("Verifica que 'node bot_whatsapp.js' este corriendo")
        logger.error("y que aparezca 'WhatsApp conectado!' en su consola")
        return
    logger.info("Conectado!")

    state = {
        site["name"]: {
            "last_alerts": {},
            "camiones_criticos": {},      # Solo para alertas de criticos
            "camiones_en_planta": {},     # TODOS los camiones visibles (para resumen)
            "last_banner_time": None
        }
        for site in CONFIG["sites"]
    }
    
    last_summary_check = None

    try:
        while True:
            now = datetime.now(TIMEZONE)
            logger.info(f"Consultando centros...")
            
            current_minute = now.replace(second=0, microsecond=0)
            if last_summary_check != current_minute:
                check_and_send_daily_summary()
                last_summary_check = current_minute

            for site in CONFIG["sites"]:
                site_name = site["name"]
                # Usar WHATSAPP_GROUP_ID si está disponible (más rápido), sino GROUP_ID
                group_id = site.get("whatsapp_group_id") or site.get("group_id", "")
                if not group_id:
                    logger.warning(f"Sin group_id para {site_name}, las alertas no se enviarán")

                SUMMARY_MANAGER.check_and_reset_if_needed(site_name)

                try:
                    if auth and site.get("centro_id"):
                        rows = fetch_camiones_en_planta(site, auth)
                    else:
                        html = fetch_html_tabla(site)
                        rows = parse_table_rows(html)

                    visible = set()
                    camiones_criticos = state[site_name]["camiones_criticos"]
                    camiones_en_planta = state[site_name]["camiones_en_planta"]
                    last_banner_time = state[site_name]["last_banner_time"]

                    logger.info(f"[{site_name}] {len(rows)} camiones")

                    should_send_banner = (
                        last_banner_time is None or 
                        (now - last_banner_time) >= REALERT_EVERY
                    )

                    if should_send_banner and len(rows) > 0:
                        center_status = analyze_center_status(site, rows)
                        banner_path = make_banner_png(center_status)
                        summary_msg = format_banner_summary_message(center_status)
                        
                        if send_image_to_group(group_id, banner_path, summary_msg):
                            logger.info(f"[{site_name}] Banner enviado")
                            state[site_name]["last_banner_time"] = now
                        else:
                            logger.error(f"[{site_name}] Error enviando banner")

                    for row in rows:
                        patente = (row.get("Patente") or "").strip()
                        if not patente:
                            continue
                        visible.add(patente)

                        t_str = (row.get("Tiempo en Planta") or "").strip()
                        if not t_str:
                            continue

                        try:
                            t = parse_tiempo_en_planta(t_str)
                        except:
                            continue

                        empresa = (row.get("Empresa") or "").strip()
                        umbral = get_umbral_para_camion(site, empresa)

                        tipo_ingreso = (row.get("Tipo de Ingreso") or "").strip()

                        # Trackear TODOS los camiones para el resumen
                        if patente not in camiones_en_planta:
                            camiones_en_planta[patente] = {
                                "tiempo": t,
                                "primera_deteccion": now,
                                "empresa": empresa,
                                "tipo_ingreso": tipo_ingreso,
                            }
                        else:
                            # Actualizar tiempo (siempre guardar el ultimo conocido)
                            camiones_en_planta[patente]["tiempo"] = t

                        # Trackear criticos para alertas de WhatsApp
                        if t > umbral:
                            if patente not in camiones_criticos:
                                camiones_criticos[patente] = {
                                    "tiempo": t,
                                    "primera_deteccion": now,
                                    "empresa": empresa,
                                }
                                logger.info(f"[{site_name}] Camion {patente} critico ({fmt_td(t)})")
                            else:
                                camiones_criticos[patente]["tiempo"] = t

                    # Actualizar cache live para endpoint /trucks-live
                    _live_trucks[site_name] = {
                        p: {
                            "patente": p,
                            "empresa": info.get("empresa", ""),
                            "tipo_descarga": get_tipo_descarga(info.get("empresa", "")),
                            "tipo_ingreso": info.get("tipo_ingreso", ""),
                            "minutos": int(info["tiempo"].total_seconds() / 60),
                            "tiempo_str": fmt_td(info["tiempo"]),
                        }
                        for p, info in camiones_en_planta.items()
                        if p in visible
                    }

                    # Detectar camiones despachados (desaparecieron de la tabla)
                    for patente in list(camiones_en_planta.keys()):
                        if patente not in visible:
                            trt = camiones_en_planta[patente]["tiempo"]
                            empresa = camiones_en_planta[patente].get("empresa", "")
                            tipo_descarga = get_tipo_descarga_for_site(
                                empresa,
                                site.get("umbral_minutes_trasera", 0),
                                site.get("umbral_minutes_interna", 0),
                            )
                            fue_critico = patente in camiones_criticos

                            # Registrar en el resumen (TODOS los camiones)
                            # La hora de ingreso se calcula internamente como hora_despacho - TRT
                            SUMMARY_MANAGER.register_dispatch(
                                site_name, patente, empresa, tipo_descarga, trt, fue_critico
                            )
                            logger.info(f"[{site_name}] Despacho registrado: {patente} (TRT: {fmt_td(trt)}, critico: {fue_critico})")

                            # Eliminar del tracking general
                            del camiones_en_planta[patente]
                            
                            # Si era critico, enviar alerta y eliminar de criticos
                            if fue_critico:
                                msg = format_dispatch_alert(site_name, patente, trt)
                                if send_text_to_group(group_id, msg):
                                    logger.info(f"[{site_name}] Alerta despacho critico {patente} enviada")
                                del camiones_criticos[patente]

                except Exception as e:
                    logger.error(f"[{site_name}] Error: {e}")

            time.sleep(POLL_SECONDS)
            
    except KeyboardInterrupt:
        logger.info("Sistema detenido")


if __name__ == "__main__":
    main()