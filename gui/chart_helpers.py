# Chart helpers - Funciones para crear graficos matplotlib embebidos en CTk
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from .styles import Colors, Fonts

# Colores corporativos para matplotlib
_GREEN = Colors.CHART_TODAY       # "#009F4D"
_GRAY = Colors.CHART_YESTERDAY   # "#A0AEC0"
_RED = Colors.CHART_THRESHOLD    # "#D32F2F"
_GRID = Colors.CHART_GRID        # "#EDF2F7"
_TEXT = Colors.TEXT_MUTED         # "#718096"
_TEXT_DARK = Colors.TEXT_PRIMARY  # "#2D3748"
_BG = Colors.CHART_BG            # "#FFFFFF"
_GREEN_LIGHT = "#E6F5ED"
_WARNING = Colors.WARNING         # "#FCB500"


def _apply_base_style(ax, fig):
    """Aplica estilo base profesional a un axes"""
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_GRID)
    ax.spines["bottom"].set_color(_GRID)
    ax.tick_params(colors=_TEXT, labelsize=9)
    ax.grid(axis="y", color=_GRID, linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)


def create_daily_trend_chart(fig, data, threshold=60):
    """Grafico de linea con tendencia diaria de TRT

    Args:
        fig: matplotlib Figure
        data: lista de (fecha_str, avg_trt_min, count, critical_count)
        threshold: umbral en minutos
    """
    ax = fig.add_subplot(111)
    _apply_base_style(ax, fig)

    if not data or all(d[1] == 0 for d in data):
        ax.text(0.5, 0.5, "Sin datos para el periodo seleccionado",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=13, color=_TEXT, fontfamily=Fonts.FAMILY)
        return

    # Filtrar solo dias con datos
    dates = [d[0] for d in data]
    values = [d[1] for d in data]
    counts = [d[2] for d in data]

    x = np.arange(len(dates))

    # Area de relleno bajo la linea
    ax.fill_between(x, values, alpha=0.15, color=_GREEN)

    # Linea principal
    ax.plot(x, values, color=_GREEN, linewidth=2.5, marker="o",
            markersize=4, markerfacecolor=_BG, markeredgecolor=_GREEN,
            markeredgewidth=2, zorder=5)

    # Linea de umbral
    ax.axhline(y=threshold, color=_RED, linewidth=1.5, linestyle="--",
               label=f"Umbral ({threshold} min)", zorder=4)

    # Resaltar puntos criticos (sobre umbral)
    for i, v in enumerate(values):
        if v > threshold and v > 0:
            ax.plot(i, v, "o", color=_RED, markersize=7, zorder=6)

    # Etiquetas
    ax.set_ylabel("TRT Promedio (min)", fontsize=10, color=_TEXT_DARK,
                   fontfamily=Fonts.FAMILY)

    # Eje X: mostrar solo algunas fechas para no saturar
    step = max(1, len(dates) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)],
                        rotation=45, ha="right", fontsize=8)

    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax.set_xlim(-0.5, len(dates) - 0.5)
    if max(values) > 0:
        ax.set_ylim(0, max(max(values), threshold) * 1.15)

    fig.tight_layout(pad=1.5)


def create_hourly_distribution_chart(fig, data, threshold=60):
    """Bar chart de distribucion por hora de llegada

    Args:
        fig: matplotlib Figure
        data: dict {hora: avg_trt_min}
        threshold: umbral en minutos
    """
    ax = fig.add_subplot(111)
    _apply_base_style(ax, fig)

    hours = list(range(24))
    values = [data.get(h, 0) for h in hours]

    if all(v == 0 for v in values):
        ax.text(0.5, 0.5, "Sin datos para el periodo seleccionado",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=13, color=_TEXT, fontfamily=Fonts.FAMILY)
        return

    # Colores: verde si bajo umbral, rojo si sobre
    bar_colors = [_RED if v > threshold else _GREEN for v in values]

    bars = ax.bar(hours, values, color=bar_colors, width=0.7, alpha=0.85,
                  edgecolor="white", linewidth=0.5, zorder=3)

    # Linea de umbral
    ax.axhline(y=threshold, color=_RED, linewidth=1.5, linestyle="--",
               label=f"Umbral ({threshold} min)", zorder=4)

    # Etiquetas
    ax.set_xlabel("Hora de Llegada", fontsize=10, color=_TEXT_DARK,
                   fontfamily=Fonts.FAMILY)
    ax.set_ylabel("TRT Promedio (min)", fontsize=10, color=_TEXT_DARK,
                   fontfamily=Fonts.FAMILY)

    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}" for h in hours], fontsize=8)
    ax.set_xlim(-0.5, 23.5)
    if max(values) > 0:
        ax.set_ylim(0, max(max(values), threshold) * 1.15)

    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.tight_layout(pad=1.5)


def create_heatmap_chart(fig, data):
    """Heatmap de hora x dia de la semana

    Args:
        fig: matplotlib Figure
        data: lista de 24 listas, cada una con 7 valores (Lun-Dom)
    """
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(_BG)

    matrix = np.array(data)  # 24 x 7

    if matrix.max() == 0:
        ax.set_facecolor(_BG)
        ax.text(0.5, 0.5, "Sin datos para el periodo seleccionado",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=13, color=_TEXT, fontfamily=Fonts.FAMILY)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    # Crear colormap personalizado: blanco -> verde claro -> verde oscuro
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "trt", ["#FFFFFF", _GREEN_LIGHT, _GREEN, "#005C35"]
    )

    im = ax.imshow(matrix, cmap=cmap, aspect="auto", interpolation="nearest")

    # Etiquetas
    dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    ax.set_xticks(range(7))
    ax.set_xticklabels(dias, fontsize=9)

    # Mostrar solo algunas horas en Y
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    ax.set_yticks(range(0, 24, 2))
    ax.set_yticklabels([hour_labels[h] for h in range(0, 24, 2)], fontsize=8)

    ax.set_ylabel("Hora de Llegada", fontsize=10, color=_TEXT_DARK,
                   fontfamily=Fonts.FAMILY)

    ax.tick_params(colors=_TEXT, labelsize=9)

    # Anotar valores en celdas con datos
    for h in range(24):
        for d in range(7):
            val = matrix[h, d]
            if val > 0:
                text_color = "white" if val > matrix.max() * 0.6 else _TEXT_DARK
                ax.text(d, h, f"{val:.0f}", ha="center", va="center",
                        fontsize=7, color=text_color, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("TRT (min)", fontsize=9, color=_TEXT)
    cbar.ax.tick_params(labelsize=8, colors=_TEXT)

    # Bordes
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout(pad=1.5)
