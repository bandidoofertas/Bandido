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

        await env.DB.prepare("DELETE FROM ofertas WHERE url_afiliado = ?").bind(data.url_afiliado).run();

        await env.DB.prepare(`
          INSERT INTO ofertas (
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
          data.categoria_principal || "TOD",
          data.subcategoria || "TOD",
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

        if (data.id) {
          await env.DB.prepare("DELETE FROM ofertas WHERE id = ?").bind(data.id).run();
        }
        if (target) {
          const asinMatch = target.match(/\/dp\/([A-Z0-9]{10})/i);
          if (asinMatch) {
            await env.DB.prepare("DELETE FROM ofertas WHERE url_afiliado = ? OR instr(url_afiliado, ?) > 0")
              .bind(target, asinMatch[1])
              .run();
          } else {
            const baseUrl = target.split("#")[0].split("?")[0];
            await env.DB.prepare("DELETE FROM ofertas WHERE url_afiliado = ? OR instr(url_afiliado, ?) > 0")
              .bind(target, baseUrl)
              .run();
          }
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
<script defer src="https://utt.impactcdn.com/P-A8317154-f2f4-4a1b-80c7-b3f3d160d4ba1.js" onload="window.impactStat=window.impactStat||function(){(window.impactStat.a=window.impactStat.a||[]).push(arguments)};impactStat('transformLinks');impactStat('trackImpression');"></script>
<style>
*, *::before, *::after { box-sizing: border-box; }
html { overflow-y: scroll; scrollbar-gutter: stable; }
:root { --bg: #0f172a; --card-bg: #1e293b; --accent: #38bdf8; --primary-blue: #2563eb; --text: #f8fafc; --text-muted: #94a3b8; --badge-discount: #ef4444; --nivel-0: #7c3aed; --fire-bg: #dc2626; --nivel-2: #ea580c; --nivel-3: #0284c7; --nivel-4: #475569; }
body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 24px 20px 110px 20px; }
header { text-align: center; padding: 10px 0 12px 0; }
h1 { margin: 0; color: var(--accent); font-size: 2.2rem; }
.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 6px; }
.controls { max-width: 1200px; margin: 16px auto 24px auto; display: flex; flex-direction: column; gap: 12px; align-items: center; }
.top-bar { display: flex; flex-wrap: wrap; gap: 10px; width: 100%; justify-content: center; align-items: center; }
.search-bar { width: 100%; max-width: 440px; padding: 11px 18px; border-radius: 25px; border: 1px solid #334155; background: #1e293b; color: #fff; font-size: 0.98rem; outline: none; }
.search-bar:focus { border-color: var(--accent); }
.sort-group, .store-filter-group { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.sort-btn, .store-filter-btn { background: #1e293b; border: 1px solid #475569; color: #cbd5e1; padding: 9px 14px; border-radius: 20px; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: transform 0.1s, background-color 0.15s, border-color 0.15s; }
.sort-btn.active { background: #0284c7; border-color: #7dd3fc; color: #fff; box-shadow: 0 0 0 2px rgba(125, 211, 252, 0.35); }
.store-filter-btn.active { background: #2563eb; border-color: #93c5fd; color: #fff; box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.4); }
.store-filter-btn.ml.active { background: #ca8a04; border-color: #fef08a; color: #fff; box-shadow: 0 0 0 2px rgba(254, 240, 138, 0.4); }
.categories { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; width: 100%; padding: 4px 0; }
.cat-btn { background: #1e293b; border: 1px solid #334155; color: var(--text); padding: 8px 15px; border-radius: 20px; cursor: pointer; font-size: 0.88rem; font-weight: 600; transition: transform 0.1s, background-color 0.15s, border-color 0.15s, box-shadow 0.15s; white-space: nowrap; }
.cat-btn:hover { border-color: #7dd3fc; }
.cat-btn.active { background: var(--primary-blue); color: #fff; border-color: #ffffff; box-shadow: 0 0 0 2px #38bdf8; }
.cat-btn.btn-mejores { background: linear-gradient(135deg, #dc2626, #b91c1c); color: #fff; border-color: #f87171; }
.cat-btn.btn-mejores.active { background: linear-gradient(135deg, #ef4444, #991b1b); border-color: #ffffff; box-shadow: 0 0 0 3px #fde047, 0 0 16px rgba(239, 68, 68, 0.75); transform: scale(1.04); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 22px; max-width: 1200px; margin: 20px auto; align-items: stretch; }
.card { background: var(--card-bg); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); overflow: hidden; content-visibility: auto; contain-intrinsic-size: 460px; }
.card.card-imperdible { border: 2px solid #a855f7; box-shadow: 0 0 18px rgba(124, 58, 237, 0.45); }
.product-img-container { width: 100%; height: 170px; background: #ffffff; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 12px; padding: 6px; position: relative; }
.product-img { max-width: 100%; max-height: 100%; object-fit: contain; }
.timer-bar { display: flex; align-items: center; justify-content: space-between; background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 6px; padding: 5px 9px; margin-bottom: 8px; font-size: 0.76rem; font-variant-numeric: tabular-nums; }
.timer-bar.urgent { border-color: #f59e0b; background: rgba(120, 53, 15, 0.35); color: #fde68a; }
.timer-bar.critical { border-color: #ef4444; background: rgba(127, 29, 29, 0.45); color: #fecaca; }
.timer-label { color: #94a3b8; font-weight: 600; }
.timer-clock { font-weight: 800; color: #38bdf8; letter-spacing: 0.4px; }
.badges-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; font-size: 0.75rem; margin-bottom: 6px; }
.store { background: var(--primary-blue); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
.store.ml { background: #ca8a04; color: #fff; }
.discount { background: var(--badge-discount); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
.nivel-badge { font-size: 0.74rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block; margin-bottom: 8px; }
.nivel-0 { background: linear-gradient(135deg, #7c3aed, #9333ea); color: #fef08a; border: 1px solid #c084fc; }
.nivel-1 { background: var(--fire-bg); color: white; }
.nivel-2 { background: var(--nivel-2); color: white; }
.nivel-3 { background: var(--nivel-3); color: white; }
.nivel-4 { background: var(--nivel-4); color: white; }
.title { font-size: 0.95rem; margin: 4px 0 10px 0; color: #fff; line-height: 1.3; }
.bandido-box { background: rgba(37, 99, 235, 0.14); border: 1px solid #38bdf8; border-radius: 8px; padding: 9px 11px; margin: 8px 0; font-size: 0.84rem; color: #e0f2fe; line-height: 1.45; }
.ver-mas-btn { background: none; border: none; color: #38bdf8; font-weight: 700; font-size: 0.8rem; cursor: pointer; padding: 0 0 0 4px; text-decoration: underline; }
.ver-mas-btn:hover { color: #7dd3fc; }
.prices { margin: 12px 0 8px 0; text-align: center; }
.original-row { margin-bottom: 2px; }
.original { text-decoration: line-through; color: #94a3b8; font-size: 0.95rem; margin-right: 6px; }
.discount-tag { color: #ef4444; font-size: 0.85rem; font-weight: bold; }
.offer { font-size: 1.6rem; font-weight: bold; color: #4ade80; display: block; }
.btn-buy { display: block; width: 100%; text-align: center; background: var(--primary-blue); color: white; text-decoration: none; padding: 11px 12px; border-radius: 8px; font-weight: bold; transition: background-color 0.2s; margin-top: 10px; }
.btn-buy:hover { background: #1d4ed8; }
.load-more-wrap { text-align: center; margin: 24px auto 0 auto; }
.load-more-btn { background: #1e293b; border: 1px solid #38bdf8; color: #f8fafc; padding: 12px 26px; border-radius: 25px; font-size: 0.92rem; font-weight: bold; cursor: pointer; }
.load-more-btn:hover { background: #2563eb; }
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
<div class="store-filter-group">
<button class="store-filter-btn active" id="storeTodas" onclick="filtrarTienda('todas')">🏪 Todas las tiendas</button>
<button class="store-filter-btn" id="storeAmz" onclick="filtrarTienda('amazon')">🛒 Amazon</button>
<button class="store-filter-btn ml" id="storeMl" onclick="filtrarTienda('mercadolibre')">🤝 Mercado Libre</button>
</div>
<div class="sort-group">
<button class="sort-btn active" id="sortNivel" onclick="cambiarOrden('nivel')">👑 Mejores primero</button>
<button class="sort-btn" id="sortFecha" onclick="cambiarOrden('fecha')">🕒 Más recientes</button>
</div>
</div>
<div class="categories" id="categoryMenu">
<button class="cat-btn active" onclick="filtrarCategoria('todas', this)">Todas</button>
<button class="cat-btn btn-mejores" onclick="filtrarCategoria('mejores', this)">🔥 Mejores ofertas</button>
<button class="cat-btn" onclick="filtrarCategoria('por_caducar', this)" style="border-color: #f59e0b; color: #fde68a;">⏳ Por caducar (&lt;6h)</button>
<button class="cat-btn" onclick="filtrarCategoria('TEC', this)">🛸 Tecnología y TV</button>
<button class="cat-btn" onclick="filtrarCategoria('AUD', this)">🎧 Audio y Música</button>
<button class="cat-btn" onclick="filtrarCategoria('VID', this)">🎮 Videojuegos</button>
<button class="cat-btn" onclick="filtrarCategoria('CEL', this)">📱 Celulares y Tablets</button>
<button class="cat-btn" onclick="filtrarCategoria('COM', this)">💻 Computación</button>
<button class="cat-btn" onclick="filtrarCategoria('HOG', this)">🏠 Hogar y Cocina</button>
<button class="cat-btn" onclick="filtrarCategoria('ROP', this)">👕 Ropa, Calzado y Equipaje</button>
<button class="cat-btn" onclick="filtrarCategoria('PER', this)">✨ Uso Personal</button>
<button class="cat-btn" onclick="filtrarCategoria('HER', this)">🛠️ Herramientas y Auto</button>
<button class="cat-btn" onclick="filtrarCategoria('TMP', this)">🎄 Temporada y Juguetes</button>
</div>
</div>
<main class="grid" id="container"><p style="text-align:center; grid-column: 1/-1;">Cargando ofertas en tiempo real...</p></main>
<div class="load-more-wrap" id="loadMoreWrap" style="display:none;">
<button class="load-more-btn" id="loadMoreBtn" onclick="cargarMasTarjetas()">Mostrar más ofertas</button>
</div>
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
  if (document.hidden) return;
  const ahora = Date.now();
  const barras = document.getElementsByClassName("timer-bar");
  for (let i = 0; i < barras.length; i++) {
    const bar = barras[i];
    const expStr = bar.getAttribute("data-exp");
    if (!expStr) continue;
    const exp = parseInt(expStr, 10);
    const diff = exp - ahora;
    const el = bar.lastElementChild;
    if (el) el.textContent = formatearCuentaRegresiva(diff);
    const estado = diff > 0 && diff <= 3600000 ? "critical" : (diff > 0 && diff <= 21600000 ? "urgent" : "");
    if (bar.dataset.estado !== estado) {
      bar.dataset.estado = estado;
      bar.className = estado ? ("timer-bar " + estado) : "timer-bar";
    }
  }
}

let ofertasGlobales = [];
let filtradasActuales = [];
let limiteRender = 24;
const LOTE_RENDER = 24;
let categoriaActual = "todas";
let tiendaActual = "todas";
let ordenActual = "nivel";

async function load() {
  try {
    const r = await fetch("/api/ofertas");
    ofertasGlobales = await r.json();
    aplicarFiltrosYRender(true);
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
  for (let nivel = 0; nivel <= 5; nivel++) {
    const grupo = lista.filter(o => Number(o.score ?? 3) === nivel);
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

function filtrarTienda(tienda) {
  tiendaActual = tienda;
  document.getElementById("storeTodas").classList.toggle("active", tienda === "todas");
  document.getElementById("storeAmz").classList.toggle("active", tienda === "amazon");
  document.getElementById("storeMl").classList.toggle("active", tienda === "mercadolibre");
  aplicarFiltrosYRender(true);
}

function cambiarOrden(tipo) {
  ordenActual = tipo;
  document.getElementById("sortNivel").classList.toggle("active", tipo === "nivel");
  document.getElementById("sortFecha").classList.toggle("active", tipo === "fecha");
  aplicarFiltrosYRender(true);
}

function construirTarjetaHTML(o, ahora) {
  const sc = Number(o.score ?? 3);
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
  const badgeTxt = sc === 0 ? "👑 Imperdible"
    : sc === 1 ? "🔥 Excelente oferta"
    : sc === 2 ? "⚡ Muy buena oferta"
    : sc === 3 ? "⭐ Buena oferta"
    : "💎 Oportunidad";
  const cardCls = sc === 0 ? "card card-imperdible" : "card";
  const storeCls = (o.tienda || "").toLowerCase().includes("mercado") ? "store ml" : "store";
  const rawTxt = (o.mensaje_redes || o.razonamiento || "🌙 Botín nocturno rescatado antes de que suba de precio 🦝✨")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  let bandidoHtml = "🦝 " + rawTxt;
  if (rawTxt.length > 165) {
    let corte = rawTxt.lastIndexOf(" ", 165);
    if (corte < 110) corte = 165;
    const corto = rawTxt.slice(0, corte).replace(/[.,;:]+$/, "");
    const resto = rawTxt.slice(corte);
    bandidoHtml = "🦝 " + corto +
      "<span class='bandido-dots'>...</span>" +
      "<span class='bandido-more' style='display:none;'>" + resto + "</span>" +
      "<button type='button' class='ver-mas-btn' onclick='expandirBandido(this)'>Ver más</button>";
  }
  const imgHtml = o.imagen_url ? "<div class='product-img-container'><img src='" + o.imagen_url + "' class='product-img' loading='lazy' decoding='async'></div>" : "";
  return "<div class='" + cardCls + "'><div>" + imgHtml + timerHtml + "<div class='badges-row'><span class='" + storeCls + "'>" + o.tienda + "</span><span class='discount'>" + (o.descuento || "Oferta") + "</span></div><span class='nivel-badge nivel-" + Math.min(sc, 4) + "'>" + badgeTxt + "</span><h3 class='title'>" + o.titulo + "</h3><div class='bandido-box'>" + bandidoHtml + "</div></div><div><div class='prices'>" + preciosHtml + "</div><a href='" + o.url_afiliado + "' target='_blank' rel='noopener' class='btn-buy'>Ver la oferta 🚀</a></div></div>";
}

function aplicarFiltrosYRender(reiniciarLimite = true) {
  if (reiniciarLimite) limiteRender = LOTE_RENDER;
  const container = document.getElementById("container");
  const wrap = document.getElementById("loadMoreWrap");
  const btnMore = document.getElementById("loadMoreBtn");
  const q = document.getElementById("searchInput").value.toLowerCase();
  const ahora = Date.now();

  let filtradas = ofertasGlobales.filter(o => {
    const sub = (o.subcategoria || "").toUpperCase().trim();
    const catBase = sub.split("-")[0];
    const titLow = (o.titulo || "").toLowerCase();
    const tiendaLow = (o.tienda || "").toLowerCase();
    const exp = parsearVencimientoUTC(o.fecha_vencimiento);
    const sc = Number(o.score ?? 3);

    if (tiendaActual === "amazon" && tiendaLow.includes("mercado")) return false;
    if (tiendaActual === "mercadolibre" && !tiendaLow.includes("mercado")) return false;

    let okCat = false;
    if (categoriaActual === "todas") okCat = true;
    else if (categoriaActual === "mejores") okCat = (sc <= 2);
    else if (categoriaActual === "por_caducar") okCat = (exp && (exp - ahora) > 0 && (exp - ahora) <= 21600000);
    else if (categoriaActual === "TEC" || categoriaActual === "COM") {
      okCat = (catBase === categoriaActual) || (catBase === "CEL" && /(tablet|ipad|galaxy tab|redmi pad|matepad)/i.test(titLow));
    } else {
      okCat = (catBase === categoriaActual);
    }

    const okQ = !q || titLow.includes(q) || tiendaLow.includes(q);
    return okCat && okQ;
  });

  if (ordenActual === "fecha") {
    filtradas = [...filtradas].sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
  } else {
    filtradas = aplicarSesgoTiendas(filtradas);
  }

  filtradasActuales = filtradas;

  if (!filtradas.length) {
    container.innerHTML = "<p style='text-align:center; grid-column: 1/-1;'>No se encontraron ofertas activas con esos filtros. 🦝</p>";
    wrap.style.display = "none";
    return;
  }

  const visibles = filtradas.slice(0, limiteRender);
  const chunks = [];
  for (let i = 0; i < visibles.length; i++) {
    chunks.push(construirTarjetaHTML(visibles[i], ahora));
  }
  container.innerHTML = chunks.join("");

  const restantes = filtradas.length - visibles.length;
  if (restantes > 0) {
    btnMore.textContent = "Mostrar más ofertas (" + restantes + " restantes)";
    wrap.style.display = "block";
  } else {
    wrap.style.display = "none";
  }
}

function cargarMasTarjetas() {
  const container = document.getElementById("container");
  const wrap = document.getElementById("loadMoreWrap");
  const btnMore = document.getElementById("loadMoreBtn");
  const ahora = Date.now();
  const nuevoLimite = limiteRender + LOTE_RENDER;
  const siguientes = filtradasActuales.slice(limiteRender, nuevoLimite);
  if (siguientes.length) {
    const chunks = [];
    for (let i = 0; i < siguientes.length; i++) {
      chunks.push(construirTarjetaHTML(siguientes[i], ahora));
    }
    container.insertAdjacentHTML("beforeend", chunks.join(""));
  }
  limiteRender = nuevoLimite;
  const restantes = filtradasActuales.length - limiteRender;
  if (restantes > 0) {
    btnMore.textContent = "Mostrar más ofertas (" + restantes + " restantes)";
    wrap.style.display = "block";
  } else {
    wrap.style.display = "none";
  }
}

function expandirBandido(btn) {
  const box = btn.parentElement;
  const dots = box.querySelector(".bandido-dots");
  const more = box.querySelector(".bandido-more");
  if (dots) dots.remove();
  if (more) more.style.display = "inline";
  btn.remove();
}
function filtrarCategoria(cat, btn) {
  categoriaActual = cat;
  document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  aplicarFiltrosYRender(true);
}

let _searchTimer;
document.getElementById("searchInput").addEventListener("input", () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => aplicarFiltrosYRender(true), 150);
});

cargarPromos();
load();
setInterval(actualizarRelojesEnVivo, 1000);
</script>
</body>
</html>`;