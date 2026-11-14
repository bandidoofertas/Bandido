export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      await env.DB.prepare(`
        CREATE TABLE IF NOT EXISTS ofertas (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          titulo TEXT,
          precio_oferta TEXT,
          precio_original TEXT,
          descuento TEXT,
          tienda TEXT,
          url_afiliado TEXT UNIQUE,
          score INTEGER,
          es_hot INTEGER,
          categoria_principal TEXT,
          subcategoria TEXT,
          razonamiento TEXT,
          mensaje_redes TEXT,
          metodos_pago TEXT,
          fecha_vencimiento TEXT,
          imagen_url TEXT,
          fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
      `).run();
    } catch (err) {}

    if (url.pathname === "/api/ofertas" && request.method === "GET") {
      try {
        const { results } = await env.DB.prepare(
          "SELECT * FROM ofertas ORDER BY score ASC, id DESC LIMIT 120"
        ).all();

        return new Response(JSON.stringify(results || []), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }
    }

    if (url.pathname === "/api/guardar" && request.method === "POST") {
      try {
        const data = await request.json();
        const authHeader = request.headers.get("Authorization");
        if (authHeader !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), {
            status: 401,
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
          });
        }

        const stmt = env.DB.prepare(`
          INSERT OR IGNORE INTO ofertas (
            titulo, precio_oferta, precio_original, descuento, tienda, 
            url_afiliado, score, es_hot, categoria_principal, subcategoria, 
            razonamiento, mensaje_redes, metodos_pago, fecha_vencimiento, imagen_url
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);

        await stmt.bind(
          data.titulo,
          data.precio_oferta || "Ver en sitio",
          data.precio_original || "",
          data.descuento || "Oferta",
          data.tienda,
          data.url_afiliado,
          data.score,
          data.es_hot ? 1 : 0,
          data.categoria_principal || "H",
          data.subcategoria || "H2",
          data.razonamiento || "",
          data.mensaje_redes || "",
          data.metodos_pago || "",
          data.fecha_vencimiento || null,
          data.imagen_url || ""
        ).run();

        return new Response(JSON.stringify({ success: true, message: "Oferta guardada" }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }
    }

    if (url.pathname === "/api/eliminar" && request.method === "POST") {
      try {
        const data = await request.json();
        const authHeader = request.headers.get("Authorization");
        if (authHeader !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), {
            status: 401,
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
          });
        }

        if (data.url_afiliado) {
          await env.DB.prepare("DELETE FROM ofertas WHERE url_afiliado = ?").bind(data.url_afiliado).run();
        } else if (data.id) {
          await env.DB.prepare("DELETE FROM ofertas WHERE id = ?").bind(data.id).run();
        }

        return new Response(JSON.stringify({ success: true, message: "Oferta eliminada por caducidad" }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }
    }

    return new Response(HTML_CONTENT, {
      headers: {
        "Content-Type": "text/html;charset=UTF-8",
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    });
  },
};

const HTML_CONTENT = [
  '<!DOCTYPE html>',
  '<html lang="es">',
  '<head>',
  '<meta charset="UTF-8">',
  '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
  '<title>Bandido Ofertas 🦝 | Gangas Reales en México</title>',
  '<style>',
  ':root { --bg: #0f172a; --card-bg: #1e293b; --accent: #38bdf8; --primary-blue: #2563eb; --text: #f8fafc; --text-muted: #94a3b8; --badge-discount: #ef4444; --fire-bg: #dc2626; --nivel-2: #ea580c; }',
  'body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 0 20px 100px 20px; }',
  '.promo-bar { position: sticky; top: 0; z-index: 900; background: linear-gradient(90deg, #1e1b4b, #1d4ed8, #0f172a); border-bottom: 1px solid #38bdf8; padding: 10px 15px; margin: 0 -20px 15px -20px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }',
  '.promo-msg { text-align: center; font-size: 0.88rem; color: #e0f2fe; font-weight: 600; margin-bottom: 8px; }',
  '.banks-scroll { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin; max-width: 1200px; margin: 0 auto; }',
  '.banks-scroll::-webkit-scrollbar { height: 4px; }',
  '.banks-scroll::-webkit-scrollbar-thumb { background: #38bdf8; border-radius: 4px; }',
  '.bank-chip { flex: 0 0 auto; background: #0f172a; border: 1px solid #38bdf8; color: #fff; padding: 6px 12px; border-radius: 16px; font-size: 0.8rem; font-weight: bold; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 5px; }',
  '.bank-chip:hover { background: #2563eb; transform: translateY(-1px); }',
  '.bank-options-drawer { max-width: 700px; margin: 8px auto 0 auto; background: #0f172a; border: 1px solid #38bdf8; border-radius: 10px; padding: 10px; display: none; flex-wrap: wrap; gap: 8px; justify-content: center; align-items: center; }',
  '.bank-opt-btn { background: #dc2626; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: bold; cursor: pointer; }',
  '.bank-opt-btn.info-only { background: #334155; cursor: default; }',
  '.cookie-toast { position: fixed; bottom: 20px; right: 20px; z-index: 1000; background: #0284c7; color: #fff; padding: 12px 18px; border-radius: 12px; font-size: 0.88rem; font-weight: bold; box-shadow: 0 8px 20px rgba(0,0,0,0.5); border: 1px solid #7dd3fc; display: none; max-width: 320px; }',
  'header { text-align: center; padding: 10px 0; }',
  'h1 { margin: 0; color: var(--accent); font-size: 2.2rem; }',
  '.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 5px; }',
  '.controls { max-width: 1200px; margin: 15px auto; display: flex; flex-direction: column; gap: 15px; align-items: center; }',
  '.search-bar { width: 100%; max-width: 500px; padding: 12px 18px; border-radius: 25px; border: 1px solid #334155; background: #1e293b; color: #fff; font-size: 1rem; outline: none; }',
  '.search-bar:focus { border-color: var(--accent); }',
  '.categories { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }',
  '.cat-btn { background: #1e293b; border: 1px solid #334155; color: var(--text); padding: 8px 16px; border-radius: 20px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }',
  '.cat-btn:hover, .cat-btn.active { background: var(--primary-blue); color: #fff; font-weight: bold; border-color: var(--primary-blue); }',
  '.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 20px auto; }',
  '.card { background: var(--card-bg); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); }',
  '.product-img-container { width: 100%; height: 170px; background: #ffffff; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 12px; padding: 6px; box-sizing: border-box; }',
  '.product-img { max-width: 100%; max-height: 100%; object-fit: contain; }',
  '.badges-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; font-size: 0.75rem; margin-bottom: 6px; }',
  '.store { background: var(--primary-blue); padding: 3px 8px; border-radius: 4px; font-weight: bold; }',
  '.discount { background: var(--badge-discount); padding: 3px 8px; border-radius: 4px; font-weight: bold; }',
  '.nivel-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block; margin-bottom: 8px; }',
  '.nivel-hot { background: var(--fire-bg); color: white; }',
  '.nivel-buena { background: var(--nivel-2); color: white; }',
  '.title { font-size: 0.95rem; margin: 4px 0 10px 0; color: #fff; line-height: 1.3; }',
  '.bandido-box { background: rgba(37, 99, 235, 0.16); border: 1px solid #38bdf8; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.84rem; color: #e0f2fe; cursor: pointer; transition: background 0.2s; line-height: 1.4; }',
  '.bandido-box:hover { background: rgba(37, 99, 235, 0.28); }',
  '.bandido-divider { display: block; text-align: center; color: #38bdf8; font-weight: bold; font-size: 0.78rem; margin-top: 6px; letter-spacing: 0.5px; }',
  '.prices { margin: 12px 0 8px 0; text-align: center; }',
  '.original-row { margin-bottom: 2px; }',
  '.original { text-decoration: line-through; color: #94a3b8; font-size: 0.95rem; margin-right: 6px; }',
  '.discount-tag { color: #ef4444; font-size: 0.85rem; font-weight: bold; }',
  '.offer { font-size: 1.6rem; font-weight: bold; color: #4ade80; display: block; }',
  '.btn-buy { display: block; text-align: center; background: var(--primary-blue); color: white; text-decoration: none; padding: 10px; border-radius: 8px; font-weight: bold; transition: background 0.2s; margin-top: 10px; }',
  '.btn-buy:hover { background: #1d4ed8; }',
  '</style>',
  '</head>',
  '<body>',
  '<div class="promo-bar">',
  '<div class="promo-msg" id="promoDynamicMsg">💳 ¿Pagas con tarjeta participante? Toca tu banco para copiar cupón extra y bajar aún más el precio 🦝✨</div>',
  '<div class="banks-scroll" id="banksContainer"></div>',
  '<div class="bank-options-drawer" id="bankDrawer"></div>',
  '</div>',
  '<div class="cookie-toast" id="cookieToast"></div>',
  '<header>',
  '<h1>🦝 Bandido Ofertas</h1>',
  '<p class="subtitle">El arte de cazar los mejores descuentos en México</p>',
  '</header>',
  '<div class="controls">',
  '<input type="text" id="searchInput" class="search-bar" placeholder="🔍 Buscar oferta (ej. Audífonos, Nintendo, Laptop)...">',
  '<div class="categories" id="categoryMenu">',
  '<button class="cat-btn active" onclick="filtrarCategoria(\'todas\', this)">Todas</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'hot\', this)" style="background: #dc2626; color: white;">🔥 Hot (Score 1-2)</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'a\', this)">🎧 Audio</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'b\', this)">🎮 Videojuegos</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'c\', this)">🏠 Hogar</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'d\', this)">📱 Celulares</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'e\', this)">💻 Computación</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'f\', this)">⚽ Deportes</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'g\', this)">🛠️ Herramientas</button>',
  '<button class="cat-btn" onclick="filtrarCategoria(\'h\', this)">✨ General</button>',
  '</div>',
  '</div>',
  '<main class="grid" id="container"><p style="text-align:center; grid-column: 1/-1;">Cargando ofertas en tiempo real...</p></main>',
  '<script>',
  'const PROMOS_BANCOS = [',
  '  { banco: "Banamex", opciones: [{ code: "BNMXBF", desc: "10% cupón a 3, 6 y 9 MSI" }, { code: "", desc: "Hasta 30% bonif. desde 12 MSI" }] },',
  '  { banco: "BBVA", opciones: [{ code: "BBVABF", desc: "10% cupón a 3, 6 y 9 MSI" }, { code: "", desc: "15% bonif. desde 12 MSI" }] },',
  '  { banco: "Mercado Pago", opciones: [{ code: "TCMPBF", desc: "15% o 24 MSI T. Crédito" }, { code: "CREDITOBF", desc: "10% Mercado Crédito" }, { code: "CREDITO40", desc: "40% 1ra compra" }] },',
  '  { banco: "Santander", opciones: [{ code: "SANTBF", desc: "15% cupón 1 exhibición" }, { code: "", desc: "10% cashback desde 6 MSI" }] },',
  '  { banco: "Banorte", opciones: [{ code: "BNRTBF", desc: "10% cupón 1 exhibición" }, { code: "", desc: "+10% bonif. o Puntos Triples" }] },',
  '  { banco: "HSBC", opciones: [{ code: "HSBCBF", desc: "+10% cupón 1 exh. o 3-6 MSI" }, { code: "", desc: "Hasta 30% dev. desde 6 MSI" }] },',
  '  { banco: "OXXO", opciones: [{ code: "OXXOBF", desc: "10% cupón pagando en efectivo" }] },',
  '  { banco: "Amex", opciones: [{ code: "AMEXBF", desc: "+10% cupón 1 exh. o 3 MSI" }, { code: "", desc: "$1,500 bonif. en MSI" }] },',
  '  { banco: "Scotiabank", opciones: [{ code: "SCBABF", desc: "+15% cupón 1 exhibición" }, { code: "", desc: "Hasta 25% cashback" }] },',
  '  { banco: "Afirme", opciones: [{ code: "AFRMBF", desc: "20% cupón 1 exh. o 3-12 MSI" }] },',
  '  { banco: "Invex", opciones: [{ code: "INVEBF", desc: "10% cupón 3, 6, 9 y 12 MSI" }] },',
  '  { banco: "Openbank", opciones: [{ code: "OPBABF", desc: "+10% cupón 1 exhibición" }, { code: "", desc: "15% cashback al diferir" }] },',
  '  { banco: "Mifel", opciones: [{ code: "MIFEBF", desc: "15% cupón 1 exhibición" }, { code: "", desc: "Hasta $6,000 bonif. 12 MSI" }] },',
  '  { banco: "Nu", opciones: [{ code: "", desc: "Hasta $100k bonif. a 6+ MSI (directo)" }] },',
  '  { banco: "Klar", opciones: [{ code: "", desc: "10% cashback desde 6 MSI (directo)" }] },',
  '  { banco: "DiDi Card", opciones: [{ code: "", desc: "Hasta 20% cashback T. Crédito (directo)" }] },',
  '  { banco: "BanCoppel", opciones: [{ code: "", desc: "Hasta 20% bonificación (directo)" }] },',
  '  { banco: "Falabella", opciones: [{ code: "", desc: "15% cashback a MSI (directo)" }] }',
  '];',
  'function mostrarAvisoCookie(texto) {',
  '  document.cookie = "bandido_promo=" + encodeURIComponent(texto) + "; max-age=86400; path=/";',
  '  const toast = document.getElementById("cookieToast");',
  '  toast.textContent = texto;',
  '  toast.style.display = "block";',
  '  document.getElementById("promoDynamicMsg").textContent = texto;',
  '  clearTimeout(window._toastTimer);',
  '  window._toastTimer = setTimeout(() => { toast.style.display = "none"; }, 5000);',
  '}',
  'function copiarCupon(banco, code, desc) {',
  '  if (code) {',
  '    navigator.clipboard.writeText(code).catch(() => {});',
  '    mostrarAvisoCookie("🦝 ¡Cupón " + code + " (" + banco + ") copiado al portapapeles! " + desc);',
  '  } else {',
  '    mostrarAvisoCookie("💳 " + banco + ": " + desc + " (No requiere código)");',
  '  }',
  '}',
  'function initBancos() {',
  '  const cont = document.getElementById("banksContainer");',
  '  const drawer = document.getElementById("bankDrawer");',
  '  PROMOS_BANCOS.forEach(item => {',
  '    const btn = document.createElement("button");',
  '    btn.className = "bank-chip";',
  '    btn.textContent = "💳 " + item.banco;',
  '    btn.onclick = () => {',
  '      if (item.opciones.length === 1) {',
  '        drawer.style.display = "none";',
  '        copiarCupon(item.banco, item.opciones[0].code, item.opciones[0].desc);',
  '      } else {',
  '        drawer.innerHTML = "<span style=\\"font-size:0.8rem;color:#38bdf8;font-weight:bold;\\">" + item.banco + ":</span>";',
  '        item.opciones.forEach(op => {',
  '          const ob = document.createElement("button");',
  '          ob.className = op.code ? "bank-opt-btn" : "bank-opt-btn info-only";',
  '          ob.textContent = op.code ? ("Copiar " + op.code + " (" + op.desc + ")") : op.desc;',
  '          ob.onclick = () => copiarCupon(item.banco, op.code, op.desc);',
  '          drawer.appendChild(ob);',
  '        });',
  '        drawer.style.display = "flex";',
  '      }',
  '    };',
  '    cont.appendChild(btn);',
  '  });',
  '}',
  'let ofertasGlobales = [];',
  'let categoriaActual = "todas";',
  'function intercalarDiscreto(lista) {',
  '  const porScore = { 1: [], 2: [], 3: [], 4: [], 5: [] };',
  '  lista.forEach(o => {',
  '    const s = (o.score >= 1 && o.score <= 5) ? o.score : 3;',
  '    porScore[s].push(o);',
  '  });',
  '  const resultado = [];',
  '  const patron = ["M", "M", "M", "M", "A", "A", "M", "A", "M", "M", "A", "A"];',
  '  [1, 2, 3, 4, 5].forEach(s => {',
  '    const meli = [];',
  '    const amz = [];',
  '    porScore[s].forEach(item => {',
  '      const t = (item.tienda || "").toLowerCase();',
  '      if (t.includes("amazon")) amz.push(item); else meli.push(item);',
  '    });',
  '    let idx = Math.floor(Math.random() * patron.length);',
  '    while (meli.length > 0 || amz.length > 0) {',
  '      const turno = patron[idx % patron.length];',
  '      idx++;',
  '      if (turno === "M" && meli.length > 0) resultado.push(meli.shift());',
  '      else if (turno === "A" && amz.length > 0) resultado.push(amz.shift());',
  '      else if (meli.length > 0) resultado.push(meli.shift());',
  '      else if (amz.length > 0) resultado.push(amz.shift());',
  '    }',
  '  });',
  '  return resultado;',
  '}',
  'async function load() {',
  '  try {',
  '    const r = await fetch("/api/ofertas");',
  '    const raw = await r.json();',
  '    ofertasGlobales = intercalarDiscreto(raw);',
  '    render();',
  '  } catch(e) {',
  '    document.getElementById("container").innerHTML = "<p style=\\"text-align:center; grid-column: 1/-1; color: #ef4444;\\">Error al conectar con la base de datos.</p>";',
  '  }',
  '}',
  'function limpiarPrecio(texto) {',
  '  if (!texto) return 0;',
  '  let limpio = texto.replace(/\\$/g, "").replace(/,/g, "").trim();',
  '  let match = limpio.match(/[0-9.]+/);',
  '  return match ? parseFloat(match[0]) : 0;',
  '}',
  'function formatearMoneda(num) {',
  '  return "$" + num.toLocaleString("es-MX", { minimumFractionDigits: 0, maximumFractionDigits: 0 });',
  '}',
  'function toggleCardTexto(el) {',
  '  const shortEl = el.querySelector(".txt-short");',
  '  const fullEl = el.querySelector(".txt-full");',
  '  const divEl = el.querySelector(".bandido-divider");',
  '  if (fullEl.style.display === "none") {',
  '    shortEl.style.display = "none";',
  '    fullEl.style.display = "inline";',
  '    divEl.textContent = "____ cerrar tarjeta ____";',
  '  } else {',
  '    shortEl.style.display = "inline";',
  '    fullEl.style.display = "none";',
  '    divEl.textContent = "____ abrir tarjeta completa ____";',
  '  }',
  '}',
  'function render() {',
  '  const container = document.getElementById("container");',
  '  const busqueda = document.getElementById("searchInput").value.toLowerCase();',
  '  container.innerHTML = "";',
  '  const filtradas = ofertasGlobales.filter(o => {',
  '    const subCat = (o.subcategoria || "").toLowerCase().trim();',
  '    let coincideCategoria = false;',
  '    if (categoriaActual === "todas") {',
  '      coincideCategoria = true;',
  '    } else if (categoriaActual === "hot") {',
  '      coincideCategoria = (o.score == 1 || o.score == 2);',
  '    } else {',
  '      coincideCategoria = (subCat === categoriaActual || subCat.startsWith(categoriaActual));',
  '    }',
  '    const coincideBusqueda = (o.titulo && o.titulo.toLowerCase().includes(busqueda)) || (o.tienda && o.tienda.toLowerCase().includes(busqueda));',
  '    return coincideCategoria && coincideBusqueda;',
  '  });',
  '  if (!filtradas || filtradas.length === 0) {',
  '    container.innerHTML = "<p style=\\"text-align:center; grid-column: 1/-1;\\">No se encontraron ofertas activas en esta categoría. 🦝</p>";',
  '    return;',
  '  }',
  '  filtradas.forEach(o => {',
  '    const esHot = o.score == 1 || o.score == 2;',
  '    const nivelClase = esHot ? "nivel-hot" : "nivel-buena";',
  '    const nivelTexto = esHot ? "🔥 Gangas Fuego Total (HOT)" : "⭐ Oferta Sólida";',
  '    let numOferta = limpiarPrecio(o.precio_oferta);',
  '    let numOrig = limpiarPrecio(o.precio_original);',
  '    if (numOrig <= numOferta && o.descuento && o.descuento.includes("%")) {',
  '      const matchPct = o.descuento.match(/([0-9]+)\\s*%/);',
  '      if (matchPct && numOferta > 0) {',
  '        const pct = parseFloat(matchPct[1]);',
  '        if (pct > 0 && pct < 99) numOrig = Math.round(numOferta / (1 - (pct / 100)));',
  '      }',
  '    }',
  '    let preciosHtml = "";',
  '    if (numOrig > numOferta && numOferta > 0) {',
  '      let ahorroPorc = Math.round(((numOrig - numOferta) / numOrig) * 100);',
  '      preciosHtml = "<div class=\\"original-row\\"><span class=\\"original\\">" + formatearMoneda(numOrig) + "</span><span class=\\"discount-tag\\">-" + ahorroPorc + "%</span></div><span class=\\"offer\\">" + formatearMoneda(numOferta) + "</span>";',
  '    } else {',
  '      preciosHtml = "<span class=\\"offer\\">" + (numOferta > 0 ? formatearMoneda(numOferta) : o.precio_oferta) + "</span>";',
  '    }',
  '    const textoCompleto = (o.razonamiento || "Oye lindura... mira este precio que te cacé antes de que vuele. Prometo no morder... a menos que tú quieras 🦝🔥").replace(/"/g, "&quot;");',
  '    const corte = Math.min(62, Math.floor(textoCompleto.length * 0.55));',
  '    const textoCorto = textoCompleto.length > 65 ? textoCompleto.slice(0, corte) + "..." : textoCompleto;',
  '    const boxHtml = "<div class=\\"bandido-box\\" onclick=\\"toggleCardTexto(this)\\"><span class=\\"txt-short\\">🦝 " + textoCorto + "</span><span class=\\"txt-full\\" style=\\"display:none;\\">🦝 " + textoCompleto + "</span><span class=\\"bandido-divider\\">____ abrir tarjeta completa ____</span></div>";',
  '    let imagenHtml = o.imagen_url ? "<div class=\\"product-img-container\\"><img src=\\"" + o.imagen_url + "\\" class=\\"product-img\\" alt=\\"Producto\\" loading=\\"lazy\\"></div>" : "";',
  '    container.innerHTML += "<div class=\\"card\\"><div>" + imagenHtml + "<div class=\\"badges-row\\"><span class=\\"store\\">" + o.tienda + "</span><span class=\\"discount\\">" + (o.descuento || "Oferta") + "</span></div><span class=\\"nivel-badge " + nivelClase + "\\">" + nivelTexto + "</span><h3 class=\\"title\\">" + o.titulo + "</h3>" + boxHtml + "</div><div><div class=\\"prices\\">" + preciosHtml + "</div><a href=\\"" + o.url_afiliado + "\\" target=\\"_blank\\" rel=\\"noopener\\" class=\\"btn-buy\\">Ver la oferta 🚀</a></div></div>";',
  '  });',
  '}',
  'function filtrarCategoria(cat, btn) {',
  '  categoriaActual = cat;',
  '  document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));',
  '  btn.classList.add("active");',
  '  render();',
  '}',
  'document.getElementById("searchInput").addEventListener("input", render);',
  'initBancos();',
  'load();',
  '</script>',
  '</body>',
  '</html>'
].join('\n');