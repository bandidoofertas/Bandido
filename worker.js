export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // API Endpoint para enviar las ofertas registradas
    if (url.pathname === "/api/ofertas") {
      try {
        const { results } = await env.DB.prepare(
          "SELECT * FROM ofertas ORDER BY fecha DESC LIMIT 50"
        ).all();

        return new Response(JSON.stringify(results), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // Retorna la aplicación web dinámica
    return new Response(HTML_CONTENT, {
      headers: { "Content-Type": "text/html;charset=UTF-8" },
    });
  },
};

const HTML_CONTENT = `
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bandido Ofertas 🦝 | Chollos Reales en México</title>
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: #38bdf8;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --badge-store: #4f46e5;
            --badge-discount: #ef4444;
            --badge-min: #eab308;
        }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 20px;
        }
        header { text-align: center; padding: 20px 0 10px 0; }
        h1 { margin: 0; color: var(--accent); font-size: 2.2rem; }
        .subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 5px; }

        /* Controles: Buscador y Categorías */
        .controls {
            max-width: 1200px;
            margin: 20px auto;
            display: flex;
            flex-direction: column;
            gap: 15px;
            align-items: center;
        }
        .search-bar {
            width: 100%;
            max-width: 500px;
            padding: 12px 18px;
            border-radius: 25px;
            border: 1px solid #334155;
            background: #1e293b;
            color: #fff;
            font-size: 1rem;
            outline: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .search-bar:focus { border-color: var(--accent); }

        .categories {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }
        .cat-btn {
            background: #1e293b;
            border: 1px solid #334155;
            color: var(--text);
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        .cat-btn:hover, .cat-btn.active {
            background: var(--accent);
            color: #0f172a;
            font-weight: bold;
            border-color: var(--accent);
        }

        /* Grid y Tarjetas */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 20px auto;
        }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border: 1px solid #334155;
            position: relative;
        }
        .badges-row {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            align-items: center;
            font-size: 0.75rem;
        }
        .store { background: var(--badge-store); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
        .discount { background: var(--badge-discount); padding: 3px 8px; border-radius: 4px; font-weight: bold; }
        .min-price { background: var(--badge-min); color: #000; padding: 3px 8px; border-radius: 4px; font-weight: bold; }

        .title { font-size: 1.1rem; margin: 12px 0 8px 0; color: #fff; line-height: 1.3; }

        /* Lista de características por viñetas */
        .features {
            background: #0f172a;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 12px;
            line-height: 1.4;
        }

        .prices { margin: 10px 0; }
        .original { text-decoration: line-through; color: var(--text-muted); font-size: 0.85rem; }
        .offer { font-size: 1.4rem; font-weight: bold; color: #4ade80; }
        .coupon { background: #334155; padding: 6px; border-radius: 6px; font-size: 0.8rem; text-align: center; margin-bottom: 10px; }
        
        .btn-buy {
            display: block;
            text-align: center;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: white;
            text-decoration: none;
            padding: 10px;
            border-radius: 8px;
            font-weight: bold;
            transition: transform 0.2s;
        }
        .btn-buy:hover { transform: scale(1.02); }
    </style>
</head>
<body>
    <header>
        <h1>🦝 Bandido Ofertas</h1>
        <p class="subtitle">El cazador ligero de los mejores descuentos en México</p>
    </header>

    <div class="controls">
        <input type="text" id="searchInput" class="search-bar" placeholder="🔍 Buscar oferta (ej. Switch, ASUS, Hisense)...">
        <div class="categories">
            <button class="cat-btn active" onclick="filtrarCategoria('todas', this)">Todas</button>
            <button class="cat-btn" onclick="filtrarCategoria('Computadoras', this)">💻 Computadoras</button>
            <button class="cat-btn" onclick="filtrarCategoria('Consolas', this)">🎮 Consolas</button>
            <button class="cat-btn" onclick="filtrarCategoria('Televisores', this)">📺 Televisores</button>
            <button class="cat-btn" onclick="filtrarCategoria('Audifonos', this)">🎧 Audífonos</button>
        </div>
    </div>

    <main class="grid" id="container">
        <p style="text-align:center; grid-column: 1/-1;">Cargando ofertas en tiempo real...</p>
    </main>

    <script>
        let ofertasGlobales = [];
        let categoriaActual = 'todas';

        async function load() {
            try {
                const r = await fetch('/api/ofertas');
                ofertasGlobales = await r.json();
                render();
            } catch(e) {
                console.error("Error al cargar ofertas:", e);
            }
        }

        function render() {
            const container = document.getElementById('container');
            const busqueda = document.getElementById('searchInput').value.toLowerCase();
            container.innerHTML = '';

            const filtradas = ofertasGlobales.filter(o => {
                const coincideCategoria = (categoriaActual === 'todas') || (o.categoria === categoriaActual);
                const coincideBusqueda = o.titulo.toLowerCase().includes(busqueda) || 
                                         (o.tienda && o.tienda.toLowerCase().includes(busqueda)) ||
                                         (o.caracteristicas && o.caracteristicas.toLowerCase().includes(busqueda));
                return coincideCategoria && coincideBusqueda;
            });

            if(!filtradas || filtradas.length === 0) {
                container.innerHTML = '<p style="text-align:center; grid-column: 1/-1;">No se encontraron ofertas activas. 🦝</p>';
                return;
            }

            filtradas.forEach(o => {
                const esMinimo = o.es_minimo_historico == 1 || o.es_minimo_historico == true;
                const featuresHtml = o.caracteristicas ? \`<div class="features">⚡ \${o.caracteristicas}</div>\` : '';

                container.innerHTML += \`
                    <div class="card">
                        <div>
                            <div class="badges-row">
                                <span class="store">\${o.tienda}</span>
                                <span class="discount">-\${o.descuento}</span>
                                \${esMinimo ? '<span class="min-price">🔥 Mínimo Histórico</span>' : ''}
                            </div>
                            <h3 class="title">\${o.titulo}</h3>
                            \${featuresHtml}
                        </div>
                        <div>
                            <div class="prices">
                                <span class="original">\${o.precio_original}</span><br>
                                <span class="offer">\${o.precio_oferta}</span>
                            </div>
                            \${o.cupon && o.cupon !== 'SIN CUPÓN' ? \`<div class="coupon">✂️ Cupón: <strong>\${o.cupon}</strong></div>\` : ''}
                            <a href="\${o.url_afiliado}" target="_blank" rel="noopener" class="btn-buy">Ir a la oferta 🚀</a>
                        </div>
                    </div>
                \`;
            });
        }

        function filtrarCategoria(cat, btn) {
            categoriaActual = cat;
            document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            render();
        }

        document.getElementById('searchInput').addEventListener('input', render);

        load();
    </script>
</body>
</html>
`;