/**
 * Bot de WhatsApp - Sistema Unificado v2
 * 
 * Funcionalidades:
 * 1. Escucha menciones en grupos para comando "status" y "resumen"
 * 2. Expone API HTTP para que Python envie mensajes/imagenes
 * 3. Toma screenshots de la pagina del TRT
 */

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const axios = require('axios');
const cheerio = require('cheerio');

// =============================================================================
// CARGA DE PUERTOS DESDE ports.txt (independiente de config.txt)
// =============================================================================

function loadPortsConfig(portsPath = 'ports.txt') {
    const ports = {
        botPort: 5050,
        monitorPort: 5051
    };

    try {
        const fullPath = path.resolve(__dirname, '..', portsPath);
        if (!fs.existsSync(fullPath)) {
            console.log('ports.txt no encontrado, usando puertos por defecto');
            return ports;
        }

        const lines = fs.readFileSync(fullPath, 'utf-8').split('\n');

        for (let line of lines) {
            line = line.trim();

            // Saltar comentarios y lineas vacias
            if (!line || line.startsWith('#')) {
                continue;
            }

            if (line.includes('=')) {
                const [key, ...valueParts] = line.split('=');
                const value = valueParts.join('=').trim();
                const keyTrim = key.trim().toUpperCase();

                if (keyTrim === 'BOT_PORT') ports.botPort = parseInt(value);
                else if (keyTrim === 'MONITOR_PORT') ports.monitorPort = parseInt(value);
            }
        }

        console.log(`Puertos configurados: Bot=${ports.botPort}, Monitor=${ports.monitorPort}`);

    } catch (error) {
        console.error('Error cargando ports.txt:', error.message);
        console.log('Usando puertos por defecto');
    }

    return ports;
}

// =============================================================================
// CARGA DE CONFIGURACION DESDE config.txt
// =============================================================================

function loadConfigFile(configPath = 'config.txt') {
    const config = {
        baseUrl: null,
        pollSeconds: null,
        realertMinutes: null,
        sites: []
    };
    
    try {
        const fullPath = path.resolve(__dirname, '..', configPath);
        if (!fs.existsSync(fullPath)) {
            console.error(`No se encontro: ${fullPath}`);
            return config;
        }
        
        const lines = fs.readFileSync(fullPath, 'utf-8').split('\n');
        let currentSite = {};
        
        for (let line of lines) {
            line = line.trim();
            
            // Linea vacia o comentario: guardar sitio actual si existe
            if (!line || line.startsWith('#')) {
                if (currentSite.name) {
                    config.sites.push(currentSite);
                    currentSite = {};
                }
                continue;
            }
            
            if (line.includes('=')) {
                const [key, ...valueParts] = line.split('=');
                const value = valueParts.join('=').trim();
                const keyTrim = key.trim();
                
                if (keyTrim === 'BASE_URL') config.baseUrl = value;
                else if (keyTrim === 'POLL_SECONDS') config.pollSeconds = parseInt(value);
                else if (keyTrim === 'REALERT_MINUTES') config.realertMinutes = parseInt(value);
                else if (keyTrim === 'SITE_NAME') currentSite.name = value;
                else if (keyTrim === 'GROUP_ID') currentSite.groupId = value;
                else if (keyTrim === 'UMBRAL_MINUTES') currentSite.umbral = parseInt(value);
                else if (keyTrim === 'UMBRAL_MINUTES_LATERAL') currentSite.umbralLateral = parseInt(value);
                else if (keyTrim === 'UMBRAL_MINUTES_TRASERA') currentSite.umbralTrasera = parseInt(value);
                else if (keyTrim === 'UMBRAL_MINUTES_INTERNA') currentSite.umbralInterna = parseInt(value);
                else if (keyTrim === 'DB_NAME') currentSite.db = value;
                else if (keyTrim === 'OP_CODE') currentSite.op = value;
                else if (keyTrim === 'CD_CODE') currentSite.cd = value;
                else if (keyTrim === 'REFERER_ID') currentSite.refererId = value;
                else if (keyTrim === 'WHATSAPP_GROUP_ID') currentSite.whatsappGroupId = value;
            }
        }
        
        // Guardar ultimo sitio si existe
        if (currentSite.name) {
            config.sites.push(currentSite);
        }
        
        console.log(`Configuracion cargada: ${config.sites.length} sitios`);
        for (const site of config.sites) {
            if (site.umbral) {
                console.log(`  - ${site.name}: umbral=${site.umbral} min`);
            } else if (site.umbralInterna) {
                console.log(`  - ${site.name}: lateral=${site.umbralLateral} min, trasera=${site.umbralTrasera} min, interna=${site.umbralInterna} min`);
            } else {
                console.log(`  - ${site.name}: lateral=${site.umbralLateral} min, trasera=${site.umbralTrasera} min`);
            }
        }
        
    } catch (error) {
        console.error('Error cargando config.txt:', error.message);
    }
    
    return config;
}

// Cargar puertos desde ports.txt (independiente de config.txt)
const PORTS_CONFIG = loadPortsConfig();

// Cargar configuracion de sitios desde config.txt
const SITES_CONFIG = loadConfigFile();

// =============================================================================
// CONFIGURACION
// =============================================================================

const CONFIG = {
    // Puerto del servidor HTTP (desde ports.txt)
    httpPort: PORTS_CONFIG.botPort,

    // Puerto de la API de resumenes (desde ports.txt)
    monitorApiPort: PORTS_CONFIG.monitorPort,
    
    // Numeros que activan el bot (se llenan automaticamente al conectar)
    botPhoneNumbers: [],
    
    // Keywords para comando status
    triggerKeywords: ['status', 'estado', 'reporte', 'informe'],
    
    // Keywords para comando resumen
    resumenKeywords: ['resumen'],
    
    // URL base del sistema TRT (para screenshots) - se sobreescribe con config.txt
    trtBaseUrl: SITES_CONFIG.baseUrl || 'http://192.168.55.79',
    
    // Directorio de sesion WhatsApp
    sessionDir: './whatsapp_session',
    
    // Directorio temporal para imagenes
    tempDir: './temp',
};

// Crear directorio temporal
if (!fs.existsSync(CONFIG.tempDir)) {
    fs.mkdirSync(CONFIG.tempDir, { recursive: true });
}

// =============================================================================
// CLIENTE WHATSAPP
// =============================================================================

console.log('='.repeat(50));
console.log('SISTEMA WHATSAPP - CCU v2');
console.log('='.repeat(50));

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: CONFIG.sessionDir
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

let clientReady = false;
let currentQR = null;
let waStatus = 'initializing';

client.on('qr', (qr) => {
    currentQR = qr;
    waStatus = 'waiting_scan';
    console.log('\nEscanea este codigo QR con WhatsApp:\n');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => {
    console.log('Autenticacion exitosa!');
});

client.on('auth_failure', (msg) => {
    console.error('Error de autenticacion:', msg);
    process.exit(1);
});

client.on('ready', () => {
    clientReady = true;
    currentQR = null;
    waStatus = 'connected';
    console.log('\nWhatsApp conectado!');
    console.log('Numero:', client.info.wid.user);
    
    // Detectar automaticamente los identificadores del bot
    const botUser = client.info.wid.user;
    if (!CONFIG.botPhoneNumbers.includes(botUser)) {
        CONFIG.botPhoneNumbers.push(botUser);
    }
    
    // Detectar LID si existe
    if (client.info.lid && client.info.lid.user) {
        const lidUser = client.info.lid.user;
        console.log('LID:', lidUser);
        if (!CONFIG.botPhoneNumbers.includes(lidUser)) {
            CONFIG.botPhoneNumbers.push(lidUser);
        }
    }
    
    console.log('Identificadores del bot:', CONFIG.botPhoneNumbers);
    console.log('\nComandos de consola:');
    console.log('  grupos  - Lista los IDs de todos los grupos');
    console.log('  salir   - Cierra el sistema\n');
    console.log('API HTTP en puerto', CONFIG.httpPort);
    console.log('='.repeat(50) + '\n');
});

client.on('disconnected', (reason) => {
    clientReady = false;
    waStatus = 'disconnected';
    console.log('WhatsApp desconectado:', reason);
});

// =============================================================================
// COMANDOS DE CONSOLA
// =============================================================================

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

rl.on('line', async (input) => {
    const cmd = input.trim().toLowerCase();
    
    if (cmd === 'grupos') {
        if (!clientReady) {
            console.log('WhatsApp no esta conectado aun.\n');
            return;
        }
        console.log('\nObteniendo grupos...\n');
        try {
            const chats = await client.getChats();
            const groups = chats.filter(chat => chat.isGroup);
            
            if (groups.length === 0) {
                console.log('No se encontraron grupos.\n');
            } else {
                console.log('='.repeat(60));
                console.log('GRUPOS DISPONIBLES');
                console.log('='.repeat(60));
                groups.forEach((group, i) => {
                    console.log((i + 1) + '. ' + group.name);
                    console.log('   ID: ' + group.id._serialized);
                });
                console.log('='.repeat(60) + '\n');
            }
        } catch (error) {
            console.error('Error:', error.message);
        }
    } else if (cmd === 'salir' || cmd === 'exit') {
        console.log('Cerrando...');
        await client.destroy();
        process.exit(0);
    } else if (cmd !== '') {
        console.log('Comandos: grupos, salir');
    }
});

// =============================================================================
// ESCUCHA DE MENCIONES (COMANDOS STATUS Y RESUMEN)
// =============================================================================

client.on('message_create', async (message) => {
    // Ignorar mensajes enviados por el propio bot
    if (message.fromMe) return;
    
    // Solo procesar mensajes de grupos
    if (!message.from.endsWith('@g.us')) return;
    
    const mentionedIds = message.mentionedIds || [];
    
    // Extraer todos los identificadores mencionados
    const mentionedNumbers = mentionedIds.map(id => {
        if (typeof id === 'string') return id.split('@')[0];
        else if (id.user) return id.user;
        else if (id._serialized) return id._serialized.split('@')[0];
        return '';
    }).filter(n => n);
    
    // Verificar si el bot fue mencionado
    const isBotMentioned = mentionedNumbers.some(num => CONFIG.botPhoneNumbers.includes(num));
    
    // Auto-detectar LID: si el mensaje tiene keywords del bot y hay un LID no reconocido
    if (!isBotMentioned && mentionedNumbers.length > 0) {
        const text = message.body.toLowerCase();
        const hasAnyKeyword = [...CONFIG.triggerKeywords, ...CONFIG.resumenKeywords].some(kw => text.includes(kw));
        
        if (hasAnyKeyword) {
            // Buscar posibles LIDs (numeros largos que no son telefonos normales)
            for (const num of mentionedNumbers) {
                if (num.length > 12 && !CONFIG.botPhoneNumbers.includes(num)) {
                    console.log('LID detectado automaticamente:', num);
                    CONFIG.botPhoneNumbers.push(num);
                    console.log('Identificadores del bot:', CONFIG.botPhoneNumbers);
                }
            }
            // Re-verificar si ahora el bot fue mencionado
            if (mentionedNumbers.some(num => CONFIG.botPhoneNumbers.includes(num))) {
                // Continuar procesando el mensaje
            } else {
                return;
            }
        } else {
            return;
        }
    } else if (!isBotMentioned) {
        return;
    }
    
    const text = message.body.toLowerCase();
    
    // Verificar comando resumen (tiene prioridad)
    const hasResumenKeyword = CONFIG.resumenKeywords.some(kw => text.includes(kw));
    if (hasResumenKeyword) {
        await handleResumenCommand(message);
        return;
    }
    
    // Verificar comando status
    const hasStatusKeyword = CONFIG.triggerKeywords.some(kw => text.includes(kw));
    if (hasStatusKeyword) {
        await handleStatusCommand(message);
        return;
    }
});

// =============================================================================
// COMANDO RESUMEN
// =============================================================================

async function handleResumenCommand(message) {
    const groupId = message.from;

    try {
        // sendStateTyping puede fallar, ignorar error
        try {
            const chat = await message.getChat();
            await chat.sendStateTyping();
        } catch (e) {}

        console.log(`[RESUMEN] Grupo: ${groupId}`);

        let site = null;
        let siteId = null;
        let siteName = null;

        // Buscar en config.txt por WHATSAPP_GROUP_ID
        site = SITES_CONFIG.sites.find(s => s.whatsappGroupId === groupId);
        if (site) {
            siteId = site.refererId;
            siteName = site.name;
        }

        // Si no se encontro, intentar extraer del mensaje
        if (!siteId) {
            const match = message.body.match(/resumen\s*(\d+)/i);
            if (match) {
                siteId = match[1];
                site = SITES_CONFIG.sites.find(s => s.refererId === siteId);
                if (site) siteName = site.name;
            }
        }

        console.log(`[RESUMEN] SiteId encontrado: ${siteId || 'ninguno'}`);

        if (!siteId || !siteName) {
            await client.sendMessage(groupId, 'No se encontro sitio configurado para este grupo.\nVerifica que WHATSAPP_GROUP_ID este configurado en config.txt', { sendSeen: false });
            return;
        }

        // Consultar API de resumenes
        const resumenData = await getResumenFromMonitor(siteName);

        if (resumenData.success) {
            await client.sendMessage(groupId, resumenData.message, { sendSeen: false });
        } else {
            await client.sendMessage(groupId, `Error obteniendo resumen: ${resumenData.error}`, { sendSeen: false });
        }

    } catch (error) {
        console.error('Error en resumen:', error.message);
        try {
            await client.sendMessage(groupId, 'Error al procesar comando de resumen.', { sendSeen: false });
        } catch (e) {}
    }
}

async function getResumenFromMonitor(siteName) {
    try {
        // Formatear nombre para la URL
        const siteNameUrl = encodeURIComponent(siteName.toLowerCase().replace(/ /g, '_'));
        const url = `http://localhost:${CONFIG.monitorApiPort}/resumen/${siteNameUrl}`;
        
        const response = await axios.get(url, { timeout: 5000 });
        
        if (response.data && response.data.success) {
            return {
                success: true,
                message: response.data.message
            };
        } else {
            return {
                success: false,
                error: response.data.error || 'Respuesta invalida'
            };
        }
    } catch (error) {
        console.error('Error consultando monitor:', error.message);
        return {
            success: false,
            error: 'No se pudo conectar con el monitor de alertas'
        };
    }
}

// =============================================================================
// COMANDO STATUS (EXISTENTE)
// =============================================================================

async function handleStatusCommand(message) {
    const groupId = message.from;

    try {
        // sendStateTyping puede fallar, ignorar error
        try {
            const chat = await message.getChat();
            await chat.sendStateTyping();
        } catch (e) {}

        console.log(`[STATUS] Grupo: ${groupId}`);

        let site = null;
        let siteId = null;

        // Buscar en config.txt por WHATSAPP_GROUP_ID
        site = SITES_CONFIG.sites.find(s => s.whatsappGroupId === groupId);
        if (site) {
            siteId = site.refererId;
        }

        // Si no se encontro, intentar extraer del mensaje
        if (!siteId) {
            const match = message.body.match(/status\s*(\d+)/i);
            if (match) {
                siteId = match[1];
                site = SITES_CONFIG.sites.find(s => s.refererId === siteId);
            }
        }

        console.log(`[STATUS] SiteId encontrado: ${siteId || 'ninguno'}`);

        if (!siteId || !site) {
            await client.sendMessage(groupId, 'No se encontro sitio configurado para este grupo.\nVerifica que WHATSAPP_GROUP_ID este configurado en config.txt', { sendSeen: false });
            return;
        }

        // Obtener datos del sitio
        const statusData = await getStatusFromMonitor(siteId);

        // Tomar screenshot
        const screenshotPath = await takeScreenshot(siteId);

        if (screenshotPath) {
            const media = MessageMedia.fromFilePath(screenshotPath);
            await client.sendMessage(groupId, media, { caption: statusData.summary, sendSeen: false });
            fs.unlinkSync(screenshotPath);
        } else {
            await client.sendMessage(groupId, statusData.summary, { sendSeen: false });
        }

    } catch (error) {
        console.error('Error en status:', error.message);
        try {
            await client.sendMessage(groupId, 'Error al procesar comando.', { sendSeen: false });
        } catch (e) {}
    }
}

async function getStatusFromMonitor(siteId) {
    // Buscar sitio en la configuracion cargada de config.txt
    const site = SITES_CONFIG.sites.find(s => s.refererId === siteId);
    
    if (!site) {
        return { summary: `*Sitio ${siteId}*\n_Sitio no configurado en config.txt_` };
    }
    
    try {
        // Consultar datos del TRT
        const baseUrl = SITES_CONFIG.baseUrl || CONFIG.trtBaseUrl;
        const url = `${baseUrl}/ces/home/inicio/`;
        const referer = `${baseUrl}/ces/home/registro/${siteId}`;
        
        const response = await axios.post(url, 
            `db=${site.db}&op=${site.op}&cd=${site.cd}`,
            {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': referer,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout: 10000
            }
        );
        
        // Parsear HTML
        const $ = cheerio.load(response.data);
        const tds = [];
        $('td').each((i, el) => {
            tds.push($(el).text().trim());
        });
        
        // Procesar filas (9 columnas por fila)
        const COLS = 9;
        const rows = [];
        for (let i = 0; i + COLS <= tds.length; i += COLS) {
            const patente = tds[i + 1];
            const empresa = tds[i + 2];
            const tiempoStr = tds[i + 5];
            if (patente && tiempoStr) {
                rows.push({ patente, empresa, tiempoStr });
            }
        }
        
        // Parsear tiempo y clasificar
        let nGreen = 0, nYellow = 0, nRed = 0;
        const timeRegex = /(\d+)\s*d[ia]as?\s*(\d{2}):(\d{2}):(\d{2})/i;
        
        for (const row of rows) {
            const match = row.tiempoStr.match(timeRegex);
            if (!match) continue;
            
            const days = parseInt(match[1]);
            const hours = parseInt(match[2]);
            const minutes = parseInt(match[3]);
            const totalMinutes = days * 1440 + hours * 60 + minutes;
            
            // Obtener umbral segun empresa (igual que Python)
            let umbral;
            if (site.umbral) {
                // Si tiene umbral unico, usarlo
                umbral = site.umbral;
            } else {
                // Si tiene umbrales diferenciados, determinar tipo de descarga
                const empresaUpper = (row.empresa || '').toUpperCase();
                
                // Detectar tipo de descarga (misma logica que Python)
                let tipoDescarga = 'LATERAL';
                if (empresaUpper.includes('ROMANI') || empresaUpper.includes('LOGISTICA DEL NORTE')) {
                    tipoDescarga = 'INTERNA';
                } else if (empresaUpper.includes('INTERANDINOS')) {
                    tipoDescarga = 'TRASERA';
                }
                
                // Asignar umbral segun tipo
                if (tipoDescarga === 'INTERNA') {
                    umbral = site.umbralInterna || site.umbralLateral || 60;
                } else if (tipoDescarga === 'TRASERA') {
                    umbral = site.umbralTrasera || 60;
                } else {
                    umbral = site.umbralLateral || 60;
                }
            }
            
            // Clasificar (misma logica que Python)
            const umbral80 = umbral * 0.8;
            const umbral130 = umbral * 1.3;
            
            if (totalMinutes < umbral80) {
                nGreen++;
            } else if (totalMinutes < umbral130) {
                nYellow++;
            } else {
                nRed++;
            }
        }
        
        const total = nGreen + nYellow + nRed;
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0]; // HH:MM:SS
        
        const summary = [
            `*${site.name}*`,
            `_Actualizacion: ${timeStr}_`,
            '',
            `Camiones en planta: *${total}*`,
            `OK: ${nGreen}  |  Riesgo: ${nYellow}  |  Excedido: ${nRed}`
        ].join('\n');
        
        return { summary };
        
    } catch (error) {
        console.error('Error consultando TRT:', error.message);
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        return { summary: `*${site.name}*\n_Actualizacion: ${timeStr}_\n\n_Error obteniendo datos_` };
    }
}

// =============================================================================
// SCREENSHOT CON PUPPETEER (reutiliza el de WhatsApp)
// =============================================================================

async function takeScreenshot(siteId) {
    const url = `${CONFIG.trtBaseUrl}/ces/home/registro/${siteId}`;
    const screenshotPath = path.join(CONFIG.tempDir, `screenshot_${siteId}_${Date.now()}.png`);
    
    try {
        // Usar el navegador de puppeteer del cliente WhatsApp
        const browser = await client.pupPage.browser();  // Forma correcta de acceder al navegador
        const page = await browser.newPage();
        
        await page.setViewport({ width: 1920, height: 1080 });
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });
        await page.waitForTimeout(3000);
        await page.screenshot({ path: screenshotPath });
        await page.close();
        
        return screenshotPath;
    } catch (error) {
        console.error('Error screenshot:', error.message);
        return null;
    }
}

// =============================================================================
// SERVIDOR HTTP - API PARA PYTHON
// =============================================================================

const app = express();
app.use(express.json());

// Configurar multer para recibir imagenes
const upload = multer({ dest: CONFIG.tempDir });

// Health check
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        whatsapp: clientReady ? 'connected' : 'disconnected' 
    });
});

// Info del bot (estado de conexion y numero)
app.get('/info', (req, res) => {
    res.json({
        connected: clientReady,
        phone: clientReady && client.info ? client.info.wid.user : null,
        name: clientReady && client.info ? (client.info.pushname || null) : null,
    });
});

// Estado del QR para vinculacion
app.get('/qr', (req, res) => {
    if (waStatus === 'connected') {
        res.json({ status: 'connected', phone: client.info ? client.info.wid.user : null });
    } else if (waStatus === 'waiting_scan' && currentQR) {
        res.json({ status: 'waiting_scan', qr: currentQR });
    } else {
        res.json({ status: waStatus, qr: null });
    }
});

// Lista de grupos del bot
app.get('/groups', async (req, res) => {
    if (!clientReady) {
        return res.json({ success: false, groups: [], error: 'WhatsApp no conectado' });
    }
    try {
        const chats = await client.getChats();
        const groups = chats.filter(c => c.isGroup).map(g => ({
            id: g.id._serialized,
            name: g.name,
            participants: g.participants ? g.participants.length : 0
        }));
        res.json({ success: true, groups });
    } catch (e) {
        res.json({ success: false, groups: [], error: e.message });
    }
});

// Logout: destruye la sesion y reinicia el cliente para pedir nuevo QR
app.post('/logout', async (req, res) => {
    res.json({ success: true, message: 'Cerrando sesion...' });

    // Ejecutar despues de responder para no bloquear
    setTimeout(async () => {
        try {
            clientReady = false;
            waStatus = 'initializing';
            currentQR = null;

            await client.destroy();

            // Eliminar carpeta de sesion guardada
            const sessionPath = path.resolve(__dirname, CONFIG.sessionDir);
            if (fs.existsSync(sessionPath)) {
                fs.rmSync(sessionPath, { recursive: true, force: true });
            }

            console.log('Sesion eliminada. Reiniciando cliente...');

            // Reiniciar cliente despues de un segundo
            setTimeout(() => {
                client.initialize();
            }, 1000);
        } catch (e) {
            console.error('Error en logout:', e.message);
        }
    }, 100);
});

// Enviar mensaje de texto a un grupo
app.post('/send/text', async (req, res) => {
    if (!clientReady) {
        return res.status(503).json({ success: false, error: 'WhatsApp no conectado' });
    }
    
    const { groupId, message } = req.body;
    
    if (!groupId || !message) {
        return res.status(400).json({ success: false, error: 'Falta groupId o message' });
    }
    
    try {
        // Convertir GROUP_ID del config (invitacion) a ID interno si es necesario
        const chatId = await resolveGroupId(groupId);
        
        if (!chatId) {
            return res.status(404).json({ success: false, error: 'Grupo no encontrado' });
        }
        
        await client.sendMessage(chatId, message, { sendSeen: false });
        res.json({ success: true });
        
    } catch (error) {
        console.error('Error enviando texto:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Enviar imagen a un grupo
app.post('/send/image', upload.single('image'), async (req, res) => {
    if (!clientReady) {
        return res.status(503).json({ success: false, error: 'WhatsApp no conectado' });
    }
    
    const { groupId, caption } = req.body;
    const imageFile = req.file;
    
    if (!groupId) {
        return res.status(400).json({ success: false, error: 'Falta groupId' });
    }
    
    if (!imageFile) {
        return res.status(400).json({ success: false, error: 'Falta imagen' });
    }
    
    try {
        const chatId = await resolveGroupId(groupId);
        
        if (!chatId) {
            fs.unlinkSync(imageFile.path);
            return res.status(404).json({ success: false, error: 'Grupo no encontrado' });
        }
        
        const media = MessageMedia.fromFilePath(imageFile.path);
        await client.sendMessage(chatId, media, { caption: caption || '', sendSeen: false });

        // Eliminar archivo temporal
        fs.unlinkSync(imageFile.path);
        
        res.json({ success: true });
        
    } catch (error) {
        console.error('Error enviando imagen:', error.message);
        if (imageFile && fs.existsSync(imageFile.path)) {
            fs.unlinkSync(imageFile.path);
        }
        res.status(500).json({ success: false, error: error.message });
    }
});

// Enviar imagen desde ruta local
app.post('/send/image-path', async (req, res) => {
    if (!clientReady) {
        return res.status(503).json({ success: false, error: 'WhatsApp no conectado' });
    }
    
    const { groupId, imagePath, caption, deleteAfter } = req.body;
    
    if (!groupId || !imagePath) {
        return res.status(400).json({ success: false, error: 'Falta groupId o imagePath' });
    }
    
    if (!fs.existsSync(imagePath)) {
        return res.status(404).json({ success: false, error: 'Imagen no encontrada' });
    }
    
    try {
        const chatId = await resolveGroupId(groupId);
        
        if (!chatId) {
            return res.status(404).json({ success: false, error: 'Grupo no encontrado' });
        }
        
        const media = MessageMedia.fromFilePath(imagePath);
        await client.sendMessage(chatId, media, { caption: caption || '', sendSeen: false });

        // Eliminar archivo si se solicita
        if (deleteAfter) {
            fs.unlinkSync(imagePath);
        }
        
        res.json({ success: true });
        
    } catch (error) {
        console.error('Error enviando imagen:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Cache de grupos para no buscar cada vez
let groupCache = {};
let groupCacheTime = 0;
const CACHE_TTL = 60000; // 1 minuto

async function resolveGroupId(groupIdOrInvite) {
    // Si ya es un ID completo (@g.us), usarlo directamente
    if (groupIdOrInvite.endsWith('@g.us')) {
        return groupIdOrInvite;
    }
    
    // Actualizar cache si es necesario
    const now = Date.now();
    if (now - groupCacheTime > CACHE_TTL) {
        try {
            const chats = await client.getChats();
            groupCache = {};
            for (const chat of chats) {
                if (chat.isGroup) {
                    // Guardar por ID y por codigo de invitacion
                    groupCache[chat.id._serialized] = chat.id._serialized;
                    
                    // Intentar obtener codigo de invitacion
                    try {
                        const inviteCode = await chat.getInviteCode();
                        if (inviteCode) {
                            groupCache[inviteCode] = chat.id._serialized;
                        }
                    } catch (e) {
                        // No todos los grupos permiten obtener codigo
                    }
                }
            }
            groupCacheTime = now;
        } catch (e) {
            console.error('Error actualizando cache de grupos:', e.message);
        }
    }
    
    // Buscar en cache
    if (groupCache[groupIdOrInvite]) {
        return groupCache[groupIdOrInvite];
    }
    
    // Buscar directamente en los chats
    try {
        const chats = await client.getChats();
        for (const chat of chats) {
            if (chat.isGroup) {
                try {
                    const inviteCode = await chat.getInviteCode();
                    if (inviteCode === groupIdOrInvite) {
                        groupCache[groupIdOrInvite] = chat.id._serialized;
                        return chat.id._serialized;
                    }
                } catch (e) {}
            }
        }
    } catch (e) {}
    
    return null;
}

// =============================================================================
// INICIAR SERVICIOS
// =============================================================================

console.log('Iniciando servicios...\n');


// Iniciar servidor HTTP
app.listen(CONFIG.httpPort, () => {
    console.log(`API HTTP en puerto ${CONFIG.httpPort}`);
});

// Iniciar cliente WhatsApp
client.initialize();

// Manejo de cierre
process.on('SIGINT', async () => {
    console.log('\nCerrando sistema...');
    await client.destroy();
    process.exit(0);
});