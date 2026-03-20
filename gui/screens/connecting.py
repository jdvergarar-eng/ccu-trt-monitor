# Connecting Screen - Pantalla de espera de conexion del bot de WhatsApp
# Se muestra antes del dashboard para verificar que el bot esta conectado.
# Si tarda mucho, ofrece desvincular la cuenta y reconectar con QR.
import customtkinter as ctk
import threading
import time
import qrcode
from PIL import Image, ImageTk
from pathlib import Path
from ..styles import Colors, Fonts
from ..components import Card, PrimaryButton, SecondaryButton, StatusBadge

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core import get_whatsapp_client


class ConnectingScreen(ctk.CTkFrame):
    """Pantalla de espera que verifica la conexion del bot antes del dashboard"""

    TIMEOUT_SECONDS = 25   # Segundos antes de ofrecer logout
    POLL_MS = 3000         # Intervalo de polling en ms

    def __init__(self, master, on_connected: callable, **kwargs):
        super().__init__(master, fg_color=Colors.BG_PRIMARY, **kwargs)

        self.on_connected = on_connected
        self.wa_client = get_whatsapp_client()

        self.active = True           # Se pone False al destruir la pantalla
        self.elapsed = 0             # Segundos transcurridos
        self.phase = "waiting"       # waiting | timeout | qr | done
        self.logout_shown = False

        # Animacion de puntos
        self._dot_count = 0

        # References a widgets que se actualizan
        self._status_text = None
        self._detail_text = None
        self._badge = None
        self._timeout_card = None
        self._qr_wrapper = None
        self._qr_label = None
        self._progress_bar = None

        self._build_ui()
        self._tick()       # timer de 1 segundo
        self._poll()       # primer poll inmediato

    # ── Construccion de la UI ─────────────────────────────────

    def _build_ui(self):
        # Usar scrollable frame para pantallas pequenas
        scroll_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=Colors.CARD_BORDER,
            scrollbar_button_hover_color=Colors.BG_HOVER
        )
        scroll_container.pack(fill="both", expand=True)

        center = ctk.CTkFrame(scroll_container, fg_color="transparent")
        center.pack(expand=True, pady=40)

        # Card principal contenedora
        main_card = ctk.CTkFrame(
            center,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.CARD_BORDER,
        )
        main_card.pack(padx=80)

        # Barra verde superior
        ctk.CTkFrame(
            main_card,
            fg_color=Colors.CCU_GREEN,
            height=4,
            corner_radius=0,
        ).place(relx=0, rely=0, relwidth=1)

        card_content = ctk.CTkFrame(main_card, fg_color="transparent")
        card_content.pack(padx=60, pady=50)

        # Logo CCU pequeno
        try:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
            logo_path = assets_dir / "Logo_CCU.png"

            if logo_path.exists():
                logo_img = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(140, 65)
                )
                ctk.CTkLabel(
                    card_content,
                    text="",
                    image=logo_img,
                ).pack(pady=(0, 20))
                self._logo_ref = logo_img
        except Exception:
            pass

        # Icono circular con fondo verde sutil
        icon_bg = ctk.CTkFrame(
            card_content, fg_color=Colors.ACTION_GREEN_LIGHT,
            corner_radius=36, width=72, height=72,
        )
        icon_bg.pack(pady=(0, 20))
        icon_bg.pack_propagate(False)

        # Icono WhatsApp desde assets si existe
        try:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
            dashboard_dir = assets_dir / "Dashboard"
            wa_icon_path = dashboard_dir / "whatsapp.png"

            if wa_icon_path.exists():
                wa_icon = ctk.CTkImage(
                    light_image=Image.open(wa_icon_path),
                    dark_image=Image.open(wa_icon_path),
                    size=(36, 36)
                )
                ctk.CTkLabel(
                    icon_bg, text="", image=wa_icon,
                ).place(relx=0.5, rely=0.5, anchor="center")
                self._wa_icon_ref = wa_icon
            else:
                ctk.CTkLabel(
                    icon_bg, text="WA",
                    text_color=Colors.ACTION_GREEN,
                    font=(Fonts.FAMILY, 20, "bold"),
                ).place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            ctk.CTkLabel(
                icon_bg, text="WA",
                text_color=Colors.ACTION_GREEN,
                font=(Fonts.FAMILY, 20, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

        # Titulo
        ctk.CTkLabel(
            card_content, text="Conectando al Bot de WhatsApp",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 8))

        # Texto de estado
        self._status_text = ctk.CTkLabel(
            card_content, text="Iniciando...",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
        )
        self._status_text.pack(pady=(0, 16))

        # Barra de progreso indeterminada
        self._progress_bar = ctk.CTkProgressBar(
            card_content,
            width=300,
            height=4,
            progress_color=Colors.ACTION_GREEN,
            fg_color=Colors.CARD_BORDER,
            corner_radius=2,
        )
        self._progress_bar.pack(pady=(0, 16))
        self._progress_bar.configure(mode="indeterminate")
        self._progress_bar.start()

        # Badge de estado
        badge_frame = ctk.CTkFrame(card_content, fg_color="transparent")
        badge_frame.pack(pady=(0, 8))

        self._badge = StatusBadge(badge_frame, status="disconnected", label="Esperando bot...")
        self._badge.pack()

        # Texto de detalle
        self._detail_text = ctk.CTkLabel(
            card_content, text="",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
            wraplength=400,
            justify="center",
        )
        self._detail_text.pack(pady=(4, 0))

        # ── Card de timeout (oculta hasta que se necesite) ──
        self._timeout_card = ctk.CTkFrame(
            center,
            fg_color=Colors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Colors.WARNING,
        )
        # NO se hace pack aca — se muestra despues del timeout

        tc = ctk.CTkFrame(self._timeout_card, fg_color="transparent")
        tc.pack(padx=28, pady=24)

        # Icono de advertencia
        warn_icon = ctk.CTkFrame(
            tc, fg_color=Colors.WARNING_BG,
            corner_radius=16, width=36, height=36,
        )
        warn_icon.pack(pady=(0, 10))
        warn_icon.pack_propagate(False)
        ctk.CTkLabel(
            warn_icon, text="!",
            text_color=Colors.WARNING,
            font=(Fonts.FAMILY, 18, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            tc, text="La conexion esta tardando mucho",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 15, "bold"),
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            tc,
            text="Puedes desvincular la cuenta actual y reconectar\nescaneando un nuevo codigo QR.",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 13),
            justify="center",
        ).pack(pady=(0, 16))

        PrimaryButton(
            tc, text="Desvincular y reconectar con QR",
            command=self._on_logout, width=280,
        ).pack()

        # ── Wrapper del QR (oculto hasta despues del logout) ──
        self._qr_wrapper = ctk.CTkFrame(center, fg_color="transparent")
        # NO se hace pack aca

        qr_card = ctk.CTkFrame(
            self._qr_wrapper,
            fg_color=Colors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Colors.CARD_BORDER,
        )
        qr_card.pack(pady=(12, 10))

        qr_card_content = ctk.CTkFrame(qr_card, fg_color="transparent")
        qr_card_content.pack(padx=24, pady=20)

        ctk.CTkLabel(
            qr_card_content,
            text="Escanea el codigo QR",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 15, "bold"),
        ).pack(pady=(0, 12))

        qr_box = ctk.CTkFrame(
            qr_card_content, fg_color=Colors.BG_PRIMARY,
            corner_radius=8, width=220, height=220,
        )
        qr_box.pack()
        qr_box.pack_propagate(False)

        self._qr_label = ctk.CTkLabel(
            qr_box, text="Generando QR...",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 13),
        )
        self._qr_label.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self._qr_wrapper,
            text="Abre WhatsApp  >  Configuracion  >  Dispositivos vinculados\n"
                 ">  Vincular dispositivo  >  Escanea el codigo QR",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
            justify="center",
        ).pack(pady=(10, 0))

    # ── Actualizadores de UI ──────────────────────────────────

    def _set_status(self, msg: str, badge_status: str, detail: str = ""):
        try:
            if self._status_text and self._status_text.winfo_exists():
                self._status_text.configure(text=msg)
            if self._badge and self._badge.winfo_exists():
                self._badge.set_status(badge_status, msg)
            if self._detail_text and self._detail_text.winfo_exists():
                self._detail_text.configure(text=detail)
        except Exception:
            pass

    # ── Timer (cuenta segundos y activa timeout) ─────────────

    def _tick(self):
        if not self.active:
            return
        self.elapsed += 1

        # Mostrar card de logout despues del timeout
        if self.elapsed >= self.TIMEOUT_SECONDS and not self.logout_shown and self.phase == "waiting":
            self.logout_shown = True
            self.phase = "timeout"
            try:
                # Detener progress bar
                if self._progress_bar and self._progress_bar.winfo_exists():
                    self._progress_bar.stop()
                    self._progress_bar.configure(mode="determinate")
                    self._progress_bar.set(0)
                self._timeout_card.pack(pady=(16, 0))
            except Exception:
                pass

        self.after(1000, self._tick)

    # ── Polling de estado del bot ─────────────────────────────

    def _poll(self):
        if not self.active or self.phase == "done":
            return
        threading.Thread(target=self._poll_worker, daemon=True).start()

    def _poll_worker(self):
        try:
            if not self.wa_client.health_check():
                # Bot no responde aun
                self.after(0, lambda: self._set_status(
                    "Iniciando el bot...",
                    "disconnected",
                    "El bot de WhatsApp se esta iniciando, por favor espera"
                ))
            elif self.wa_client.is_whatsapp_connected():
                # Conectado correctamente
                self.phase = "done"
                self.active = False
                self.after(0, self._go_connected)
                return
            else:
                # Bot corriendo pero WhatsApp no vinculado
                self.after(0, lambda: self._set_status(
                    "Esperando cuenta vinculada...",
                    "warning",
                    "El bot esta corriendo pero no tiene cuenta de WhatsApp vinculada"
                ))
        except Exception:
            self.after(0, lambda: self._set_status("Conectando...", "disconnected", ""))

        # Siguiente ciclo
        if self.active and self.phase != "done":
            self.after(self.POLL_MS, self._poll)

    def _go_connected(self):
        """Transicion al dashboard cuando se confirma la conexion"""
        try:
            if self._progress_bar and self._progress_bar.winfo_exists():
                self._progress_bar.stop()
                self._progress_bar.configure(mode="determinate", progress_color=Colors.SUCCESS)
                self._progress_bar.set(1.0)
        except Exception:
            pass
        self._set_status("Conectado", "connected", "")
        self.after(600, self.on_connected)

    # ── Logout + reconexion con QR ────────────────────────────

    def _on_logout(self):
        """El usuario clickeo 'Desvincular y reconectar'"""
        self.phase = "qr"

        # Ocultar card de timeout
        try:
            self._timeout_card.pack_forget()
        except Exception:
            pass

        self._set_status("Desvinculando cuenta...", "disconnected", "")
        threading.Thread(target=self._do_logout, daemon=True).start()

    def _do_logout(self):
        """Llama al endpoint de logout del bot y espera a que reinicie"""
        try:
            self.wa_client.logout()
        except Exception as e:
            print(f"Error logout: {e}")

        # Esperar a que el bot elimine la sesion y se reinicie
        time.sleep(3)

        if self.active:
            self.after(0, self._show_qr)

    def _show_qr(self):
        """Muestra el frame del codigo QR y empezar a buscar"""
        self._set_status("Escanea el codigo QR", "disconnected", "")
        try:
            self._qr_wrapper.pack(pady=(8, 0))
        except Exception:
            pass
        self._poll_qr()

    # ── Polling del codigo QR ─────────────────────────────────

    def _poll_qr(self):
        if not self.active or self.phase != "qr":
            return
        threading.Thread(target=self._poll_qr_worker, daemon=True).start()

    def _poll_qr_worker(self):
        try:
            data = self.wa_client.get_qr_status()
            status = data.get("status", "error")

            if status == "connected":
                # Ya se escano el QR exitosamente
                self.phase = "done"
                self.active = False
                self.after(0, self._go_connected)
                return
            elif status == "waiting_scan":
                qr_str = data.get("qr")
                if qr_str:
                    self.after(0, lambda q=qr_str: self._render_qr(q))
            elif status == "initializing":
                self.after(0, lambda: self._set_qr_text(
                    "Inicializando...\nEsto puede tomar unos segundos"
                ))
            else:
                self.after(0, lambda: self._set_qr_text("Esperando QR..."))

        except Exception:
            self.after(0, lambda: self._set_qr_text("Conectando con el bot..."))

        # Siguiente ciclo
        if self.active and self.phase == "qr":
            self.after(3000, self._poll_qr)

    def _set_qr_text(self, text: str):
        try:
            if self._qr_label and self._qr_label.winfo_exists():
                self._qr_label.configure(text=text, image="")
        except Exception:
            pass

    def _render_qr(self, qr_string: str):
        """Genera y muestra la imagen del codigo QR"""
        try:
            if not self._qr_label or not self._qr_label.winfo_exists():
                return

            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(qr_string)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((200, 200))
            photo = ImageTk.PhotoImage(img)

            self._qr_label.configure(image=photo, text="")
            self._qr_label.image = photo  # Mantener referencia para que no se destruya
        except Exception as e:
            print(f"Error generando QR: {e}")
