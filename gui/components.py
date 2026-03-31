# Reusable GUI components for CCU-TRT application - Light Corporate Theme
import customtkinter as ctk
from typing import Callable, Optional, List, Dict, Any
from .styles import Colors, Fonts, Dimensions
from core.banner import get_tipo_descarga, get_tipo_descarga_for_site


class Card(ctk.CTkFrame):
    """Tarjeta blanca con borde sutil - estilo corporativo"""

    def __init__(self, master, hover: bool = False, **kwargs):
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=Dimensions.CARD_RADIUS,
            border_width=1,
            border_color=Colors.CARD_BORDER,
            **kwargs
        )

        if hover:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.configure(fg_color=Colors.BG_HOVER)

    def _on_leave(self, event):
        self.configure(fg_color=Colors.BG_CARD)


class StatusBadge(ctk.CTkFrame):
    """Badge de estado minimalista - punto de color + texto"""

    STATUS_COLORS = {
        "connected": (Colors.SUCCESS_BG, Colors.SUCCESS),
        "disconnected": (Colors.ERROR_BG, Colors.ERROR),
        "warning": (Colors.WARNING_BG, Colors.WARNING),
        "idle": (Colors.INFO_BG, Colors.INFO),
    }

    def __init__(self, master, status: str = "idle", label: str = "", label_color: str = None, **kwargs):
        bg_color, text_color = self.STATUS_COLORS.get(status, self.STATUS_COLORS["idle"])
        self._label_color = label_color

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        # Punto indicador
        self.dot = ctk.CTkLabel(
            self,
            text="",
            width=8,
            height=8,
            fg_color=text_color,
            corner_radius=4,
        )
        self.dot.pack(side="left", padx=(4, 6), pady=4)

        # Texto
        self.label = ctk.CTkLabel(
            self,
            text=label,
            text_color=self._label_color or Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
        )
        self.label.pack(side="left", padx=(0, 4), pady=4)

        self._status = status

    def set_status(self, status: str, label: str = None):
        """Actualiza el estado del badge"""
        bg_color, text_color = self.STATUS_COLORS.get(status, self.STATUS_COLORS["idle"])
        self.dot.configure(fg_color=text_color)
        if label:
            self.label.configure(text=label)
        self._status = status


class PercentageBadge(ctk.CTkFrame):
    """Badge que muestra porcentaje de cambio vs ayer"""

    def __init__(self, master, value: int, inverted: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        is_positive = value < 0 if inverted else value > 0
        color = Colors.SUCCESS if is_positive else Colors.ERROR
        arrow = "↑" if value > 0 else "↓" if value < 0 else ""

        self.value_label = ctk.CTkLabel(
            self,
            text=f"{arrow} {abs(value)}%",
            text_color=color,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE, "bold"),
        )
        self.value_label.pack(side="left")

        self.vs_label = ctk.CTkLabel(
            self,
            text=" vs ayer",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.TINY_SIZE),
        )
        self.vs_label.pack(side="left")


class PrimaryButton(ctk.CTkButton):
    """Boton primario - Verde institucional CCU"""

    def __init__(self, master, text: str, command: Callable = None, size: str = "md", **kwargs):
        sizes = {
            "sm": (12, 6, Fonts.SMALL_SIZE),
            "md": (20, 10, Fonts.BODY_SIZE),
            "lg": (28, 14, Fonts.SUBHEADING_SIZE - 2),
        }
        pad_x, pad_y, font_size = sizes.get(size, sizes["md"])

        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=Colors.CCU_GREEN,
            hover_color=Colors.CCU_GREEN_HOVER,
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, font_size, "bold"),
            corner_radius=Dimensions.BUTTON_RADIUS,
            **kwargs
        )


class SecondaryButton(ctk.CTkButton):
    """Boton secundario con borde - estilo corporativo"""

    def __init__(self, master, text: str, command: Callable = None, size: str = "md", **kwargs):
        sizes = {
            "sm": (12, 6, Fonts.SMALL_SIZE),
            "md": (20, 10, Fonts.BODY_SIZE),
            "lg": (28, 14, Fonts.SUBHEADING_SIZE - 2),
        }
        pad_x, pad_y, font_size = sizes.get(size, sizes["md"])

        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.CARD_BORDER,
            font=(Fonts.FAMILY, font_size),
            corner_radius=Dimensions.BUTTON_RADIUS,
            **kwargs
        )


class SuccessButton(ctk.CTkButton):
    """Boton de accion/iniciar - Verde accion"""

    def __init__(self, master, text: str, command: Callable = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=Colors.ACTION_GREEN,
            hover_color=Colors.ACTION_GREEN_HOVER,
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold"),
            corner_radius=Dimensions.BUTTON_RADIUS,
            **kwargs
        )


class DangerButton(ctk.CTkButton):
    """Boton de peligro/eliminar"""

    def __init__(self, master, text: str, command: Callable = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=Colors.ERROR,
            hover_color="#C62828",
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold"),
            corner_radius=Dimensions.BUTTON_RADIUS,
            **kwargs
        )


class GoldButton(ctk.CTkButton):
    """Boton verde especial CCU"""

    def __init__(self, master, text: str, command: Callable = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=Colors.ACTION_GREEN,
            hover_color=Colors.ACTION_GREEN_HOVER,
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold"),
            corner_radius=Dimensions.BUTTON_RADIUS,
            **kwargs
        )


class LabeledInput(ctk.CTkFrame):
    """Input con label - estilo corporativo limpio"""

    def __init__(
        self,
        master,
        label: str,
        placeholder: str = "",
        value: str = "",
        input_type: str = "text",
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        if label:
            self.label = ctk.CTkLabel(
                self,
                text=label,
                text_color=Colors.TEXT_SECONDARY,
                font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
                anchor="w",
            )
            self.label.pack(fill="x", pady=(0, 6))

        show = "*" if input_type == "password" else ""

        self.input = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_LIGHT,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
            show=show,
        )
        self.input.pack(fill="x")

        if value:
            self.input.insert(0, value)

    def get(self) -> str:
        return self.input.get()

    def set(self, value: str):
        self.input.delete(0, "end")
        self.input.insert(0, value)


class LabeledSelect(ctk.CTkFrame):
    """Select/Dropdown con label"""

    def __init__(
        self,
        master,
        label: str,
        options: List[str],
        placeholder: str = "Seleccionar...",
        value: str = None,
        command: Callable = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        if label:
            self.label = ctk.CTkLabel(
                self,
                text=label,
                text_color=Colors.TEXT_SECONDARY,
                font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
                anchor="w",
            )
            self.label.pack(fill="x", pady=(0, 6))

        self.select = ctk.CTkOptionMenu(
            self,
            values=options if options else [placeholder],
            fg_color=Colors.BG_CARD,
            button_color=Colors.CARD_BORDER,
            button_hover_color=Colors.BG_HOVER,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
            command=command,
        )
        self.select.pack(fill="x")

        if value and value in options:
            self.select.set(value)
        elif not value:
            self.select.set(placeholder)

    def get(self) -> str:
        return self.select.get()

    def set(self, value: str):
        self.select.set(value)

    def set_options(self, options: List[str]):
        """Actualiza las opciones del selector"""
        self.select.configure(values=options if options else ["Sin opciones"])


class LabeledComboBox(ctk.CTkFrame):
    """ComboBox con label (permite escribir y buscar)"""

    def __init__(
        self,
        master,
        label: str,
        options: List[str],
        placeholder: str = "Seleccionar...",
        value: str = None,
        command: Callable = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        if label:
            self.label = ctk.CTkLabel(
                self,
                text=label,
                text_color=Colors.TEXT_SECONDARY,
                font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
                anchor="w",
            )
            self.label.pack(fill="x", pady=(0, 6))

        self.combo = ctk.CTkComboBox(
            self,
            values=options if options else [placeholder],
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            button_color=Colors.CARD_BORDER,
            button_hover_color=Colors.BG_HOVER,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
            command=command,
        )
        self.combo.pack(fill="x")

        if value and value in options:
            self.combo.set(value)
        elif not value:
            self.combo.set(placeholder)

    def get(self) -> str:
        return self.combo.get()

    def set(self, value: str):
        self.combo.set(value)

    def set_options(self, options: List[str]):
        """Actualiza las opciones del combo"""
        self.combo.configure(values=options if options else ["Sin opciones"])


class ProgressSteps(ctk.CTkFrame):
    """Indicador de pasos de progreso - tema verde corporativo"""

    def __init__(self, master, steps: List[str], current_step: int = 0, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.steps = steps
        self.current_step = current_step
        self.step_widgets = []
        self.line_widgets = []

        self._create_widgets()

    def _create_widgets(self):
        for i, step in enumerate(self.steps):
            # Contenedor del paso
            step_frame = ctk.CTkFrame(self, fg_color="transparent")
            step_frame.pack(side="left", padx=4)

            # Circulo del paso
            is_completed = i < self.current_step
            is_current = i == self.current_step

            circle_color = Colors.CCU_GREEN if i <= self.current_step else Colors.CARD_BORDER
            text_color = Colors.TEXT_PRIMARY if i <= self.current_step else Colors.TEXT_MUTED

            circle = ctk.CTkLabel(
                step_frame,
                text="✓" if is_completed else str(i + 1),
                width=36,
                height=36,
                fg_color=circle_color,
                corner_radius=18,
                text_color=Colors.TEXT_ON_GREEN if i <= self.current_step else Colors.TEXT_MUTED,
                font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold"),
            )
            circle.pack()

            # Nombre del paso
            label = ctk.CTkLabel(
                step_frame,
                text=step,
                text_color=text_color,
                font=(Fonts.FAMILY, Fonts.TINY_SIZE, "bold" if is_current else "normal"),
                wraplength=80,
            )
            label.pack(pady=(8, 0))

            self.step_widgets.append((circle, label))

            # Linea entre pasos
            if i < len(self.steps) - 1:
                line_color = Colors.CCU_GREEN if i < self.current_step else Colors.CARD_BORDER
                line = ctk.CTkFrame(
                    self,
                    width=40,
                    height=2,
                    fg_color=line_color,
                )
                line.pack(side="left", pady=(0, 30))
                self.line_widgets.append(line)

    def set_step(self, step: int):
        """Actualiza el paso actual"""
        self.current_step = step

        for i, (circle, label) in enumerate(self.step_widgets):
            is_completed = i < self.current_step
            is_current = i == self.current_step

            circle_color = Colors.CCU_GREEN if i <= self.current_step else Colors.CARD_BORDER
            text_color = Colors.TEXT_PRIMARY if i <= self.current_step else Colors.TEXT_MUTED

            circle.configure(
                text="✓" if is_completed else str(i + 1),
                fg_color=circle_color,
                text_color=Colors.TEXT_ON_GREEN if i <= self.current_step else Colors.TEXT_MUTED,
            )
            label.configure(
                text_color=text_color,
                font=(Fonts.FAMILY, Fonts.TINY_SIZE, "bold" if is_current else "normal"),
            )

        for i, line in enumerate(self.line_widgets):
            line_color = Colors.CCU_GREEN if i < self.current_step else Colors.CARD_BORDER
            line.configure(fg_color=line_color)


class CenterCard(Card):
    """Tarjeta de centro de distribucion para el dashboard"""

    def __init__(
    self,
    master,
    name: str,
    status: str = "normal",
    trucks_in_plant: int = 0,
    avg_time: int = 0,
    threshold: int = 100,
    alerts: int = 0,
    trucks_list: list = None,
    threshold_lateral: int = 100,
    threshold_trasera: int = 100,
    threshold_interna: int = 100,
    **kwargs
):
        super().__init__(master, hover=True, **kwargs)

        self.configure(width=400)

        # Guardar datos para actualizacion
        self.name = name
        self.status = status
        self.trucks_in_plant = trucks_in_plant
        self.avg_time = avg_time
        self.threshold = threshold
        self.alerts = alerts
        self.trucks_list = trucks_list or []
        self.threshold_lateral = threshold_lateral
        self.threshold_trasera = threshold_trasera
        self.threshold_interna = threshold_interna

        # Guardar colores de estado
        self.status_colors = {
            "normal": Colors.SUCCESS,
            "warning": Colors.WARNING,
            "critical": Colors.ERROR,
        }

        # Header con nombre y status
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 16))

        name_frame = ctk.CTkFrame(header, fg_color="transparent")
        name_frame.pack(side="left")

        ctk.CTkLabel(
            name_frame,
            text=name,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 16, "bold"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            name_frame,
            text="Centro de Distribucion",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
            anchor="w",
        ).pack(anchor="w")

        # Status dot
        status_color = self.status_colors.get(status, Colors.SUCCESS)

        self.status_dot = ctk.CTkLabel(
            header,
            text="",
            width=12,
            height=12,
            fg_color=status_color,
            corner_radius=6,
        )
        self.status_dot.pack(side="right")

        # Stats
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(0, 16))

        # Camiones en planta
        trucks_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        trucks_frame.pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(
            trucks_frame,
            text="Camiones en planta",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.TINY_SIZE),
            anchor="w",
        ).pack(anchor="w")

        self.trucks_label = ctk.CTkLabel(
            trucks_frame,
            text=str(trucks_in_plant),
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
            anchor="w",
        )
        self.trucks_label.pack(anchor="w")

        # Tiempo promedio
        time_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        time_frame.pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(
            time_frame,
            text="Tiempo promedio",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.TINY_SIZE),
            anchor="w",
        ).pack(anchor="w")

        time_label_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
        time_label_frame.pack(anchor="w")

        self.time_label = ctk.CTkLabel(
            time_label_frame,
            text=str(avg_time),
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 24, "bold"),
        )
        self.time_label.pack(side="left")

        ctk.CTkLabel(
            time_label_frame,
            text=" min",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
        ).pack(side="left", pady=(8, 0))

        # Progress bar
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=20, pady=(0, 12))

        percentage = min((avg_time / threshold) * 100, 100) if threshold > 0 else 0

        header_progress = ctk.CTkFrame(progress_frame, fg_color="transparent")
        header_progress.pack(fill="x", pady=(0, 6))

        self.threshold_label = ctk.CTkLabel(
            header_progress,
            text=f"Umbral: {threshold} min",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, Fonts.TINY_SIZE),
        )
        self.threshold_label.pack(side="left")

        self.percentage_label = ctk.CTkLabel(
            header_progress,
            text=f"{int(percentage)}%",
            text_color=status_color,
            font=(Fonts.FAMILY, Fonts.TINY_SIZE, "bold"),
        )
        self.percentage_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            width=360,
            height=6,
            fg_color=Colors.BG_HOVER,
            progress_color=status_color,
            corner_radius=3,
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(percentage / 100)

        # Alerts container - NO pack si no hay alertas (evita espacio vacio)
        self.alerts_container = ctk.CTkFrame(self, fg_color="transparent")
        if alerts > 0:
            self.alerts_container.pack(fill="x", padx=20, pady=(0, 12))
            alert_frame = ctk.CTkFrame(
                self.alerts_container,
                fg_color=Colors.ERROR_BG,
                corner_radius=6,
            )
            alert_frame.pack(fill="x")

            ctk.CTkLabel(
                alert_frame,
                text=f"{alerts} alertas activas",
                text_color=Colors.ERROR,
                font=(Fonts.FAMILY, Fonts.SMALL_SIZE, "bold"),
            ).pack(padx=12, pady=8)

        # Truck detail table container
        self.table_container = ctk.CTkFrame(self, fg_color="transparent")
        self.table_container.pack(fill="x", padx=20, pady=(0, 16))

        if self.trucks_list:
            self._build_truck_table()

    def _get_truck_threshold(self, tipo: str) -> int:
        """Devuelve umbral en minutos segun tipo de descarga"""
        tipo_upper = tipo.upper() if tipo else "LATERAL"
        if tipo_upper == "INTERNA":
            return self.threshold_interna or self.threshold
        elif tipo_upper == "TRASERA":
            return self.threshold_trasera or self.threshold
        return self.threshold_lateral or self.threshold

    def _get_trt_color(self, minutes: int, threshold: int) -> str:
        """Color de texto para TRT: <80% verde, 80-130% amarillo, >130% rojo"""
        if threshold <= 0:
            return Colors.TEXT_PRIMARY
        ratio = minutes / threshold
        if ratio < 0.8:
            return Colors.SUCCESS
        elif ratio < 1.3:
            return Colors.WARNING
        return Colors.ERROR

    def _get_row_bg(self, minutes: int, threshold: int) -> str:
        """Color de fondo de fila: solo para warning/critical"""
        if threshold <= 0:
            return "transparent"
        ratio = minutes / threshold
        if ratio >= 1.3:
            return Colors.ERROR_BG
        elif ratio >= 0.8:
            return Colors.WARNING_BG
        return "transparent"

    def _build_truck_table(self):
        """Construye la tabla de detalle de camiones dentro de table_container"""
        # Limpiar contenedor
        for widget in self.table_container.winfo_children():
            widget.destroy()

        trucks = self.trucks_list
        if not trucks:
            return

        # Separador sutil
        separator = ctk.CTkFrame(self.table_container, fg_color=Colors.CARD_BORDER, height=1)
        separator.pack(fill="x", pady=(0, 8))

        # Titulo
        ctk.CTkLabel(
            self.table_container,
            text=f"Detalle camiones ({len(trucks)})",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        # Ordenar por TRT descendente (mas critico arriba)
        sorted_trucks = sorted(trucks, key=lambda t: t.time_in_plant_minutes, reverse=True)

        # Columnas con pesos fijos que sumen a un total coherente
        # Patente | Empresa | Tipo | Ingreso | TRT
        col_configs = [
            {"weight": 3, "minsize": 70},   # Patente
            {"weight": 4, "minsize": 90},   # Empresa
            {"weight": 2, "minsize": 40},   # Tipo
            {"weight": 4, "minsize": 95},   # Ingreso
            {"weight": 3, "minsize": 70},   # TRT
        ]

        def _configure_cols(frame):
            for i, cfg in enumerate(col_configs):
                frame.grid_columnconfigure(i, weight=cfg["weight"], minsize=cfg["minsize"])

        # Header row
        header_frame = ctk.CTkFrame(self.table_container, fg_color=Colors.BG_HOVER, corner_radius=4)
        header_frame.pack(fill="x")
        _configure_cols(header_frame)

        header_font = (Fonts.FAMILY, 11, "bold")
        header_color = Colors.TEXT_MUTED
        header_texts = ["Patente", "Empresa", "Tipo", "Ingreso", "TRT"]
        for col_idx, col_text in enumerate(header_texts):
            ctk.CTkLabel(
                header_frame, text=col_text, text_color=header_color,
                font=header_font, anchor="w",
            ).grid(row=0, column=col_idx, padx=(10 if col_idx == 0 else 4, 4), pady=6, sticky="ew")

        # Scrollable area for rows
        row_count = len(sorted_trucks)
        row_height = 30
        needed_height = row_count * row_height
        scroll_height = min(needed_height, 200)

        scroll_frame = ctk.CTkScrollableFrame(
            self.table_container,
            fg_color="transparent",
            height=scroll_height,
            corner_radius=0,
        )
        scroll_frame.pack(fill="x", expand=True)
        _configure_cols(scroll_frame)

        cell_font = (Fonts.FAMILY, 11)
        cell_font_bold = (Fonts.FAMILY, 11, "bold")

        for row_idx, truck in enumerate(sorted_trucks):
            tipo = get_tipo_descarga_for_site(truck.company, self.threshold_trasera, self.threshold_interna)
            tipo_short = {"LATERAL": "LAT", "TRASERA": "TRA", "INTERNA": "INT"}.get(tipo, "LAT")
            threshold_for_truck = self._get_truck_threshold(tipo)
            minutes = truck.time_in_plant_minutes
            row_bg = self._get_row_bg(minutes, threshold_for_truck)
            trt_color = self._get_trt_color(minutes, threshold_for_truck)

            # Formatear TRT intuitivo: Xh Ym
            hours = minutes // 60
            mins = minutes % 60
            if hours > 0:
                trt_text = f"{hours}h {mins:02d}m"
            else:
                trt_text = f"{mins}m"

            # Formatear hora de ingreso: DD/MM HH:MM
            arrival_raw = truck.arrival_time or ""
            if " " in arrival_raw:
                parts = arrival_raw.strip().split(" ")
                date_part = parts[0] if parts else ""
                time_part = parts[-1][:5] if len(parts) > 1 else ""
                if "-" in date_part and len(date_part) >= 10:
                    date_part = f"{date_part[8:10]}/{date_part[5:7]}"
                elif "-" in date_part:
                    date_part = date_part.replace("-", "/")
                arrival = f"{date_part} {time_part}".strip()
            elif len(arrival_raw) >= 5:
                arrival = arrival_raw
            else:
                arrival = arrival_raw

            # Empresa: fallback si esta vacia
            empresa = (truck.company or "").strip()
            if not empresa:
                empresa = "Sin info"
            elif len(empresa) > 16:
                empresa = empresa[:15] + "."

            # Row frame con fondo segun estado
            row_frame = ctk.CTkFrame(scroll_frame, fg_color=row_bg, corner_radius=2, height=row_height)
            row_frame.grid(row=row_idx, column=0, columnspan=5, sticky="ew", pady=(1, 0))
            _configure_cols(row_frame)
            row_frame.grid_propagate(False)

            ctk.CTkLabel(
                row_frame, text=truck.plate or "", text_color=Colors.TEXT_PRIMARY,
                font=cell_font, anchor="w",
            ).grid(row=0, column=0, padx=(10, 4), sticky="ew")

            empresa_color = Colors.TEXT_MUTED if empresa == "Sin info" else Colors.TEXT_SECONDARY
            ctk.CTkLabel(
                row_frame, text=empresa, text_color=empresa_color,
                font=cell_font, anchor="w",
            ).grid(row=0, column=1, padx=4, sticky="ew")

            ctk.CTkLabel(
                row_frame, text=tipo_short, text_color=Colors.TEXT_MUTED,
                font=cell_font, anchor="w",
            ).grid(row=0, column=2, padx=4, sticky="ew")

            ctk.CTkLabel(
                row_frame, text=arrival, text_color=Colors.TEXT_MUTED,
                font=cell_font, anchor="w",
            ).grid(row=0, column=3, padx=4, sticky="ew")

            ctk.CTkLabel(
                row_frame, text=trt_text, text_color=trt_color,
                font=cell_font_bold, anchor="w",
            ).grid(row=0, column=4, padx=4, sticky="ew")

    def update_data(
        self, status: str, trucks_in_plant: int, avg_time: int, threshold: int, alerts: int,
        trucks_list: list = None, threshold_lateral: int = None,
        threshold_trasera: int = None, threshold_interna: int = None,
    ):
        """Actualiza los datos de la card sin recrearla (sin parpadeo)"""
        try:
            self.status = status
            self.trucks_in_plant = trucks_in_plant
            self.avg_time = avg_time
            self.threshold = threshold
            self.alerts = alerts
            if trucks_list is not None:
                self.trucks_list = trucks_list
            if threshold_lateral is not None:
                self.threshold_lateral = threshold_lateral
            if threshold_trasera is not None:
                self.threshold_trasera = threshold_trasera
            if threshold_interna is not None:
                self.threshold_interna = threshold_interna

            # Actualizar status dot
            status_color = self.status_colors.get(status, Colors.SUCCESS)
            if hasattr(self, 'status_dot'):
                self.status_dot.configure(fg_color=status_color)

            # Actualizar labels
            if hasattr(self, 'trucks_label'):
                self.trucks_label.configure(text=str(trucks_in_plant))
            if hasattr(self, 'time_label'):
                self.time_label.configure(text=str(avg_time))
            if hasattr(self, 'threshold_label'):
                self.threshold_label.configure(text=f"Umbral: {threshold} min")

            # Actualizar progress bar
            percentage = min((avg_time / threshold) * 100, 100) if threshold > 0 else 0
            if hasattr(self, 'percentage_label'):
                self.percentage_label.configure(text=f"{int(percentage)}%", text_color=status_color)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.configure(progress_color=status_color)
                self.progress_bar.set(percentage / 100)

            # Actualizar alertas - pack/unpack dinamicamente
            if hasattr(self, 'alerts_container'):
                for widget in self.alerts_container.winfo_children():
                    widget.destroy()

                if alerts > 0:
                    # Asegurar que esta visible
                    if not self.alerts_container.winfo_manager():
                        # Insertar antes del table_container
                        self.alerts_container.pack(fill="x", padx=20, pady=(0, 12),
                                                    before=self.table_container)
                    alert_frame = ctk.CTkFrame(
                        self.alerts_container,
                        fg_color=Colors.ERROR_BG,
                        corner_radius=6,
                    )
                    alert_frame.pack(fill="x")

                    ctk.CTkLabel(
                        alert_frame,
                        text=f"{alerts} alertas activas",
                        text_color=Colors.ERROR,
                        font=(Fonts.FAMILY, Fonts.SMALL_SIZE, "bold"),
                    ).pack(padx=12, pady=8)
                else:
                    # Ocultar el contenedor si no hay alertas
                    self.alerts_container.pack_forget()

            # Actualizar tabla de camiones
            if hasattr(self, 'table_container'):
                self._build_truck_table()

        except Exception as e:
            print(f"Error actualizando CenterCard: {e}")


class LogViewer(ctk.CTkFrame):
    """Visor de logs con scroll y limite de entradas"""

    MAX_LINES = 100

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Colors.BG_PRIMARY,
            corner_radius=8,
            **kwargs
        )

        self.textbox = ctk.CTkTextbox(
            self,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.TEXT_SECONDARY,
            font=("Consolas", Fonts.SMALL_SIZE),
            wrap="word",
            state="disabled",
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=12)
        self.line_count = 0

    def add_log(self, time: str, log_type: str, message: str):
        """Agrega una entrada de log (con limite de 100 lineas)"""
        self.textbox.configure(state="normal")

        if self.line_count >= self.MAX_LINES:
            self.textbox.delete("1.0", "2.0")
            self.line_count -= 1

        self.textbox.insert("end", f"[{time}] {message}\n")
        self.line_count += 1

        self.textbox.configure(state="disabled")
        self.textbox.see("end")

    def clear(self):
        """Limpia el log"""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")


class SidebarButton(ctk.CTkFrame):
    """Boton del sidebar con icono y texto - sobre fondo verde"""

    def __init__(
        self,
        master,
        icon: str,
        text: str,
        command: Callable = None,
        is_active: bool = False,
        collapsed: bool = False,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=Colors.BG_ACTIVE if is_active else "transparent",
            corner_radius=8,
            **kwargs
        )

        self.command = command
        self.is_active = is_active
        self.collapsed = collapsed
        self.icon = icon
        self.text = text

        # Border izquierdo activo
        self.border = ctk.CTkFrame(
            self,
            width=3,
            fg_color=Colors.TEXT_ON_GREEN if is_active else "transparent",
        )
        self.border.pack(side="left", fill="y")

        # Contenido
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=12, pady=12)

        # Detectar si el icono es una imagen CTkImage o texto
        if isinstance(icon, ctk.CTkImage):
            self.icon_label = ctk.CTkLabel(
                content,
                text="",
                image=icon,
            )
        else:
            self.icon_label = ctk.CTkLabel(
                content,
                text=icon,
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 18),
            )
        self.icon_label.pack(side="left")

        if not collapsed:
            self.text_label = ctk.CTkLabel(
                content,
                text=text,
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold" if is_active else "normal"),
            )
            self.text_label.pack(side="left", padx=(12, 0))

        # Eventos
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        for widget in self.winfo_children():
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, event):
        if self.command:
            self.command()

    def _on_enter(self, event):
        if not self.is_active:
            self.configure(fg_color=Colors.CCU_GREEN_LIGHT)

    def _on_leave(self, event):
        if not self.is_active:
            self.configure(fg_color="transparent")

    def set_active(self, active: bool):
        self.is_active = active
        self.configure(fg_color=Colors.BG_ACTIVE if active else "transparent")
        self.border.configure(fg_color=Colors.TEXT_ON_GREEN if active else "transparent")
        if hasattr(self, 'text_label'):
            self.text_label.configure(
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, Fonts.BODY_SIZE, "bold" if active else "normal"),
            )


class ToggleSwitch(ctk.CTkFrame):
    """Switch de toggle personalizado"""

    def __init__(self, master, initial: bool = False, command: Callable = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.value = initial
        self.command = command

        self.switch = ctk.CTkSwitch(
            self,
            text="",
            width=48,
            height=24,
            switch_width=44,
            switch_height=22,
            fg_color=Colors.CARD_BORDER,
            progress_color=Colors.ACTION_GREEN,
            button_color=Colors.BG_CARD,
            button_hover_color=Colors.BG_CARD,
            command=self._on_toggle,
        )
        self.switch.pack()

        if initial:
            self.switch.select()

    def _on_toggle(self):
        self.value = self.switch.get() == 1
        if self.command:
            self.command(self.value)

    def get(self) -> bool:
        return self.switch.get() == 1

    def set(self, value: bool):
        if value:
            self.switch.select()
        else:
            self.switch.deselect()
        self.value = value


class ConnectionErrorNotification(ctk.CTkToplevel):
    """Notificacion de error de conexion con auto-cierre"""

    def __init__(self, parent, error_message: str, on_retry: Callable = None, auto_close_ms: int = 300000):
        super().__init__(parent)

        self.on_retry = on_retry
        self.auto_close_ms = auto_close_ms

        # Configurar ventana
        self.title("Error de Conexion")
        self.geometry("450x250")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)

        # Centrar en pantalla
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.winfo_screenheight() // 2) - (250 // 2)
        self.geometry(f"450x250+{x}+{y}")

        # Siempre al frente
        self.attributes("-topmost", True)

        # Contenedor principal
        container = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=12,
                                 border_width=1, border_color=Colors.CARD_BORDER)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header con icono de error
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        icon_frame = ctk.CTkFrame(
            header,
            fg_color=Colors.ERROR_BG,
            corner_radius=24,
            width=48,
            height=48
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        ctk.CTkLabel(
            icon_frame,
            text="!",
            text_color=Colors.ERROR,
            font=(Fonts.FAMILY, 24, "bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0), fill="x", expand=True)

        ctk.CTkLabel(
            text_frame,
            text="Error de Conexion",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 18, "bold"),
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame,
            text="No se puede conectar al servidor TRT",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
            anchor="w"
        ).pack(anchor="w")

        # Mensaje de error
        error_frame = ctk.CTkFrame(
            container,
            fg_color=Colors.BG_PRIMARY,
            corner_radius=8
        )
        error_frame.pack(fill="both", expand=True, padx=20, pady=10)

        display_message = error_message if len(error_message) < 200 else error_message[:200] + "..."

        ctk.CTkLabel(
            error_frame,
            text=display_message,
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 11),
            wraplength=380,
            justify="left"
        ).pack(padx=12, pady=12)

        # Botones
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(10, 20))

        SecondaryButton(
            button_frame,
            text="Cerrar",
            command=self._close,
            size="sm"
        ).pack(side="right", padx=(8, 0))

        if on_retry:
            PrimaryButton(
                button_frame,
                text="Reintentar",
                command=self._retry,
                size="sm"
            ).pack(side="right")

        self.close_timer = self.after(auto_close_ms, self._auto_close)

    def _retry(self):
        if self.on_retry:
            self.on_retry()
        self._close()

    def _close(self):
        try:
            if hasattr(self, 'close_timer'):
                self.after_cancel(self.close_timer)
        except Exception:
            pass
        self.destroy()

    def _auto_close(self):
        self._close()


class AddCenterDialog(ctk.CTkToplevel):
    """Dialogo para agregar un nuevo centro"""

    def __init__(self, parent, on_save: Callable = None, available_centers: List = None, whatsapp_groups: List = None):
        super().__init__(parent)

        self.on_save = on_save
        self.result = None
        self.available_centers = available_centers or []
        self.whatsapp_groups = whatsapp_groups or []
        self.selected_center = None

        # Configurar ventana
        self.title("Agregar Centro de Distribucion")
        self.geometry("500x650")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)

        # Centrar en pantalla
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (650 // 2)
        self.geometry(f"500x650+{x}+{y}")

        # Bloquear interaccion con ventana principal
        self.transient(parent)
        self.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        # Contenedor principal con scroll
        main_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=Colors.BG_CARD,
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        ctk.CTkLabel(
            main_frame,
            text="Nuevo Centro",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 20, "bold")
        ).pack(anchor="w", pady=(10, 5))

        ctk.CTkLabel(
            main_frame,
            text="Escribe para buscar un centro",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12)
        ).pack(anchor="w", pady=(0, 20))

        # Selector de centro con busqueda
        ctk.CTkLabel(
            main_frame,
            text="Centro* (escribe para filtrar)",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        center_names = [c['name'] for c in self.available_centers] if self.available_centers else ["No hay centros disponibles"]
        self.all_center_names = center_names.copy()

        self.center_select = ctk.CTkComboBox(
            main_frame,
            values=center_names,
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            button_color=Colors.CARD_BORDER,
            button_hover_color=Colors.BG_HOVER,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
            command=self._on_center_selected,
        )
        self.center_select.pack(fill="x", pady=(0, 12))
        self.center_select.set("Escribe o selecciona...")

        self.center_select.bind("<KeyRelease>", self._filter_centers)

        self.referer_label = ctk.CTkLabel(
            main_frame,
            text="",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 11),
            anchor="w",
        )
        self.referer_label.pack(fill="x", pady=(0, 12))

        # Separador
        ctk.CTkFrame(
            main_frame,
            fg_color=Colors.CARD_BORDER,
            height=1
        ).pack(fill="x", pady=16)

        ctk.CTkLabel(
            main_frame,
            text="Umbrales de Tiempo (minutos)",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14, "bold")
        ).pack(anchor="w", pady=(0, 12))

        self.lateral_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Lateral*",
            placeholder="Ej: 105",
            value="105"
        )
        self.lateral_input.pack(fill="x", pady=(0, 12))

        self.trasera_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Trasera (opcional)",
            placeholder="Ej: 120",
            value=""
        )
        self.trasera_input.pack(fill="x", pady=(0, 12))

        self.interna_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Interna (opcional)",
            placeholder="Ej: 150",
            value=""
        )
        self.interna_input.pack(fill="x", pady=(0, 12))

        # Selector de grupo de WhatsApp con filtrado
        group_names = [g['name'] for g in self.whatsapp_groups] if self.whatsapp_groups else ["No hay grupos disponibles"]
        self.all_group_names = group_names.copy()

        ctk.CTkLabel(
            main_frame,
            text="Grupo de WhatsApp* (escribe para filtrar)",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        self.group_combo = ctk.CTkComboBox(
            main_frame,
            values=group_names,
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            button_color=Colors.CARD_BORDER,
            button_hover_color=Colors.BG_HOVER,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
        )
        self.group_combo.pack(fill="x", pady=(0, 12))
        self.group_combo.set("Escribe o selecciona...")

        self.group_combo.bind("<KeyRelease>", self._filter_groups)

        # Nota
        note_frame = ctk.CTkFrame(
            main_frame,
            fg_color=Colors.INFO_BG,
            corner_radius=8,
            border_width=1,
            border_color=Colors.INFO
        )
        note_frame.pack(fill="x", pady=(12, 16))

        ctk.CTkLabel(
            note_frame,
            text="Los campos marcados con * son obligatorios",
            text_color=Colors.INFO,
            font=(Fonts.FAMILY, 11)
        ).pack(padx=12, pady=8)

        # Botones
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(12, 10))

        SecondaryButton(
            button_frame,
            text="Cancelar",
            command=self._cancel
        ).pack(side="right", padx=(8, 0))

        PrimaryButton(
            button_frame,
            text="Guardar Centro",
            command=self._save
        ).pack(side="right")

    def _filter_centers(self, event=None):
        search_text = self.center_select.get().lower()
        if not search_text or search_text == "escribe o selecciona...":
            filtered = self.all_center_names
        else:
            filtered = [name for name in self.all_center_names if search_text in name.lower()]
        if filtered:
            self.center_select.configure(values=filtered)
        else:
            self.center_select.configure(values=["No se encontraron coincidencias"])

    def _filter_groups(self, event=None):
        search_text = self.group_combo.get().lower()
        if not search_text or search_text == "escribe o selecciona...":
            filtered = self.all_group_names
        else:
            filtered = [name for name in self.all_group_names if search_text in name.lower()]
        if filtered:
            self.group_combo.configure(values=filtered)
        else:
            self.group_combo.configure(values=["No se encontraron coincidencias"])

    def _on_center_selected(self, center_name: str):
        for center in self.available_centers:
            if center['name'] == center_name:
                self.selected_center = center
                info_text = (
                    f"ID: {center['referer_id']} | "
                    f"DB: {center['db_name']} | "
                    f"Op: {center['op_code']} | "
                    f"CD: {center['cd_code']}"
                )
                self.referer_label.configure(text=info_text)
                break

    def _validate_inputs(self) -> bool:
        if not self.selected_center:
            return False
        if not self.lateral_input.get().strip():
            return False
        group_value = self.group_combo.get()
        if not group_value or group_value in ["Escribe o selecciona...", "No hay grupos disponibles", "No se encontraron coincidencias"]:
            return False
        return True

    def _save(self):
        if not self._validate_inputs():
            error_label = ctk.CTkLabel(
                self,
                text="Por favor selecciona un centro, define el umbral lateral y selecciona un grupo",
                text_color=Colors.ERROR,
                font=(Fonts.FAMILY, 11)
            )
            error_label.place(relx=0.5, rely=0.92, anchor="center")
            self.after(3000, error_label.destroy)
            return

        selected_group_name = self.group_combo.get()
        whatsapp_group_id = ""
        for group in self.whatsapp_groups:
            if group['name'] == selected_group_name:
                whatsapp_group_id = group['id']
                break

        self.result = {
            "name": self.selected_center['name'],
            "referer_id": self.selected_center['referer_id'],
            "db_name": self.selected_center['db_name'],
            "op_code": self.selected_center['op_code'],
            "cd_code": self.selected_center['cd_code'],
            "umbral_minutes_lateral": int(self.lateral_input.get() or 105),
            "umbral_minutes_trasera": int(self.trasera_input.get() or 0) if self.trasera_input.get().strip() else None,
            "umbral_minutes_interna": int(self.interna_input.get() or 0) if self.interna_input.get().strip() else None,
            "whatsapp_group_id": whatsapp_group_id,
            "group_id": whatsapp_group_id,
            "umbral_minutes": int(self.lateral_input.get() or 105)
        }

        if self.on_save:
            self.on_save(self.result)

        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class EditCenterDialog(ctk.CTkToplevel):
    """Dialogo para editar un centro existente"""

    def __init__(self, parent, site, on_save: Callable = None, whatsapp_groups: List = None):
        super().__init__(parent)

        self.on_save = on_save
        self.site = site
        self.old_name = site.name
        self.result = None
        self.whatsapp_groups = whatsapp_groups or []

        self.title(f"Editar Centro: {site.name}")
        self.geometry("500x600")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"500x600+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=Colors.BG_CARD,
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text=f"Editar: {self.site.name}",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 20, "bold")
        ).pack(anchor="w", pady=(10, 5))

        ctk.CTkLabel(
            main_frame,
            text="Modifica los parametros del centro",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12)
        ).pack(anchor="w", pady=(0, 20))

        info_card = ctk.CTkFrame(main_frame, fg_color=Colors.INFO_BG, corner_radius=8)
        info_card.pack(fill="x", pady=(0, 20))

        info_text = (
            f"ID: {self.site.referer_id} | "
            f"DB: {self.site.db_name} | "
            f"Op: {self.site.op_code} | "
            f"CD: {self.site.cd_code}"
        )

        ctk.CTkLabel(
            info_card,
            text=info_text,
            text_color=Colors.INFO,
            font=(Fonts.FAMILY, 11),
        ).pack(padx=12, pady=8)

        ctk.CTkFrame(
            main_frame,
            fg_color=Colors.CARD_BORDER,
            height=1
        ).pack(fill="x", pady=16)

        ctk.CTkLabel(
            main_frame,
            text="Umbrales de Tiempo (minutos)",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 14, "bold")
        ).pack(anchor="w", pady=(0, 12))

        self.lateral_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Lateral*",
            placeholder="Ej: 105",
            value=str(self.site.umbral_minutes_lateral or "")
        )
        self.lateral_input.pack(fill="x", pady=(0, 12))

        self.trasera_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Trasera (opcional)",
            placeholder="Ej: 120",
            value=str(self.site.umbral_minutes_trasera or "")
        )
        self.trasera_input.pack(fill="x", pady=(0, 12))

        self.interna_input = LabeledInput(
            main_frame,
            label="Umbral Descarga Interna (opcional)",
            placeholder="Ej: 150",
            value=str(self.site.umbral_minutes_interna or "")
        )
        self.interna_input.pack(fill="x", pady=(0, 12))

        group_names = [g['name'] for g in self.whatsapp_groups] if self.whatsapp_groups else ["No hay grupos disponibles"]
        self.all_group_names = group_names.copy()

        current_group_id = self.site.whatsapp_group_id or self.site.group_id
        current_group_name = "Seleccionar grupo..."
        for group in self.whatsapp_groups:
            if group['id'] == current_group_id:
                current_group_name = group['name']
                break

        ctk.CTkLabel(
            main_frame,
            text="Grupo de WhatsApp* (escribe para filtrar)",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, Fonts.SMALL_SIZE),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        self.group_combo = ctk.CTkComboBox(
            main_frame,
            values=group_names,
            fg_color=Colors.BG_CARD,
            border_color=Colors.CARD_BORDER,
            button_color=Colors.CARD_BORDER,
            button_hover_color=Colors.BG_HOVER,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, Fonts.BODY_SIZE),
            corner_radius=Dimensions.INPUT_RADIUS,
            height=42,
        )
        self.group_combo.pack(fill="x", pady=(0, 12))
        self.group_combo.set(current_group_name)

        self.group_combo.bind("<KeyRelease>", self._filter_groups)

        note_frame = ctk.CTkFrame(
            main_frame,
            fg_color=Colors.INFO_BG,
            corner_radius=8,
            border_width=1,
            border_color=Colors.INFO
        )
        note_frame.pack(fill="x", pady=(12, 16))

        ctk.CTkLabel(
            note_frame,
            text="Los campos marcados con * son obligatorios",
            text_color=Colors.INFO,
            font=(Fonts.FAMILY, 11)
        ).pack(padx=12, pady=8)

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(12, 10))

        SecondaryButton(
            button_frame,
            text="Cancelar",
            command=self._cancel
        ).pack(side="right", padx=(8, 0))

        PrimaryButton(
            button_frame,
            text="Guardar Cambios",
            command=self._save
        ).pack(side="right")

    def _filter_groups(self, event=None):
        search_text = self.group_combo.get().lower()
        if not search_text or search_text == "seleccionar grupo...":
            filtered = self.all_group_names
        else:
            filtered = [name for name in self.all_group_names if search_text in name.lower()]
        if filtered:
            self.group_combo.configure(values=filtered)
        else:
            self.group_combo.configure(values=["No se encontraron coincidencias"])

    def _validate_inputs(self) -> bool:
        if not self.lateral_input.get().strip():
            return False
        group_value = self.group_combo.get()
        if not group_value or group_value in ["Seleccionar grupo...", "No hay grupos disponibles", "No se encontraron coincidencias"]:
            return False
        return True

    def _save(self):
        if not self._validate_inputs():
            error_label = ctk.CTkLabel(
                self,
                text="Por favor completa todos los campos obligatorios",
                text_color=Colors.ERROR,
                font=(Fonts.FAMILY, 11)
            )
            error_label.place(relx=0.5, rely=0.92, anchor="center")
            self.after(3000, error_label.destroy)
            return

        selected_group_name = self.group_combo.get()
        whatsapp_group_id = ""
        for group in self.whatsapp_groups:
            if group['name'] == selected_group_name:
                whatsapp_group_id = group['id']
                break

        self.result = {
            "name": self.site.name,
            "referer_id": self.site.referer_id,
            "db_name": self.site.db_name,
            "op_code": self.site.op_code,
            "cd_code": self.site.cd_code,
            "umbral_minutes_lateral": int(self.lateral_input.get() or 105),
            "umbral_minutes_trasera": int(self.trasera_input.get() or 0) if self.trasera_input.get().strip() else None,
            "umbral_minutes_interna": int(self.interna_input.get() or 0) if self.interna_input.get().strip() else None,
            "whatsapp_group_id": whatsapp_group_id,
            "group_id": whatsapp_group_id,
            "umbral_minutes": int(self.lateral_input.get() or 105)
        }

        if self.on_save:
            self.on_save(self.old_name, self.result)

        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class ConfirmDialog(ctk.CTkToplevel):
    """Dialogo de confirmacion generico"""

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        confirm_text: str = "Confirmar",
        cancel_text: str = "Cancelar",
        on_confirm: Callable = None,
        danger: bool = False
    ):
        super().__init__(parent)

        self.on_confirm = on_confirm
        self.confirmed = False

        self.title(title)
        self.geometry("550x450")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.winfo_screenheight() // 2) - (450 // 2)
        self.geometry(f"550x450+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        container = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=12,
                                 border_width=1, border_color=Colors.CARD_BORDER)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        icon_color = Colors.ERROR_BG if danger else Colors.WARNING_BG
        icon_text_color = Colors.ERROR if danger else Colors.WARNING

        icon_frame = ctk.CTkFrame(
            header,
            fg_color=icon_color,
            corner_radius=24,
            width=48,
            height=48
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        ctk.CTkLabel(
            icon_frame,
            text="!" if danger else "?",
            text_color=icon_text_color,
            font=(Fonts.FAMILY, 24, "bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0), fill="x", expand=True)

        ctk.CTkLabel(
            text_frame,
            text=title,
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 18, "bold"),
            anchor="w"
        ).pack(anchor="w")

        message_container = ctk.CTkScrollableFrame(
            container,
            fg_color=Colors.BG_PRIMARY,
            corner_radius=8,
            height=240
        )
        message_container.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            message_container,
            text=message,
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 13),
            wraplength=480,
            justify="left",
            anchor="w"
        ).pack(padx=12, pady=12, fill="x")

        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(10, 20))

        SecondaryButton(
            button_frame,
            text=cancel_text,
            command=self._cancel
        ).pack(side="right", padx=(8, 0))

        if danger:
            DangerButton(
                button_frame,
                text=confirm_text,
                command=self._confirm
            ).pack(side="right")
        else:
            PrimaryButton(
                button_frame,
                text=confirm_text,
                command=self._confirm
            ).pack(side="right")

    def _confirm(self):
        self.confirmed = True
        if self.on_confirm:
            self.on_confirm()
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.confirmed = False
        self.grab_release()
        self.destroy()
