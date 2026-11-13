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
          "SELECT * FROM ofertas ORDER BY id DESC LIMIT 100"
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
  'header { text-align: center; padding: 20px 0 10px 0; }',
  'h1 { margin: 0; color: var(--accent); font-size: 2.2rem; }',
  '.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 5px; }',
  '.controls { max-width: 1200px; margin: 20px auto; display: flex; flex-direction: column; gap: 15px; align-items: center; }',
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
  '.prices { margin: 14px 0 10px 0; text-align: center; }',
  '.original-row { margin-bottom: 2px; }',
  '.original { text-decoration: line-through; color: #94a3b8; font-size: 0.95rem; margin-right: 6px; }',
  '.discount-tag { color: #ef4444; font-size: 0.85rem; font-weight: bold; }',
  '.offer { font-size: 1.6rem; font-weight: bold; color: #4ade80; display: block; }',
  '.btn-buy { display: block; text-align: center; background: var(--primary-blue); color: white; text-decoration: none; padding: 10px; border-radius: 8px; font-weight: bold; transition: background 0.2s; margin-top: 10px; }',
  '.btn-buy:hover { background: #1d4ed8; }',
  '</style>',
  '</head>',
  '<body>',
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
  'let ofertasGlobales = [];',
  'let categoriaActual = "todas";',
  'async function load() {',
  '  try {',
  '    const r = await fetch("/api/ofertas");',
  '    ofertasGlobales = await r.json();',
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
  '    let imagenHtml = o.imagen_url ? "<div class=\\"product-img-container\\"><img src=\\"" + o.imagen_url + "\\" class=\\"product-img\\" alt=\\"Producto\\" loading=\\"lazy\\"></div>" : "";',
  '    container.innerHTML += "<div class=\\"card\\"><div>" + imagenHtml + "<div class=\\"badges-row\\"><span class=\\"store\\">" + o.tienda + "</span><span class=\\"discount\\">" + (o.descuento || "Oferta") + "</span></div><span class=\\"nivel-badge " + nivelClase + "\\">" + nivelTexto + "</span><h3 class=\\"title\\">" + o.titulo + "</h3></div><div><div class=\\"prices\\">" + preciosHtml + "</div><a href=\\"" + o.url_afiliado + "\\" target=\\"_blank\\" rel=\\"noopener\\" class=\\"btn-buy\\">Ver la oferta 🚀</a></div></div>";',
  '  });',
  '}',
  'function filtrarCategoria(cat, btn) {',
  '  categoriaActual = cat;',
  '  document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));',
  '  btn.classList.add("active");',
  '  render();',
  '}',
  'document.getElementById("searchInput").addEventListener("input", render);',
  'load();',
  '</script>',
  '</body>',
  '</html>'
].join('\n');