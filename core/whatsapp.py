# WhatsApp Bot Client - Comunicacion con bot_whatsapp.js via HTTP
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class WhatsAppGroup:
    """Grupo de WhatsApp"""
    id: str
    name: str
    participants: int = 0


@dataclass
class BotStatus:
    """Estado del bot de WhatsApp"""
    connected: bool
    phone: Optional[str] = None
    name: Optional[str] = None


class WhatsAppClient:
    """Cliente HTTP para comunicarse con el bot de WhatsApp"""

    def __init__(self, bot_url: str = "http://localhost:5050"):
        self.bot_url = bot_url.rstrip("/")
        self.timeout = 10

    def health_check(self) -> bool:
        """Verifica si el bot esta corriendo"""
        try:
            r = requests.get(f"{self.bot_url}/health", timeout=self.timeout)
            data = r.json()
            return data.get("status") == "ok"
        except Exception:
            return False

    def get_status(self) -> BotStatus:
        """Obtiene el estado del bot"""
        try:
            r = requests.get(f"{self.bot_url}/info", timeout=self.timeout)
            data = r.json()
            return BotStatus(
                connected=data.get("connected", False),
                phone=data.get("phone"),
                name=data.get("name"),
            )
        except Exception:
            return BotStatus(connected=False)

    def get_qr_status(self) -> Dict:
        """
        Obtiene el estado del QR para vinculacion.

        Returns:
            Dict con status ('connected', 'waiting_scan', 'initializing'), qr (string o None), phone
        """
        try:
            # Timeout más largo porque el bot puede tardar en inicializar
            r = requests.get(f"{self.bot_url}/qr", timeout=30)
            return r.json()
        except requests.exceptions.Timeout:
            return {"status": "initializing", "qr": None, "message": "Bot inicializando..."}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": "No se puede conectar al bot", "qr": None}
        except Exception as e:
            return {"status": "error", "error": str(e), "qr": None}

    def get_groups(self) -> List[WhatsAppGroup]:
        """Obtiene la lista de grupos de WhatsApp"""
        groups = []

        try:
            r = requests.get(f"{self.bot_url}/groups", timeout=30)  # Timeout largo
            data = r.json()

            if data.get("success"):
                for g in data.get("groups", []):
                    groups.append(WhatsAppGroup(
                        id=g.get("id", ""),
                        name=g.get("name", ""),
                        participants=g.get("participants", 0),
                    ))

        except Exception as e:
            print(f"Error obteniendo grupos: {e}")

        return groups

    def send_text(self, group_id: str, message: str) -> bool:
        """Envia un mensaje de texto a un grupo"""
        try:
            r = requests.post(
                f"{self.bot_url}/send/text",
                json={"groupId": group_id, "message": message},
                timeout=self.timeout
            )
            return r.json().get("success", False)
        except Exception:
            return False

    def send_image(self, group_id: str, image_path: str, caption: str = "") -> bool:
        """Envia una imagen a un grupo"""
        try:
            r = requests.post(
                f"{self.bot_url}/send/image-path",
                json={
                    "groupId": group_id,
                    "imagePath": image_path,
                    "caption": caption,
                    "deleteAfter": False
                },
                timeout=30
            )
            return r.json().get("success", False)
        except Exception:
            return False

    def logout(self) -> bool:
        """Hace logout del bot (destruye sesion de WhatsApp y reinicia)"""
        try:
            r = requests.post(f"{self.bot_url}/logout", timeout=10)
            return r.json().get("success", False)
        except Exception:
            return False

    def is_bot_running(self) -> bool:
        """Verifica si el proceso del bot esta corriendo"""
        return self.health_check()

    def is_whatsapp_connected(self) -> bool:
        """Verifica si WhatsApp esta conectado"""
        try:
            r = requests.get(f"{self.bot_url}/health", timeout=self.timeout)
            data = r.json()
            return data.get("whatsapp") == "connected"
        except Exception:
            return False


# Instancia global
_whatsapp_client: Optional[WhatsAppClient] = None


def get_whatsapp_client(bot_url: str = None) -> WhatsAppClient:
    """
    Obtiene la instancia global del WhatsAppClient.

    Si no se proporciona bot_url, lo lee desde ports.txt
    (independiente de config.txt).
    """
    global _whatsapp_client

    if bot_url is None:
        # Leer puerto desde ports.txt (independiente de config.txt)
        try:
            from core.config import get_bot_port
            bot_port = get_bot_port()
            bot_url = f"http://localhost:{bot_port}"
        except Exception:
            bot_url = "http://localhost:5050"  # Fallback en caso de error

    if _whatsapp_client is None or _whatsapp_client.bot_url != bot_url:
        _whatsapp_client = WhatsAppClient(bot_url)
    return _whatsapp_client
