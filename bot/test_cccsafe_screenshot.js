/**
 * test_cccsafe_screenshot.js
 *
 * Script de prueba para verificar que el screenshot de CCCSafe funciona.
 * Ejecutar desde la carpeta bot/:
 *   node test_cccsafe_screenshot.js
 *
 * Guarda el screenshot en bot/temp/test_cccsafe.png
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// ── Leer credenciales desde config.txt ──────────────────────────────────────

function loadConfig(configPath = '../config.txt') {
    const result = { apiEmail: '', apiPassword: '', sites: [] };
    let currentSite = {};

    try {
        const fullPath = path.resolve(__dirname, configPath);
        const lines = fs.readFileSync(fullPath, 'utf-8').split('\n');

        for (let line of lines) {
            line = line.trim();
            if (!line || line.startsWith('#')) {
                if (currentSite.name) {
                    result.sites.push(currentSite);
                    currentSite = {};
                }
                continue;
            }
            if (line.includes('=')) {
                const [key, ...rest] = line.split('=');
                const value = rest.join('=').trim();
                const k = key.trim();
                if (k === 'API_EMAIL')       result.apiEmail = value;
                else if (k === 'API_PASSWORD')    result.apiPassword = value;
                else if (k === 'SITE_NAME')       currentSite.name = value;
                else if (k === 'CD_CODE')         currentSite.cd = value;
                else if (k === 'CENTRO_ID')       currentSite.centroId = parseInt(value);
                else if (k === 'CENTRO_NOMBRE')   currentSite.centroNombre = value;
            }
        }
        if (currentSite.name) result.sites.push(currentSite);
    } catch (e) {
        console.error('Error leyendo config.txt:', e.message);
    }

    return result;
}

// ── Lógica del screenshot (misma que bot_whatsapp.js) ───────────────────────

async function takeCCCSafeScreenshot(page, site, apiEmail, apiPassword) {
    const TRUCKS_URL = 'https://www.cccsafe.cl/camiones-planta';
    const centroCodigo = site.centroNombre || 'STGOSUR';

    console.log(`\n[1] Navegando a ${TRUCKS_URL} ...`);
    await page.goto(TRUCKS_URL, { waitUntil: 'networkidle2', timeout: 25000 });
    console.log(`    URL actual: ${page.url()}`);

    // Login si redirigió
    const urlAfter = page.url();
    if (urlAfter.includes('login') || urlAfter.includes('auth') || urlAfter.includes('signin')) {
        console.log('\n[2] Detectado login — autenticando...');

        // Esperar un poco a que cargue el JS del form
        await new Promise(r => setTimeout(r, 2000));

        // Captura de la pantalla de login para debugging
        await page.screenshot({ path: path.resolve(__dirname, 'temp/test_login_page.png') });
        console.log('    Screenshot de login guardado en temp/test_login_page.png');

        // Inspeccionar TODOS los inputs antes de intentar interactuar
        const loginInputs = await page.$$eval('input, button', els => els.map(el => ({
            tag: el.tagName,
            type: el.getAttribute('type') || '',
            name: el.getAttribute('name') || '',
            id: el.getAttribute('id') || '',
            placeholder: el.getAttribute('placeholder') || '',
            class: (el.className || '').substring(0, 80),
        })));
        console.log(`\n    Elementos en la página de login (${loginInputs.length}):`);
        loginInputs.forEach((el, i) => console.log(`      [${i}] <${el.tag.toLowerCase()}> type="${el.type}" name="${el.name}" id="${el.id}" placeholder="${el.placeholder}"`));

        // Intentar encontrar el campo de email con múltiples selectores
        const emailSelectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id*="email" i]',
            'input[placeholder*="email" i]',
            'input[placeholder*="correo" i]',
            'input[placeholder*="usuario" i]',
            'input:first-of-type',
        ];
        let emailInput = null;
        for (const sel of emailSelectors) {
            emailInput = await page.$(sel);
            if (emailInput) { console.log(`\n    Campo email encontrado con selector: ${sel}`); break; }
        }
        if (!emailInput) throw new Error('No se encontró campo de email/usuario en el login');

        const passSelectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[id*="pass" i]',
            'input[placeholder*="contraseña" i]',
            'input[placeholder*="password" i]',
        ];
        let passInput = null;
        for (const sel of passSelectors) {
            passInput = await page.$(sel);
            if (passInput) { console.log(`    Campo password encontrado con selector: ${sel}`); break; }
        }
        if (!passInput) throw new Error('No se encontró campo de password en el login');

        await emailInput.click({ clickCount: 3 });
        await emailInput.type(apiEmail);
        await passInput.click({ clickCount: 3 });
        await passInput.type(apiPassword);

        await page.screenshot({ path: path.resolve(__dirname, 'temp/test_login_filled.png') });
        console.log('    Screenshot con form relleno guardado en temp/test_login_filled.png');

        // Buscar botón de submit
        const submitSelectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:not([type="button"])',
        ];
        let submitBtn = null;
        for (const sel of submitSelectors) {
            submitBtn = await page.$(sel);
            if (submitBtn) { console.log(`    Botón submit encontrado con selector: ${sel}`); break; }
        }
        if (!submitBtn) throw new Error('No se encontró botón de submit en el login');

        await submitBtn.click();
        console.log('    Formulario enviado, esperando navegación...');
        await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 });
        console.log(`    URL después del login: ${page.url()}`);
    } else {
        console.log('[2] Ya autenticado (sesión previa o no requiere login)');
    }

    // Siempre navegar a camiones-planta (el login redirige a /acarreo)
    if (!page.url().includes('camiones-planta')) {
        console.log(`\n[3] Navegando a ${TRUCKS_URL} ...`);
        await page.goto(TRUCKS_URL, { waitUntil: 'networkidle2', timeout: 20000 });
        console.log(`    URL actual: ${page.url()}`);
    }

    await new Promise(r => setTimeout(r, 2000));

    // Screenshot antes de seleccionar para ver el estado inicial
    await page.screenshot({ path: path.resolve(__dirname, 'temp/test_before_select.png') });
    console.log('\n[4] Screenshot pre-selección guardado en temp/test_before_select.png');

    // Mostrar todos los inputs, selects y elementos con role=combobox/listbox
    const inputs = await page.$$eval(
        'input:not([type="hidden"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"]), select, [role="combobox"], [role="listbox"]',
        els => els.map(el => ({
            tag: el.tagName,
            type: el.getAttribute('type') || '',
            placeholder: el.getAttribute('placeholder') || '',
            name: el.getAttribute('name') || '',
            id: el.getAttribute('id') || '',
            role: el.getAttribute('role') || '',
            ariaLabel: el.getAttribute('aria-label') || '',
            class: (el.className || '').substring(0, 80),
        }))
    );
    console.log(`\n    Inputs/selects/comboboxes encontrados (${inputs.length}):`);
    inputs.forEach((el, i) => console.log(`      [${i}] <${el.tag.toLowerCase()}> type="${el.type}" role="${el.role}" placeholder="${el.placeholder}" aria-label="${el.ariaLabel}" id="${el.id}" class="${el.class}"`));

    // ── Selección MUI Autocomplete: segundo combobox ──
    console.log(`\n[5] Seleccionando "${centroCodigo}" en el segundo combobox...`);
    let selected = false;
    try {
        const comboboxes = await page.$$('input[role="combobox"]');
        console.log(`    Comboboxes encontrados: ${comboboxes.length}`);
        if (comboboxes.length === 0) throw new Error('No se encontraron comboboxes');

        // El segundo combobox es el de "interior planta"
        const targetIndex = comboboxes.length >= 2 ? 1 : 0;
        console.log(`    Usando combobox índice ${targetIndex}`);

        await comboboxes[targetIndex].click({ clickCount: 3 });
        await comboboxes[targetIndex].type(centroCodigo);
        await new Promise(r => setTimeout(r, 1500));

        await page.screenshot({ path: path.resolve(__dirname, 'temp/test_after_type.png') });
        console.log('    Screenshot tras escribir guardado en temp/test_after_type.png');

        // Mostrar opciones del listbox visible
        const opciones = await page.evaluate(() => {
            return Array.from(document.querySelectorAll('[role="option"]'))
                .map(el => el.textContent.trim());
        });
        console.log(`    Opciones del dropdown (${opciones.length}): ${JSON.stringify(opciones)}`);

        // Hacer click en la opción que contiene el texto buscado
        selected = await page.evaluate((texto) => {
            const opts = document.querySelectorAll('[role="option"]');
            for (const opt of opts) {
                if (opt.textContent.trim().toUpperCase().includes(texto.toUpperCase())) {
                    opt.click();
                    return true;
                }
            }
            return false;
        }, centroCodigo);

        console.log(`    Opción seleccionada: ${selected}`);
    } catch (e) {
        console.log('    Error en selección:', e.message);
    }

    if (!selected) {
        console.log('\n    AVISO: No se pudo seleccionar el sitio automáticamente.');
        console.log('    Revisa temp/test_after_type.png para ver el estado del dropdown.');
    }

    // Esperar carga final y tomar screenshot definitivo
    await new Promise(r => setTimeout(r, 3000));
    const outPath = path.resolve(__dirname, 'temp/test_cccsafe.png');
    await page.screenshot({ path: outPath });
    console.log(`\n[6] Screenshot final guardado en: ${outPath}`);
    return outPath;
}

// ── Main ────────────────────────────────────────────────────────────────────

(async () => {
    const config = loadConfig();
    console.log('='.repeat(50));
    console.log('TEST - Screenshot CCCSafe');
    console.log('='.repeat(50));
    console.log(`Email: ${config.apiEmail}`);
    console.log(`Password: ${'*'.repeat(config.apiPassword.length)}`);

    const cccsafeSite = config.sites.find(s => s.centroId);
    if (!cccsafeSite) {
        console.error('No se encontró ningún sitio con CENTRO_ID en config.txt');
        process.exit(1);
    }
    console.log(`Sitio: ${cccsafeSite.name} (cd=${cccsafeSite.cd}, centroId=${cccsafeSite.centroId})`);

    // Crear carpeta temp si no existe
    const tempDir = path.resolve(__dirname, 'temp');
    if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);

    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        await takeCCCSafeScreenshot(page, cccsafeSite, config.apiEmail, config.apiPassword);

        console.log('\nTest completado. Revisa los archivos en bot/temp/:');
        console.log('  test_cccsafe.png       → Screenshot final');
        console.log('  test_before_select.png → Página antes de seleccionar sitio');
        console.log('  test_after_type.png    → Después de escribir en el campo (si aplica)');
        console.log('  test_login_page.png    → Pantalla de login (si aplica)');
    } finally {
        await browser.close();
    }
})();
