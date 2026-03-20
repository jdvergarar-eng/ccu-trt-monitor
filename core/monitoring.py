# MonitoringService - Lógica de monitoreo extraída de dashboard.py
# Servicio independiente del GUI, thread-safe para uso web multi-usuario

import os
import logging
import threading
from collections import deque
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from .config import ConfigManager, SiteConfig
from .trt_api import TRTClient
from .whatsapp import WhatsAppClient
from .banner import make_banner_png, format_banner_summary_message, analyze_trucks_for_banner


@dataclass
class LogEntry:
    """Entrada del log de actividad"""
    time: str
    level: str  # success, warning, error, info
    message: str


@dataclass
class AlertResult:
    """Resultado de envío de alerta"""
    site_name: str
    severity: str
    success: bool
    error: Optional[str] = None


class MonitoringService:
    """Servicio de monitoreo de TRT - thread-safe, independiente del GUI"""

    def __init__(self, config_manager: ConfigManager,
                 trt_client: Optional[TRTClient],
                 wa_client: Optional[WhatsAppClient]):
        self.config_manager = config_manager
        self.trt_client = trt_client
        self.wa_client = wa_client

        # Estado interno protegido por lock
        self._lock = threading.Lock()
        self.centers_stats_cache: Dict[str, dict] = {}
        self.sent_alerts: Dict[str, datetime] = {}  # rate limiting
        self.monitor_running = False
        self.alerts_enabled = True  # Flag global: habilita/deshabilita envio de alertas WhatsApp
        self.bot_status = "disconnected"
        self.whatsapp_phone: Optional[str] = None
        self.whatsapp_name: Optional[str] = None
        self.trt_connected = False
        self.last_update: Optional[datetime] = None
        self.logs: deque = deque(maxlen=200)

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def config(self):
        return self.config_manager.config

    def add_log(self, level: str, message: str):
        """Agrega una entrada al log (thread-safe)"""
        entry = LogEntry(
            time=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message
        )
        with self._lock:
            self.logs.append(entry)

    def get_logs(self) -> List[LogEntry]:
        """Obtiene los logs actuales (thread-safe)"""
        with self._lock:
            return list(self.logs)

    def _get_qr_data(self) -> dict:
        """Obtiene estado del QR del bot (non-blocking, max 3 s)."""
        if not self.wa_client:
            return {"status": "unknown", "qr": ""}
        try:
            import requests as _req
            base_url = getattr(self.wa_client, "base_url", "http://localhost:5050")
            resp = _req.get(f"{base_url}/qr", timeout=3)
            return resp.json()
        except Exception:
            return {"status": self.bot_status, "qr": ""}

    def start(self):
        """Inicia el monitoreo en un hilo de background"""
        if self.monitor_running:
            return

        self.monitor_running = True
        self._stop_event.clear()
        self.add_log("success", "Monitor iniciado")

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """Detiene el monitoreo"""
        self.monitor_running = False
        self._stop_event.set()
        self.add_log("warning", "Monitor detenido")

    def enable_alerts(self):
        """Activa el envío de alertas por WhatsApp"""
        self.alerts_enabled = True
        self.add_log("success", "Alertas WhatsApp activadas")

    def disable_alerts(self):
        """Desactiva el envío de alertas por WhatsApp"""
        self.alerts_enabled = False
        self.add_log("warning", "Alertas WhatsApp desactivadas")

    def _monitor_loop(self):
        """Loop principal de monitoreo"""
        while not self._stop_event.is_set():
            self.check_status()
            self.poll_all_sites()

            poll_seconds = self.config.poll_seconds or 10
            self._stop_event.wait(timeout=poll_seconds)

    def check_status(self) -> dict:
        """Verifica estado del bot de WhatsApp y TRT"""
        old_wa = self.bot_status
        old_trt = self.trt_connected

        # Verificar WhatsApp
        try:
            if self.wa_client and self.wa_client.health_check():
                status = self.wa_client.get_status()
                if status.connected:
                    self.bot_status = "connected"
                    self.whatsapp_phone = status.phone
                    self.whatsapp_name = status.name
                else:
                    self.bot_status = "warning"
            else:
                self.bot_status = "disconnected"
        except Exception:
            self.bot_status = "disconnected"

        # Verificar TRT
        self.trt_connected = self.trt_client is not None

        # Log cambios de estado
        if old_wa != self.bot_status or old_trt != self.trt_connected:
            if self.bot_status == "connected":
                self.add_log("success", f"WhatsApp conectado ({self.whatsapp_phone or 'OK'})")
                # Si el bot reconecta y el monitor está corriendo con alertas activas, confirmar
                if self.monitor_running and self.alerts_enabled:
                    self.add_log("success", "Alertas WhatsApp reanudadas")
            elif self.bot_status == "warning":
                self.add_log("warning", "Bot activo pero WhatsApp no conectado")
                if self.monitor_running and self.alerts_enabled:
                    self.add_log("warning", "Alertas bloqueadas: vincula tu cuenta de WhatsApp")
            else:
                self.add_log("error", "Bot de WhatsApp no disponible")
                if self.monitor_running and self.alerts_enabled:
                    self.add_log("error", "Alertas bloqueadas: bot no responde")

        return {
            "bot_status": self.bot_status,
            "whatsapp_phone": self.whatsapp_phone,
            "whatsapp_name": self.whatsapp_name,
            "trt_connected": self.trt_connected,
            "monitor_running": self.monitor_running,
        }

    def poll_all_sites(self) -> Dict[str, dict]:
        """Consulta todos los sitios y actualiza cache (thread-safe)"""
        if not self.trt_client:
            self.add_log("warning", "Cliente TRT no configurado")
            return {}

        total_trucks = 0
        total_alerts = 0
        alerts_to_send = []

        for site in self.config.sites:
            try:
                site_config = {
                    "referer_id": site.referer_id,
                    "db_name": site.db_name,
                    "op_code": site.op_code,
                    "cd_code": site.cd_code,
                }
                stats = self.trt_client.get_center_stats(site_config)

                trucks = stats.get("trucks", [])
                threshold = site.umbral_minutes_lateral or site.umbral_minutes or 60
                alerts = sum(1 for t in trucks if t.time_in_plant_minutes >= threshold)

                with self._lock:
                    self.centers_stats_cache[site.name] = {
                        "total_trucks": stats.get("total_trucks", 0),
                        "avg_time": stats.get("avg_time_minutes", 0),
                        "max_time": stats.get("max_time_minutes", 0),
                        "trucks": trucks,
                        "alerts": alerts,
                    }

                total_trucks += stats.get("total_trucks", 0)
                total_alerts += alerts

                if trucks and site.whatsapp_group_id:
                    alerts_to_send.append({
                        "site": site,
                        "all_trucks": trucks,
                        "threshold": threshold,
                    })

            except Exception as e:
                error_msg = str(e)
                self.add_log("error", f"Error {site.name}: {error_msg[:50]}")

        with self._lock:
            self.last_update = datetime.now()

        # Enviar alertas si corresponde
        if alerts_to_send and self.bot_status == "connected" and self.alerts_enabled:
            self.send_alerts_if_needed(alerts_to_send)

        if total_alerts > 0:
            self.add_log("warning", f"{total_alerts} alerta(s) detectada(s) - {total_trucks} camiones en planta")

        return self.centers_stats_cache

    def send_alerts_if_needed(self, alerts_to_send: list) -> List[AlertResult]:
        """Envía alertas por WhatsApp con rate limiting"""
        results = []
        realert_minutes = self.config.realert_minutes or 30
        now = datetime.now()

        for alert_data in alerts_to_send:
            site = alert_data["site"]
            all_trucks = alert_data["all_trucks"]
            threshold = alert_data["threshold"]

            # Saltar sitios con alertas deshabilitadas
            if not site.alerts_enabled:
                continue

            # Rate limiting
            site_key = f"site_{site.referer_id}"
            with self._lock:
                last_alert = self.sent_alerts.get(site_key)
                if last_alert is not None and (now - last_alert).total_seconds() < realert_minutes * 60:
                    continue
                self.sent_alerts[site_key] = now

            try:
                center_status = analyze_trucks_for_banner(site.name, all_trucks, threshold)
                banner_path = make_banner_png(center_status)
                summary_message = format_banner_summary_message(center_status)

                success = self.wa_client.send_image(
                    site.whatsapp_group_id,
                    banner_path,
                    summary_message
                )

                if success:
                    self.add_log("success", f"Banner {center_status.severity} enviado: {site.name}")
                else:
                    self.add_log("error", f"Error enviando banner a {site.name}")

                if banner_path and os.path.exists(banner_path):
                    try:
                        os.remove(banner_path)
                    except Exception as e:
                        self.add_log("warning", f"No se pudo eliminar banner: {e}")

                results.append(AlertResult(
                    site_name=site.name,
                    severity=center_status.severity,
                    success=success
                ))

            except Exception as e:
                self.add_log("error", f"Error banner: {str(e)[:30]}")
                results.append(AlertResult(
                    site_name=site.name,
                    severity="ERROR",
                    success=False,
                    error=str(e)
                ))

        return results

    def force_send_banner(self, site_name: str = None):
        """Fuerza el envío de banners (limpia rate limiting)"""
        self.add_log("info", f"Forzando envio de banner: {site_name or 'todos'}...")
        with self._lock:
            if site_name:
                # Buscar el site por nombre para obtener su referer_id
                site = next((s for s in self.config.sites if s.name == site_name), None)
                if site:
                    key = f"site_{site.referer_id}"
                    self.sent_alerts.pop(key, None)
                else:
                    self.sent_alerts.clear()
            else:
                self.sent_alerts.clear()
        self.poll_all_sites()

    def get_centers_data(self) -> List[dict]:
        """Obtiene datos de centros formateados para la UI"""
        centers_data = []

        for site in self.config.sites:
            with self._lock:
                stats = self.centers_stats_cache.get(site.name, {})

            trucks = stats.get("total_trucks", 0)
            avg_time = stats.get("avg_time", 0)
            alerts = stats.get("alerts", 0)
            threshold = site.umbral_minutes_lateral or site.umbral_minutes or 60

            if alerts > 0:
                status = "critical"
            elif avg_time == 0:
                status = "normal"
            elif avg_time >= threshold * 0.8:
                status = "warning"
            else:
                status = "normal"

            centers_data.append({
                "name": site.name,
                "status": status,
                "trucks_in_plant": trucks,
                "avg_time": avg_time,
                "threshold": threshold,
                "alerts": alerts,
                "trucks_list": stats.get("trucks", []),
                "threshold_lateral": site.umbral_minutes_lateral or site.umbral_minutes or 60,
                "threshold_trasera": site.umbral_minutes_trasera or site.umbral_minutes or 60,
                "threshold_interna": site.umbral_minutes_interna or site.umbral_minutes or 60,
            })

        return centers_data

    def get_summary(self) -> dict:
        """Obtiene resumen general del estado del sistema"""
        centers_data = self.get_centers_data()
        return {
            "total_alerts": sum(c["alerts"] for c in centers_data),
            "total_trucks": sum(c["trucks_in_plant"] for c in centers_data),
            "centers": centers_data,
            "bot_status": self.bot_status,
            "monitor_running": self.monitor_running,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "whatsapp_phone": self.whatsapp_phone,
        }


# Instancia global singleton
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(config_manager: ConfigManager = None,
                           trt_client: TRTClient = None,
                           wa_client: WhatsAppClient = None) -> MonitoringService:
    """Obtiene la instancia global del MonitoringService"""
    global _monitoring_service
    if _monitoring_service is None:
        if config_manager is None:
            from . import get_config_manager, get_trt_client, get_whatsapp_client
            config_manager = get_config_manager()
            try:
                trt_client = get_trt_client(config_manager.config.base_url)
            except Exception:
                trt_client = None
            try:
                wa_client = get_whatsapp_client()
            except Exception:
                wa_client = None
        _monitoring_service = MonitoringService(config_manager, trt_client, wa_client)
    return _monitoring_service
