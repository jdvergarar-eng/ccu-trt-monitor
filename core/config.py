# Configuration manager - Lee y escribe config.txt
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class SiteConfig:
    """Configuracion de un sitio/centro"""
    name: str
    referer_id: str
    db_name: str
    op_code: str
    cd_code: str
    group_id: str = ""
    whatsapp_group_id: str = ""
    umbral_minutes_lateral: int = 0
    umbral_minutes_trasera: int = 0
    umbral_minutes_interna: int = 0
    umbral_minutes: int = 0  # Umbral unico (legacy)
    realert_minutes: int = 30  # Reenvio de alertas por centro (minutos)
    alerts_enabled: bool = True  # Habilita/deshabilita alertas WhatsApp para este centro


@dataclass
class AppConfig:
    """Configuracion general de la aplicacion"""
    base_url: str = "http://192.168.55.79"
    poll_seconds: int = 10
    realert_minutes: int = 30
    sites: List[SiteConfig] = field(default_factory=list)


class ConfigManager:
    """Gestor de configuracion - lee y escribe config.txt"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            config_path = base_dir / "config.txt"
        self.config_path = Path(config_path)
        self._config: Optional[AppConfig] = None
        self._lock = threading.Lock()

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = self.load()
        return self._config

    def exists(self) -> bool:
        """Verifica si el archivo de configuracion existe"""
        return self.config_path.exists()

    def load(self) -> AppConfig:
        """Carga la configuracion desde config.txt (thread-safe)"""
        with self._lock:
            return self._load_internal()

    def _load_internal(self) -> AppConfig:
        """Carga interna sin lock (para uso dentro de métodos con lock)"""
        if not self.config_path.exists():
            return AppConfig()

        config = AppConfig()
        current_site = {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Linea vacia o comentario: guardar sitio actual si existe
                if not line or line.startswith("#"):
                    if current_site and "name" in current_site:
                        config.sites.append(self._dict_to_site(current_site))
                        current_site = {}
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()

                    if key == "BASE_URL":
                        config.base_url = value
                    elif key == "POLL_SECONDS":
                        config.poll_seconds = int(value)
                    elif key == "REALERT_MINUTES":
                        config.realert_minutes = int(value)
                    elif key == "SITE_NAME":
                        current_site["name"] = value
                    elif key == "GROUP_ID":
                        current_site["group_id"] = value
                    elif key == "WHATSAPP_GROUP_ID":
                        current_site["whatsapp_group_id"] = value
                    elif key == "UMBRAL_MINUTES":
                        current_site["umbral_minutes"] = int(value)
                    elif key == "UMBRAL_MINUTES_LATERAL":
                        current_site["umbral_minutes_lateral"] = int(value)
                    elif key == "UMBRAL_MINUTES_TRASERA":
                        current_site["umbral_minutes_trasera"] = int(value)
                    elif key == "UMBRAL_MINUTES_INTERNA":
                        current_site["umbral_minutes_interna"] = int(value)
                    elif key == "SITE_REALERT_MINUTES":
                        current_site["realert_minutes"] = int(value)
                    elif key == "ALERTS_ENABLED":
                        current_site["alerts_enabled"] = value.lower() not in ("false", "0", "no")
                    elif key == "DB_NAME":
                        current_site["db_name"] = value
                    elif key == "OP_CODE":
                        current_site["op_code"] = value
                    elif key == "CD_CODE":
                        current_site["cd_code"] = value
                    elif key == "REFERER_ID":
                        current_site["referer_id"] = value

        # Guardar ultimo sitio si existe
        if current_site and "name" in current_site:
            config.sites.append(self._dict_to_site(current_site))

        self._config = config
        return config

    def _dict_to_site(self, d: dict) -> SiteConfig:
        """Convierte un diccionario a SiteConfig"""
        return SiteConfig(
            name=d.get("name", ""),
            referer_id=d.get("referer_id", ""),
            db_name=d.get("db_name", ""),
            op_code=d.get("op_code", ""),
            cd_code=d.get("cd_code", ""),
            group_id=d.get("group_id", ""),
            whatsapp_group_id=d.get("whatsapp_group_id", ""),
            umbral_minutes_lateral=d.get("umbral_minutes_lateral", 0),
            umbral_minutes_trasera=d.get("umbral_minutes_trasera", 0),
            umbral_minutes_interna=d.get("umbral_minutes_interna", 0),
            umbral_minutes=d.get("umbral_minutes", 0),
            realert_minutes=d.get("realert_minutes", 30),
            alerts_enabled=d.get("alerts_enabled", True),
        )

    def save(self, config: AppConfig = None):
        """Guarda la configuracion en config.txt (thread-safe)"""
        with self._lock:
            self._save_internal(config)

    def _save_internal(self, config: AppConfig = None):
        """Guardado interno sin lock"""
        if config is None:
            config = self._config
        if config is None:
            raise ValueError("No hay configuracion para guardar")

        lines = []
        lines.append("# Configuracion del Monitor de Alertas TRT")
        lines.append("# Generado automaticamente por CCU-TRT GUI")
        lines.append("")
        lines.append("# ===========================================")
        lines.append("# CONFIGURACION GENERAL")
        lines.append("# ===========================================")
        lines.append(f"BASE_URL={config.base_url}")
        lines.append(f"POLL_SECONDS={config.poll_seconds}")
        lines.append(f"REALERT_MINUTES={config.realert_minutes}")
        lines.append("")

        for i, site in enumerate(config.sites, 1):
            lines.append("# ===========================================")
            lines.append(f"# SITIO {i}: {site.name}")
            lines.append("# ===========================================")
            lines.append(f"SITE_NAME={site.name}")
            lines.append(f"DB_NAME={site.db_name}")
            lines.append(f"OP_CODE={site.op_code}")
            lines.append(f"CD_CODE={site.cd_code}")
            lines.append(f"REFERER_ID={site.referer_id}")

            if site.group_id:
                lines.append(f"GROUP_ID={site.group_id}")
            if site.whatsapp_group_id:
                lines.append(f"WHATSAPP_GROUP_ID={site.whatsapp_group_id}")

            # Umbrales
            if site.umbral_minutes > 0:
                lines.append(f"UMBRAL_MINUTES={site.umbral_minutes}")
            else:
                if site.umbral_minutes_lateral > 0:
                    lines.append(f"UMBRAL_MINUTES_LATERAL={site.umbral_minutes_lateral}")
                if site.umbral_minutes_trasera > 0:
                    lines.append(f"UMBRAL_MINUTES_TRASERA={site.umbral_minutes_trasera}")
                if site.umbral_minutes_interna > 0:
                    lines.append(f"UMBRAL_MINUTES_INTERNA={site.umbral_minutes_interna}")

            lines.append(f"SITE_REALERT_MINUTES={site.realert_minutes}")
            lines.append(f"ALERTS_ENABLED={site.alerts_enabled}")
            lines.append("")

        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self._config = config

    def add_site(self, site: SiteConfig):
        """Agrega un sitio a la configuracion (thread-safe)"""
        with self._lock:
            self.config.sites.append(site)
            self._save_internal()

    def remove_site(self, site_name: str):
        """Elimina un sitio de la configuracion (thread-safe)"""
        with self._lock:
            self.config.sites = [s for s in self.config.sites if s.name != site_name]
            self._save_internal()

    def update_site(self, site_name: str, updated_site: SiteConfig):
        """Actualiza un sitio existente (thread-safe)"""
        with self._lock:
            for i, site in enumerate(self.config.sites):
                if site.name == site_name:
                    self.config.sites[i] = updated_site
                    break
            self._save_internal()

    def get_site(self, site_name: str) -> Optional[SiteConfig]:
        """Obtiene un sitio por nombre (thread-safe)"""
        with self._lock:
            for site in self.config.sites:
                if site.name == site_name:
                    return site
            return None


# Instancia global
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Obtiene la instancia global del ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# =============================================================================
# CONFIGURACION DE PUERTOS (archivo separado)
# =============================================================================

def load_ports_config(ports_file: str = None) -> dict:
    """
    Carga la configuracion de puertos desde ports.txt

    Este archivo es independiente de config.txt y permite cambiar
    los puertos sin afectar la configuracion principal.

    Returns:
        dict con 'bot_port' y 'monitor_port'
    """
    if ports_file is None:
        base_dir = Path(__file__).resolve().parent.parent
        ports_file = base_dir / "ports.txt"
    else:
        ports_file = Path(ports_file)

    # Valores por defecto
    ports = {
        "bot_port": 5050,
        "monitor_port": 5051
    }

    # Si el archivo no existe, retornar defaults
    if not ports_file.exists():
        return ports

    # Leer archivo
    try:
        with open(ports_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Saltar comentarios y lineas vacias
                if not line or line.startswith("#"):
                    continue

                # Parsear key=value
                if "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip().upper(), value.strip()

                    if key == "BOT_PORT":
                        ports["bot_port"] = int(value)
                    elif key == "MONITOR_PORT":
                        ports["monitor_port"] = int(value)

    except Exception as e:
        # Si hay error leyendo el archivo, usar defaults
        print(f"Error leyendo ports.txt: {e}. Usando puertos por defecto.")

    return ports


# Cargar puertos al importar el modulo
_PORTS_CONFIG = load_ports_config()


def get_bot_port() -> int:
    """Obtiene el puerto del bot de WhatsApp"""
    return _PORTS_CONFIG["bot_port"]


def get_monitor_port() -> int:
    """Obtiene el puerto del monitor de alertas"""
    return _PORTS_CONFIG["monitor_port"]
