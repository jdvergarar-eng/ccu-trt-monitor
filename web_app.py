"""
CCU-TRT Monitor - Version Web (NiceGUI)
Sistema de Alertas de Tiempo de Residencia en Planta

Entry point para la version web accesible por navegador.
Reemplaza a main.py para el modo web.

Ejecutar: python web_app.py
Acceder: http://localhost:8080
"""

import sys
import os
import atexit

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.responses import Response
from nicegui import app, ui
from web.theme import CCU_CSS
from web.auth import setup_auth

# Importar paginas
from web.pages.login import setup_login_page
from web.pages.splash import setup_splash_page
from web.pages.welcome import setup_welcome_page
from web.pages.setup import setup_setup_page
from web.pages.connecting import setup_connecting_page
from web.pages.dashboard import setup_dashboard_page
from web.pages.centers import setup_centers_page
from web.pages.analytics import setup_analytics_page
from web.pages.settings import setup_settings_page


def main():
    """Punto de entrada principal para la version web"""

    # Ruta para silenciar peticiones del navegador a /sw.js (service worker residual)
    @app.get('/sw.js')
    async def service_worker():
        return Response(
            content='self.addEventListener("install", () => self.skipWaiting()); '
                    'self.addEventListener("activate", () => self.registration.unregister());',
            media_type='application/javascript',
        )

    # Configurar autenticacion Azure AD
    setup_auth(app)

    # Agregar CSS del tema CCU
    app.add_static_files('/assets', 'assets')
    ui.add_head_html(f'<style>{CCU_CSS}</style>', shared=True)

    # Registrar todas las paginas
    setup_login_page()
    setup_splash_page()
    setup_welcome_page()
    setup_setup_page()
    setup_connecting_page()
    setup_dashboard_page()
    setup_centers_page()
    setup_analytics_page()
    setup_settings_page()

    # Iniciar el MonitoringService (singleton)
    from core import get_config_manager, get_monitoring_service
    config_manager = get_config_manager()

    if config_manager.exists() and config_manager.config.sites:
        get_monitoring_service()
        # No auto-start - the user controls it from the dashboard

    # Iniciar NiceGUI
    ui.run(
        title="CCU-TRT Monitor",
        host="0.0.0.0",
        port=8080,
        favicon="assets/Logo_CCU.png",
        dark=False,
        storage_secret="ccu-trt-monitor-storage-secret",
        show=False,  # No abrir navegador automaticamente (server mode)
    )


if __name__ == "__main__":
    # Iniciar servicios solo en el proceso principal (no en el worker de NiceGUI)
    try:
        from main import (
            start_whatsapp_bot, stop_whatsapp_bot,
            start_monitor_alertas, stop_monitor_alertas,
        )
        start_whatsapp_bot()
        atexit.register(stop_whatsapp_bot)

        start_monitor_alertas()
        atexit.register(stop_monitor_alertas)
    except Exception as e:
        print(f"Advertencia: No se pudieron iniciar los servicios: {e}")
    main()
elif __name__ == "__mp_main__":
    main()
