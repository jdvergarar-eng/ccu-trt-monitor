# Welcome Screen - Pantalla de requisitos del sistema
import customtkinter as ctk
from ..styles import Colors, Fonts
from ..components import Card, PrimaryButton, SecondaryButton


class WelcomeScreen(ctk.CTkFrame):
    """Pantalla de bienvenida con requisitos del sistema"""

    def __init__(self, master, on_back: callable, on_continue: callable, **kwargs):
        super().__init__(master, fg_color=Colors.DARK_BG, **kwargs)

        self.on_back = on_back
        self.on_continue = on_continue

        self._create_widgets()

    def _create_widgets(self):
        # Contenedor central con scroll
        container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            width=600,
        )
        container.place(relx=0.5, rely=0.5, anchor="center", relheight=0.9)

        # Titulo
        ctk.CTkLabel(
            container,
            text="Bienvenido al Sistema de Alertas TRT",
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 28, "bold"),
        ).pack(pady=(20, 12))

        ctk.CTkLabel(
            container,
            text="Antes de comenzar, asegurate de cumplir con los siguientes requisitos",
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 15),
        ).pack(pady=(0, 40))

        # Requisitos
        requirements = [
            {
                "icon": "📱",
                "title": "Telefono con WhatsApp",
                "description": "Recomendamos un telefono dedicado exclusivamente para el bot, por temas de seguridad y estabilidad.",
                "important": True,
            },
            {
                "icon": "💻",
                "title": "PC encendido permanentemente",
                "description": "El computador debe estar encendido 24/7. Puedes usar WinToys para configurar que no entre en suspension.",
                "important": True,
            },
            {
                "icon": "🌐",
                "title": "Conexion a red CCU",
                "description": "El equipo debe estar conectado a la red local de CCU para acceder al sistema TRT.",
                "important": True,
            },
            {
                "icon": "👥",
                "title": "Grupos de WhatsApp creados",
                "description": "Debes tener creados los grupos de WhatsApp donde se enviaran las alertas de cada centro.",
                "important": False,
            },
        ]

        for req in requirements:
            self._create_requirement_card(container, req)

        # Botones
        buttons_frame = ctk.CTkFrame(container, fg_color="transparent")
        buttons_frame.pack(pady=40)

        SecondaryButton(
            buttons_frame,
            text="Volver",
            command=self.on_back,
            width=150,
        ).pack(side="left", padx=10)

        PrimaryButton(
            buttons_frame,
            text="Tengo todo listo, continuar",
            command=self.on_continue,
            width=250,
        ).pack(side="left", padx=10)

    def _create_requirement_card(self, parent, req: dict):
        """Crea una tarjeta de requisito"""
        card = Card(parent)
        card.pack(fill="x", pady=8)

        if req["important"]:
            card.configure(border_color=Colors.CCU_RED_ALPHA_30)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=20)

        # Icono
        icon_frame = ctk.CTkFrame(
            content,
            fg_color=Colors.CCU_RED_ALPHA_15 if req["important"] else Colors.DARK_BG,
            corner_radius=12,
            width=48,
            height=48,
        )
        icon_frame.pack(side="left", padx=(0, 16))
        icon_frame.pack_propagate(False)

        ctk.CTkLabel(
            icon_frame,
            text=req["icon"],
            font=(Fonts.FAMILY, 24),
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Texto
        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        title_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        title_frame.pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text=req["title"],
            text_color=Colors.TEXT_PRIMARY,
            font=(Fonts.FAMILY, 15, "bold"),
        ).pack(side="left")

        if req["important"]:
            badge = ctk.CTkLabel(
                title_frame,
                text="REQUERIDO",
                text_color=Colors.TEXT_ON_GREEN,
                font=(Fonts.FAMILY, 9, "bold"),
                fg_color=Colors.CCU_GREEN,
                corner_radius=4,
                padx=8,
                pady=2,
            )
            badge.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            text_frame,
            text=req["description"],
            text_color=Colors.TEXT_SECONDARY,
            font=(Fonts.FAMILY, 13),
            wraplength=450,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))
