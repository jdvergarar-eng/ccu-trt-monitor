# Main application window - CCU-TRT Monitor
import customtkinter as ctk
from typing import Optional
import threading
import os
import sys

from .styles import Colors, Fonts, Dimensions, configure_customtkinter
from .screens import SplashScreen, WelcomeScreen, SetupWizard, Dashboard, ConnectingScreen


class CCUTRTApp(ctk.CTk):
    """Aplicacion principal CCU-TRT Monitor"""

    def __init__(self):
        configure_customtkinter()
        super().__init__()

        # Configurar ventana
        self.title("CCU-TRT Monitor - Sistema de Alertas")

        # Configurar escalado DPI en Windows para mejor adaptación
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # Configurar tamaño inicial y mínimo
        self.geometry(f"{Dimensions.WINDOW_WIDTH}x{Dimensions.WINDOW_HEIGHT}+0+0")
        self.minsize(Dimensions.WINDOW_MIN_WIDTH, Dimensions.WINDOW_MIN_HEIGHT)
        self.configure(fg_color=Colors.BG_PRIMARY)

        # Estado de la aplicacion
        self.current_screen: Optional[ctk.CTkFrame] = None
        self.is_first_run = self._check_first_run()
        self.minimize_to_tray = True

        # Configurar cierre de ventana
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Intentar cargar icono
        self._load_icon()

        # Mostrar pantalla inicial según configuración
        if self.is_first_run:
            self._show_splash()
        else:
            # Ya hay configuracion: esperar conexion del bot antes del dashboard
            self._show_connecting()

        # Maximizar ventana después de que todo esté cargado
        self.after(100, self._maximize_window)

    def _maximize_window(self):
        """Maximiza la ventana de forma robusta en el monitor principal"""
        try:
            self.update_idletasks()
            # Asegurar que la ventana esté en el monitor principal primero
            # Posicionar en esquina superior izquierda
            self.geometry(f"+0+0")
            self.update_idletasks()
            # Ahora maximizar
            self.state('zoomed')
        except Exception as e:
            print(f"Error maximizando con zoomed: {e}")
            # Fallback: configurar tamaño de pantalla completa manualmente
            try:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                # Asegurar que comience en 0,0 para el monitor principal
                self.geometry(f"{screen_width}x{screen_height}+0+0")
                self.update_idletasks()
            except Exception as e2:
                print(f"Error con fallback de maximización: {e2}")

    def _center_window(self):
        """Centra la ventana en la pantalla"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _load_icon(self):
        """Intenta cargar el icono de la aplicacion"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _check_first_run(self) -> bool:
        """Verifica si es la primera ejecucion"""
        from core import get_config_manager
        config_manager = get_config_manager()
        # Es primera ejecución si no hay configuración o no hay sitios configurados
        return not config_manager.exists() or not config_manager.config.sites

    def _clear_screen(self):
        """Limpia la pantalla actual"""
        if self.current_screen:
            # Detener polling si la pantalla tiene uno activo
            if hasattr(self.current_screen, 'active'):
                self.current_screen.active = False
            self.current_screen.destroy()
            self.current_screen = None

    def _show_splash(self):
        """Muestra la pantalla de inicio"""
        self._clear_screen()
        self.current_screen = SplashScreen(
            self,
            on_start_config=self._show_welcome,
        )
        self.current_screen.pack(fill="both", expand=True)

    def _show_welcome(self):
        """Muestra la pantalla de bienvenida con requisitos"""
        self._clear_screen()
        self.current_screen = WelcomeScreen(
            self,
            on_back=self._show_splash,
            on_continue=self._show_setup,
        )
        self.current_screen.pack(fill="both", expand=True)

    def _show_setup(self):
        """Muestra el wizard de configuracion"""
        self._clear_screen()
        self.current_screen = SetupWizard(
            self,
            on_back=self._show_welcome,
            on_finish=self._show_connecting,
        )
        self.current_screen.pack(fill="both", expand=True)

    def _show_connecting(self):
        """Muestra la pantalla de espera de conexion del bot"""
        self._clear_screen()
        self.current_screen = ConnectingScreen(
            self,
            on_connected=self._show_dashboard,
        )
        self.current_screen.pack(fill="both", expand=True)

    def _show_dashboard(self):
        """Muestra el dashboard principal"""
        self._clear_screen()
        self.current_screen = Dashboard(
            self,
            on_minimize=self._minimize_to_tray,
            on_exit=self._quit_app,
        )
        self.current_screen.pack(fill="both", expand=True)

    def _minimize_to_tray(self):
        """Minimiza la aplicacion a la bandeja del sistema"""
        if self.minimize_to_tray:
            self.withdraw()  # Oculta la ventana
            self._show_tray_icon()
        else:
            self.iconify()  # Minimiza normalmente

    def _show_tray_icon(self):
        """Muestra el icono en la bandeja del sistema"""
        try:
            import pystray
            from PIL import Image

            # Crear imagen para el icono
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                # Crear imagen simple si no existe el icono
                image = Image.new('RGB', (64, 64), color=Colors.CCU_RED)

            # Crear menu
            menu = pystray.Menu(
                pystray.MenuItem("Abrir CCU-TRT", self._restore_from_tray),
                pystray.MenuItem("Salir", self._quit_app),
            )

            # Crear icono
            self.tray_icon = pystray.Icon(
                "CCU-TRT Monitor",
                image,
                "CCU-TRT Monitor",
                menu,
            )

            # Ejecutar en thread separado
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        except ImportError:
            # Si pystray no esta disponible, solo minimizar
            self.iconify()
        except Exception as e:
            print(f"Error creando icono de bandeja: {e}")
            self.iconify()

    def _restore_from_tray(self):
        """Restaura la ventana desde la bandeja"""
        try:
            if hasattr(self, 'tray_icon'):
                self.tray_icon.stop()
        except Exception:
            pass

        self.deiconify()  # Muestra la ventana
        self.lift()  # La trae al frente
        self.focus_force()  # Le da el foco

    def _on_close(self):
        """Maneja el cierre de la ventana"""
        if self.minimize_to_tray:
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _quit_app(self):
        """Cierra completamente la aplicacion"""
        try:
            if hasattr(self, 'tray_icon'):
                self.tray_icon.stop()
        except Exception:
            pass

        self.quit()
        self.destroy()


def run():
    """Funcion principal para ejecutar la aplicacion"""
    app = CCUTRTApp()
    app.mainloop()


if __name__ == "__main__":
    run()
