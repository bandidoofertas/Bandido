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
        const incluirVencidas = url.searchParams.get("incluir_vencidas") === "1";
        const query = incluirVencidas
          ? "SELECT * FROM ofertas ORDER BY score ASC, id DESC LIMIT 150"
          : "SELECT * FROM ofertas WHERE fecha_vencimiento IS NULL OR datetime(fecha_vencimiento) > datetime('now') ORDER BY score ASC, id DESC LIMIT 120";

        const { results } = await env.DB.prepare(query).all();

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

    if (url.pathname === "/api/renovar" && request.method === "POST") {
      try {
        const data = await request.json();
        const authHeader = request.headers.get("Authorization");
        if (authHeader !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), {
            status: 401,
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
          });
        }

        if (data.url_afiliado && data.fecha_vencimiento) {
          await env.DB.prepare("UPDATE ofertas SET fecha_vencimiento = ? WHERE url_afiliado = ?")
            .bind(data.fecha_vencimiento, data.url_afiliado)
            .run();
        }

        return new Response(JSON.stringify({ success: true, message: "Vigencia renovada" }), {
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

        return new Response(JSON.stringify({ success: true, message: "Oferta eliminada" }), {
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
  'body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; padding-bottom: 100px; }',
  'header { text-align: center; padding: 15px 0 10px 0; }',
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
  '.product-img-container { width: 100%; height: 170px; background: #ffffff; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 12px; padding: 6px; box-sizing: border-box; position: relative; }',
  '.product-img { max-width: 100%; max-height: 100%; object-fit: contain; }',
  '/* Reloj de caducidad en tarjeta */',
  '.timer-bar { display: flex; align-items: center; justify-content: space-between; background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 6px; padding: 5px 9px; margin-bottom: 8px; font-size: 0.76rem; font-variant-numeric: tabular-nums; }',
  '.timer-bar.urgent { border-color: #f59e0b; background: rgba(120, 53, 15, 0.35); color: #fde68a; }',
  '.timer-bar.critical { border-color: #ef4444; background: rgba(127, 29, 29, 0.45); color: #fecaca; animation: pulseBorder 1.8s infinite; }',
  '@keyframes pulseBorder { 0%, 100% { border-color: #ef4444; } 50% { border-color: #fca5a5; } }',
  '.timer-label { color: #94a3b8; font-weight: 600; }',
  '.timer-clock { font-weight: 800; color: #38bdf8; letter-spacing: 0.4px; }',
  '.timer-bar.urgent .timer-clock { color: #fbbf24; }',
  '.timer-bar.critical .timer-clock { color: #f87171; }',
  '.badges-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; font-size: 0.75rem; margin-bottom: 6px; }',
  '.store { background: var(--primary-blue); padding: 3px 8px; border-radius: 4px; font-weight: bold; }',
  '.discount { background: var(--badge-discount); padding: 3px 8px; border-radius: 4px; font-weight: bold; }',
  '.nivel-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block; margin-bottom: 8px; }',
  '.nivel-hot { background: var(--fire-bg); color: white; }',
  '.nivel-buena { background: var(--nivel-2); color: white; }',
  '.title { font-size: 0.95rem; margin: 4px 0 10px 0; color: #fff; line-height: 1.3; }',
  '.bandido-box { background: rgba(37, 99, 235, 0.16); border: 1px solid #38bdf8; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 0.85rem; color: #e0f2fe; cursor: pointer; transition: background 0.2s; line-height: 1.4; }',
  '.bandido-box:hover { background: rgba(37, 99, 235, 0.28); }',
  '.bandido-divider { display: block; text-align: center; color: #38bdf8; font-weight: bold; font-size: 0.78rem; margin-top: 6px; letter-spacing: 0.5px; }',
  '.prices { margin: 12px 0 8px 0; text-align: center; }',
  '.original-row { margin-bottom: 2px; }',
  '.original { text-decoration: line-through; color: #94a3b8; font-size: 0.95rem; margin-right: 6px; }',
  '.discount-tag { color: #ef4444; font-size: 0.85rem; font-weight: bold; }',
  '.offer { font-size: 1.6rem; font-weight: bold; color: #4ade80; display: block; }',
  '.btn-buy { display: block; text-align: center; background: var(--primary-blue); color: white; text-decoration: none; padding: 10px; border-radius: 8px; font-weight: bold; transition: background 0.2s; margin-top: 10px; }',
  '.btn-buy:hover { background: #1d4ed8; }',
  '/* Botón Flotante Izquierdo (Menú Bancos + Logo Buen Fin) */',
  '.float-menu-btn { position: fixed; bottom: 20px; left: 20px; z-index: 950; background: #0f172a; border: 1px solid #94a3b8; color: #f8fafc; padding: 10px 16px; border-radius: 4px; font-size: 0.82rem; font-weight: 700; letter-spacing: 1.5px; cursor: pointer; display: flex; align-items: center; gap: 10px; box-shadow: 0 6px 18px rgba(0,0,0,0.5); transition: all 0.2s; }',
  '.float-menu-btn:hover { border-color: #ef4444; background: #1e293b; }',
  '.bf-badge { background: linear-gradient(135deg, #dc2626, #b91c1c); color: #fef08a; padding: 3px 7px; border-radius: 3px; font-size: 0.68rem; font-weight: 900; letter-spacing: 0.5px; border: 1px solid #facc15; }',
  '.promo-panel { position: fixed; bottom: 72px; left: 20px; z-index: 940; width: 340px; max-width: calc(100vw - 40px); background: #0f172a; border: 1px solid #38bdf8; border-radius: 12px; padding: 14px; box-shadow: 0 12px 30px rgba(0,0,0,0.7); display: none; flex-direction: column; gap: 10px; }',
  '.promo-panel-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 8px; }',
  '.promo-panel-title { font-size: 0.85rem; font-weight: bold; color: #facc15; }',
  '.promo-close { background: none; border: none; color: #94a3b8; font-size: 1.1rem; cursor: pointer; }',
  '.promo-tip { font-size: 0.78rem; color: #cbd5e1; line-height: 1.3; }',
  '.banks-scroll { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px; scrollbar-width: thin; }',
  '.banks-scroll::-webkit-scrollbar { height: 4px; }',
  '.banks-scroll::-webkit-scrollbar-thumb { background: #38bdf8; border-radius: 4px; }',
  '.bank-chip { flex: 0 0 auto; background: #1e293b; border: 1px solid #38bdf8; color: #fff; padding: 6px 11px; border-radius: 16px; font-size: 0.78rem; font-weight: bold; cursor: pointer; }',
  '.bank-chip:hover { background: #2563eb; }',
  '.bank-options-drawer { background: #1e293b; border-radius: 8px; padding: 8px; display: none; flex-direction: column; gap: 6px; }',
  '.bank-opt-btn { background: #dc2626; color: white; border: none; padding: 7px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: bold; cursor: pointer; text-align: left; }',
  '.bank-opt-btn.info-only { background: #334155; cursor: default; }',
  '/* Botón Flotante Derecho (WhatsApp Discreto) */',
  '.wa-float-btn { position: fixed; bottom: 20px; right: 20px; z-index: 950; background: #1e293b; border: 1px solid #22c55e; color: #f8fafc; width: 46px; height: 46px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 6px 18px rgba(0,0,0,0.5); transition: transform 0.2s; }',
  '.wa-float-btn:hover { transform: scale(1.07); background: #14532d; }',
  '.wa-popup { position: fixed; bottom: 76px; right: 20px; z-index: 945; width: 280px; background: #0f172a; border: 1px solid #22c55e; border-radius: 12px; padding: 14px; box-shadow: 0 12px 28px rgba(0,0,0,0.7); display: none; flex-direction: column; gap: 10px; }',
  '.wa-popup-text { font-size: 0.85rem; color: #e2e8f0; line-height: 1.4; margin: 0; }',
  '.wa-go-btn { display: block; text-align: center; background: #22c55e; color: #052e16; font-weight: 800; text-decoration: none; padding: 9px 12px; border-radius: 8px; font-size: 0.85rem; }',
  '.wa-go-btn:hover { background: #16a34a; color: #fff; }',
  '.cookie-toast { position: fixed; top: 18px; left: 50%; transform: translateX(-50%); z-index: 1000; background: #0284c7; color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 0.84rem; font-weight: bold; box-shadow: 0 8px 20px rgba(0,0,0,0.5); border: 1px solid #7dd3fc; display: none; max-width: 90vw; text-align: center; }',
  '</style>',
  '</head>',
  '<body>',
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
  '<button class="cat-btn" onclick="filtrarCategoria(\'por_caducar\', this)" style="border-color: #f59e0b; color: #fde68a;">⏳ Por caducar (&lt;6h)</button>',
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
  '<!-- Botón flotante izquierdo: Menú Bancos con logo Buen Fin -->',
  '<button class="float-menu-btn" onclick="togglePromoPanel()">',
  '<span class="bf-badge">EL BUEN FIN</span>',
  '<span>CUPONES &rarr;</span>',
  '</button>',
  '<div class="promo-panel" id="promoPanel">',
  '<div class="promo-panel-header">',
  '<span class="promo-panel-title">💳 Bonificaciones y Cupones Bancarios</span>',
  '<button class="promo-close" onclick="togglePromoPanel()">&times;</button>',
  '</div>',
  '<div class="promo-tip" id="promoDynamicMsg">Si pagas con tarjeta participante hay descuento extra. Desliza y toca tu banco para copiar el cupón:</div>',
  '<div class="banks-scroll" id="banksContainer"></div>',
  '<div class="bank-options-drawer" id="bankDrawer"></div>',
  '</div>',
  '<!-- Botón flotante derecho: WhatsApp discreto -->',
  '<button class="wa-float-btn" onclick="toggleWaPopup()" title="Chat con Bandido">',
  '<svg width="24" height="24" viewBox="0 0 24 24" fill="#22c55e"><path d="M12.031 6.172c-3.181 0-5.767 2.586-5.768 5.766-.001 1.298.38 2.27 1.019 3.287l-.582 2.128 2.182-.573c.978.58 1.911.928 3.145.929 3.178 0 5.767-2.587 5.768-5.766.001-3.187-2.575-5.77-5.764-5.771zm3.392 8.244c-.144.405-.837.774-1.17.824-.299.045-.677.063-1.092-.069-.252-.08-.575-.187-.988-.365-1.739-.751-2.874-2.502-2.961-2.617-.087-.116-.708-.94-.708-1.793s.448-1.273.607-1.446c.159-.173.346-.217.462-.217l.332.006c.106.005.249-.04.39.298.144.347.491 1.2.534 1.287.043.087.072.188.014.304-.058.116-.087.188-.173.289l-.26.304c-.087.086-.177.18-.076.354.101.174.449.741.964 1.201.662.591 1.221.774 1.394.86s.274.072.376-.043c.101-.116.433-.506.549-.68.116-.173.231-.145.39-.087s1.011.477 1.184.564.289.13.332.202c.045.072.045.419-.1.824z"/></svg>',
  '</button>',
  '<div class="wa-popup" id="waPopup">',
  '<p class="wa-popup-text">🦝 ¿Quieres hablar con Bandido para recibir ofertas por WhatsApp directamente?</p>',
  '<a class="wa-go-btn" href="https://wa.me/522201675141?text=Hola%20Bandido" target="_blank" rel="noopener">Hablar por WhatsApp 💬</a>',
  '</div>',
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
  'function togglePromoPanel() {',
  '  const p = document.getElementById("promoPanel");',
  '  p.style.display = (p.style.display === "flex") ? "none" : "flex";',
  '}',
  'function toggleWaPopup() {',
  '  const w = document.getElementById("waPopup");',
  '  w.style.display = (w.style.display === "flex") ? "none" : "flex";',
  '}',
  'function mostrarAvisoCookie(texto) {',
  '  document.cookie = "bandido_promo=" + encodeURIComponent(texto) + "; max-age=86400; path=/";',
  '  const toast = document.getElementById("cookieToast");',
  '  toast.textContent = texto;',
  '  toast.style.display = "block";',
  '  document.getElementById("promoDynamicMsg").textContent = texto;',
  '  clearTimeout(window._toastTimer);',
  '  window._toastTimer = setTimeout(() => { toast.style.display = "none"; }, 4500);',
  '}',
  'function copiarCupon(banco, code, desc) {',
  '  if (code) {',
  '    navigator.clipboard.writeText(code).catch(() => {});',
  '    mostrarAvisoCookie("🦝 ¡Cupón " + code + " (" + banco + ") copiado! " + desc);',
  '  } else {',
  '    mostrarAvisoCookie("💳 " + banco + ": " + desc);',
  '  }',
  '}',
  'function initBancos() {',
  '  const cont = document.getElementById("banksContainer");',
  '  const drawer = document.getElementById("bankDrawer");',
  '  PROMOS_BANCOS.forEach(item => {',
  '    const btn = document.createElement("button");',
  '    btn.className = "bank-chip";',
  '    btn.textContent = item.banco;',
  '    btn.onclick = () => {',
  '      if (item.opciones.length === 1) {',
  '        drawer.style.display = "none";',
  '        copiarCupon(item.banco, item.opciones[0].code, item.opciones[0].desc);',
  '      } else {',
  '        drawer.innerHTML = "<span style=\\"font-size:0.78rem;color:#38bdf8;font-weight:bold;\\">" + item.banco + ":</span>";',
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
  'function parsearVencimientoUTC(str) {',
  '  if (!str) return null;',
  '  const iso = str.replace(" ", "T") + "Z";',
  '  const ms = Date.parse(iso);',
  '  return isNaN(ms) ? null : ms;',
  '}',
  'function formatearCuentaRegresiva(msRestantes) {',
  '  if (msRestantes <= 0) return "Revalidando stock...";',
  '  const totalSeg = Math.floor(msRestantes / 1000);',
  '  const hrs = Math.floor(totalSeg / 3600);',
  '  const mins = Math.floor((totalSeg % 3600) / 60);',
  '  const segs = totalSeg % 60;',
  '  const pad = n => String(n).padStart(2, "0");',
  '  return pad(hrs) + "h " + pad(mins) + "m " + pad(segs) + "s";',
  '}',
  'function actualizarRelojesEnVivo() {',
  '  const ahora = Date.now();',
  '  document.querySelectorAll(".timer-bar[data-exp]").forEach(bar => {',
  '    const exp = parseInt(bar.getAttribute("data-exp"), 10);',
  '    if (!exp) return;',
  '    const diff = exp - ahora;',
  '    const clockEl = bar.querySelector(".timer-clock");',
  '    if (clockEl) clockEl.textContent = formatearCuentaRegresiva(diff);',
  '    bar.classList.remove("urgent", "critical");',
  '    if (diff > 0 && diff <= 3600000) bar.classList.add("critical");',
  '    else if (diff > 0 && diff <= 21600000) bar.classList.add("urgent");',
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
  '  const ahora = Date.now();',
  '  container.innerHTML = "";',
  '  const filtradas = ofertasGlobales.filter(o => {',
  '    const subCat = (o.subcategoria || "").toLowerCase().trim();',
  '    const expMs = parsearVencimientoUTC(o.fecha_vencimiento);',
  '    let coincideCategoria = false;',
  '    if (categoriaActual === "todas") {',
  '      coincideCategoria = true;',
  '    } else if (categoriaActual === "hot") {',
  '      coincideCategoria = (o.score == 1 || o.score == 2);',
  '    } else if (categoriaActual === "por_caducar") {',
  '      coincideCategoria = (expMs !== null && (expMs - ahora) > 0 && (expMs - ahora) <= 21600000);',
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
  '    const expMs = parsearVencimientoUTC(o.fecha_vencimiento);',
  '    let timerHtml = "";',
  '    if (expMs) {',
  '      const diff = expMs - ahora;',
  '      const clsExtra = (diff > 0 && diff <= 3600000) ? " critical" : ((diff > 0 && diff <= 21600000) ? " urgent" : "");',
  '      timerHtml = "<div class=\\"timer-bar" + clsExtra + "\\" data-exp=\\"" + expMs + "\\"><span class=\\"timer-label\\">⏳ Vigencia:</span><span class=\\"timer-clock\\">" + formatearCuentaRegresiva(diff) + "</span></div>";',
  '    } else {',
  '      timerHtml = "<div class=\\"timer-bar\\"><span class=\\"timer-label\\">⏳ Vigencia:</span><span class=\\"timer-clock\\">Activa hoy</span></div>";',
  '    }',
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
  '    const textoCompleto = (o.razonamiento || "Oye lindura... ¿por qué no te llevas esto y cuando te llegue lo probamos juntos? Prometo no morder... a menos que tú quieras 🤖🦝🔥").replace(/"/g, "&quot;");',
  '    const corte = Math.min(58, Math.floor(textoCompleto.length * 0.52));',
  '    const textoCorto = textoCompleto.length > 62 ? textoCompleto.slice(0, corte) + "..." : textoCompleto;',
  '    const boxHtml = "<div class=\\"bandido-box\\" onclick=\\"toggleCardTexto(this)\\"><span class=\\"txt-short\\">🦝 " + textoCorto + "</span><span class=\\"txt-full\\" style=\\"display:none;\\">🦝 " + textoCompleto + "</span><span class=\\"bandido-divider\\">____ abrir tarjeta completa ____</span></div>";',
  '    let imagenHtml = o.imagen_url ? "<div class=\\"product-img-container\\"><img src=\\"" + o.imagen_url + "\\" class=\\"product-img\\" alt=\\"Producto\\" loading=\\"lazy\\"></div>" : "";',
  '    container.innerHTML += "<div class=\\"card\\"><div>" + imagenHtml + timerHtml + "<div class=\\"badges-row\\"><span class=\\"store\\">" + o.tienda + "</span><span class=\\"discount\\">" + (o.descuento || "Oferta") + "</span></div><span class=\\"nivel-badge " + nivelClase + "\\">" + nivelTexto + "</span><h3 class=\\"title\\">" + o.titulo + "</h3>" + boxHtml + "</div><div><div class=\\"prices\\">" + preciosHtml + "</div><a href=\\"" + o.url_afiliado + "\\" target=\\"_blank\\" rel=\\"noopener\\" class=\\"btn-buy\\">Ver la oferta 🚀</a></div></div>";',
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
  'setInterval(actualizarRelojesEnVivo, 1000);',
  '</script>',
  '</body>',
  '</html>'
].join('\n');