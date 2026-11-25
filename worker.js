export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const corsHeaders = {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    };

    if (url.pathname === "/api/ofertas" && request.method === "GET") {
      try {
        const incluirVencidas = url.searchParams.get("incluir_vencidas") === "1";
        const query = incluirVencidas
          ? "SELECT * FROM ofertas ORDER BY score ASC, id DESC LIMIT 150"
          : "SELECT * FROM ofertas WHERE fecha_vencimiento IS NULL OR datetime(fecha_vencimiento) > datetime('now') ORDER BY score ASC, id DESC LIMIT 120";

        const { results } = await env.DB.prepare(query).all();
        return new Response(JSON.stringify(results || []), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
      }
    }

    if (url.pathname === "/api/promos" && request.method === "GET") {
      try {
        await env.DB.prepare(`
          CREATE TABLE IF NOT EXISTS promos (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            campana TEXT,
            datos_json TEXT,
            actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `).run();
        const row = await env.DB.prepare("SELECT campana, datos_json FROM promos WHERE id = 1").first();
        if (!row) {
          return new Response(JSON.stringify({ campana: "PROMOS", tiendas: { amazon: [], mercadolibre: [] } }), { headers: corsHeaders });
        }
        return new Response(JSON.stringify({
          campana: row.campana || "PROMOS",
          tiendas: JSON.parse(row.datos_json || '{"amazon":[],"mercadolibre":[]}')
        }), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
      }
    }

    if (url.pathname === "/api/promos/actualizar" && request.method === "POST") {
      try {
        if (request.headers.get("Authorization") !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), { status: 401, headers: corsHeaders });
        }
        const body = await request.json();
        await env.DB.prepare(`
          CREATE TABLE IF NOT EXISTS promos (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            campana TEXT,
            datos_json TEXT,
            actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `).run();
        await env.DB.prepare(`
          INSERT OR REPLACE INTO promos (id, campana, datos_json, actualizado)
          VALUES (1, ?, ?, CURRENT_TIMESTAMP)
        `).bind(
          body.campana || "PROMOS",
          JSON.stringify(body.tiendas || { amazon: [], mercadolibre: [] })
        ).run();
        return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
      }
    }

    if (url.pathname === "/api/guardar" && request.method === "POST") {
      try {
        if (request.headers.get("Authorization") !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), { status: 401, headers: corsHeaders });
        }
        const data = await request.json();

        await env.DB.prepare(`
          INSERT OR REPLACE INTO ofertas (
            titulo, precio_oferta, precio_original, descuento, tienda, 
            url_afiliado, score, es_hot, categoria_principal, subcategoria, 
            razonamiento, mensaje_redes, metodos_pago, fecha_vencimiento, imagen_url
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).bind(
          data.titulo,
          data.precio_oferta || "Ver en sitio",
          data.precio_original || "",
          data.descuento || "Oferta",
          data.tienda,
          data.url_afiliado,
          data.score,
          data.es_hot ? 1 : 0,
          data.categoria_principal || "H",
          data.subcategoria || "H1",
          data.razonamiento || "",
          data.mensaje_redes || "",
          data.metodos_pago || "",
          data.fecha_vencimiento || null,
          data.imagen_url || ""
        ).run();

        return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
      }
    }

    if (url.pathname === "/api/purgar" && request.method === "POST") {
      try {
        if (request.headers.get("Authorization") !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), { status: 401, headers: corsHeaders });
        }
        await env.DB.prepare("DELETE FROM ofertas").run();
        return new Response(JSON.stringify({ success: true, message: "Tabla ofertas purgada" }), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
      }
    }

    if (url.pathname === "/api/borrar" && request.method === "POST") {
      try {
        if (request.headers.get("Authorization") !== "Bearer bandido_secret") {
          return new Response(JSON.stringify({ error: "No autorizado" }), { status: 401, headers: corsHeaders });
        }
        const data = await request.json();
        const target = data.url || data.url_normal || data.url_afiliado;
        if (target) {
          const asinMatch = target.match(/\/dp\/([A-Z0-9]{10})/i);
          const terminoBusqueda = asinMatch ? `%${asinMatch[1]}%` : `%${target}%`;
          await env.DB.prepare("DELETE FROM ofertas WHERE url_afiliado = ? OR url_afiliado LIKE ?").bind(target, terminoBusqueda).run();
        } else if (data.id) {
          await env.DB.prepare("DELETE FROM ofertas WHERE id = ?").bind(data.id).run();
        }
        return new Response(JSON.stringify({ success: true, message: "Oferta eliminada correctamente" }), { headers: corsHeaders });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
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

const HTML_CONTENT = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bandido Ofertas 🦝 | Gangas Reales en México</title>
<script type="text/javascript">(function(i,m,p,a,c,t){c.ire_o=p;c[p]=c[p]||function(){(c[p].a=c[p].a||[]).push(arguments)};t=a.createElement(m);var z=a.getElementsByTagName(m)[0];t.async=1;t.src=i;z.parentNode.insertBefore(t,z)})('https://utt.impactcdn.com/P-A8317154-f2f4-4a1b-80c7-b3f3d160d4ba1.js','script','impactStat',document,window);impactStat('transformLinks');impactStat('trackImpression');</script>
<style>
:root { --bg: #0f172a; --card-bg: #1e293b; --accent: #38bdf8; --primary-blue: #2563eb; --text: #f8fafc; --text-muted: #94a3b8; --badge-discount: #ef4444; --fire-bg: #dc2626; --nivel-2: #ea580c; --nivel-3: #0284c7; --nivel-4: #475569; }
body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; padding-bottom: 100px; }
header { text-align: center; padding: 15px 0 10px 0; }
h1 { margin: 0; color: var(--accent); font-size: 2.2rem; }
.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 5px; }
.controls { max-width: 1200px; margin: 15px auto; display: flex; flex-direction: column; gap: 14px; align-items: center; }
.top-bar { display: flex; flex-wrap: wrap; gap: 10px; width: 100%; justify-content: center; align-items: center; }
.search-bar { width: 100%; max-width: 460px; padding: 11px 18px; border-radius: 25px; border: 1px solid #334155; background: #1e293b; color: #fff; font-size: 0.98rem; outline: none; }
.search-bar:focus { border-color: var(--accent); }
.sort-group { display: flex; gap: 6px; }
.sort-btn { background: #1e293b; border: 1px solid #475569; color: #cbd5e1; padding: 9px 14px; border-radius: 20px; cursor: pointer; font-size: 0.82rem; font-weight: bold; }
.sort-btn.active { background: #0284c7; border-color: #7dd3fc; color: #fff; }
.categories { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.cat-btn { background: #1e293b; border: 1px solid #334155; color: var(--text); padding: 8px 15px; border-radius: 20px; cursor: pointer; font-size: 0.88rem; transition: all 0.2s; }
.cat-btn:hover, .cat-btn.active { background: var(--primary-blue); color: #fff; font-weight: bold; border-color: var(--primary-blue); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 20px auto; }
.card { background: var(--card-bg); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); }
.product-img-container { width: 100%; height: 170px; background: #ffffff; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 12px; padding: 6px; box-sizing: border-box; position: relative; }
.product-img { max-width: 100%; max-height: 100%; object-fit: contain; }
.timer-bar { display: flex; align-items: center; justify-content: space-between; background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 6px; padding: 5px 9px; margin-bottom: 8px; font-size: 0.76rem; font-variant-numeric: tabular-nums; }
.timer-bar.urgent { border-color: #f59e0b; background: rgba(120, 53, 15, 0.35); color: #fde68a; }
.timer-bar.critical { border-color: #ef4444; background: rgba(127, 29, 29, 0.45); color: #fecaca; animation: pulseBorder 1.8s infinite; }
@keyframes pulseBorder { 0%, 100% { border-color: #ef4444; } 50% { border-color: #fca5a5; } }
.timer-label { color: #94a3b8; font-weight: 600; }
.timer-clock { font-weight: 800; color: #38bdf8; letter-spacing: 0.4px; }
.badges-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; font-size: 0.75rem; margin-bottom: 6px; }
.store { background: var(--primary-blue); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
.discount { background: var(--badge-discount); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
.nivel-badge { font-size: 0.74rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block; margin-bottom: 8px; }
.nivel-1 { background: var(--fire-bg); color: white; }
.nivel-2 { background: var(--nivel-2); color: white; }
.nivel-3 { background: var(--nivel-3); color: white; }
.nivel-4 { background: var(--nivel-4); color: white; }
.title { font-size: 0.95rem; margin: 4px 0 10px 0; color: #fff; line-height: 1.3; }
.bandido-box { background: rgba(37, 99, 235, 0.14); border: 1px solid #38bdf8; border-radius: 8px; padding: 9px 11px; margin: 8px 0; font-size: 0.84rem; color: #e0f2fe; line-height: 1.4; }
.prices { margin: 12px 0 8px 0; text-align: center; }
.original-row { margin-bottom: 2px; }
.original { text-decoration: line-through; color: #94a3b8; font-size: 0.95rem; margin-right: 6px; }
.discount-tag { color: #ef4444; font-size: 0.85rem; font-weight: bold; }
.offer { font-size: 1.6rem; font-weight: bold; color: #4ade80; display: block; }
.btn-buy { display: block; text-align: center; background: var(--primary-blue); color: white; text-decoration: none; padding: 10px; border-radius: 8px; font-weight: bold; transition: background 0.2s; margin-top: 10px; }
.btn-buy:hover { background: #1d4ed8; }
.float-menu-btn { position: fixed; bottom: 20px; left: 20px; z-index: 950; background: #0f172a; border: 1px solid #94a3b8; color: #f8fafc; padding: 10px 16px; border-radius: 4px; font-size: 0.82rem; font-weight: 700; letter-spacing: 1.5px; cursor: pointer; display: flex; align-items: center; gap: 10px; box-shadow: 0 6px 18px rgba(0,0,0,0.5); }
.bf-badge { background: linear-gradient(135deg, #dc2626, #b91c1c); color: #fef08a; padding: 3px 7px; border-radius: 3px; font-size: 0.68rem; font-weight: 900; border: 1px solid #facc15; }
.promo-wrapper { position: fixed; bottom: 72px; left: 20px; z-index: 940; display: none; flex-direction: row; align-items: flex-end; gap: 10px; max-width: calc(100vw - 40px); }
.promo-panel { width: 210px; background: #0f172a; border: 1px solid #38bdf8; border-radius: 12px; padding: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.75); display: flex; flex-direction: column; gap: 8px; }
.promo-panel-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 6px; }
.promo-panel-title { font-size: 0.82rem; font-weight: bold; color: #facc15; }
.promo-close { background: none; border: none; color: #94a3b8; font-size: 1.1rem; cursor: pointer; }
.store-tabs { display: flex; gap: 6px; }
.store-tab { flex: 1; background: #1e293b; border: 1px solid #334155; color: #cbd5e1; padding: 6px 4px; border-radius: 6px; font-size: 0.74rem; font-weight: bold; cursor: pointer; text-align: center; }
.store-tab.active { background: #2563eb; border-color: #7dd3fc; color: #fff; }
.banks-vertical { display: flex; flex-direction: column; gap: 6px; max-height: 250px; overflow-y: auto; padding-right: 4px; }
.bank-chip { width: 100%; text-align: left; background: #1e293b; border: 1px solid #334155; color: #f8fafc; padding: 8px 11px; border-radius: 8px; font-size: 0.8rem; font-weight: bold; cursor: pointer; display: flex; justify-content: space-between; }
.bank-chip:hover, .bank-chip.active { background: #2563eb; border-color: #7dd3fc; color: #fff; }
.bank-side-drawer { width: 260px; max-width: calc(100vw - 260px); background: #0f172a; border: 1px solid #38bdf8; border-radius: 12px; padding: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.75); display: none; flex-direction: column; gap: 8px; }
.side-drawer-title { font-size: 0.85rem; color: #38bdf8; font-weight: bold; border-bottom: 1px solid #334155; padding-bottom: 6px; }
.bank-opt-btn { background: #dc2626; border: none; color: #fff; padding: 9px 10px; border-radius: 7px; font-size: 0.78rem; font-weight: bold; cursor: pointer; text-align: left; line-height: 1.35; }
.bank-opt-btn:hover { background: #b91c1c; }
.bank-opt-btn.info-only { background: #1e293b; border: 1px solid #475569; color: #e2e8f0; cursor: default; }
.cookie-toast { position: fixed; top: 18px; left: 50%; transform: translateX(-50%); z-index: 1000; background: #0284c7; color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 0.84rem; font-weight: bold; display: none; box-shadow: 0 8px 20px rgba(0,0,0,0.5); border: 1px solid #7dd3fc; }
</style>
</head>
<body>
<div class="cookie-toast" id="cookieToast"></div>
<header>
<h1>🦝 Bandido Ofertas</h1>
<p class="subtitle">El arte de cazar los mejores descuentos en México</p>
</header>
<div class="controls">
<div class="top-bar">
<input type="text" id="searchInput" class="search-bar" placeholder="🔍 Buscar oferta (ej. Audífonos, Nintendo, Laptop)...">
<div class="sort-group">
<button class="sort-btn active" id="sortNivel" onclick="cambiarOrden('nivel')">🔥 Nivel 1→5</button>
<button class="sort-btn" id="sortFecha" onclick="cambiarOrden('fecha')">🕒 Más recientes</button>
</div>
</div>
<div class="categories" id="categoryMenu">
<button class="cat-btn active" onclick="filtrarCategoria('todas', this)">Todas</button>
<button class="cat-btn" onclick="filtrarCategoria('hot', this)" style="background: #dc2626; color: white;">🔥 Hot (Score 1-2)</button>
<button class="cat-btn" onclick="filtrarCategoria('por_caducar', this)" style="border-color: #f59e0b; color: #fde68a;">⏳ Por caducar (&lt;6h)</button>
<button class="cat-btn" onclick="filtrarCategoria('a', this)">🎧 Audio</button>
<button class="cat-btn" onclick="filtrarCategoria('b', this)">🎮 Videojuegos</button>
<button class="cat-btn" onclick="filtrarCategoria('c', this)">🏠 Hogar</button>
<button class="cat-btn" onclick="filtrarCategoria('d', this)">📱 Celulares</button>
<button class="cat-btn" onclick="filtrarCategoria('e', this)">💻 Computación</button>
<button class="cat-btn" onclick="filtrarCategoria('f', this)">👕 Ropa, Calzado y Deporte</button>
<button class="cat-btn" onclick="filtrarCategoria('g', this)">🛠️ Herramientas</button>
<button class="cat-btn" onclick="filtrarCategoria('h', this)">✨ General</button>
</div>
</div>
<main class="grid" id="container"><p style="text-align:center; grid-column: 1/-1;">Cargando ofertas en tiempo real...</p></main>
<button class="float-menu-btn" id="floatPromoBtn" onclick="togglePromoPanel()" style="display:none;">
<span class="bf-badge" id="campanaBadge">PROMOS</span>
<span>CUPONES &rarr;</span>
</button>
<div class="promo-wrapper" id="promoWrapper">
<div class="promo-panel">
<div class="promo-panel-header">
<span class="promo-panel-title">💳 Elige Tienda</span>
<button class="promo-close" onclick="togglePromoPanel()">&times;</button>
</div>
<div class="store-tabs">
<button class="store-tab active" id="tabAmz" onclick="cambiarTienda('amazon')">🛒 Amazon</button>
<button class="store-tab" id="tabMl" onclick="cambiarTienda('mercadolibre')">🤝 Mercado Libre</button>
</div>
<div class="banks-vertical" id="banksContainer"></div>
</div>
<div class="bank-side-drawer" id="bankDrawer"></div>
</div>
<script>
let PROMOS_TIENDAS = { amazon: [], mercadolibre: [] };

async function cargarPromos() {
  try {
    const r = await fetch("/api/promos");
    const data = await r.json();
    if (data && data.tiendas) {
      PROMOS_TIENDAS = data.tiendas;
      const total = (PROMOS_TIENDAS.amazon?.length || 0) + (PROMOS_TIENDAS.mercadolibre?.length || 0);
      const btn = document.getElementById("floatPromoBtn");
      const badge = document.getElementById("campanaBadge");
      if (total > 0) {
        badge.textContent = data.campana || "PROMOS";
        btn.style.display = "flex";
        cambiarTienda("amazon");
      } else {
        btn.style.display = "none";
      }
    }
  } catch (e) {}
}

function togglePromoPanel() {
  const w = document.getElementById("promoWrapper");
  const d = document.getElementById("bankDrawer");
  if (w.style.display === "flex") { w.style.display = "none"; d.style.display = "none"; }
  else { w.style.display = "flex"; }
}
function mostrarToast(texto) {
  const t = document.getElementById("cookieToast");
  t.textContent = texto;
  t.style.display = "block";
  clearTimeout(window._tTimer);
  window._tTimer = setTimeout(() => { t.style.display = "none"; }, 4200);
}
function cambiarTienda(tienda) {
  document.getElementById("tabAmz").classList.toggle("active", tienda === "amazon");
  document.getElementById("tabMl").classList.toggle("active", tienda === "mercadolibre");
  const cont = document.getElementById("banksContainer");
  const drawer = document.getElementById("bankDrawer");
  cont.innerHTML = "";
  drawer.style.display = "none";
  const lista = PROMOS_TIENDAS[tienda] || [];
  if (!lista.length) {
    cont.innerHTML = "<span style='color:#94a3b8;font-size:0.78rem;padding:6px;'>Sin cupones activos hoy.</span>";
    return;
  }
  lista.forEach(item => {
    const btn = document.createElement("button");
    btn.className = "bank-chip";
    btn.innerHTML = "<span>" + item.banco + "</span><span>&rsaquo;</span>";
    btn.onclick = () => {
      document.querySelectorAll(".bank-chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      drawer.innerHTML = "<div class='side-drawer-title'>💳 " + item.banco + "</div>";
      const ob = document.createElement("button");
      ob.className = item.code ? "bank-opt-btn" : "bank-opt-btn info-only";
      ob.textContent = item.code ? ("📋 Copiar " + item.code + " — " + item.desc) : ("ℹ️ " + item.desc);
      if (item.code) {
        ob.onclick = () => {
          navigator.clipboard.writeText(item.code).catch(() => {});
          mostrarToast("🦝 Cupón " + item.code + " copiado al portapapeles");
        };
      }
      drawer.appendChild(ob);
      drawer.style.display = "flex";
    };
    cont.appendChild(btn);
  });
}
function parsearVencimientoUTC(str) {
  if (!str) return null;
  const ms = Date.parse(str.replace(" ", "T") + "Z");
  return isNaN(ms) ? null : ms;
}
function formatearCuentaRegresiva(ms) {
  if (ms <= 0) return "Revalidando stock...";
  const s = Math.floor(ms / 1000);
  const pad = n => String(n).padStart(2, "0");
  return pad(Math.floor(s / 3600)) + "h " + pad(Math.floor((s % 3600) / 60)) + "m " + pad(s % 60) + "s";
}
function actualizarRelojesEnVivo() {
  const ahora = Date.now();
  document.querySelectorAll(".timer-bar[data-exp]").forEach(bar => {
    const exp = parseInt(bar.getAttribute("data-exp"), 10);
    if (!exp) return;
    const diff = exp - ahora;
    const el = bar.querySelector(".timer-clock");
    if (el) el.textContent = formatearCuentaRegresiva(diff);
    bar.classList.remove("urgent", "critical");
    if (diff > 0 && diff <= 3600000) bar.classList.add("critical");
    else if (diff > 0 && diff <= 21600000) bar.classList.add("urgent");
  });
}
let ofertasGlobales = [];
let categoriaActual = "todas";
let ordenActual = "nivel";
async function load() {
  try {
    const r = await fetch("/api/ofertas");
    ofertasGlobales = await r.json();
    render();
  } catch(e) {
    document.getElementById("container").innerHTML = "<p style='text-align:center; grid-column: 1/-1; color: #ef4444;'>Error conectando con D1.</p>";
  }
}
function limpiarPrecio(t) {
  if (!t) return 0;
  const m = String(t).replace(/\$/g, "").replace(/,/g, "").match(/[0-9.]+/);
  return m ? parseFloat(m[0]) : 0;
}
function formatearMoneda(n) { return "$" + n.toLocaleString("es-MX", { maximumFractionDigits: 0 }); }

function aplicarSesgoTiendas(lista) {
  const patron = ["M","M","A","M","A","M","M","M","A","A","M","A","A"];
  const salida = [];
  for (let nivel = 1; nivel <= 5; nivel++) {
    const grupo = lista.filter(o => Number(o.score || 3) === nivel);
    if (!grupo.length) continue;
    const ml = grupo.filter(o => (o.tienda || "").toLowerCase().includes("mercado"));
    const amz = grupo.filter(o => !(o.tienda || "").toLowerCase().includes("mercado"));
    let i = 0;
    while (ml.length || amz.length) {
      const turno = patron[i % patron.length];
      if (turno === "M" && ml.length) salida.push(ml.shift());
      else if (turno === "A" && amz.length) salida.push(amz.shift());
      else if (ml.length) salida.push(ml.shift());
      else if (amz.length) salida.push(amz.shift());
      i++;
    }
  }
  return salida;
}

function cambiarOrden(tipo) {
  ordenActual = tipo;
  document.getElementById("sortNivel").classList.toggle("active", tipo === "nivel");
  document.getElementById("sortFecha").classList.toggle("active", tipo === "fecha");
  render();
}

function render() {
  const container = document.getElementById("container");
  const q = document.getElementById("searchInput").value.toLowerCase();
  const ahora = Date.now();
  container.innerHTML = "";
  let filtradas = ofertasGlobales.filter(o => {
    const sub = (o.subcategoria || "").toLowerCase().trim();
    const exp = parsearVencimientoUTC(o.fecha_vencimiento);
    let okCat = categoriaActual === "todas" ? true
      : categoriaActual === "hot" ? (o.score == 1 || o.score == 2)
      : categoriaActual === "por_caducar" ? (exp && (exp - ahora) > 0 && (exp - ahora) <= 21600000)
      : (sub === categoriaActual || sub.startsWith(categoriaActual));
    const okQ = (o.titulo || "").toLowerCase().includes(q) || (o.tienda || "").toLowerCase().includes(q);
    return okCat && okQ;
  });

  if (ordenActual === "fecha") {
    filtradas = [...filtradas].sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
  } else {
    filtradas = aplicarSesgoTiendas(filtradas);
  }

  if (!filtradas.length) {
    container.innerHTML = "<p style='text-align:center; grid-column: 1/-1;'>No se encontraron ofertas activas en esta categoría. 🦝</p>";
    return;
  }
  filtradas.forEach(o => {
    const sc = Number(o.score || 3);
    const exp = parsearVencimientoUTC(o.fecha_vencimiento);
    const diff = exp ? exp - ahora : 0;
    const clsExtra = exp ? (diff > 0 && diff <= 3600000 ? " critical" : (diff > 0 && diff <= 21600000 ? " urgent" : "")) : "";
    const timerHtml = exp
      ? "<div class='timer-bar" + clsExtra + "' data-exp='" + exp + "'><span class='timer-label'>⏳ Vigencia:</span><span class='timer-clock'>" + formatearCuentaRegresiva(diff) + "</span></div>"
      : "<div class='timer-bar'><span class='timer-label'>⏳ Vigencia:</span><span class='timer-clock'>Activa hoy</span></div>";
    let pOf = limpiarPrecio(o.precio_oferta), pOr = limpiarPrecio(o.precio_original);
    let preciosHtml = (pOr > pOf && pOf > 0)
      ? "<div class='original-row'><span class='original'>" + formatearMoneda(pOr) + "</span><span class='discount-tag'>-" + Math.round(((pOr - pOf) / pOr) * 100) + "%</span></div><span class='offer'>" + formatearMoneda(pOf) + "</span>"
      : "<span class='offer'>" + (pOf > 0 ? formatearMoneda(pOf) : o.precio_oferta) + "</span>";
    const badgeTxt = sc === 1 ? "🔥 Nivel 1 · Ganga Histórica" : sc === 2 ? "⚡ Nivel 2 · Oferta Hot" : sc === 3 ? "⭐ Nivel 3 · Buen Descuento" : "💎 Nivel 4 · Oportunidad";
    const txt = (o.mensaje_redes || o.razonamiento || "🌙 Botín nocturno rescatado antes de que suba de precio 🦝✨").replace(/"/g, "&quot;");
    const imgHtml = o.imagen_url ? "<div class='product-img-container'><img src='" + o.imagen_url + "' class='product-img' loading='lazy'></div>" : "";
    container.innerHTML += "<div class='card'><div>" + imgHtml + timerHtml + "<div class='badges-row'><span class='store'>" + o.tienda + "</span><span class='discount'>" + (o.descuento || "Oferta") + "</span></div><span class='nivel-badge nivel-" + Math.min(sc, 4) + "'>" + badgeTxt + "</span><h3 class='title'>" + o.titulo + "</h3><div class='bandido-box'>🦝 " + txt + "</div></div><div><div class='prices'>" + preciosHtml + "</div><a href='" + o.url_afiliado + "' target='_blank' rel='noopener' class='btn-buy'>Ver la oferta 🚀</a></div></div>";
  });
}
function filtrarCategoria(cat, btn) {
  categoriaActual = cat;
  document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  render();
}
document.getElementById("searchInput").addEventListener("input", render);
cargarPromos();
load();
setInterval(actualizarRelojesEnVivo, 1000);
</script>
</body>
</html>`;