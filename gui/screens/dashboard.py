# Dashboard - Pantalla principal con sidebar y tabs
import customtkinter as ctk
import threading
from datetime import datetime
from pathlib import Path
from PIL import Image
from ..styles import Colors, Fonts, Dimensions, get_alpha_bg
from ..components import (
    Card, StatusBadge, PercentageBadge, CenterCard, LogViewer,
    PrimaryButton, SecondaryButton, DangerButton, SuccessButton,
    SidebarButton, LabeledInput, LabeledSelect, ToggleSwitch,
    ConnectionErrorNotification, AddCenterDialog, ConfirmDialog
)
from core import (
    get_whatsapp_client, get_trt_client, get_config_manager,
    make_banner_png, format_banner_summary_message, analyze_trucks_for_banner,
    AnalyticsService
)
from .. import chart_helpers

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class Dashboard(ctk.CTkFrame):
    """Dashboard principal con sidebar y multiples tabs"""

    def __init__(self, master, on_minimize: callable, on_exit: callable, **kwargs):
        super().__init__(master, fg_color=Colors.BG_PRIMARY, **kwargs)

        self.on_minimize = on_minimize
        self.on_exit = on_exit
        self.active_tab = "home"
        self.sidebar_collapsed = False

        # Control de notificaciones de error de conexión (inicializar temprano)
        self.connection_error_shown = False
        self.last_connection_error = None
        self.connection_check_count = 0  # Contador de verificaciones fallidas consecutivas
        self.connection_error_threshold = 3  # Mostrar popup solo después de 3 fallos consecutivos

        # Estado del sistema (inicializar ANTES de cargar iconos o threads)
        self.bot_status = "disconnected"
        self.monitor_running = False
        self.trt_connected = False  # IMPORTANTE: inicializar temprano para evitar AttributeError en threads
        self.whatsapp_phone = None
        self.whatsapp_name = None

        # Cargar imágenes de iconos (después de inicializar estado)
        self._load_icon_images()

        # Inicializar clientes para obtener datos reales
        try:
            self.whatsapp_client = get_whatsapp_client()
        except Exception as e:
            print(f"Error inicializando cliente WhatsApp: {e}")
            self.whatsapp_client = None

        self.config_manager = get_config_manager()
        self.trt_client = None  # Se inicializa con la URL de config

        # Cargar configuración
        self.config = self.config_manager.config
        if self.config.base_url:
            try:
                self.trt_client = get_trt_client(self.config.base_url)
            except Exception as e:
                print(f"Error inicializando cliente TRT: {e}")
                self.trt_client = None

        # Cache de datos para evitar consultas repetitivas
        self.centers_stats_cache = {}
        self.last_update = None
        self.update_interval = (self.config.poll_seconds or 10) * 1000  # Usar config

        # Referencias a widgets del Home tab (para auto-actualización)
        self.home_log_viewer = None
        self.home_update_label = None
        self.home_start_btn = None
        self.home_stop_btn = None
        self.home_wa_badge = None
        self.home_monitor_badge = None
        self.home_alerts_label = None  # Label de alertas en stat card
        self.home_trucks_label = None  # Label de camiones en stat card
        self.home_centers_container = None  # Contenedor de center cards

        # Control de alertas enviadas (para no reenviar la misma alerta)
        self.sent_alerts = {}  # {plate: last_alert_time}

        # Variables de estado para Analytics
        self.selected_analytics_center = None  # Centro seleccionado para análisis
        self.selected_analytics_period = 30  # Periodo en dias (7, 15, 30)
        self.analytics_service = AnalyticsService()
        self.analytics_figures = []  # Referencias a figuras matplotlib para cleanup
        self.analytics_canvas_widgets = []  # Referencias a canvas widgets para cleanup

        self._create_widgets()

        # Verificar estado real en un thread (después de crear widgets)
        # Dar tiempo para que la red corporativa esté lista antes de la primera verificación
        self.after(2000, self._check_real_status)

    def _load_icon_images(self):
        """Carga las imágenes de iconos desde assets"""
        try:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
            dashboard_dir = assets_dir / "Dashboard"
            menu_dir = assets_dir / "Menu"
            stats_dir = assets_dir / "Estadisticas"

            # Tamaño estándar para iconos de dashboard
            icon_size = (36, 36)
            # Tamaño para iconos del menú (sidebar)
            menu_icon_size = (24, 24)
            # Tamaño para iconos de estadísticas
            stats_icon_size = (32, 32)

            # Cargar iconos de Dashboard
            self.icon_whatsapp = ctk.CTkImage(
                light_image=Image.open(dashboard_dir / "whatsapp.png"),
                dark_image=Image.open(dashboard_dir / "whatsapp.png"),
                size=icon_size
            )
            self.icon_monitor = ctk.CTkImage(
                light_image=Image.open(dashboard_dir / "monitor.png"),
                dark_image=Image.open(dashboard_dir / "monitor.png"),
                size=icon_size
            )
            self.icon_alertas = ctk.CTkImage(
                light_image=Image.open(dashboard_dir / "alertas.png"),
                dark_image=Image.open(dashboard_dir / "alertas.png"),
                size=icon_size
            )
            self.icon_camiones = ctk.CTkImage(
                light_image=Image.open(dashboard_dir / "camiones.png"),
                dark_image=Image.open(dashboard_dir / "camiones.png"),
                size=icon_size
            )

            # Cargar iconos del menú (sidebar)
            self.icon_menu_inicio = ctk.CTkImage(
                light_image=Image.open(menu_dir / "Inicio.png"),
                dark_image=Image.open(menu_dir / "Inicio.png"),
                size=menu_icon_size
            )
            self.icon_menu_centros = ctk.CTkImage(
                light_image=Image.open(menu_dir / "Centros.png"),
                dark_image=Image.open(menu_dir / "Centros.png"),
                size=menu_icon_size
            )
            self.icon_menu_estadisticas = ctk.CTkImage(
                light_image=Image.open(menu_dir / "Estadisticas.png"),
                dark_image=Image.open(menu_dir / "Estadisticas.png"),
                size=menu_icon_size
            )
            self.icon_menu_configuracion = ctk.CTkImage(
                light_image=Image.open(menu_dir / "Configuracion.png"),
                dark_image=Image.open(menu_dir / "Configuracion.png"),
                size=menu_icon_size
            )

            # Cargar iconos de estadísticas
            self.icon_stats_trt = ctk.CTkImage(
                light_image=Image.open(stats_dir / "trt.png"),
                dark_image=Image.open(stats_dir / "trt.png"),
                size=stats_icon_size
            )
            self.icon_stats_camiones = ctk.CTkImage(
                light_image=Image.open(stats_dir / "camiones.png"),
                dark_image=Image.open(stats_dir / "camiones.png"),
                size=stats_icon_size
            )
            self.icon_stats_alerta = ctk.CTkImage(
                light_image=Image.open(stats_dir / "alerta.png"),
                dark_image=Image.open(stats_dir / "alerta.png"),
                size=stats_icon_size
            )
        except Exception as e:
            print(f"Error cargando iconos: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: usar None y los widgets mostrarán texto
            self.icon_whatsapp = None
            self.icon_monitor = None
            self.icon_alertas = None
            self.icon_camiones = None
            self.icon_menu_inicio = None
            self.icon_menu_centros = None
            self.icon_menu_estadisticas = None
            self.icon_menu_configuracion = None
            self.icon_stats_trt = None
            self.icon_stats_camiones = None
            self.icon_stats_alerta = None

        # Iniciar verificación periódica de estados (cada 5 segundos)
        self._start_status_polling()

    def _create_widgets(self):
        # Layout principal con grid para mejor control
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._create_sidebar()

        # Contenido principal
        self.content_area = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_area.pack(side="left", fill="both", expand=True)

        # Header
        self._create_header()

        # Content frame con scrollable
        self.content_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Mostrar tab inicial
        self._show_tab("home")

    def _create_sidebar(self):
        """Crea el sidebar de navegacion"""
        self.sidebar = ctk.CTkFrame(
            self.main_container,
            fg_color=Colors.BG_SIDEBAR,
            width=Dimensions.SIDEBAR_WIDTH,
            corner_radius=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo header con imagen CCU (fijo arriba)
        logo_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
            height=90,
        )
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)

        logo_content = ctk.CTkFrame(logo_frame, fg_color="transparent")
        logo_content.pack(expand=True, padx=16)

        # Cargar logo CCU real
        try:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
            logo_path = assets_dir / "Logo_CCU.png"

            if logo_path.exists():
                sidebar_logo = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(130, 60)
                )
                ctk.CTkLabel(
                    logo_content,
                    text="",
                    image=sidebar_logo,
                ).pack(pady=(0, 4))
                # Guardar referencia para que no se destruya
                self._sidebar_logo_ref = sidebar_logo
            else:
                self._create_sidebar_text_logo(logo_content)
        except Exception:
            self._create_sidebar_text_logo(logo_content)

        ctk.CTkLabel(
            logo_content,
            text="Monitor TRT v2.0",
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, 10),
        ).pack()

        # Separador
        ctk.CTkFrame(
            self.sidebar,
            fg_color=Colors.CCU_GREEN_LIGHT,
            height=1,
        ).pack(fill="x")

        # Contenedor scrollable para el resto del contenido
        scrollable_content = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=Colors.CCU_GREEN_LIGHT,
            scrollbar_button_hover_color=Colors.CCU_GREEN_HOVER
        )
        scrollable_content.pack(fill="both", expand=True)

        # Menu items
        nav_frame = ctk.CTkFrame(scrollable_content, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8, pady=16)

        self.nav_buttons = {}

        # Tabs con iconos de imagen (si están disponibles, sino fallback a texto)
        tabs = [
            ("home", self.icon_menu_inicio if hasattr(self, 'icon_menu_inicio') else "■", "Inicio"),
            ("centers", self.icon_menu_centros if hasattr(self, 'icon_menu_centros') else "●", "Centros"),
            ("analytics", self.icon_menu_estadisticas if hasattr(self, 'icon_menu_estadisticas') else "▲", "Estadisticas"),
            ("settings", self.icon_menu_configuracion if hasattr(self, 'icon_menu_configuracion') else "◆", "Configuracion"),
        ]

        for tab_id, icon, label in tabs:
            btn = SidebarButton(
                nav_frame,
                icon=icon,
                text=label,
                command=lambda t=tab_id: self._show_tab(t),
                is_active=(tab_id == self.active_tab),
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[tab_id] = btn

        # Separador
        ctk.CTkFrame(
            scrollable_content,
            fg_color=Colors.CCU_GREEN_LIGHT,
            height=1,
        ).pack(fill="x", pady=16)

        # User info
        user_frame = ctk.CTkFrame(scrollable_content, fg_color="transparent")
        user_frame.pack(fill="x", padx=16, pady=(0, 16))

        user_card = ctk.CTkFrame(
            user_frame,
            fg_color=Colors.CCU_GREEN_HOVER,
            corner_radius=8,
        )
        user_card.pack(fill="x")

        user_content = ctk.CTkFrame(user_card, fg_color="transparent")
        user_content.pack(padx=10, pady=10, fill="x")

        # Avatar
        avatar = ctk.CTkFrame(
            user_content,
            fg_color=Colors.ACTION_GREEN,
            corner_radius=16,
            width=32,
            height=32,
        )
        avatar.pack(anchor="w", pady=(0, 8))
        avatar.pack_propagate(False)

        # Iniciales de CCU
        ctk.CTkLabel(
            avatar,
            text="CCU",
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, 9, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Información de centros
        num_sites = len(self.config.sites)
        if num_sites > 0:
            ctk.CTkLabel(
                user_content,
                text=f"{num_sites} Centro{'s' if num_sites > 1 else ''}",
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 11, "bold"),
                anchor="w"
            ).pack(anchor="w", fill="x")

            ctk.CTkLabel(
                user_content,
                text="Monitoreando TRT",
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 9),
                anchor="w"
            ).pack(anchor="w", fill="x")
        else:
            ctk.CTkLabel(
                user_content,
                text="CCU-TRT Monitor",
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 11, "bold"),
                anchor="w"
            ).pack(anchor="w", fill="x")

            ctk.CTkLabel(
                user_content,
                text="Sin centros",
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 9),
                anchor="w"
            ).pack(anchor="w", fill="x")

    def _create_header(self):
        """Crea el header superior"""
        self.header = ctk.CTkFrame(
            self.content_area,
            fg_color=Colors.BG_HEADER,
            height=60,
            corner_radius=0,
        )
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        header_content = ctk.CTkFrame(self.header, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=16)

        # Left side - Status badges
        left_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        left_frame.pack(side="left", fill="y")

        # Status badges (con texto blanco para fondo verde)
        self.whatsapp_badge = StatusBadge(
            left_frame,
            status=self.bot_status,
            label=f"WhatsApp: {'Conectado' if self.bot_status == 'connected' else 'Desconectado'}",
            label_color=Colors.TEXT_ON_GREEN,
        )
        self.whatsapp_badge.pack(side="left", padx=(8, 12), pady=15)

        monitor_status = "connected" if self.monitor_running else "disconnected"
        self.monitor_badge = StatusBadge(
            left_frame,
            status=monitor_status,
            label=f"Monitor: {'Activo' if self.monitor_running else 'Detenido'}",
            label_color=Colors.TEXT_ON_GREEN,
        )
        self.monitor_badge.pack(side="left", pady=15)

        # Right side - Date y botones
        right_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        right_frame.pack(side="right", fill="y")

        # Label de fecha/hora (se actualizará automáticamente)
        self.header_date_label = ctk.CTkLabel(
            right_frame,
            text="",
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, 13),
        )
        self.header_date_label.pack(side="left", padx=(0, 16), pady=20)

        # Iniciar actualización de fecha/hora
        self._update_header_datetime()

        SecondaryButton(
            right_frame,
            text="Minimizar",
            command=self.on_minimize,
            size="sm",
        ).pack(side="left", padx=4, pady=15)

        SecondaryButton(
            right_frame,
            text="Salir",
            command=self.on_exit,
            size="sm",
        ).pack(side="left", padx=4, pady=15)

    def _toggle_sidebar(self):
        """Colapsa/expande el sidebar"""
        self.sidebar_collapsed = not self.sidebar_collapsed
        new_width = Dimensions.SIDEBAR_COLLAPSED_WIDTH if self.sidebar_collapsed else Dimensions.SIDEBAR_WIDTH
        self.sidebar.configure(width=new_width)

    def _create_sidebar_text_logo(self, parent):
        """Fallback: logo de texto si no se encuentra la imagen"""
        ctk.CTkLabel(
            parent,
            text="CCU",
            text_color=Colors.TEXT_ON_GREEN,
            font=("Arial Black", 28, "bold"),
        ).pack(pady=(0, 2))

    def _update_header_datetime(self):
        """Actualiza la fecha/hora del header en español"""
        # Diccionarios de traducción
        dias = {
            'Monday': 'Lunes',
            'Tuesday': 'Martes',
            'Wednesday': 'Miércoles',
            'Thursday': 'Jueves',
            'Friday': 'Viernes',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }

        meses = {
            'January': 'enero',
            'February': 'febrero',
            'March': 'marzo',
            'April': 'abril',
            'May': 'mayo',
            'June': 'junio',
            'July': 'julio',
            'August': 'agosto',
            'September': 'septiembre',
            'October': 'octubre',
            'November': 'noviembre',
            'December': 'diciembre'
        }

        now = datetime.now()
        day_name = dias[now.strftime("%A")]
        month_name = meses[now.strftime("%B")]

        date_str = f"{day_name}, {now.day} de {month_name} de {now.year} - {now.strftime('%H:%M')}"

        # Actualizar el label si existe
        try:
            if hasattr(self, 'header_date_label') and self.header_date_label.winfo_exists():
                self.header_date_label.configure(text=date_str)
        except Exception:
            pass

        # Programar siguiente actualización en 60 segundos (1 minuto)
        self.after(60000, self._update_header_datetime)

    def _check_real_status(self):
        """Verifica el estado real del bot de WhatsApp y la conexión TRT"""
        def check():
            # Verificar WhatsApp
            wa_changed = False
            old_wa_status = self.bot_status

            try:
                if hasattr(self, 'whatsapp_client') and self.whatsapp_client:
                    if self.whatsapp_client.health_check():
                        status = self.whatsapp_client.get_status()
                        if status.connected:
                            self.bot_status = "connected"
                            self.whatsapp_phone = status.phone
                            self.whatsapp_name = status.name
                            wa_changed = (old_wa_status != "connected")
                        else:
                            self.bot_status = "warning"  # Bot corriendo pero WA no conectado
                            wa_changed = (old_wa_status != "warning")
                    else:
                        self.bot_status = "disconnected"
                        wa_changed = (old_wa_status != "disconnected")
                else:
                    self.bot_status = "disconnected"
                    wa_changed = (old_wa_status != "disconnected")
            except Exception as e:
                print(f"Error verificando WhatsApp: {e}")
                self.bot_status = "disconnected"
                wa_changed = (old_wa_status != "disconnected")

            # Verificar TRT (conexión al servidor)
            # NOTA: La verificación activa de test_connection() está DESHABILITADA
            # porque causa falsos positivos. Si el cliente TRT existe, asumimos que
            # la conexión funciona. Los errores reales se capturarán cuando fallen
            # las consultas reales de datos (get_center_stats).
            old_trt_status = self.trt_connected
            if hasattr(self, 'trt_client') and self.trt_client:
                self.trt_connected = True
            else:
                self.trt_connected = False
            trt_changed = (old_trt_status != self.trt_connected)

            # Actualizar UI en el hilo principal
            self.after(0, self._update_status_badges)

            # Agregar logs solo si cambió el estado (para evitar spam)
            if wa_changed or trt_changed:
                self.after(0, self._add_status_logs)

        threading.Thread(target=check, daemon=True).start()

    def _add_status_logs(self):
        """Agrega logs del estado actual de conexiones"""
        now = datetime.now().strftime("%H:%M:%S")

        if self.bot_status == "connected":
            self._add_log("success", f"WhatsApp conectado ({self.whatsapp_phone or 'OK'})")
        elif self.bot_status == "warning":
            self._add_log("warning", "Bot activo pero WhatsApp no conectado")
        else:
            self._add_log("warning", "WhatsApp no conectado")

        if self.trt_connected:
            self._add_log("success", f"TRT servidor disponible ({self.config.base_url})")
        else:
            self._add_log("warning", "Cliente TRT no configurado")

    def _update_status_badges(self):
        """Actualiza los badges de status en el header y en el panel si está visible"""
        try:
            if hasattr(self, 'whatsapp_badge') and self.whatsapp_badge.winfo_exists():
                wa_label = "Conectado" if self.bot_status == "connected" else "Desconectado"
                self.whatsapp_badge.set_status(self.bot_status, f"WhatsApp: {wa_label}")

            if hasattr(self, 'monitor_badge') and self.monitor_badge.winfo_exists():
                if self.monitor_running:
                    self.monitor_badge.set_status("connected", "Monitor: Activo")
                else:
                    self.monitor_badge.set_status("disconnected", "Monitor: Detenido")

            # Actualizar también los badges en el panel Home si está visible
            if hasattr(self, 'home_wa_badge') and self.home_wa_badge and self.home_wa_badge.winfo_exists():
                wa_label = "Conectado" if self.bot_status == "connected" else "Desconectado"
                self.home_wa_badge.set_status(self.bot_status, wa_label)

            if hasattr(self, 'home_monitor_badge') and self.home_monitor_badge and self.home_monitor_badge.winfo_exists():
                if self.monitor_running:
                    self.home_monitor_badge.set_status("connected", "Activo")
                else:
                    self.home_monitor_badge.set_status("disconnected", "Detenido")
        except Exception:
            pass  # Widget puede haber sido destruido

    def _start_status_polling(self):
        """Inicia la verificación periódica de estados"""
        self._check_real_status()
        # Programar siguiente verificación cada 5 segundos
        self.after(5000, self._start_status_polling)

    def _start_monitor(self):
        """Inicia el monitor de alertas"""
        if self.monitor_running:
            return

        self.monitor_running = True
        self._update_status_badges()
        self._add_log("success", "Monitor iniciado")
        self._do_monitor_cycle()

        # Refrescar tab home para actualizar botones
        if self.active_tab == "home":
            self._refresh_home_control_buttons()

    def _stop_monitor(self):
        """Detiene el monitor de alertas"""
        self.monitor_running = False
        self._update_status_badges()
        self._add_log("warning", "Monitor detenido")
        self._refresh_home_tab()

        # Refrescar tab home para actualizar botones
        if self.active_tab == "home":
            self._refresh_home_control_buttons()

    def _do_monitor_cycle(self):
        """Ejecuta un ciclo del monitor"""
        if not self.monitor_running:
            return

        # Verificar estado de conexiones
        self._check_real_status()

        # Actualizar estadísticas de centros
        self._update_centers_stats()

        # Programar siguiente ciclo si el monitor está activo
        if self.monitor_running:
            self.after(self.update_interval, self._do_monitor_cycle)

    def _add_log(self, level: str, message: str):
        """Agrega una entrada al log viewer si existe"""
        now = datetime.now().strftime("%H:%M:%S")
        try:
            if self.home_log_viewer and self.home_log_viewer.winfo_exists():
                self.home_log_viewer.add_log(now, level, message)
        except Exception:
            pass

    def _send_whatsapp_alerts(self, alerts_to_send: list):
        """Envía alertas por WhatsApp con banner (imagen)"""
        realert_minutes = self.config.realert_minutes or 30
        now = datetime.now()

        for alert_data in alerts_to_send:
            site = alert_data["site"]
            all_trucks = alert_data["all_trucks"]  # Todos los camiones para el banner
            threshold = alert_data["threshold"]

            # Verificar si debemos enviar alerta (control de reenvío)
            site_key = f"site_{site.referer_id}"
            last_alert = self.sent_alerts.get(site_key)
            if last_alert is not None and (now - last_alert).total_seconds() < realert_minutes * 60:
                continue

            # Marcar que enviamos alerta para este sitio
            self.sent_alerts[site_key] = now

            try:
                # Analizar camiones y generar banner
                center_status = analyze_trucks_for_banner(site.name, all_trucks, threshold)

                # Generar imagen del banner
                banner_path = make_banner_png(center_status)

                # Crear mensaje de resumen
                summary_message = format_banner_summary_message(center_status)

                # Enviar imagen con caption
                success = self.whatsapp_client.send_image(
                    site.whatsapp_group_id,
                    banner_path,
                    summary_message
                )

                if success:
                    self.after(0, lambda s=site.name, sev=center_status.severity:
                        self._add_log("success", f"Banner {sev} enviado: {s}"))
                else:
                    self.after(0, lambda s=site.name:
                        self._add_log("error", f"Error enviando banner a {s}"))

            except Exception as e:
                print(f"Error generando/enviando banner: {e}")
                self.after(0, lambda err=str(e):
                    self._add_log("error", f"Error banner: {err[:30]}"))

    def _force_send_banner(self):
        """Fuerza el envío de un banner/alerta inmediatamente"""
        self._add_log("info", "Forzando envio de banner...")

        # Limpiar alertas previas para forzar reenvío
        self.sent_alerts.clear()

        # Ejecutar consulta y envío
        self._check_real_status()
        self._update_centers_stats()

    def _refresh_home_tab(self):
        """Refresca el tab Home si está activo"""
        if self.active_tab == "home":
            self._show_tab("home")

    def _refresh_home_center_cards(self):
        """Actualiza las center cards en el Home tab SIN recrearlas (sin parpadeo)"""
        try:
            if not hasattr(self, 'home_centers_container') or not self.home_centers_container:
                return

            if not self.home_centers_container.winfo_exists():
                return

            # Obtener datos actualizados
            centers_data = self._get_centers_data()

            # Obtener cards existentes
            existing_cards = [w for w in self.home_centers_container.winfo_children() if isinstance(w, CenterCard)]

            # Si hay la misma cantidad de centers y cards, solo actualizar
            if len(existing_cards) == len(centers_data):
                for card, center_data in zip(existing_cards, centers_data):
                    if card.name == center_data["name"]:
                        # Actualizar sin recrear (sin parpadeo)
                        card.update_data(
                            status=center_data["status"],
                            trucks_in_plant=center_data["trucks_in_plant"],
                            avg_time=center_data["avg_time"],
                            threshold=center_data["threshold"],
                            alerts=center_data["alerts"],
                            trucks_list=center_data.get("trucks_list", []),
                            threshold_lateral=center_data.get("threshold_lateral", 100),
                            threshold_trasera=center_data.get("threshold_trasera", 100),
                            threshold_interna=center_data.get("threshold_interna", 100),
                        )
            else:
                # Si cambió la cantidad de centros, recrear todo
                for widget in self.home_centers_container.winfo_children():
                    widget.destroy()

                if centers_data:
                    cols = min(len(centers_data), 2)
                    for c in range(cols):
                        self.home_centers_container.grid_columnconfigure(c, weight=1)

                    for i, center in enumerate(centers_data):
                        row = i // 2
                        col = i % 2
                        card = CenterCard(self.home_centers_container, **center)
                        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
                else:
                    ctk.CTkLabel(
                        self.home_centers_container,
                        text="No hay centros configurados.",
                        text_color=Colors.TEXT_MUTED,
                        font=(Fonts.FAMILY, 14),
                    ).pack(pady=20)

        except Exception as e:
            print(f"Error refrescando center cards: {e}")

    def _refresh_home_control_buttons(self):
        """Actualiza los botones de control sin recrear todo el tab"""
        try:
            # Buscar el frame de botones y recrear solo esa sección
            if hasattr(self, 'home_start_btn'):
                if self.home_start_btn and self.home_start_btn.winfo_exists():
                    self.home_start_btn.destroy()
                    self.home_start_btn = None

            if hasattr(self, 'home_stop_btn'):
                if self.home_stop_btn and self.home_stop_btn.winfo_exists():
                    self.home_stop_btn.destroy()
                    self.home_stop_btn = None

            # Necesitamos el control_buttons frame - por ahora solo forzar refresh del tab
            self._show_tab("home")
        except Exception as e:
            print(f"Error actualizando botones: {e}")

    def _update_centers_stats(self):
        """Actualiza las estadísticas de los centros en background"""
        def update():
            if not self.trt_client:
                self.after(0, lambda: self._add_log("warning", "Cliente TRT no configurado"))
                return

            total_trucks = 0
            total_alerts = 0
            alerts_to_send = []  # Lista de alertas para enviar por WhatsApp

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

                    # Contar alertas (camiones sobre umbral)
                    alerts = sum(1 for t in trucks if t.time_in_plant_minutes >= threshold)

                    self.centers_stats_cache[site.name] = {
                        "total_trucks": stats.get("total_trucks", 0),
                        "avg_time": stats.get("avg_time_minutes", 0),
                        "max_time": stats.get("max_time_minutes", 0),
                        "trucks": trucks,
                        "alerts": alerts,
                    }

                    total_trucks += stats.get("total_trucks", 0)
                    total_alerts += alerts

                    # Preparar banner para envío (si hay camiones en planta)
                    if trucks and site.whatsapp_group_id:
                        alerts_to_send.append({
                            "site": site,
                            "all_trucks": trucks,  # Todos los camiones para el banner
                            "threshold": threshold,
                        })

                except Exception as e:
                    error_msg = str(e)
                    print(f"Error obteniendo stats de {site.name}: {e}")
                    self.after(0, lambda s=site.name, err=error_msg: self._add_log("error", f"Error {s}: {err[:30]}"))

                    # NO mostrar popup de error - solo logear
                    # Los errores transitorios son normales y se resolverán en el siguiente ciclo
                    # Si hay un problema persistente, el usuario lo verá en los logs

            self.last_update = datetime.now()

            # Enviar alertas por WhatsApp si hay
            if alerts_to_send and self.bot_status == "connected":
                self._send_whatsapp_alerts(alerts_to_send)

            # Actualizar UI
            def update_ui():
                # Actualizar label de última actualización
                try:
                    if self.home_update_label and self.home_update_label.winfo_exists():
                        self.home_update_label.configure(text=f"Ultima actualizacion: {self.last_update.strftime('%H:%M:%S')}")
                except Exception:
                    pass

                # Actualizar stat cards de alertas y camiones en Home
                try:
                    if self.home_alerts_label and self.home_alerts_label.winfo_exists():
                        self.home_alerts_label.configure(text=str(total_alerts))
                    if self.home_trucks_label and self.home_trucks_label.winfo_exists():
                        self.home_trucks_label.configure(text=str(total_trucks))
                except Exception:
                    pass

                # Refrescar center cards si estamos en el tab Home
                if self.active_tab == "home":
                    self._refresh_home_center_cards()

                # Log de resultado (solo si hay alertas o cambios importantes)
                # NO logear consultas normales para evitar spam cada 10 segundos
                if total_alerts > 0:
                    # Solo logear si hay alertas activas
                    self._add_log("warning", f"{total_alerts} alerta(s) detectada(s) - {total_trucks} camiones en planta")

            self.after(0, update_ui)

        threading.Thread(target=update, daemon=True).start()

    def _show_connection_error(self, error_message: str):
        """Muestra una notificación de error de conexión"""
        if self.connection_error_shown:
            return

        self.connection_error_shown = True
        self.last_connection_error = error_message

        # Obtener URL del servidor de forma segura
        server_url = "el servidor TRT"
        try:
            if hasattr(self, 'config') and self.config and hasattr(self.config, 'base_url'):
                server_url = self.config.base_url
            elif hasattr(self, 'trt_client') and self.trt_client and hasattr(self.trt_client, 'base_url'):
                server_url = self.trt_client.base_url
        except Exception:
            pass

        # Limpiar el mensaje de error para hacerlo más legible
        clean_message = error_message

        # Detectar tipos comunes de errores de red
        if "timeout" in clean_message.lower() or "timed out" in clean_message.lower():
            clean_message = f"Tiempo de espera agotado al conectar al servidor TRT.\n\nEl servidor ({server_url}) no responde.\n\nVerifica que:\n• El servidor esté encendido y accesible\n• Estés conectado a la red corporativa CCU\n• La dirección IP sea correcta en Configuración"
        elif "connection" in clean_message.lower() and ("refused" in clean_message.lower() or "aborted" in clean_message.lower()):
            clean_message = f"No se pudo establecer conexión con el servidor TRT.\n\nEl servidor rechazó la conexión o la cerró inesperadamente.\n\nPosibles causas:\n• El servidor TRT no está en ejecución\n• Firewall o proxy bloqueando la conexión\n• Problemas de red corporativa"
        elif "max retries" in clean_message.lower():
            clean_message = f"Se alcanzó el máximo de reintentos de conexión.\n\nEl servidor TRT no está respondiendo.\n\nVerifica tu conexión de red."
        elif len(clean_message) > 300:
            # Si el mensaje es muy largo, simplificarlo
            clean_message = f"Error al conectar con el servidor TRT:\n\n{clean_message[:250]}...\n\nVerifica tu conexión de red y la configuración del servidor."

        try:
            # Cerrar cualquier notificación anterior si existe
            if hasattr(self, '_active_error_notification') and self._active_error_notification:
                try:
                    self._active_error_notification.destroy()
                except:
                    pass

            # Crear nueva notificación
            self._active_error_notification = ConnectionErrorNotification(
                self,
                clean_message,
                on_retry=self._retry_connection,
                auto_close_ms=300000  # 5 minutos
            )
        except Exception as e:
            print(f"Error mostrando notificación: {e}")
            import traceback
            traceback.print_exc()
            self.connection_error_shown = False

    def _retry_connection(self):
        """Reintenta la conexión al TRT"""
        # Cerrar la notificación actual
        if hasattr(self, '_active_error_notification') and self._active_error_notification:
            try:
                self._active_error_notification.destroy()
            except:
                pass
            self._active_error_notification = None

        # Resetear flags y contador
        self.connection_error_shown = False
        self.last_connection_error = None
        self.connection_check_count = 0  # Resetear contador de fallos

        # Log y reintentar
        self._add_log("info", "Reintentando conexión al servidor TRT...")
        self._check_real_status()

    def _show_add_center_dialog(self):
        """Muestra el diálogo para agregar un nuevo centro"""
        # Obtener centros disponibles y grupos de WhatsApp
        available_centers = []
        whatsapp_groups = []

        try:
            if self.trt_client:
                centers = self.trt_client.get_available_centers()
                available_centers = [
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
            print(f"Error obteniendo centros: {e}")

        try:
            if self.whatsapp_client:
                groups = self.whatsapp_client.get_groups()
                whatsapp_groups = [{"id": g.id, "name": g.name} for g in groups]
        except Exception as e:
            print(f"Error obteniendo grupos: {e}")

        AddCenterDialog(
            self,
            on_save=self._add_center,
            available_centers=available_centers,
            whatsapp_groups=whatsapp_groups
        )

    def _add_center(self, center_data: dict):
        """Agrega un nuevo centro a la configuración"""
        try:
            from core import SiteConfig

            # Crear SiteConfig desde el diccionario
            new_site = SiteConfig(**center_data)

            # Agregar a la configuración
            self.config_manager.add_site(new_site)

            # Recargar configuración
            self.config = self.config_manager.config

            # Log success
            self._add_log("success", f"Centro agregado: {new_site.name}")

            # Refrescar la vista de centros
            if self.active_tab == "centers":
                self._show_tab("centers")

        except Exception as e:
            print(f"Error agregando centro: {e}")
            self._add_log("error", f"Error al agregar centro: {str(e)[:30]}")

    def _edit_center(self, site):
        """Muestra diálogo para editar un centro existente"""
        # Obtener grupos de WhatsApp
        whatsapp_groups = []
        try:
            if self.whatsapp_client:
                groups = self.whatsapp_client.get_groups()
                whatsapp_groups = [{"id": g.id, "name": g.name} for g in groups]
        except Exception as e:
            print(f"Error obteniendo grupos: {e}")

        from ..components import EditCenterDialog
        EditCenterDialog(
            self,
            site=site,
            on_save=self._update_center,
            whatsapp_groups=whatsapp_groups
        )

    def _update_center(self, old_name: str, updated_data: dict):
        """Actualiza un centro existente en la configuración"""
        try:
            from core import SiteConfig

            # Crear SiteConfig actualizado
            updated_site = SiteConfig(**updated_data)

            # Actualizar en la configuración
            self.config_manager.update_site(old_name, updated_site)

            # Recargar configuración
            self.config = self.config_manager.config

            # Log success
            self._add_log("success", f"Centro actualizado: {updated_site.name}")

            # Refrescar la vista de centros
            if self.active_tab == "centers":
                self._show_tab("centers")

        except Exception as e:
            print(f"Error actualizando centro: {e}")
            self._add_log("error", f"Error al actualizar centro: {str(e)[:30]}")

    def _delete_center(self, site):
        """Elimina un centro de la configuración"""
        # Mostrar confirmación
        ConfirmDialog(
            self,
            title="¿Eliminar centro?",
            message=f"¿Estás seguro de que deseas eliminar el centro '{site.name}'?\n\nEsta acción no se puede deshacer.",
            confirm_text="Eliminar",
            cancel_text="Cancelar",
            on_confirm=lambda: self._do_delete_center(site),
            danger=True
        )

    def _do_delete_center(self, site):
        """Ejecuta la eliminación del centro"""
        try:
            # Eliminar de la configuración (usar el nombre del sitio)
            self.config_manager.remove_site(site.name)

            # Recargar configuración
            self.config = self.config_manager.config

            # Log success
            self._add_log("success", f"Centro eliminado: {site.name}")

            # Refrescar la vista de centros
            if self.active_tab == "centers":
                self._show_tab("centers")

        except Exception as e:
            print(f"Error eliminando centro: {e}")
            self._add_log("error", f"Error al eliminar centro: {str(e)[:30]}")

    def _confirm_disconnect_whatsapp(self):
        """Muestra diálogo de confirmación para desvincular WhatsApp"""
        ConfirmDialog(
            self,
            title="¿Desvincular WhatsApp?",
            message="Esta acción cerrará la sesión de WhatsApp en el bot. Deberás escanear el código QR nuevamente para volver a conectar.\n\nLas alertas automáticas NO se enviarán hasta que vuelvas a vincular WhatsApp.\n\n¿Deseas continuar?",
            confirm_text="Sí, desvincular",
            cancel_text="Cancelar",
            on_confirm=self._disconnect_whatsapp,
            danger=True
        )

    def _disconnect_whatsapp(self):
        """Desvincula WhatsApp del bot"""
        try:
            self._add_log("info", "Desvinculando WhatsApp...")

            # Llamar al método logout del bot
            if self.whatsapp_client:
                success = self.whatsapp_client.logout()

                if success:
                    self._add_log("success", "WhatsApp desvinculado correctamente")
                    self.bot_status = "disconnected"
                    self.whatsapp_phone = None
                    self.whatsapp_name = None
                    self._update_status_badges()
                else:
                    self._add_log("error", "No se pudo desvincular WhatsApp")
            else:
                self._add_log("error", "Cliente WhatsApp no disponible")

        except Exception as e:
            print(f"Error desvinculando WhatsApp: {e}")
            self._add_log("error", f"Error: {str(e)[:30]}")

    def _confirm_reset_config(self):
        """Muestra diálogo de confirmación para borrar la configuración"""
        ConfirmDialog(
            self,
            title="¿Borrar toda la configuración?",
            message="Esta acción eliminará todos los centros configurados, parámetros y configuraciones de WhatsApp. La aplicación se reiniciará y deberás configurar todo nuevamente desde cero.\n\n¿Estás seguro de que deseas continuar?",
            confirm_text="Sí, borrar todo",
            cancel_text="Cancelar",
            on_confirm=self._reset_config,
            danger=True
        )

    def _reset_config(self):
        """Borra la configuración y reinicia la aplicación"""
        try:
            import os

            # Borrar archivo de configuración
            if self.config_manager.config_path.exists():
                os.remove(self.config_manager.config_path)
                self._add_log("warning", "Configuración eliminada")

            # Esperar un momento y reiniciar
            self.after(1000, self._restart_app)

        except Exception as e:
            print(f"Error reseteando configuración: {e}")
            self._add_log("error", f"Error al resetear: {str(e)[:30]}")

    def _restart_app(self):
        """Reinicia la aplicación para volver al setup inicial"""
        import sys
        import subprocess

        try:
            # Cerrar ventana actual
            self.master.destroy()

            # Reiniciar proceso
            python = sys.executable
            subprocess.Popen([python] + sys.argv)
            sys.exit(0)

        except Exception as e:
            print(f"Error reiniciando aplicación: {e}")
            # Si falla el reinicio, al menos cerrar la app
            sys.exit(0)

    def _get_centers_data(self):
        """Obtiene datos de los centros configurados con estadísticas reales"""
        centers_data = []

        for site in self.config.sites:
            stats = self.centers_stats_cache.get(site.name, {})
            trucks = stats.get("total_trucks", 0)
            avg_time = stats.get("avg_time", 0)
            alerts = stats.get("alerts", 0)

            # Determinar umbral (usar lateral como principal si existe)
            threshold = site.umbral_minutes_lateral or site.umbral_minutes or 60

            # Determinar status basado en alertas y tiempo promedio
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

    def _show_tab(self, tab_id: str):
        """Muestra una tab especifica"""
        # Limpiar figuras matplotlib al salir del tab analytics
        if self.active_tab == "analytics":
            self._cleanup_analytics_figures()

        self.active_tab = tab_id

        # Actualizar botones
        for tid, btn in self.nav_buttons.items():
            btn.set_active(tid == tab_id)

        # Limpiar contenido
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Mostrar contenido
        tab_methods = {
            "home": self._tab_home,
            "centers": self._tab_centers,
            "analytics": self._tab_analytics,
            "settings": self._tab_settings,
        }
        tab_methods.get(tab_id, self._tab_home)()

    # ========== TAB: Home ==========
    def _tab_home(self):
        # Scrollable container
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Header
        ctk.CTkLabel(
            scroll,
            text="Panel de Control",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            scroll,
            text="Vista general del sistema de alertas TRT",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w", pady=(0, 24))

        # Status cards
        status_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        status_frame.pack(fill="x", pady=(0, 24))
        status_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # WhatsApp status card
        self.home_wa_badge = self._create_status_card(
            status_frame, 0, self.icon_whatsapp, "WhatsApp",
            self.bot_status, "Conectado" if self.bot_status == "connected" else "Desconectado"
        )

        # Monitor status card
        monitor_status = "connected" if self.monitor_running else "disconnected"
        self.home_monitor_badge = self._create_status_card(
            status_frame, 1, self.icon_monitor, "Monitor",
            monitor_status, "Activo" if self.monitor_running else "Detenido"
        )

        # Calcular estadísticas reales
        centers_data = self._get_centers_data()
        total_alerts = sum(c["alerts"] for c in centers_data)
        total_trucks = sum(c["trucks_in_plant"] for c in centers_data)

        # Alertas card (guardar referencia para actualizar)
        self.home_alerts_label = self._create_stat_card(
            status_frame, 2, self.icon_alertas, "Alertas hoy", str(total_alerts), Colors.WARNING, 0, True
        )

        # Camiones card (guardar referencia para actualizar)
        self.home_trucks_label = self._create_stat_card(
            status_frame, 3, self.icon_camiones, "Camiones en centros", str(total_trucks), Colors.ICON_TRUCKS, 0, False
        )

        # Control del monitor
        control_card = Card(scroll)
        control_card.pack(fill="x", pady=(0, 24))

        control_content = ctk.CTkFrame(control_card, fg_color="transparent")
        control_content.pack(fill="x", padx=20, pady=20)

        control_text = ctk.CTkFrame(control_content, fg_color="transparent")
        control_text.pack(side="left")

        ctk.CTkLabel(
            control_text,
            text="Control del Monitor",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w")

        # Calcular tiempo desde última actualización
        if self.last_update:
            seconds_ago = (datetime.now() - self.last_update).seconds
            update_text = f"Ultima actualizacion: hace {seconds_ago} segundos"
        else:
            update_text = "Ultima actualizacion: esperando inicio..."

        self.home_update_label = ctk.CTkLabel(
            control_text,
            text=update_text,
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 13),
        )
        self.home_update_label.pack(anchor="w")

        control_buttons = ctk.CTkFrame(control_content, fg_color="transparent")
        control_buttons.pack(side="right")

        if self.monitor_running:
            self.home_stop_btn = DangerButton(
                control_buttons,
                text="⏹ Detener",
                command=self._stop_monitor
            )
            self.home_stop_btn.pack(side="left", padx=4)
        else:
            self.home_start_btn = SuccessButton(
                control_buttons,
                text="▶ Iniciar",
                command=self._start_monitor
            )
            self.home_start_btn.pack(side="left", padx=4)

        SecondaryButton(
            control_buttons,
            text="📢 Forzar envio",
            command=self._force_send_banner
        ).pack(side="left", padx=4)

        # Centers grid - usando datos reales de la configuración
        self.home_centers_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.home_centers_container.pack(fill="x", pady=(0, 24))

        if centers_data:
            # Configurar columnas según cantidad de centros
            cols = min(len(centers_data), 2)
            for c in range(cols):
                self.home_centers_container.grid_columnconfigure(c, weight=1)

            for i, center in enumerate(centers_data):
                row = i // 2
                col = i % 2
                card = CenterCard(self.home_centers_container, **center)
                card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        else:
            # Mensaje cuando no hay centros configurados
            ctk.CTkLabel(
                self.home_centers_container,
                text="No hay centros configurados. Ve a Configuración para agregar centros.",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 14),
            ).pack(pady=20)

        # Log viewer
        log_card = Card(scroll)
        log_card.pack(fill="x")

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(20, 16))

        ctk.CTkLabel(
            log_header,
            text="Registro de Actividad",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(side="left")

        self.home_log_viewer = LogViewer(log_card, height=200)
        self.home_log_viewer.pack(fill="x", padx=20, pady=(0, 20))

        # Agregar solo log inicial - los estados se verificarán en background
        # y se agregarán cuando estén listos
        now = datetime.now().strftime("%H:%M:%S")
        self.home_log_viewer.add_log(now, "info", "Dashboard iniciado - verificando conexiones...")

        if self.config.sites:
            self.home_log_viewer.add_log(now, "info", f"Configurados {len(self.config.sites)} centro(s)")

        if self.monitor_running:
            self.home_log_viewer.add_log(now, "success", "Monitor activo")
        else:
            self.home_log_viewer.add_log(now, "info", "Monitor detenido - presiona Iniciar para comenzar")

    def _create_status_card(self, parent, col, icon, label, status, status_label):
        """Crea una tarjeta de estado y devuelve el badge para actualizarlo después"""
        card = Card(parent)
        card.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=20, pady=20)

        icon_bg_color = Colors.SUCCESS_BG if status == "connected" else Colors.ERROR_BG

        # Tamaño estándar del frame de iconos: 52x52
        icon_frame = ctk.CTkFrame(
            content,
            fg_color=icon_bg_color,
            corner_radius=12,
            width=52,
            height=52,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        # Usar imagen si está disponible, sino texto
        if icon and isinstance(icon, ctk.CTkImage):
            ctk.CTkLabel(
                icon_frame,
                text="",
                image=icon
            ).place(relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(
                icon_frame,
                text=icon if icon else "?",
                text_color=Colors.TEXT_PRIMARY if status == "connected" else Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 18, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            text_frame,
            text=label,
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        badge = StatusBadge(text_frame, status=status, label=status_label)
        badge.pack(anchor="w", pady=(4, 0))
        return badge

    def _create_stat_card(self, parent, col, icon, label, value, color, change, inverted):
        """Crea una tarjeta de estadistica"""
        card = Card(parent)
        card.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=20, pady=20)

        # Tamaño estándar del frame de iconos: 52x52
        icon_frame = ctk.CTkFrame(
            content,
            fg_color=get_alpha_bg(color),
            corner_radius=12,
            width=52,
            height=52,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        # Usar imagen si está disponible, sino texto
        if icon and isinstance(icon, ctk.CTkImage):
            ctk.CTkLabel(
                icon_frame,
                text="",
                image=icon
            ).place(relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(
                icon_frame,
                text=icon if icon else "?",
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 20, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            text_frame,
            text=label,
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            text_frame,
            text=value,
            text_color=color,
            font=(Fonts.FAMILY, 24, "bold"),
        )
        value_label.pack(anchor="w")

        PercentageBadge(text_frame, value=change, inverted=inverted).pack(anchor="w")

        return value_label  # Devolver referencia para poder actualizarlo después

    # ========== TAB: Centers ==========
    def _tab_centers(self):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Header
        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))

        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left")

        ctk.CTkLabel(
            text_frame,
            text="Centros de Distribucion",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame,
            text="Administra los centros monitoreados",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w")

        PrimaryButton(
            header,
            text="+ Agregar Centro",
            command=self._show_add_center_dialog
        ).pack(side="right")

        # Centers list - usar datos reales de configuración
        if not self.config.sites:
            ctk.CTkLabel(
                scroll,
                text="No hay centros configurados. Usa el asistente de configuración para agregar centros.",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 14),
            ).pack(pady=40)
            return

        for site in self.config.sites:
            # Convertir SiteConfig a diccionario para el template
            center = {
                "name": site.name,
                "lateral": site.umbral_minutes_lateral or None,
                "trasera": site.umbral_minutes_trasera or None,
                "interna": site.umbral_minutes_interna or None,
                "group": site.whatsapp_group_id or site.group_id or "No configurado",
            }
            card = Card(scroll)
            card.pack(fill="x", pady=8)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=20, pady=20)

            # Info
            info_frame = ctk.CTkFrame(content, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                info_frame,
                text=center["name"],
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 18, "bold"),
            ).pack(anchor="w", pady=(0, 12))

            # Thresholds
            thresholds_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            thresholds_frame.pack(anchor="w", pady=(0, 12))

            for label, value in [("Umbral Lateral", center["lateral"]), ("Umbral Trasera", center["trasera"]), ("Umbral Interna", center["interna"])]:
                tf = ctk.CTkFrame(thresholds_frame, fg_color="transparent")
                tf.pack(side="left", padx=(0, 24))

                ctk.CTkLabel(
                    tf,
                    text=label,
                    text_color=Colors.TEXT_MUTED,
                    font=(Fonts.FAMILY, 11),
                ).pack(anchor="w")

                val_text = f"{value} min" if value else "No configurado"
                val_color = Colors.TEXT_PRIMARY if value else Colors.TEXT_MUTED

                ctk.CTkLabel(
                    tf,
                    text=val_text,
                    text_color=val_color,
                    font=(Fonts.FAMILY, 16, "bold"),
                ).pack(anchor="w")

            # Group
            group_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            group_frame.pack(anchor="w")

            ctk.CTkLabel(
                group_frame,
                text="Grupo:",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 13),
            ).pack(side="left")

            ctk.CTkLabel(
                group_frame,
                text=center["group"],
                text_color=Colors.ACTION_GREEN,
                font=(Fonts.FAMILY, 13, "bold"),
            ).pack(side="left", padx=(8, 0))

            # Buttons
            buttons = ctk.CTkFrame(content, fg_color="transparent")
            buttons.pack(side="right")

            SecondaryButton(
                buttons,
                text="Editar",
                size="sm",
                command=lambda s=site: self._edit_center(s)
            ).pack(side="left", padx=4)

            DangerButton(
                buttons,
                text="Eliminar",
                command=lambda s=site: self._delete_center(s)
            ).pack(side="left", padx=4)

    # ========== TAB: Analytics ==========
    def _get_site_threshold(self, center_name: str) -> int:
        """Obtiene el umbral en minutos para un centro"""
        if center_name and self.config.sites:
            for site in self.config.sites:
                if site.name == center_name:
                    return site.umbral_minutes_lateral or site.umbral_minutes or 60
        return 60

    def _cleanup_analytics_figures(self):
        """Limpia figuras matplotlib y canvas para evitar memory leaks"""
        for canvas_widget in self.analytics_canvas_widgets:
            try:
                canvas_widget.get_tk_widget().destroy()
            except Exception:
                pass
        for fig in self.analytics_figures:
            try:
                plt.close(fig)
            except Exception:
                pass
        self.analytics_figures.clear()
        self.analytics_canvas_widgets.clear()

    def _embed_chart(self, parent, fig, height=280):
        """Embebe una figura matplotlib en un frame CTk"""
        fig.set_size_inches(10, height / 100)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.configure(highlightthickness=0, borderwidth=0)
        canvas_widget.pack(fill="x", padx=16, pady=(0, 16))
        self.analytics_figures.append(fig)
        self.analytics_canvas_widgets.append(canvas)
        return canvas

    def _create_kpi_card(self, parent, icon, icon_fallback, icon_bg_color,
                          title, value, unit="", value_color=None):
        """Crea una card KPI reutilizable"""
        card = Card(parent)
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=20, pady=20)

        row = ctk.CTkFrame(content, fg_color="transparent")
        row.pack(fill="x")

        icon_frame = ctk.CTkFrame(
            row, fg_color=get_alpha_bg(icon_bg_color),
            corner_radius=12, width=52, height=52,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        if icon:
            ctk.CTkLabel(icon_frame, text="", image=icon).place(
                relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(
                icon_frame, text=icon_fallback,
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 20, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            text_frame, text=title,
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        val_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        val_frame.pack(anchor="w")

        val_label = ctk.CTkLabel(
            val_frame, text=str(value),
            text_color=value_color or Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        )
        val_label.pack(side="left")

        if unit:
            ctk.CTkLabel(
                val_frame, text=f" {unit}",
                text_color=Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, 14),
            ).pack(side="left", pady=(8, 0))

        return card, val_label

    def _tab_analytics(self):
        self._cleanup_analytics_figures()

        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self._analytics_scroll = scroll

        # Header
        ctk.CTkLabel(
            scroll, text="Estadisticas TRT",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            scroll, text="Analisis de rendimiento por centro",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w", pady=(0, 24))

        # Sin centros configurados
        if not self.config.sites:
            no_centers = ctk.CTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=12)
            no_centers.pack(fill="both", expand=True, pady=40)
            ctk.CTkLabel(
                no_centers, text="No hay centros configurados",
                text_color=Colors.TEXT_PRIMARY,
                font=(Fonts.FAMILY, 18, "bold"),
            ).pack(pady=(40, 8))
            ctk.CTkLabel(
                no_centers, text="Agrega centros en la seccion de Configuracion para ver estadisticas.",
                text_color=Colors.TEXT_MUTED, font=(Fonts.FAMILY, 14),
            ).pack(pady=(0, 40))
            return

        if self.selected_analytics_center is None:
            self.selected_analytics_center = self.config.sites[0].name

        # === Filtros ===
        filters = ctk.CTkFrame(scroll, fg_color="transparent")
        filters.pack(fill="x", pady=(0, 24))

        # Selector de centro
        center_frame = ctk.CTkFrame(filters, fg_color="transparent")
        center_frame.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(
            center_frame, text="Centro:",
            text_color=Colors.TEXT_MUTED, font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", pady=(0, 4))

        center_names = [site.name for site in self.config.sites]

        def on_center_change(selected):
            self.selected_analytics_center = selected
            self._refresh_analytics_data()

        self.analytics_center_select = LabeledSelect(
            center_frame, label="", options=center_names,
            value=self.selected_analytics_center, command=on_center_change,
        )
        self.analytics_center_select.pack()

        # Selector de periodo
        period_frame = ctk.CTkFrame(filters, fg_color="transparent")
        period_frame.pack(side="left")
        ctk.CTkLabel(
            period_frame, text="Periodo:",
            text_color=Colors.TEXT_MUTED, font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", pady=(0, 4))

        period_buttons = ctk.CTkFrame(period_frame, fg_color="transparent")
        period_buttons.pack()

        self._period_btns = {}
        for days, label in [(7, "7 dias"), (15, "15 dias"), (30, "30 dias")]:
            is_active = self.selected_analytics_period == days
            btn = ctk.CTkButton(
                period_buttons,
                text=label,
                width=80, height=32,
                corner_radius=6,
                font=(Fonts.FAMILY, 12),
                fg_color=Colors.FILTER_ACTIVE_BG if is_active else Colors.FILTER_BG,
                text_color=Colors.FILTER_ACTIVE_TEXT if is_active else Colors.TEXT_SECONDARY,
                border_width=1,
                border_color=Colors.FILTER_ACTIVE_BG if is_active else Colors.FILTER_BORDER,
                hover_color=Colors.ACTION_GREEN_HOVER if is_active else Colors.BG_HOVER,
                command=lambda d=days: self._set_analytics_period(d),
            )
            btn.pack(side="left", padx=2)
            self._period_btns[days] = btn

        # === KPI Cards (4 columnas) ===
        kpi_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 24))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Contenedor para las labels de KPI que se actualizan
        self._analytics_kpi_container = kpi_frame

        # Placeholder - se llenan en _load_analytics_data
        self.analytics_trt_label = None
        self.analytics_trucks_label = None
        self.analytics_critical_label = None
        self.analytics_max_label = None

        self._build_kpi_cards(kpi_frame, {"avg_trt_min": 0, "total_dispatches": 0, "pct_critical": 0, "max_trt_min": 0})

        # === Area de graficos ===
        self._analytics_charts_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self._analytics_charts_container.pack(fill="x")

        # Cargar datos en thread
        self._load_analytics_data()

    def _build_kpi_cards(self, parent, kpi):
        """Construye las 4 KPI cards"""
        # Card 1: TRT Promedio
        card1, self.analytics_trt_label = self._create_kpi_card(
            parent, self.icon_stats_trt, "T", Colors.ACTION_GREEN,
            "TRT Promedio", kpi["avg_trt_min"], "min"
        )
        card1.grid(row=0, column=0, padx=6, sticky="nsew")

        # Card 2: Total Despachos
        card2, self.analytics_trucks_label = self._create_kpi_card(
            parent, self.icon_stats_camiones, "C", Colors.ICON_TRUCKS,
            "Total Despachos", kpi["total_dispatches"]
        )
        card2.grid(row=0, column=1, padx=6, sticky="nsew")

        # Card 3: % Criticos
        card3, self.analytics_critical_label = self._create_kpi_card(
            parent, self.icon_stats_alerta, "!", Colors.WARNING,
            "% Criticos", f'{kpi["pct_critical"]}%',
            value_color=Colors.WARNING if kpi["pct_critical"] > 20 else Colors.TEXT_PRIMARY
        )
        card3.grid(row=0, column=2, padx=6, sticky="nsew")

        # Card 4: TRT Maximo
        card4, self.analytics_max_label = self._create_kpi_card(
            parent, None, "M", Colors.ERROR,
            "TRT Maximo", kpi["max_trt_min"], "min",
            value_color=Colors.ERROR
        )
        card4.grid(row=0, column=3, padx=6, sticky="nsew")

    def _set_analytics_period(self, days):
        """Cambia el periodo de analisis"""
        self.selected_analytics_period = days
        # Actualizar estilo de botones
        for d, btn in self._period_btns.items():
            is_active = d == days
            btn.configure(
                fg_color=Colors.FILTER_ACTIVE_BG if is_active else Colors.FILTER_BG,
                text_color=Colors.FILTER_ACTIVE_TEXT if is_active else Colors.TEXT_SECONDARY,
                border_color=Colors.FILTER_ACTIVE_BG if is_active else Colors.FILTER_BORDER,
                hover_color=Colors.ACTION_GREEN_HOVER if is_active else Colors.BG_HOVER,
            )
        self._refresh_analytics_data()

    def _load_analytics_data(self):
        """Carga datos de analytics en un thread para no bloquear UI"""
        center = self.selected_analytics_center
        days = self.selected_analytics_period

        def fetch():
            try:
                kpi = self.analytics_service.get_kpi_summary(center, days)
                daily = self.analytics_service.get_daily_trend(center, days)
                hourly = self.analytics_service.get_hourly_distribution(center, days)
                heatmap = self.analytics_service.get_heatmap_data(center, days)
                self.after(0, lambda: self._render_analytics(kpi, daily, hourly, heatmap))
            except Exception as e:
                print(f"Error cargando analytics: {e}")

        threading.Thread(target=fetch, daemon=True).start()

    def _render_analytics(self, kpi, daily, hourly, heatmap):
        """Renderiza graficos con datos reales (llamado desde main thread)"""
        # Verificar que el tab sigue activo
        if not hasattr(self, '_analytics_charts_container'):
            return
        try:
            if not self._analytics_charts_container.winfo_exists():
                return
        except Exception:
            return

        # Actualizar KPIs
        try:
            if self.analytics_trt_label and self.analytics_trt_label.winfo_exists():
                self.analytics_trt_label.configure(text=str(kpi["avg_trt_min"]))
            if self.analytics_trucks_label and self.analytics_trucks_label.winfo_exists():
                self.analytics_trucks_label.configure(text=str(kpi["total_dispatches"]))
            if self.analytics_critical_label and self.analytics_critical_label.winfo_exists():
                self.analytics_critical_label.configure(
                    text=f'{kpi["pct_critical"]}%',
                    text_color=Colors.WARNING if kpi["pct_critical"] > 20 else Colors.TEXT_PRIMARY
                )
            if self.analytics_max_label and self.analytics_max_label.winfo_exists():
                self.analytics_max_label.configure(text=str(kpi["max_trt_min"]))
        except Exception:
            pass

        # Limpiar graficos anteriores
        self._cleanup_analytics_figures()
        for widget in self._analytics_charts_container.winfo_children():
            widget.destroy()

        threshold = self._get_site_threshold(self.selected_analytics_center)

        # Grafico 1: Tendencia diaria
        trend_card = Card(self._analytics_charts_container)
        trend_card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            trend_card, text="Tendencia TRT Diario",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            trend_card, text=f"Promedio TRT por dia - Ultimos {self.selected_analytics_period} dias",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", padx=20, pady=(0, 8))

        fig1 = plt.figure(facecolor="white")
        chart_helpers.create_daily_trend_chart(fig1, daily, threshold)
        self._embed_chart(trend_card, fig1, height=300)

        # Grafico 2: Distribucion por hora
        hourly_card = Card(self._analytics_charts_container)
        hourly_card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            hourly_card, text="Distribucion por Hora de Llegada",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            hourly_card, text="TRT promedio segun hora de ingreso a planta",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", padx=20, pady=(0, 8))

        fig2 = plt.figure(facecolor="white")
        chart_helpers.create_hourly_distribution_chart(fig2, hourly, threshold)
        self._embed_chart(hourly_card, fig2, height=300)

        # Grafico 3: Heatmap
        heatmap_card = Card(self._analytics_charts_container)
        heatmap_card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            heatmap_card, text="Mapa de Calor: Hora x Dia de Semana",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            heatmap_card, text="TRT promedio por hora y dia de la semana",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w", padx=20, pady=(0, 8))

        fig3 = plt.figure(facecolor="white")
        chart_helpers.create_heatmap_chart(fig3, heatmap)
        self._embed_chart(heatmap_card, fig3, height=400)

    def _refresh_analytics_data(self):
        """Recarga datos de analytics cuando cambia centro o periodo"""
        if not hasattr(self, '_analytics_charts_container'):
            return
        try:
            if not self._analytics_charts_container.winfo_exists():
                return
        except Exception:
            return
        self._load_analytics_data()

    # ========== TAB: Settings ==========
    def _tab_settings(self):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Header
        ctk.CTkLabel(
            scroll,
            text="Configuracion",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            scroll,
            text="Ajustes generales del sistema",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w", pady=(0, 24))

        # Connection settings
        conn_card = Card(scroll)
        conn_card.pack(fill="x", pady=8)

        conn_content = ctk.CTkFrame(conn_card, fg_color="transparent")
        conn_content.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            conn_content,
            text="Conexion",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        # Usar valores reales de la configuración
        LabeledInput(conn_content, label="URL del servidor TRT", value=self.config.base_url).pack(fill="x", pady=8)
        LabeledInput(conn_content, label="Intervalo de consulta (segundos)", value=str(self.config.poll_seconds)).pack(fill="x", pady=8)
        LabeledInput(conn_content, label="Reenvio de alertas (minutos)", value=str(self.config.realert_minutes)).pack(fill="x", pady=8)

        # WhatsApp settings
        wa_card = Card(scroll)
        wa_card.pack(fill="x", pady=8)

        wa_content = ctk.CTkFrame(wa_card, fg_color="transparent")
        wa_content.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            wa_content,
            text="WhatsApp",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        wa_status = ctk.CTkFrame(wa_content, fg_color="transparent")
        wa_status.pack(fill="x", pady=(0, 16))

        wa_info = ctk.CTkFrame(wa_status, fg_color="transparent")
        wa_info.pack(side="left")

        ctk.CTkLabel(
            wa_info,
            text="Estado de conexion",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w")

        # Mostrar teléfono real del bot de WhatsApp
        phone_text = self.whatsapp_phone if self.whatsapp_phone else "No conectado"
        ctk.CTkLabel(
            wa_info,
            text=phone_text,
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        # Status real de WhatsApp
        wa_status_text = "Conectado" if self.bot_status == "connected" else "Desconectado"
        StatusBadge(wa_status, status=self.bot_status, label=wa_status_text).pack(side="right")

        SecondaryButton(
            wa_content,
            text="Desvincular WhatsApp",
            command=self._confirm_disconnect_whatsapp
        ).pack(anchor="w")

        # Window behavior
        window_card = Card(scroll)
        window_card.pack(fill="x", pady=8)

        window_content = ctk.CTkFrame(window_card, fg_color="transparent")
        window_content.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            window_content,
            text="Comportamiento de ventana",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        # Minimize to tray
        tray_row = ctk.CTkFrame(window_content, fg_color="transparent")
        tray_row.pack(fill="x", pady=8)

        tray_text = ctk.CTkFrame(tray_row, fg_color="transparent")
        tray_text.pack(side="left")

        ctk.CTkLabel(
            tray_text,
            text="Minimizar a bandeja al cerrar",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w")

        ctk.CTkLabel(
            tray_text,
            text="La aplicacion seguira ejecutandose en segundo plano",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        ToggleSwitch(tray_row, initial=True).pack(side="right")

        # Start with Windows
        startup_row = ctk.CTkFrame(window_content, fg_color="transparent")
        startup_row.pack(fill="x", pady=8)

        startup_text = ctk.CTkFrame(startup_row, fg_color="transparent")
        startup_text.pack(side="left")

        ctk.CTkLabel(
            startup_text,
            text="Iniciar con Windows",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w")

        ctk.CTkLabel(
            startup_text,
            text="El monitor se iniciara automaticamente al encender el equipo",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        ToggleSwitch(startup_row, initial=True).pack(side="right")

        # Danger zone
        danger_card = Card(scroll)
        danger_card.pack(fill="x", pady=8)

        danger_content = ctk.CTkFrame(danger_card, fg_color="transparent")
        danger_content.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            danger_content,
            text="Zona de Peligro",
            text_color=Colors.ERROR,
            font=(Fonts.FAMILY, 16, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            danger_content,
            text="Las siguientes acciones son irreversibles y eliminarán toda la configuración del sistema.",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
            wraplength=800
        ).pack(anchor="w", pady=(0, 16))

        danger_row = ctk.CTkFrame(danger_content, fg_color="transparent")
        danger_row.pack(fill="x")

        danger_text = ctk.CTkFrame(danger_row, fg_color="transparent")
        danger_text.pack(side="left")

        ctk.CTkLabel(
            danger_text,
            text="Borrar toda la configuración",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14),
        ).pack(anchor="w")

        ctk.CTkLabel(
            danger_text,
            text="Elimina todos los centros configurados y reinicia el asistente de configuración",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack(anchor="w")

        DangerButton(
            danger_row,
            text="Borrar Configuración",
            command=self._confirm_reset_config
        ).pack(side="right")

        # Save buttons
        buttons_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=24)

        SecondaryButton(buttons_frame, text="Restaurar valores").pack(side="right", padx=(8, 0))
        PrimaryButton(buttons_frame, text="Guardar cambios").pack(side="right")
