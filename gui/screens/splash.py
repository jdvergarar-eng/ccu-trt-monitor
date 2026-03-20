# Splash Screen - Pantalla de inicio con logo CCU - Tema Corporativo Claro
import customtkinter as ctk
from pathlib import Path
from PIL import Image
from ..styles import Colors, Fonts, Dimensions
from ..components import PrimaryButton


class SplashScreen(ctk.CTkFrame):
    """Pantalla de inicio con logo CCU y creditos - Tema corporativo"""

    def __init__(self, master, on_start_config: callable, **kwargs):
        super().__init__(master, fg_color=Colors.BG_PRIMARY, **kwargs)

        self.on_start_config = on_start_config

        self._create_widgets()

    def _create_widgets(self):
        # Usar scrollable frame para pantallas pequenas
        scroll_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=Colors.CARD_BORDER,
            scrollbar_button_hover_color=Colors.BG_HOVER
        )
        scroll_container.pack(fill="both", expand=True)

        # Contenedor central
        center = ctk.CTkFrame(scroll_container, fg_color="transparent")
        center.pack(expand=True, pady=40)

        # Card principal con fondo blanco y borde sutil
        main_card = ctk.CTkFrame(
            center,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.CARD_BORDER,
        )
        main_card.pack(padx=60)

        card_content = ctk.CTkFrame(main_card, fg_color="transparent")
        card_content.pack(padx=80, pady=50)

        # Barra verde superior decorativa
        ctk.CTkFrame(
            main_card,
            fg_color=Colors.CCU_GREEN,
            height=4,
            corner_radius=0,
        ).place(relx=0, rely=0, relwidth=1)

        # Logo CCU - Usar imagen real
        try:
            assets_dir = Path(__file__).parent.parent.parent / "assets"
            logo_path = assets_dir / "Logo_CCU.png"

            if logo_path.exists():
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(240, 110)
                )
                logo_label = ctk.CTkLabel(
                    card_content,
                    text="",
                    image=logo_image,
                )
                logo_label.pack(pady=(10, 16))
            else:
                self._create_text_logo(card_content)
        except Exception:
            self._create_text_logo(card_content)

        # Linea decorativa verde fina
        ctk.CTkFrame(
            card_content,
            fg_color=Colors.CARD_BORDER,
            height=1,
            width=300,
        ).pack(pady=12)

        # Titulo principal
        ctk.CTkLabel(
            card_content,
            text="Sistema de Alertas TRT",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 36, "bold"),
        ).pack(pady=(12, 6))

        ctk.CTkLabel(
            card_content,
            text="Monitor de Tiempo de Residencia en Planta",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 15),
        ).pack(pady=(0, 20))

        # Badge de origen - sutil y minimalista
        origin_badge = ctk.CTkFrame(
            card_content,
            fg_color=Colors.ACTION_GREEN_LIGHT,
            corner_radius=20,
            border_width=1,
            border_color=Colors.ACTION_GREEN,
        )
        origin_badge.pack(pady=(0, 28))

        origin_content = ctk.CTkFrame(origin_badge, fg_color="transparent")
        origin_content.pack(padx=20, pady=6)

        ctk.CTkLabel(
            origin_content,
            text="CD Santiago Sur",
            text_color=Colors.CCU_GREEN,
            font=(Fonts.FAMILY, 13, "bold"),
        ).pack(side="left", padx=(4, 0))

        # Boton principal
        PrimaryButton(
            card_content,
            text="Comenzar Configuracion",
            command=self.on_start_config,
            size="lg",
            width=320,
            height=48,
        ).pack(pady=(0, 8))

        # Creditos - fuera de la card, mas discretos
        credits_frame = ctk.CTkFrame(center, fg_color="transparent")
        credits_frame.pack(pady=(28, 0))

        ctk.CTkLabel(
            credits_frame,
            text="Desarrollado por Juan Vergara & Vicente Vergara",
            text_color=Colors.TEXT_MUTED,
            font=(Fonts.FAMILY, 12),
        ).pack()

        ctk.CTkLabel(
            credits_frame,
            text="Equipo de Operaciones - CCU",
            text_color=Colors.ACTION_GREEN,
            font=(Fonts.FAMILY, 11),
        ).pack(pady=(2, 0))

    def _create_text_logo(self, parent):
        """Fallback: logo de texto si no se encuentra la imagen"""
        logo_frame = ctk.CTkFrame(
            parent,
            fg_color=Colors.CCU_GREEN,
            corner_radius=12,
            width=240,
            height=110,
        )
        logo_frame.pack(pady=(10, 16))
        logo_frame.pack_propagate(False)

        logo_inner = ctk.CTkFrame(
            logo_frame,
            fg_color=Colors.CCU_GREEN,
            corner_radius=10,
            border_width=2,
            border_color=Colors.TEXT_ON_GREEN,
        )
        logo_inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.93, relheight=0.9)

        ctk.CTkLabel(
            logo_inner,
            text="CCU",
            text_color=Colors.TEXT_ON_GREEN,
            font=("Arial Black", 44, "bold"),
        ).place(relx=0.5, rely=0.4, anchor="center")

        ctk.CTkLabel(
            logo_inner,
            text="COMPANIA CERVECERIAS UNIDAS",
            text_color=Colors.TEXT_ON_GREEN,
            font=(Fonts.FAMILY, 8),
        ).place(relx=0.5, rely=0.78, anchor="center")
