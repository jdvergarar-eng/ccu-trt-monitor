# CCU-TRT: Sistema de Alertas de Tiempo de Residencia en Planta

Sistema de monitoreo en tiempo real de camiones en centros de distribucion CCU.
Envia alertas automaticas por WhatsApp cuando los camiones exceden los tiempos permitidos.

**Desarrollado por:** Juan Vergara & Vicente Vergara — Equipo de Operaciones, CD Santiago Sur

---

## Contenido

1. [Como funciona (resumen)](#como-funciona-resumen)
2. [Estructura del proyecto](#estructura-del-proyecto)
3. [Que hace cada archivo](#que-hace-cada-archivo)
4. [Flujo de datos](#flujo-de-datos)
5. [Configuracion](#configuracion)
6. [Donde cambiar cada cosa](#donde-cambiar-cada-cosa)
7. [Puertos usados](#puertos-usados)
8. [Como ejecutar](#como-ejecutar)
9. [Dependencias](#dependencias)

---

## Como funciona (resumen)

El sistema tiene tres partes principales que se comunican entre si:

```
┌─────────────────┐     HTTP     ┌──────────────────┐     HTTP      ┌─────────────────┐
│  GUI (Python)   │◄────────────►│  Bot WhatsApp    │◄─────────────►│  Sistema TRT    │
│  CustomTkinter  │              │  (Node.js)       │               │  (servidor CCU) │
│  puerto: ninguno│              │  puerto: 5050    │               │  192.168.55.79  │
└─────────────────┘              └──────────────────┘               └─────────────────┘
        │                                  ▲
        │ HTTP                            │ HTTP
        ▼                                  │
┌─────────────────┐              ┌──────────────────┐
│  Sistema TRT    │              │  monitor_alertas │
│  (servidor CCU) │              │  (Python Flask)  │
│  192.168.55.79  │              │  puerto: 5051    │
└─────────────────┘              └──────────────────┘
```

1. La **GUI** (`main.py` + carpeta `gui/`) es la interfaz del usuario. Inicia el bot y muestra el dashboard.
2. El **Bot de WhatsApp** (`bot/bot_whatsapp.js`) se conecta a una cuenta de WhatsApp y expone una API HTTP para enviar mensajes e imagenes a grupos.
3. El **monitor de alertas** (`monitor_alertas.py`) consulta el sistema TRT de CCU periodicamente, clasifica los camiones, genera banners (imagenes PNG) y los envia por WhatsApp a traves del bot.
4. El **core** (`core/`) contiene los clientes HTTP que la GUI usa para hablar con el bot y con el sistema TRT.

---

## Estructura del proyecto

```
trt_app/
├── main.py                      # Punto de entrada principal
├── monitor_alertas.py           # Motor del monitoreo autonomo (1600+ lineas)
├── config.txt                   # Archivo de configuracion de sitios y parametros
├── requirements.txt             # Dependencias de Python
├── start_sistema.bat            # Script para iniciar todo en Windows
├── detener_sistema.bat          # Script para detener todo en Windows
│
├── gui/                         # Interfaz grafica (CustomTkinter)
│   ├── __init__.py              # Exporta CCUTRTApp y run()
│   ├── app.py                   # Ventana principal y logica de navegacion entre pantallas
│   ├── styles.py                # Colores, fuentes y dimensiones (tema oscuro CCU)
│   ├── components.py            # Widgets reutilizables (botones, cards, badges, etc.)
│   └── screens/                 # Pantallas de la aplicacion
│       ├── __init__.py          # Exporta las 4 pantallas
│       ├── splash.py            # Pantalla de inicio (logo CCU, creditos)
│       ├── welcome.py           # Pantalla de requisitos del sistema
│       ├── setup.py             # Asistente de configuracion (5 pasos)
│       └── dashboard.py         # Dashboard principal con sidebar y tabs
│
├── core/                        # Modulos de logica de negocio
│   ├── __init__.py              # Exporta clientes y modelos publicos
│   ├── config.py                # Lee y escribe config.txt (ConfigManager)
│   ├── whatsapp.py              # Cliente HTTP para el bot (WhatsAppClient)
│   ├── trt_api.py               # Cliente HTTP para el sistema TRT (TRTClient)
│   ├── banner.py                # Generador de imagenes PNG de alertas
│   └── monitor.py               # Stub (no usado actualmente)
│
├── bot/                         # Bot de WhatsApp (Node.js)
│   ├── bot_whatsapp.js          # Codigo principal del bot
│   ├── package.json             # Dependencias npm
│   └── package-lock.json
│
├── banners/                     # Imagenes PNG generadas automaticamente
├── daily_data/                  # Resumenes diarios en JSON (uno por sitio)
├── logs/                        # Archivos de log del monitor
├── assets/                      # Recursos (iconos, imagenes)
└── scripts/                     # Scripts auxiliares de Windows
    ├── iniciar_monitor.bat
    ├── install.bat
    ├── oculto.vbs
    └── start_config.bat
```

---

## Que hace cada archivo

### Punto de entrada

| Archivo | Resumen |
|---|---|
| `main.py` | Inicia el bot de WhatsApp como subproceso (`node bot_whatsapp.js`) y luego lanza la GUI. Al cerrar la app, detiene el bot automaticamente. |

### GUI — `gui/`

| Archivo | Resumen |
|---|---|
| `app.py` | Clase `CCUTRTApp` (hereda de `ctk.CTk`). Controla la ventana, detecta si es primera ejecucion, y navega entre pantallas: Splash → Welcome → Setup → Dashboard. |
| `styles.py` | Constantes de colores corporativos CCU (rojo `#C8102E`, dorado `#D4A84B`), fuentes (`Segoe UI`) y dimensiones de la ventana (1200x750). |
| `components.py` | Widgets reutilizables: `Card`, `StatusBadge`, `PrimaryButton`, `SecondaryButton`, `SuccessButton`, `DangerButton`, `LabeledInput`, `LabeledSelect`, `ProgressSteps`, `CenterCard`, `LogViewer`, `SidebarButton`, `ToggleSwitch`. |
| `screens/splash.py` | Pantalla inicial con logo CCU, titulo "Sistema de Alertas TRT" y boton "Comenzar Configuracion". Solo se muestra en primera ejecucion. |
| `screens/welcome.py` | Lista los requisitos del sistema antes de configurar (telefono con WhatsApp, PC encendido 24/7, red CCU, grupos creados). |
| `screens/setup.py` | Asistente de 5 pasos: (1) Vincular WhatsApp via QR, (2) URL del TRT y parametros, (3) Seleccionar centros, (4) Configurar umbrales por centro, (5) Guardar. Guarda la configuracion en `config.txt` al finalizar. |
| `screens/dashboard.py` | Pantalla principal con sidebar y 4 tabs: **Inicio** (estado del sistema, centros, logs), **Centros** (lista de centros configurados), **Estadisticas** (metricas), **Configuracion** (parametros y WhatsApp). Tambien maneja el ciclo de monitoreo desde la GUI y el envio de banners. |

### Core — `core/`

| Archivo | Resumen |
|---|---|
| `config.py` | `ConfigManager`: lee y escribe `config.txt`. Expone `AppConfig` (URL base, polling, reenvio) y `SiteConfig` (datos de cada centro: nombre, db, umbrales, grupo de WhatsApp). |
| `whatsapp.py` | `WhatsAppClient`: habla con el bot por HTTP en `localhost:5050`. Metodos: `health_check()`, `get_status()`, `get_qr_status()`, `get_groups()`, `send_text()`, `send_image()`. |
| `trt_api.py` | `TRTClient`: habla con el sistema TRT de CCU. `test_connection()` verifica acceso, `get_available_centers()` obtiene los centros del sistema parseando HTML, `get_trucks_in_plant()` hace un POST y parsea la tabla de camiones, `get_center_stats()` retorna estadisticas calculadas. |
| `banner.py` | Genera las imagenes PNG de alertas (1080x1080). `analyze_trucks_for_banner()` clasifica camiones en verde/amarillo/rojo y calcula severidad (INFO / ALERTA / CRITICA). `make_banner_png()` dibuja la imagen con Pillow. `format_banner_summary_message()` genera el texto que acompana la imagen en WhatsApp. |

### Bot — `bot/`

| Archivo | Resumen |
|---|---|
| `bot_whatsapp.js` | Bot unificado que hace dos cosas: (A) Escucha menciones (`@bot`) en grupos de WhatsApp y responde a comandos `status` y `resumen`. (B) Expone un servidor Express en puerto 5050 con endpoints para que Python le pida enviar mensajes e imagenes. Tambien toma screenshots del TRT usando Puppeteer. Lee su configuracion de sitios desde `../config.txt`. |

### Monitoreo autonomo

| Archivo | Resumen |
|---|---|
| `monitor_alertas.py` | Motor completo de monitoreo que se puede ejecutar independientemente. Consulta el TRT cada N segundos, clasifica camiones, genera banners, los envia por WhatsApp, y maneja resumenes diarios con turnos (A, B, C). Expone una API Flask en puerto 5051 con endpoints `/resumen/<sitio>` y `/sites`. |

---

## Flujo de datos

### Alerta automatica (monitoreo desde la GUI)

```
1. Dashboard inicia ciclo de monitoreo cada POLL_SECONDS segundos
2. Llama a TRTClient.get_center_stats() → POST al sistema TRT (192.168.55.79)
3. Parsea la tabla HTML de camiones
4. Para cada camion calcula tiempo en planta en minutos
5. Clasifica segun umbral del centro:
       Verde:    < 80% del umbral
       Amarillo: 80-130% del umbral
       Rojo:     > 130% del umbral
6. Calcula severidad del centro:
       CRITICA:  ≥2 rojos, o exceso ≥30min, o ≥20% rojos
       ALERTA:   ≥2 amarillos, o ≥30% amarillos
       INFO:     situacion normal
7. Si hay camiones → genera banner PNG (core/banner.py)
8. Envia banner al grupo de WhatsApp via POST a localhost:5050/send/image-path
9. El bot recibe la imagen y la envía al grupo configurado
```

### Comando manual en WhatsApp

```
1. Alguien escribe "@bot status" en un grupo
2. El bot detecta la mencion y el keyword
3. Resuelve el sitio segun el WHATSAPP_GROUP_ID del grupo
4. Consulta el TRT directamente (axios POST)
5. Parsea y clasifica camiones (misma logica que Python)
6. Toma screenshot del TRT con Puppeteer
7. Envia la imagen + resumen al grupo
```

---

## Configuracion

Todo se configura en **`config.txt`**. Este archivo es leido por Python (core/config.py) y por el bot de Node.js (bot_whatsapp.js) independientemente.

```ini
# ─── PARAMETROS GENERALES ────────────────────────────────────
BASE_URL=http://192.168.55.79         # URL del servidor TRT de CCU
POLL_SECONDS=10                       # Cada cuantos segundos consultar
REALERT_MINUTES=2                     # Cada cuantos minutos reenviar alerta

# ─── SITIO 1 (se puede repetir este bloque para mas centros) ─
SITE_NAME=Rancagua Nuevo              # Nombre del centro
DB_NAME=aca_ent_rancagua_nuevo        # Base de datos en el TRT
OP_CODE=1                             # Codigo de operacion
CD_CODE=rancagua_nuevo                # Codigo del centro
REFERER_ID=6                          # ID del registro en el TRT
WHATSAPP_GROUP_ID=120363423974021024@g.us   # ID interno del grupo de WhatsApp
UMBRAL_MINUTES_LATERAL=1              # Umbral en minutos para descarga lateral
UMBRAL_MINUTES_TRASERA=2              # Umbral en minutos para descarga trasera
UMBRAL_MINUTES_INTERNA=3              # Umbral en minutos para descarga interna
```

Para agregar un segundo centro, copiar el bloque del sitio (desde `SITE_NAME`) al final del archivo con los datos del nuevo centro. El setup wizard de la GUI tambien puede hacerlo automaticamente.

### Clasificacion de tipo de descarga por empresa

La logica de que tipo de descarga tiene cada camion se basa en el nombre de la empresa:

| Empresa contiene | Tipo de descarga |
|---|---|
| ROMANI | INTERNA |
| LOGISTICA DEL NORTE | INTERNA |
| INTERANDINOS | TRASERA |
| Cualquier otra | LATERAL |

Esta logica esta en dos lugares (ambos deben coincidir):
- **Python:** `core/banner.py` — funcion `get_tipo_descarga()`
- **Node.js:** `bot/bot_whatsapp.js` — dentro de `getStatusFromMonitor()`

---

## Donde cambiar cada cosa

Esta seccion es la mas importante para quien necesite modificar el sistema.

### Si quieres cambiar colores o estilo de la GUI
→ `gui/styles.py` — todos los colores, fuentes y dimensiones estan centralizados ahi.

### Si quieres cambiar los umbrales de tiempo permitido
→ `config.txt` — cambiar `UMBRAL_MINUTES_LATERAL`, `UMBRAL_MINUTES_TRASERA` o `UMBRAL_MINUTES_INTERNA` para el sitio correspondiente.

### Si quieres agregar un nuevo centro de distribucion
→ Agregar un nuevo bloque en `config.txt` con los datos del centro. O usar el Setup Wizard de la GUI (pantalla `gui/screens/setup.py`).

### Si quieres cambiar cuanto tiempo espera entre consultas
→ `config.txt` — cambiar `POLL_SECONDS`.

### Si quieres cambiar cuanto tiempo espera antes de reenviar una alerta
→ `config.txt` — cambiar `REALERT_MINUTES`.

### Si quieres cambiar la URL del servidor TRT
→ `config.txt` — cambiar `BASE_URL`.

### Si quieres cambiar como se clasifican los camiones (verde/amarillo/rojo)
→ `core/banner.py` — funcion `classify_truck()`. Actualmente: verde < 80%, amarillo 80-130%, rojo > 130% del umbral.

### Si quieres cambiar como se calcula la severidad (INFO/ALERTA/CRITICA)
→ `core/banner.py` — funcion `calculate_center_severity()`.

### Si quieres cambiar el diseño de los banners (imagenes de alerta)
→ `core/banner.py` — funcion `make_banner_png()`. Ahi esta todo el dibujado con Pillow (colores, posiciones, textos).

### Si quieres cambiar el mensaje de texto que acompana al banner
→ `core/banner.py` — funcion `format_banner_summary_message()`.

### Si quieres cambiar que empresas corresponden a que tipo de descarga
→ `core/banner.py` — funcion `get_tipo_descarga()`. Y tambien `bot/bot_whatsapp.js` en la funcion `getStatusFromMonitor()` (ambos deben estar en sincronia).

### Si quieres cambiar como el bot detecta los comandos en WhatsApp
→ `bot/bot_whatsapp.js` — constante `CONFIG.triggerKeywords` (para status) y `CONFIG.resumenKeywords` (para resumen).

### Si quieres cambiar el grupo de WhatsApp donde van las alertas
→ `config.txt` — cambiar `WHATSAPP_GROUP_ID` del sitio correspondiente. El valor es el ID interno del grupo (formato `xxxxxxxxx@g.us`), no el codigo de invitacion.

### Si quieres cambiar la pantalla de inicio (splash)
→ `gui/screens/splash.py`.

### Si quieres cambiar los requisitos que se muestran antes de configurar
→ `gui/screens/welcome.py` — lista `requirements` en el metodo `_create_widgets()`.

### Si quieres agregar un nuevo tab al dashboard
→ `gui/screens/dashboard.py` — agregar en la lista `tabs` del sidebar y crear un metodo `_tab_nombre()` nuevo.

### Si quieres agregar un nuevo widget reutilizable
→ `gui/components.py` — agregar la nueva clase ahi y exportarla en `gui/__init__.py`.

### Si quieres cambiar como se lee o guarda la configuracion
→ `core/config.py` — clase `ConfigManager`, metodos `load()` y `save()`.

### Si quieres cambiar la forma en que el bot se conecta a WhatsApp
→ `bot/bot_whatsapp.js` — seccion "CLIENTE WHATSAPP" (la instancia de `Client` y sus opciones de Puppeteer). La sesion se guarda en `bot/whatsapp_session/`.

---

## Puertos usados

| Puerto | Servicio | Archivo |
|---|---|---|
| 5050 | API HTTP del bot de WhatsApp (Express) | `bot/bot_whatsapp.js` |
| 5051 | API HTTP del monitor de alertas (Flask) | `monitor_alertas.py` |

Ambos escuchan solo en localhost. La GUI no expone ningún puerto.

---

## Como ejecutar

### Opcion 1: Ejecutar todo desde la GUI (recomendada)

```bash
python main.py
```

Esto inicia automaticamente el bot de WhatsApp y luego la interfaz grafica. Si es primera ejecucion, te guia por el Setup Wizard.

### Opcion 2: Scripts de Windows

- **`start_sistema.bat`** — inicia el bot y el monitor en segundo plano.
- **`detener_sistema.bat`** — detiene todos los procesos.

### Opcion 3: Componentes por separado

```bash
# Terminal 1: Bot de WhatsApp
cd bot
node bot_whatsapp.js

# Terminal 2: Monitor de alertas (opcional, si no lo maneja la GUI)
python monitor_alertas.py

# Terminal 3: GUI
python main.py
```

---

## Dependencias

### Python (`requirements.txt`)

```
requests          # HTTP requests
flask             # API del monitor de alertas
beautifulsoup4    # Parsear HTML del TRT
lxml              # Parser HTML
Pillow            # Generar banners PNG
qrcode            # Generar codigo QR en la GUI
customtkinter     # Framework de GUI
pystray           # Icono en bandeja del sistema
pyinstaller       # Para empaquetar como .exe
```

Instalar con:
```bash
pip install -r requirements.txt
```

### Node.js (`bot/package.json`)

```
whatsapp-web.js   # Cliente de WhatsApp (usa Puppeteer)
qrcode-terminal   # Mostrar QR en consola
express           # Servidor HTTP
multer            # Recibir archivos por HTTP
axios             # HTTP requests
cheerio           # Parsear HTML
```

Instalar con:
```bash
cd bot
npm install
```

Node.js debe estar instalado en el sistema. Se necesita version >= 16.
