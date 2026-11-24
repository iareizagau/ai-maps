/* Constantes de Euskal Herria reutilizadas por múltiples días del challenge. */
(function () {
    "use strict";
    window.EH = {
        // Las 7 capitales históricas de Euskal Herria (lng, lat).
        capitales: [
            { name: "Vitoria-Gasteiz",     lng: -2.672, lat: 42.846, prov: "Araba"     },
            { name: "Bilbao",              lng: -2.935, lat: 43.263, prov: "Bizkaia"   },
            { name: "Donostia",            lng: -1.981, lat: 43.318, prov: "Gipuzkoa"  },
            { name: "Iruñea",              lng: -1.644, lat: 42.812, prov: "Nafarroa"  },
            { name: "Baiona",              lng: -1.479, lat: 43.493, prov: "Lapurdi"   },
            { name: "Maule",               lng: -0.887, lat: 43.228, prov: "Zuberoa"   },
            { name: "Donibane Garazi",     lng: -1.236, lat: 43.163, prov: "Nafarroa B" },
        ],
        // Bbox aproximado de Euskal Herria [w, s, e, n]
        bbox: [-3.45, 42.4, -0.3, 43.65],
        center: [-1.95, 43.03],
    };
})();
