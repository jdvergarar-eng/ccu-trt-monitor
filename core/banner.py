# Banner Generator - Genera imagenes PNG de alertas
# Basado en monitor_alertas.py original

import os
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont


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
# FUNCIONES AUXILIARES
# =============================================================================

def get_tipo_descarga(empresa: str) -> str:
    if not empresa:
        return "LATERAL"
    empresa_upper = empresa.upper().strip()
    if "ROMANI" in empresa_upper or "LOGISTICA DEL NORTE" in empresa_upper:
        return "INTERNA"
    if "TRANSPORTE INTERANDINOS" in empresa_upper or "TRANSPORTES INTERANDINOS" in empresa_upper:
        return "TRASERA"
    return "LATERAL"


def classify_truck(tiempo: timedelta, umbral: timedelta) -> str:
    umbral_80 = umbral * 0.8
    umbral_130 = umbral * 1.3
    if tiempo < umbral_80:
        return "green"
    elif tiempo < umbral_130:
        return "yellow"
    return "red"


def format_timedelta_banner(td: timedelta) -> str:
    total_seconds = int(abs(td.total_seconds()))
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


def fmt_td(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem = total // 86400, total % 86400
    hh, mm, ss = rem // 3600, (rem % 3600) // 60, rem % 60
    return f"{days}d {hh:02}:{mm:02}:{ss:02}" if days > 0 else f"{hh:02}:{mm:02}:{ss:02}"


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
    """Dibuja el semaforo con conteos y etiquetas explicativas"""
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
# CLASIFICACION DE SEVERIDAD
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


# =============================================================================
# GENERACION DE BANNER PNG
# =============================================================================

def make_banner_png(status: CenterStatus, output_dir: str = None) -> str:
    """Genera banner PNG de alerta operativa"""
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

    # SEMAFORO CON ETIQUETAS
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
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "banners"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alerta_{status.name.lower().replace(' ', '_')}_{timestamp}.png"
    output_path = output_dir / filename

    img.save(output_path, "PNG", optimize=True)

    return str(output_path)


def format_banner_summary_message(status: CenterStatus) -> str:
    """Genera el mensaje de texto que acompana al banner"""
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


def analyze_trucks_for_banner(site_name: str, trucks: list, umbral_minutes: int) -> CenterStatus:
    """
    Analiza los camiones y crea un CenterStatus para generar el banner.

    Args:
        site_name: Nombre del sitio/centro
        trucks: Lista de TruckInPlant del TRT API
        umbral_minutes: Umbral en minutos para el sitio
    """
    umbral = timedelta(minutes=umbral_minutes)

    n_green, n_yellow, n_red = 0, 0, 0
    max_overrun, max_tiempo = timedelta(0), timedelta(0)
    all_trucks = []

    for truck in trucks:
        tiempo = timedelta(minutes=truck.time_in_plant_minutes)
        empresa = truck.company or ""
        tipo_descarga = get_tipo_descarga(empresa)
        tipo_ingreso = truck.entry_type or ""

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
            plate=truck.plate,
            time_in_plant=tiempo,
            load_type=tipo_descarga,
            empresa=empresa,
            umbral=umbral,
            tipo_ingreso=tipo_ingreso
        ))

    all_trucks.sort(key=lambda t: t.time_in_plant, reverse=True)
    n_total = n_green + n_yellow + n_red
    severity = calculate_center_severity(
        n_total, n_green, n_yellow, n_red, max_overrun, max_tiempo, umbral
    )

    return CenterStatus(
        name=site_name,
        traffic=TrafficLight(n_green, n_yellow, n_red),
        worst_trucks=all_trucks,
        time_limit=umbral,
        max_overrun=max_overrun,
        severity=severity
    )
