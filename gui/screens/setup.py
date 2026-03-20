# Setup Wizard - Asistente de configuracion inicial (conectado con core real)
import customtkinter as ctk
import threading
import qrcode
from PIL import Image, ImageTk
from io import BytesIO
from typing import List, Dict
from ..styles import Colors, Fonts
from ..components import (
    Card, PrimaryButton, SecondaryButton, SuccessButton,
    ProgressSteps, LabeledInput, LabeledSelect, StatusBadge
)

# Importar modulos core
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core import get_whatsapp_client, get_trt_client, get_config_manager, SiteConfig


class SetupWizard(ctk.CTkFrame):
    """Asistente de configuracion paso a paso - conectado con APIs reales"""

    STEPS = ["WhatsApp", "Configuracion", "Centros", "Umbrales", "Finalizar"]

    def __init__(self, master, on_back: callable, on_finish: callable, **kwargs):
        super().__init__(master, fg_color=Colors.DARK_BG, **kwargs)

        self.on_back = on_back
        self.on_finish = on_finish
        self.current_step = 0

        # Clientes
        self.wa_client = get_whatsapp_client()
        self.trt_client = get_trt_client()
        self.config_manager = get_config_manager()

        # Datos de configuracion
        self.config_data = {
            "trt_url": "http://192.168.55.79",
            "poll_seconds": "10",
            "realert_minutes": "30",
        }

        # Datos cargados de las APIs
        self.available_centers: List[Dict] = []
        self.whatsapp_groups: List[Dict] = []
        self.selected_centers: List[Dict] = []
        self.center_configs: Dict[str, Dict] = {}

        # Conjunto de IDs de centros seleccionados (persiste durante filtrados)
        self.selected_center_ids: set = set()

        # Estado de WhatsApp
        self.wa_status = "disconnected"
        self.wa_phone = None
        self.qr_label = None
        self.status_badge = None
        self.polling_qr = False
        self.widget_exists = True  # Flag para saber si los widgets existen

        # Widgets para guardar referencias
        self.center_checkboxes = {}
        self.threshold_inputs = {}
        self.group_selects = {}

        # Referencias a inputs que necesitan persistir entre pasos
        self.url_input = None
        self.poll_input = None
        self.realert_input = None

        self._create_widgets()

        # Cargar centros automáticamente al iniciar
        self._load_centers_async()

    def _create_widgets(self):
        # Progress steps
        self.progress = ProgressSteps(self, steps=self.STEPS, current_step=0)
        self.progress.pack(pady=40)

        # Contenedor del contenido (sin scroll, cada pantalla individual tiene su propio scroll)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=40)

        # Botones de navegacion
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=40, pady=20)

        self.back_btn = SecondaryButton(
            self.nav_frame,
            text="Anterior",
            command=self._prev_step,
            width=150,
        )
        self.back_btn.pack(side="left")

        self.next_btn = PrimaryButton(
            self.nav_frame,
            text="Siguiente",
            command=self._next_step,
            width=150,
        )
        self.next_btn.pack(side="right")

        # Mostrar primer paso
        self._show_step()

    def _load_centers_async(self):
        """Carga los centros automáticamente en background"""
        def load():
            try:
                # Intentar conectar al TRT con la URL por defecto
                if self.trt_client.test_connection():
                    centers = self.trt_client.get_available_centers()
                    self.available_centers = [
                        {
                            "name": c.name,
                            "referer_id": c.referer_id,
                            "db_name": c.db_name,
                            "op_code": c.op_code,
                            "cd_code": c.cd_code,
                        }
                        for c in centers
                    ]
            except Exception as e:
                print(f"Error cargando centros: {e}")

        threading.Thread(target=load, daemon=True).start()

    def _show_step(self):
        """Muestra el paso actual"""
        # Guardar valores de inputs antes de destruirlos
        self._save_input_values()

        # Limpiar contenido
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Resetear referencias a widgets del paso anterior
        self.status_badge = None
        self.qr_label = None

        # Actualizar progress
        self.progress.set_step(self.current_step)

        # Actualizar botones
        self.back_btn.configure(text="Volver" if self.current_step == 0 else "Anterior")

        if self.current_step == len(self.STEPS) - 1:
            self.next_btn.pack_forget()
        else:
            self.next_btn.pack(side="right")
            self.next_btn.configure(text="Siguiente", state="normal")

        # El paso de config (1) maneja su propio estado de botón siguiente

        # Mostrar contenido del paso
        step_methods = [
            self._step_whatsapp,
            self._step_config,
            self._step_centers,
            self._step_thresholds,
            self._step_finish,
        ]
        step_methods[self.current_step]()

    def _validate_current_step(self) -> bool:
        """Valida el paso actual antes de avanzar"""
        # Paso 3: Umbrales - validar que todos los centros tengan umbral lateral y grupo
        if self.current_step == 3:
            errors = []
            for center in self.selected_centers:
                ref_id = center["referer_id"]
                inputs = self.threshold_inputs.get(ref_id, {})
                group_select = self.group_selects.get(ref_id)

                # Validar umbral lateral (obligatorio)
                lateral = inputs.get("lateral")
                if not lateral or not lateral.get().strip():
                    errors.append(f"{center['name']}: Falta el umbral lateral (obligatorio)")

                # Validar que se haya seleccionado un grupo
                if group_select:
                    selected_group = group_select.get()
                    if not selected_group or selected_group == "Seleccionar grupo..." or selected_group.startswith("(Sin grupos"):
                        errors.append(f"{center['name']}: Debes seleccionar un grupo de WhatsApp")

            if errors:
                # Mostrar errores
                error_msg = "\n\n".join(errors[:3])  # Mostrar máximo 3 errores
                if len(errors) > 3:
                    error_msg += f"\n\n... y {len(errors) - 3} error(es) más"

                self._show_validation_error("Configuración incompleta", error_msg)
                return False

        return True

    def _show_validation_error(self, title: str, message: str):
        """Muestra un error de validación"""
        try:
            # Crear diálogo de error
            error_dialog = ctk.CTkToplevel(self)
            error_dialog.title(title)
            error_dialog.geometry("500x350")
            error_dialog.resizable(False, False)
            error_dialog.configure(fg_color=Colors.DARK_BG)

            # Centrar en pantalla
            error_dialog.update_idletasks()
            x = (error_dialog.winfo_screenwidth() // 2) - (500 // 2)
            y = (error_dialog.winfo_screenheight() // 2) - (350 // 2)
            error_dialog.geometry(f"500x350+{x}+{y}")

            # Modal
            error_dialog.transient(self)
            error_dialog.grab_set()

            # Contenido
            container = ctk.CTkFrame(error_dialog, fg_color=Colors.DARK_CARD, corner_radius=12)
            container.pack(fill="both", expand=True, padx=20, pady=20)

            # Icono de error
            icon_frame = ctk.CTkFrame(
                container,
                fg_color=Colors.ERROR_BG,
                corner_radius=24,
                width=48,
                height=48
            )
            icon_frame.pack(pady=(20, 10))
            icon_frame.pack_propagate(False)

            ctk.CTkLabel(
                icon_frame,
                text="!",
                text_color=Colors.ERROR,
                font=(Fonts.FAMILY, 24, "bold")
            ).place(relx=0.5, rely=0.5, anchor="center")

            # Título
            ctk.CTkLabel(
                container,
                text=title,
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 18, "bold")
            ).pack(pady=(10, 20))

            # Mensaje con scroll
            message_frame = ctk.CTkScrollableFrame(
                container,
                fg_color=Colors.DARK_BG,
                corner_radius=8,
                height=150
            )
            message_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

            ctk.CTkLabel(
                message_frame,
                text=message,
                text_color=Colors.TEXT_SECONDARY,
                font=(Fonts.FAMILY, 13),
                wraplength=420,
                justify="left",
                anchor="w"
            ).pack(padx=12, pady=12)

            # Botón cerrar
            from ..components import PrimaryButton
            PrimaryButton(
                container,
                text="Entendido",
                command=lambda: (error_dialog.grab_release(), error_dialog.destroy())
            ).pack(pady=(0, 20))

        except Exception as e:
            print(f"Error mostrando diálogo de validación: {e}")

    def _next_step(self):
        # Validar antes de avanzar
        if not self._validate_current_step():
            return

        # Guardar datos del paso actual
        self._save_current_step_data()

        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self._show_step()

    def _prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step()
        else:
            self.polling_qr = False
            self.widget_exists = False
            self.on_back()

    def _save_input_values(self):
        """Guarda los valores de los inputs antes de destruir los widgets"""
        try:
            if self.url_input and self.url_input.winfo_exists():
                self.config_data["trt_url"] = self.url_input.get()
        except Exception:
            pass

        try:
            if self.poll_input and self.poll_input.winfo_exists():
                self.config_data["poll_seconds"] = self.poll_input.get()
        except Exception:
            pass

        try:
            if self.realert_input and self.realert_input.winfo_exists():
                self.config_data["realert_minutes"] = self.realert_input.get()
        except Exception:
            pass

    def _save_current_step_data(self):
        """Guarda los datos del paso actual"""
        if self.current_step == 2:  # Centros
            # Actualizar conjunto de IDs seleccionados basándose en checkboxes visibles
            for center in self.available_centers:
                ref_id = center.get("referer_id")
                cb = self.center_checkboxes.get(ref_id)

                if cb:  # Si el checkbox existe (está visible)
                    if cb.get():
                        self.selected_center_ids.add(ref_id)
                    else:
                        self.selected_center_ids.discard(ref_id)

            # Crear lista final de centros seleccionados basándose en los IDs
            self.selected_centers = [
                c for c in self.available_centers
                if c.get("referer_id") in self.selected_center_ids
            ]

        elif self.current_step == 3:  # Umbrales
            for center in self.selected_centers:
                ref_id = center.get("referer_id")
                inputs = self.threshold_inputs.get(ref_id, {})
                group_select = self.group_selects.get(ref_id)

                lateral = inputs.get("lateral")
                trasera = inputs.get("trasera")
                interna = inputs.get("interna")

                self.center_configs[ref_id] = {
                    "lateral": lateral.get() if lateral else None,
                    "trasera": trasera.get() if trasera else None,
                    "interna": interna.get() if interna else None,
                    "group": group_select.get() if group_select else "",
                }

    # ========== PASO 1: WhatsApp ==========
    def _step_whatsapp(self):
        container = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent",
            scrollbar_button_color=Colors.DARK_BORDER,
            scrollbar_button_hover_color=Colors.DARK_CARD_HOVER
        )
        container.pack(expand=True, fill="both")

        ctk.CTkLabel(
            container,
            text="Vincular WhatsApp",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="Escanea el codigo QR con el telefono que usaras para el bot",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
        ).pack(pady=(0, 32))

        # QR Code frame
        self.qr_frame = ctk.CTkFrame(
            container,
            fg_color=Colors.TEXT_PRIMARY,
            corner_radius=12,
            width=250,
            height=250,
        )
        self.qr_frame.pack(pady=20)
        self.qr_frame.pack_propagate(False)

        self.qr_label = ctk.CTkLabel(
            self.qr_frame,
            text="Conectando con el bot...",
            text_color=Colors.DARK_BG,
            font=(Fonts.FAMILY, 12),
        )
        self.qr_label.place(relx=0.5, rely=0.5, anchor="center")

        # Instrucciones
        instructions = Card(container)
        instructions.pack(fill="x", pady=24, padx=100)

        ctk.CTkLabel(
            instructions,
            text="""1. Abre WhatsApp en tu telefono
2. Ve a Configuracion > Dispositivos vinculados
3. Toca en "Vincular un dispositivo"
4. Escanea el codigo QR que aparece arriba""",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 13),
            justify="left",
        ).pack(padx=20, pady=16)

        # Status badge
        self.status_badge = StatusBadge(container, status="disconnected", label="Esperando conexion...")
        self.status_badge.pack(pady=16)

        # Iniciar polling del QR
        self.polling_qr = True
        self._poll_qr_status()

    def _poll_qr_status(self):
        """Consulta el estado del QR periodicamente"""
        if not self.polling_qr or not self.widget_exists:
            return

        def check():
            try:
                qr_data = self.wa_client.get_qr_status()
                status = qr_data.get("status", "error")
                print(f"QR Status: {status}")  # Debug

                if status == "connected":
                    self.wa_status = "connected"
                    self.wa_phone = qr_data.get("phone", "")
                    if self.widget_exists:
                        self.after(0, lambda: self._update_wa_connected())
                    return

                elif status == "waiting_scan":
                    qr_string = qr_data.get("qr")
                    if qr_string and self.widget_exists:
                        self.after(0, lambda q=qr_string: self._show_qr_code(q))
                    elif self.widget_exists:
                        self.after(0, lambda: self._update_qr_label("Esperando QR del bot..."))

                elif status == "initializing":
                    if self.widget_exists:
                        self.after(0, lambda: self._update_qr_label("Inicializando WhatsApp...\n\nEsto puede tomar unos segundos"))
                        self.after(0, lambda: self._update_wa_status("Bot inicializando..."))

                elif status == "error":
                    error_msg = qr_data.get("error", "Error desconocido")
                    if self.widget_exists:
                        self.after(0, lambda e=error_msg: self._update_qr_label(f"Conectando...\n\n{e[:30]}"))
                        self.after(0, lambda: self._update_wa_status("Conectando con el bot..."))

                else:
                    if self.widget_exists:
                        self.after(0, lambda: self._update_qr_label("Esperando conexion con bot..."))
                        self.after(0, lambda: self._update_wa_status("Conectando con el bot de WhatsApp..."))

            except Exception as e:
                print(f"Error en poll_qr: {e}")  # Debug
                if self.widget_exists:
                    self.after(0, lambda: self._update_qr_label(f"Conectando...\n\nEsperando bot"))
                    self.after(0, lambda: self._update_wa_status(f"Esperando bot..."))

            # Continuar polling
            if self.polling_qr and self.widget_exists:
                self.after(3000, self._poll_qr_status)  # 3 segundos de intervalo

        threading.Thread(target=check, daemon=True).start()

    def _update_qr_label(self, text: str):
        """Actualiza el texto del label del QR"""
        try:
            if self.qr_label and self.qr_label.winfo_exists():
                self.qr_label.configure(text=text, image="")
        except Exception:
            pass

    def _show_qr_code(self, qr_string: str):
        """Muestra el codigo QR"""
        try:
            if not self.qr_label or not self.qr_label.winfo_exists():
                return

            # Generar imagen QR
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(qr_string)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Convertir a formato tkinter
            img = img.resize((220, 220))
            photo = ImageTk.PhotoImage(img)

            self.qr_label.configure(image=photo, text="")
            self.qr_label.image = photo  # Mantener referencia

            self._update_wa_status("Escanea el codigo QR")

        except Exception as e:
            try:
                if self.qr_label and self.qr_label.winfo_exists():
                    self.qr_label.configure(text=f"Error generando QR:\n{e}", image="")
            except Exception:
                pass

    def _update_wa_status(self, message: str):
        """Actualiza el mensaje de estado"""
        try:
            if self.status_badge and self.status_badge.winfo_exists():
                self.status_badge.set_status("disconnected", message)
        except Exception:
            pass  # Widget fue destruido

    def _update_wa_connected(self):
        """Actualiza la UI cuando WhatsApp se conecta"""
        self.polling_qr = False
        self.wa_status = "connected"

        try:
            if self.qr_label and self.qr_label.winfo_exists():
                # Mostrar icono de check verde y mensaje de éxito
                self.qr_label.configure(
                    text=f"✓\n\nWhatsApp Conectado\n\n{self.wa_phone or 'Vinculado correctamente'}",
                    image="",
                    text_color=Colors.SUCCESS,
                    font=(Fonts.FAMILY, 18, "bold"),
                )
        except Exception:
            pass

        try:
            if self.status_badge and self.status_badge.winfo_exists():
                phone_display = self.wa_phone or "Conectado"
                self.status_badge.set_status("connected", f"WhatsApp: {phone_display}")
        except Exception:
            pass

        # Cargar grupos de WhatsApp
        self._load_whatsapp_groups()

    def _load_whatsapp_groups(self):
        """Carga los grupos de WhatsApp"""
        def load():
            try:
                groups = self.wa_client.get_groups()
                self.whatsapp_groups = [{"id": g.id, "name": g.name} for g in groups]
                print(f"Grupos cargados: {len(self.whatsapp_groups)}")
            except Exception as e:
                print(f"Error cargando grupos: {e}")

        threading.Thread(target=load, daemon=True).start()

    def _refresh_whatsapp_groups(self):
        """Refresca la lista de grupos de WhatsApp"""
        try:
            if hasattr(self, 'groups_status_label') and self.groups_status_label.winfo_exists():
                self.groups_status_label.configure(text="Cargando grupos...", text_color=Colors.TEXT_MUTED)
        except Exception:
            pass

        def load():
            try:
                groups = self.wa_client.get_groups()
                self.whatsapp_groups = [{"id": g.id, "name": g.name} for g in groups]
                print(f"Grupos cargados: {len(self.whatsapp_groups)}")

                def update_ui():
                    try:
                        if hasattr(self, 'groups_status_label') and self.groups_status_label.winfo_exists():
                            if self.whatsapp_groups:
                                self.groups_status_label.configure(
                                    text=f"{len(self.whatsapp_groups)} grupos encontrados",
                                    text_color=Colors.SUCCESS
                                )
                                # Actualizar los selectores de grupo
                                self._update_group_selectors()
                            else:
                                self.groups_status_label.configure(
                                    text="No se encontraron grupos. Verifica que WhatsApp este conectado.",
                                    text_color=Colors.WARNING
                                )
                    except Exception:
                        pass

                self.after(0, update_ui)

            except Exception as e:
                print(f"Error cargando grupos: {e}")
                def show_error():
                    try:
                        if hasattr(self, 'groups_status_label') and self.groups_status_label.winfo_exists():
                            self.groups_status_label.configure(
                                text=f"Error: {str(e)[:30]}",
                                text_color=Colors.ERROR
                            )
                    except Exception:
                        pass
                self.after(0, show_error)

        threading.Thread(target=load, daemon=True).start()

    def _update_group_selectors(self):
        """Actualiza las opciones de los selectores de grupo"""
        if not self.whatsapp_groups:
            return

        group_options = [g['name'] for g in self.whatsapp_groups]

        for ref_id, select in self.group_selects.items():
            try:
                if select and select.winfo_exists():
                    # Actualizar opciones del selector
                    select.set_options(group_options)
            except Exception:
                pass

    # ========== PASO 2: Configuracion General ==========
    def _step_config(self):
        # Deshabilitar siguiente hasta probar conexión
        self.trt_connection_tested = False
        self.next_btn.configure(state="disabled")

        container = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent",
            scrollbar_button_color=Colors.DARK_BORDER,
            scrollbar_button_hover_color=Colors.DARK_CARD_HOVER
        )
        container.pack(expand=True, fill="both", padx=100)

        ctk.CTkLabel(
            container,
            text="Configuracion General",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="Configura los parametros generales del sistema",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
        ).pack(pady=(0, 32))

        card = Card(container)
        card.pack(fill="x")

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=20)

        self.url_input = LabeledInput(
            form,
            label="URL del servidor TRT",
            placeholder="http://192.168.55.79",
            value=self.config_data["trt_url"],
        )
        self.url_input.pack(fill="x", pady=8)

        self.poll_input = LabeledInput(
            form,
            label="Intervalo de consulta (segundos)",
            placeholder="10",
            value=self.config_data["poll_seconds"],
        )
        self.poll_input.pack(fill="x", pady=8)

        realert_frame = ctk.CTkFrame(form, fg_color="transparent")
        realert_frame.pack(fill="x", pady=8)

        self.realert_input = LabeledInput(
            realert_frame,
            label="Reenvio de alertas (minutos)",
            placeholder="30",
            value=self.config_data["realert_minutes"],
        )
        self.realert_input.pack(fill="x")

        ctk.CTkLabel(
            realert_frame,
            text="Si un camion sigue excediendo el tiempo, la alerta se reenviara cada este intervalo",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", pady=(4, 0))

        # Boton probar conexion (OBLIGATORIO)
        test_frame = ctk.CTkFrame(form, fg_color="transparent")
        test_frame.pack(fill="x", pady=(16, 0))

        self.test_status = ctk.CTkLabel(
            test_frame,
            text="Debes probar la conexion para continuar",
            text_color=Colors.WARNING,
            font=(Fonts.FAMILY, 12),
        )
        self.test_status.pack(side="left")

        self.test_btn = PrimaryButton(
            test_frame,
            text="Probar conexion al TRT",
            command=self._test_trt_connection,
            size="sm",
        )
        self.test_btn.pack(side="right")

    def _test_trt_connection(self):
        """Prueba la conexion al servidor TRT"""
        try:
            if hasattr(self, 'test_status') and self.test_status.winfo_exists():
                self.test_status.configure(text="Probando conexion...", text_color=Colors.TEXT_MUTED)
            if hasattr(self, 'test_btn') and self.test_btn.winfo_exists():
                self.test_btn.configure(state="disabled")
        except Exception:
            pass

        def test():
            try:
                url = self.url_input.get() if self.url_input and self.url_input.winfo_exists() else self.config_data["trt_url"]
            except Exception:
                url = self.config_data["trt_url"]

            self.trt_client = get_trt_client(url)
            success = self.trt_client.test_connection()

            def update_ui():
                try:
                    if hasattr(self, 'test_btn') and self.test_btn.winfo_exists():
                        self.test_btn.configure(state="normal")

                    if success:
                        self.config_data["trt_url"] = url
                        self.trt_connection_tested = True

                        if hasattr(self, 'test_status') and self.test_status.winfo_exists():
                            self.test_status.configure(
                                text="Conexion exitosa - Cargando centros...",
                                text_color=Colors.SUCCESS
                            )

                        # Habilitar boton siguiente
                        if hasattr(self, 'next_btn') and self.next_btn.winfo_exists():
                            self.next_btn.configure(state="normal")

                        # Cargar centros
                        self._load_centers()
                    else:
                        self.trt_connection_tested = False
                        if hasattr(self, 'test_status') and self.test_status.winfo_exists():
                            self.test_status.configure(
                                text="No se pudo conectar. Verifica la URL.",
                                text_color=Colors.ERROR
                            )
                        if hasattr(self, 'next_btn') and self.next_btn.winfo_exists():
                            self.next_btn.configure(state="disabled")
                except Exception:
                    pass

            self.after(0, update_ui)

        threading.Thread(target=test, daemon=True).start()

    def _load_centers(self):
        """Carga los centros desde el TRT"""
        def load():
            try:
                centers = self.trt_client.get_available_centers()
                self.available_centers = [
                    {
                        "name": c.name,
                        "referer_id": c.referer_id,
                        "db_name": c.db_name,
                        "op_code": c.op_code,
                        "cd_code": c.cd_code,
                    }
                    for c in centers
                ]

                # Actualizar status en la UI
                def update_status():
                    try:
                        if hasattr(self, 'test_status') and self.test_status.winfo_exists():
                            if self.available_centers:
                                self.test_status.configure(
                                    text=f"Conexion OK - {len(self.available_centers)} centros encontrados",
                                    text_color=Colors.SUCCESS
                                )
                            else:
                                self.test_status.configure(
                                    text="Conexion OK - No se encontraron centros",
                                    text_color=Colors.WARNING
                                )
                    except Exception:
                        pass

                self.after(0, update_status)

            except Exception as e:
                print(f"Error cargando centros: {e}")

        threading.Thread(target=load, daemon=True).start()

    # ========== PASO 3: Seleccionar Centros ==========
    def _step_centers(self):
        # Los valores ya fueron guardados en _save_input_values() al cambiar de paso

        container = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=50)

        ctk.CTkLabel(
            container,
            text="Seleccionar Centros",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="Selecciona los centros que deseas monitorear",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
            wraplength=500,
        ).pack(pady=(0, 16))

        # Barra de búsqueda y botón refrescar
        search_frame = ctk.CTkFrame(container, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 16))

        # Campo de búsqueda
        search_input_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        search_input_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            search_input_frame,
            text="🔍",
            font=(Fonts.FAMILY, 16),
        ).pack(side="left", padx=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_input_frame,
            placeholder_text="Buscar centro por nombre...",
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14),
            height=36,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_centers())

        # Botón refrescar
        SecondaryButton(
            search_frame,
            text="Refrescar",
            command=lambda: self._refresh_centers(container),
            size="sm",
        ).pack(side="right", padx=(12, 0))

        # Status de centros
        self.centers_status = ctk.CTkLabel(
            container,
            text=f"{len(self.available_centers)} centros encontrados" if self.available_centers else "Cargando centros...",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        )
        self.centers_status.pack(anchor="w", pady=(0, 12))

        self.centers_container = ctk.CTkFrame(container, fg_color="transparent")
        self.centers_container.pack(fill="x")

        # Si no hay centros cargados, intentar cargar automáticamente
        if not self.available_centers:
            self._refresh_centers(container)
        else:
            self._render_centers()

    def _refresh_centers(self, container):
        """Refresca la lista de centros"""
        try:
            if hasattr(self, 'centers_status') and self.centers_status.winfo_exists():
                self.centers_status.configure(text="Cargando centros desde TRT...")
        except Exception:
            pass

        def refresh():
            try:
                # Actualizar cliente TRT con la URL configurada
                self.trt_client = get_trt_client(self.config_data["trt_url"])

                centers = self.trt_client.get_available_centers()
                self.available_centers = [
                    {
                        "name": c.name,
                        "referer_id": c.referer_id,
                        "db_name": c.db_name,
                        "op_code": c.op_code,
                        "cd_code": c.cd_code,
                    }
                    for c in centers
                ]

                def update_ui():
                    try:
                        self._render_centers()
                        if hasattr(self, 'centers_status') and self.centers_status.winfo_exists():
                            self.centers_status.configure(
                                text=f"{len(self.available_centers)} centros encontrados"
                            )
                    except Exception:
                        pass

                self.after(0, update_ui)

            except Exception as e:
                def show_error():
                    try:
                        if hasattr(self, 'centers_status') and self.centers_status.winfo_exists():
                            self.centers_status.configure(
                                text=f"Error: {str(e)[:30]}",
                                text_color=Colors.ERROR
                            )
                    except Exception:
                        pass
                self.after(0, show_error)

        threading.Thread(target=refresh, daemon=True).start()

    def _filter_centers(self):
        """Filtra los centros según el texto de búsqueda"""
        self._render_centers()

    def _on_center_checkbox_changed(self, ref_id: str):
        """Callback cuando se marca/desmarca un checkbox de centro"""
        try:
            cb = self.center_checkboxes.get(ref_id)
            if cb and cb.winfo_exists():
                if cb.get():
                    self.selected_center_ids.add(ref_id)
                else:
                    self.selected_center_ids.discard(ref_id)
        except Exception as e:
            print(f"Error en checkbox callback: {e}")

    def _render_centers(self):
        """Renderiza la lista de centros (con filtro si hay texto de búsqueda)"""
        # Guardar estado de checkboxes antes de destruir widgets
        # Actualizar el conjunto persistente de IDs seleccionados
        try:
            for ref_id, checkbox in self.center_checkboxes.items():
                try:
                    if checkbox and checkbox.winfo_exists():
                        if checkbox.get():
                            self.selected_center_ids.add(ref_id)
                        else:
                            self.selected_center_ids.discard(ref_id)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if not hasattr(self, 'centers_container') or not self.centers_container.winfo_exists():
                return

            # Destruir widgets
            for widget in self.centers_container.winfo_children():
                widget.destroy()
        except Exception:
            return

        self.center_checkboxes = {}

        if not self.available_centers:
            ctk.CTkLabel(
                self.centers_container,
                text="No se encontraron centros. Verifica la conexion al TRT.",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 14),
            ).pack(pady=20)
            return

        # Obtener texto de búsqueda
        search_text = ""
        try:
            if hasattr(self, 'search_entry') and self.search_entry.winfo_exists():
                search_text = self.search_entry.get().lower().strip()
        except Exception:
            pass

        # Filtrar centros
        filtered_centers = self.available_centers
        if search_text:
            filtered_centers = [
                c for c in self.available_centers
                if search_text in c['name'].lower()
            ]

        # Actualizar contador
        try:
            if hasattr(self, 'centers_status') and self.centers_status.winfo_exists():
                if search_text:
                    self.centers_status.configure(
                        text=f"{len(filtered_centers)} de {len(self.available_centers)} centros"
                    )
                else:
                    self.centers_status.configure(
                        text=f"{len(self.available_centers)} centros encontrados"
                    )
        except Exception:
            pass

        if not filtered_centers:
            ctk.CTkLabel(
                self.centers_container,
                text=f"No se encontraron centros que coincidan con '{search_text}'",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 14),
            ).pack(pady=20)
            return

        for center in filtered_centers:
            card = Card(self.centers_container, hover=True)
            card.pack(fill="x", pady=6)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=20, pady=16)

            # Checkbox con callback para actualizar selecciones en tiempo real
            ref_id = center["referer_id"]
            cb = ctk.CTkCheckBox(
                content,
                text="",
                width=24,
                height=24,
                checkbox_width=24,
                checkbox_height=24,
                fg_color=Colors.CCU_GREEN,
                hover_color=Colors.CCU_GREEN_HOVER,
                border_color=Colors.CARD_BORDER,
                command=lambda r=ref_id: self._on_center_checkbox_changed(r)
            )
            cb.pack(side="left")

            # Restaurar estado desde el conjunto persistente
            if ref_id in self.selected_center_ids:
                cb.select()

            self.center_checkboxes[ref_id] = cb

            # Info
            info_frame = ctk.CTkFrame(content, fg_color="transparent")
            info_frame.pack(side="left", padx=(16, 0), fill="x", expand=True)

            ctk.CTkLabel(
                info_frame,
                text=center["name"],
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 15, "bold"),
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info_frame,
                text=f"ID: {center['referer_id']} | DB: {center['db_name']}",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 12),
                anchor="w",
            ).pack(anchor="w")

    # ========== PASO 4: Configurar Umbrales ==========
    def _step_thresholds(self):
        # Guardar centros seleccionados
        self._save_current_step_data()

        container = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=50)
        self.thresholds_container = container  # Guardar referencia

        ctk.CTkLabel(
            container,
            text="Configurar Umbrales",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="Define los tiempos maximos permitidos para cada tipo de descarga",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
        ).pack(pady=(0, 16))

        # Status de grupos y botón refrescar
        groups_status_frame = ctk.CTkFrame(container, fg_color="transparent")
        groups_status_frame.pack(fill="x", pady=(0, 16))

        self.groups_status_label = ctk.CTkLabel(
            groups_status_frame,
            text=f"{len(self.whatsapp_groups)} grupos cargados" if self.whatsapp_groups else "Cargando grupos de WhatsApp...",
            text_color=Colors.TEXT_MUTED if self.whatsapp_groups else Colors.WARNING,
            font=(Fonts.FAMILY, 12),
        )
        self.groups_status_label.pack(side="left")

        SecondaryButton(
            groups_status_frame,
            text="Refrescar grupos",
            command=self._refresh_whatsapp_groups,
            size="sm",
        ).pack(side="right")

        # Si no hay grupos, cargarlos automáticamente
        if not self.whatsapp_groups:
            self._refresh_whatsapp_groups()

        self.threshold_inputs = {}
        self.group_selects = {}

        # Opciones de grupos
        group_options = [f"{g['name']}" for g in self.whatsapp_groups] if self.whatsapp_groups else ["(Sin grupos - presiona Refrescar)"]

        if not self.selected_centers:
            ctk.CTkLabel(
                container,
                text="No hay centros seleccionados. Vuelve al paso anterior.",
                text_color=Colors.WARNING,
                font=(Fonts.FAMILY, 14),
            ).pack(pady=20)
            return

        for center in self.selected_centers:
            ref_id = center["referer_id"]
            card = Card(container)
            card.pack(fill="x", pady=8)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=20, pady=20)

            ctk.CTkLabel(
                content,
                text=center["name"],
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 16, "bold"),
            ).pack(anchor="w", pady=(0, 16))

            # Selector de grupo
            group_select = LabeledSelect(
                content,
                label="Grupo de WhatsApp para alertas",
                options=group_options,
                placeholder="Seleccionar grupo...",
            )
            group_select.pack(fill="x", pady=(0, 16))
            self.group_selects[ref_id] = group_select

            # Umbrales
            thresholds_frame = ctk.CTkFrame(content, fg_color="transparent")
            thresholds_frame.pack(fill="x")
            thresholds_frame.grid_columnconfigure((0, 1, 2), weight=1)

            lateral_input = LabeledInput(
                thresholds_frame,
                label="Umbral Lateral (min) *",
                placeholder="105",
            )
            lateral_input.grid(row=0, column=0, padx=(0, 8), sticky="ew")

            trasera_input = LabeledInput(
                thresholds_frame,
                label="Umbral Trasera (min)",
                placeholder="Opcional",
            )
            trasera_input.grid(row=0, column=1, padx=4, sticky="ew")

            interna_input = LabeledInput(
                thresholds_frame,
                label="Umbral Interna (min)",
                placeholder="Opcional",
            )
            interna_input.grid(row=0, column=2, padx=(8, 0), sticky="ew")

            self.threshold_inputs[ref_id] = {
                "lateral": lateral_input,
                "trasera": trasera_input,
                "interna": interna_input,
            }

            ctk.CTkLabel(
                content,
                text="* El umbral lateral es obligatorio. Trasera e interna son opcionales.",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 11),
            ).pack(anchor="w", pady=(8, 0))

    # ========== PASO 5: Finalizar ==========
    def _step_finish(self):
        container = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent",
            scrollbar_button_color=Colors.DARK_BORDER,
            scrollbar_button_hover_color=Colors.DARK_CARD_HOVER
        )
        container.pack(expand=True, fill="both")

        # Icono de exito
        success_icon = ctk.CTkFrame(
            container,
            fg_color=Colors.SUCCESS_BG,
            corner_radius=40,
            width=80,
            height=80,
        )
        success_icon.pack(pady=(0, 24))
        success_icon.pack_propagate(False)

        ctk.CTkLabel(
            success_icon,
            text="✓",
            text_color=Colors.SUCCESS,
            font=(Fonts.FAMILY, 40, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            container,
            text="Configuracion Completa",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="El sistema esta listo para comenzar a monitorear",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 14),
        ).pack(pady=(0, 32))

        # Resumen
        card = Card(container)
        card.pack(fill="x", padx=100)

        summary = ctk.CTkFrame(card, fg_color="transparent")
        summary.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            summary,
            text="RESUMEN DE CONFIGURACION",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 11),
        ).pack(anchor="w", pady=(0, 12))

        summary_items = [
            ("Centros configurados", str(len(self.selected_centers))),
            ("Intervalo de consulta", f"{self.config_data['poll_seconds']} segundos"),
            ("Reenvio de alertas", f"{self.config_data['realert_minutes']} minutos"),
        ]

        for label, value in summary_items:
            row = ctk.CTkFrame(summary, fg_color="transparent")
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(row, text=label, text_color=Colors.TEXT_MUTED, font=(Fonts.FAMILY, 13)).pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=Colors.TEXT_PRIMARY, font=(Fonts.FAMILY, 13, "bold")).pack(side="right")

        # WhatsApp status
        wa_row = ctk.CTkFrame(summary, fg_color="transparent")
        wa_row.pack(fill="x", pady=4)

        ctk.CTkLabel(wa_row, text="WhatsApp", text_color=Colors.TEXT_MUTED, font=(Fonts.FAMILY, 13)).pack(side="left")

        wa_status = "connected" if self.wa_status == "connected" else "disconnected"
        wa_label = f"Conectado: {self.wa_phone}" if self.wa_status == "connected" else "No conectado"
        StatusBadge(wa_row, status=wa_status, label=wa_label).pack(side="right")

        # Boton guardar e iniciar
        PrimaryButton(
            container,
            text="Guardar y comenzar",
            command=self._save_and_finish,
            size="lg",
            width=250,
            height=50,
        ).pack(pady=32)

    def _save_and_finish(self):
        """Guarda la configuracion y termina"""
        # Crear configuracion
        from core import AppConfig, SiteConfig

        config = AppConfig(
            base_url=self.config_data["trt_url"],
            poll_seconds=int(self.config_data["poll_seconds"]),
            realert_minutes=int(self.config_data["realert_minutes"]),
            sites=[]
        )

        for center in self.selected_centers:
            ref_id = center["referer_id"]
            # Usar los valores guardados en center_configs (guardados al pasar al paso 5)
            center_config = self.center_configs.get(ref_id, {})

            # Obtener grupo seleccionado desde los valores guardados
            group_name = center_config.get("group", "")
            whatsapp_group_id = ""
            for g in self.whatsapp_groups:
                if g["name"] == group_name:
                    whatsapp_group_id = g["id"]
                    break

            # Obtener umbrales desde los valores guardados
            lateral_val = center_config.get("lateral")
            trasera_val = center_config.get("trasera")
            interna_val = center_config.get("interna")

            site = SiteConfig(
                name=center["name"],
                referer_id=center["referer_id"],
                db_name=center["db_name"],
                op_code=center["op_code"],
                cd_code=center["cd_code"],
                whatsapp_group_id=whatsapp_group_id,
                umbral_minutes_lateral=int(lateral_val or 0),
                umbral_minutes_trasera=int(trasera_val or 0),
                umbral_minutes_interna=int(interna_val or 0),
            )
            config.sites.append(site)

        # Guardar
        self.config_manager.save(config)

        # Terminar
        self.on_finish()
