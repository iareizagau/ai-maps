/*
 * Núcleo compartido para #30DayMapChallenge.
 * Expone window.Map30 con helpers para crear mapas MapLibre con basemaps CARTO.
 */
(function () {
    "use strict";

    // Carto Basemaps vía public CDN (no requiere API key para estos estilos públicos).
    // Si queremos usar la API autenticada en el futuro, basta con reemplazar la URL.
    const CARTO_STYLES = {
        voyager: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
        positron: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        dark_matter: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    };

    const OSM_RASTER_STYLE = {
        version: 8,
        sources: {
            osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors",
            },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
    };

    function styleFor(basemap) {
        if (basemap === "osm") return OSM_RASTER_STYLE;
        if (basemap === "none") {
            return {
                version: 8,
                sources: {},
                layers: [{ id: "bg", type: "background", paint: { "background-color": "#0b0e14" } }],
            };
        }
        return CARTO_STYLES[basemap] || CARTO_STYLES.voyager;
    }

    /**
     * Crea un mapa MapLibre apuntando a Euskal Herria.
     * @param {string} containerId - id del <div>
     * @param {Object} opts
     *   basemap: "voyager" | "positron" | "dark_matter" | "osm" | "none"
     *   center: [lng, lat]
     *   zoom: number
     */
    function createMap(containerId, opts) {
        opts = opts || {};
        const map = new maplibregl.Map({
            container: containerId,
            style: styleFor(opts.basemap || "voyager"),
            center: opts.center || [-2.2, 43.0], // Euskal Herria center
            zoom: opts.zoom != null ? opts.zoom : 7.2,
            attributionControl: true,
        });
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        return map;
    }

    /** Pequeña utilidad para añadir una leyenda tipo tarjeta flotante. */
    function addLegend(mapEl, html) {
        const el = document.createElement("div");
        el.className = "map30-legend";
        el.innerHTML = html;
        mapEl.appendChild(el);
        return el;
    }

    window.Map30 = { createMap, addLegend };
})();
