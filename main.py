"""
CCU-TRT: Sistema de Alertas de Tiempo de Residencia en Planta
Monitor de TRT con interfaz grafica

Desarrollado por: Juan Vergara & Vicente Vergara
Equipo de Operaciones - CCU
Origen: CD Santiago Sur
"""

import sys
import os
import subprocess
import time
import atexit
import signal

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Procesos globales
bot_process = None
monitor_process = None

# Flags de debug: True = muestra ventana de consola (util para depurar)
DEBUG_BOT = True
DEBUG_MONITOR = True


def start_whatsapp_bot():
    """Inicia el bot de WhatsApp como subproceso"""
    global bot_process

    bot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot")
    bot_script = os.path.join(bot_dir, "bot_whatsapp.js")

    if not os.path.exists(bot_script):
        print(f"Advertencia: No se encontro el bot de WhatsApp en {bot_script}")
        return None

    # Verificar si node está instalado
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Advertencia: Node.js no esta instalado. El bot de WhatsApp no se iniciara.")
        return None

    # Verificar si el bot ya está corriendo intentando conectar
    try:
        import requests
        r = requests.get("http://localhost:5050/health", timeout=2)
        if r.status_code == 200:
            print("Bot de WhatsApp ya esta corriendo")
            return None  # Ya está corriendo, no iniciar otro
    except Exception:
        pass  # No está corriendo, lo iniciamos

    print("Iniciando bot de WhatsApp...")

    # Iniciar el bot en background
    try:
        if sys.platform == "win32":
            if DEBUG_BOT:
                # Modo debug: nueva consola minimizada para ver logs del bot
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 6  # SW_MINIMIZE
                bot_process = subprocess.Popen(
                    ["node", bot_script],
                    cwd=bot_dir,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # Modo produccion: sin ventana visible
                bot_process = subprocess.Popen(
                    ["node", bot_script],
                    cwd=bot_dir,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
        else:
            # En Linux/Mac, ejecutar normalmente
            bot_process = subprocess.Popen(
                ["node", bot_script],
                cwd=bot_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        # Esperar un momento para que inicie
        time.sleep(3)

        # Verificar que arrancó correctamente
        if bot_process.poll() is not None:
            print("Error: El bot de WhatsApp termino inesperadamente")
            return None

        print("Bot de WhatsApp iniciado correctamente (PID: {})".format(bot_process.pid))
        return bot_process

    except Exception as e:
        print(f"Error iniciando el bot de WhatsApp: {e}")
        return None


def stop_whatsapp_bot():
    """Detiene el bot de WhatsApp"""
    global bot_process

    if bot_process is not None:
        print("Deteniendo bot de WhatsApp...")
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()
        except Exception as e:
            print(f"Error deteniendo bot: {e}")
        bot_process = None


def start_monitor_alertas():
    """Inicia monitor_alertas.py como subproceso"""
    global monitor_process

    base_dir = os.path.dirname(os.path.abspath(__file__))
    monitor_script = os.path.join(base_dir, "monitor_alertas.py")

    if not os.path.exists(monitor_script):
        print(f"Advertencia: No se encontro monitor_alertas.py en {monitor_script}")
        return None

    # Verificar si ya está corriendo
    try:
        import requests
        r = requests.get("http://localhost:5051/sites", timeout=2)
        if r.status_code == 200:
            print("Monitor de alertas ya esta corriendo")
            return None
    except Exception:
        pass  # No está corriendo, lo iniciamos

    print("Iniciando monitor de alertas...")

    try:
        python_exe = sys.executable  # mismo Python que está corriendo web_app.py

        if sys.platform == "win32":
            if DEBUG_MONITOR:
                # Modo debug: nueva consola minimizada para ver logs
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 6  # SW_MINIMIZE
                monitor_process = subprocess.Popen(
                    [python_exe, monitor_script],
                    cwd=base_dir,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # Modo produccion: sin ventana visible
                monitor_process = subprocess.Popen(
                    [python_exe, monitor_script],
                    cwd=base_dir,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
        else:
            monitor_process = subprocess.Popen(
                [python_exe, monitor_script],
                cwd=base_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Esperar a que levante
        time.sleep(3)

        if monitor_process.poll() is not None:
            print("Error: El monitor de alertas termino inesperadamente")
            return None

        print(f"Monitor de alertas iniciado correctamente (PID: {monitor_process.pid})")
        return monitor_process

    except Exception as e:
        print(f"Error iniciando monitor de alertas: {e}")
        return None


def stop_monitor_alertas():
    """Detiene el monitor de alertas"""
    global monitor_process

    if monitor_process is not None:
        print("Deteniendo monitor de alertas...")
        try:
            monitor_process.terminate()
            monitor_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            monitor_process.kill()
        except Exception as e:
            print(f"Error deteniendo monitor: {e}")
        monitor_process = None


def main():
    """Punto de entrada principal de la aplicacion"""
    # Registrar limpieza al salir
    atexit.register(stop_whatsapp_bot)

    # Manejar señales de terminación
    def signal_handler(signum, frame):
        stop_whatsapp_bot()
        sys.exit(0)

    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    try:
        # Iniciar el bot de WhatsApp primero
        start_whatsapp_bot()

        # Luego iniciar la GUI
        from gui import run
        run()

    except ImportError as e:
        print(f"Error importando modulos: {e}")
        print("\nAsegurate de tener instaladas las dependencias:")
        print("  pip install customtkinter pillow pystray requests beautifulsoup4 qrcode")
        stop_whatsapp_bot()
        sys.exit(1)
    except Exception as e:
        print(f"Error iniciando la aplicacion: {e}")
        import traceback
        traceback.print_exc()
        stop_whatsapp_bot()
        sys.exit(1)
    finally:
        stop_whatsapp_bot()


if __name__ == "__main__":
    main()
