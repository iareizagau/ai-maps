# Technical Runbook - Maps.eus Core Skills

**Capacidades técnicas clave y cómo implementarlas en Maps.eus.**

Este archivo consolida las mejores prácticas de arquitectura, optimización y desarrollo del proyecto.

---

## 🧠 SKILL 1: Hybrid Spatial-Semantic Search

**Objetivo**: Buscar lugares combinando geografía + semántica en una sola query.

### Protocolo
1. **Extract** entidades geográficas y semánticas del input
2. **Filter** espacialmente con PostGIS (ej: `ST_DWithin`)
3. **Rank** semánticamente con pgvector (Cosine Similarity)

### Implementación

```python
# ❌ No hagas esto
landmarks = Landmark.objects.all()  # Carga todo

# ✅ Haz esto
from django.db.models import F
from pgvector.django import L2Distance, CosineDistance

# 1. Filtro espacial primero
nearby = Landmark.objects.filter(
    location__distance_lte=(user_point, D(km=5))
).values('id', 'name', 'embedding')

# 2. Luego ranking semántico
ranked = nearby.annotate(
    similarity=CosineDistance(F('embedding'), query_vector)
).order_by('similarity')[:10]
```

### Query Pattern

```sql
-- PostGIS filter + pgvector ranking
SELECT id, name, ST_Distance(location, $1) as dist
FROM landmarks
WHERE ST_DWithin(location, $1, 5000)  -- 5km en metros
ORDER BY embedding <-> $2  -- pgvector cosine distance
LIMIT 10;
```

### Performance Tips
- ✅ **GIST index** en geometry, **HNSW** en embeddings
- ✅ **ST_DWithin** es más rápido que `ST_Distance` con WHERE
- ✅ Limitar bounding box antes de vectorsearch

---

## 🎨 SKILL 2: Atomic Design System

**Objetivo**: Componentes reutilizables, escalables, y mantenibles.

### Estructura Cotton

```
src/templates/cotton/
├── atoms/                      # Elementos puros
│   ├── button.html            # <c-button>
│   ├── input.html             # <c-input>
│   └── icon.html              # <c-icon>
├── molecules/                 # Combos de atoms
│   ├── search_bar.html        # Búsqueda + input
│   ├── card.html              # Card + icon + text
│   └── filter_group.html      # Checkboxes agrupados
└── organisms/                 # Secciones complejas
    ├── map_wrapper.html       # Leaflet + Alpine
    ├── navbar.html            # Logo + nav items
    └── landmark_list.html     # Lista dinámmica
```

### Ejemplo: Atom

```html
<!-- atoms/button.html -->
<button 
  class="px-4 py-2 rounded-lg transition
         bg-indigo-600 hover:bg-indigo-700 
         text-white font-medium"
  {% if disabled %}disabled{% endif %}
>
  {{ label }}
</button>
```

### Ejemplo: Molecule

```html
<!-- molecules/search_bar.html -->
<form 
  hx-get="/search"
  hx-target="#results"
  class="flex gap-2"
>
  {% include "cotton/atoms/input.html" with placeholder="Search landmarks..." %}
  {% include "cotton/atoms/button.html" with label="Search" %}
</form>
```

### Ejemplo: Organism

```html
<!-- organisms/map_wrapper.html -->
<div x-data="mapController()">
  <div id="map" class="w-full h-96"></div>
  
  {% include "cotton/molecules/search_bar.html" %}
  
  <template x-if="selectedLandmark">
    <div class="mt-4 p-4 bg-gray-800 rounded">
      {{ selectedLandmark.name }}
    </div>
  </template>
</div>
```

### Rules
- ✅ **Atoms**: Sin lógica, solo styles
- ✅ **Molecules**: HTMX para data-fetching
- ✅ **Organisms**: Alpine.js para state local
- ❌ **No**: Componentes que no cumplen la jerarquía

---

## ✅ SKILL 3: Geographic & Schema Validation

**Objetivo**: Cero regresiones en modelos espaciales y APIs.

### Geographic Tests

```python
# Validar que puntos están dentro de Euskal Herria
EUSKAL_HERRIA_BBOX = Polygon([
    (-3.5, 42.5), (-1.0, 42.5),
    (-1.0, 43.8), (-3.5, 43.8),
    (-3.5, 42.5)
])

def test_landmark_within_bounds():
    landmark = Landmark.objects.create(
        name="Test",
        location=Point(-2.5, 43.2)  # Bilbao approx
    )
    assert EUSKAL_HERRIA_BBOX.contains(landmark.location)
```

### Schema Validation

```python
# Validar que API devuelve exactamente el schema
from ninja import Schema

class LandmarkOut(Schema):
    id: int
    name: str
    distance_km: float
    category: str

def test_landmark_schema():
    resp = client.get("/api/landmarks/?lat=43.2&lon=-2.9&radius=5")
    data = resp.json()
    assert all(set(item.keys()) == set(LandmarkOut.__fields__.keys()) for item in data)
```

### CSRF Security (django-hosts)

```python
# Verificar que subdominios no filtran tokens CSRF
def test_csrf_isolation():
    # Request desde www.maps.eus
    resp1 = client.get("/login", HTTP_HOST="www.maps.eus")
    csrf1 = resp1.cookies['csrftoken'].value
    
    # No debe funcionar en bidaiak.maps.eus
    resp2 = client.post(
        "/submit",
        {"data": "test"},
        HTTP_HOST="bidaiak.maps.eus",
        HTTP_X_CSRFTOKEN=csrf1
    )
    assert resp2.status_code == 403
```

---

## 🚀 SKILL 4: Ghost Ops Deployment

**Objetivo**: Infraestructura mínima, máxima confiabilidad.

### Dockerfile Multi-stage

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY src/ /app/src/
WORKDIR /app
ENV PATH=/root/.local/bin:$PATH
CMD ["gunicorn", "core.wsgi", "--bind", "0.0.0.0:8000"]
```

### Pre-deploy Checklist

```bash
# Antes de desplegar a Coolify
python manage.py check --deploy
python manage.py migrate --no-input
python manage.py collectstatic --no-input
pytest tests/
```

### Heavy Migrations (Sin downtime)

```python
# Migración pesada en background job
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Ejecutar en horas de bajo tráfico
        heavy_spatial_index_creation()
        self.stdout.write("✅ Heavy migration complete")
```

### Environment Variables (NEVER in repo)

```bash
# .env (gitignore esto)
DATABASE_URL=postgresql://user:pass@host:5432/maps_eus
GEMINI_API_KEY=xxx
DEBUG=False
ALLOWED_HOSTS=www.maps.eus,bidaiak.maps.eus
```

---

## 🗺️ SKILL 5: Domain Orchestration

**Objetivo**: Un core compartido, múltiples apps aisladas.

### Base Model (core)

```python
# src/core/models.py
from django.db import models
from django.contrib.gis.db import models as gis_models

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

# Cada app hereda esto
# src/www/models.py
from core.models import BaseModel

class Landmark(BaseModel):
    location = gis_models.PointField()
    # ...
```

### Subdomain Isolation

```python
# settings.py
PARENT_HOST = 'maps.eus'

HOSTS = {
    'www': {
        'app': 'www',
        'allowed_apps': ['core', 'www'],
    },
    'bidaiak': {
        'app': 'bidaiak',
        'allowed_apps': ['core', 'bidaiak'],
    },
    # ...
}

# Timeouts entre apps
HTTP_TIMEOUT = 3  # segundos
```

### CSS Variables (Branding)

```css
/* src/static/css/branding.css */
:root {
  --color-primary: #6366f1;      /* Indigo */
  --color-accent: #a78bfa;       /* Violet */
  --color-bg: #0b0e14;           /* Dark bg */
  --color-text: #f3f4f6;         /* Light text */
}

/* Cada subdominio puede override */
/* bidaiak.maps.eus */
:root {
  --color-primary: #059669;  /* Green para rutas */
}
```

---

## 📊 Performance Benchmarks

### Target Metrics
- **Landmark search**: < 200ms (100k records)
- **Semantic ranking**: < 500ms (1k results)
- **Page load**: < 2s (with assets)
- **Database query**: < 50ms average

### Measurement

```python
# Usar Django Debug Toolbar en dev
# En producción: APM (Sentry, New Relic)

from django.test import TestCase
from django.test.utils import override_settings
import time

@override_settings(DEBUG=True)
def test_landmark_search_performance():
    start = time.time()
    results = Landmark.objects.filter(
        location__distance_lte=(center, D(km=5))
    ).count()
    elapsed = time.time() - start
    assert elapsed < 0.2, f"Search took {elapsed}s, target < 0.2s"
```

---

## 🎯 Decision Matrix

| Task | Tool | Why |
|------|------|-----|
| Spatial search | PostGIS `ST_DWithin` | Índices GIST, optimizado |
| Semantic ranking | pgvector cosine | Vector DB nativo |
| Real-time data | TimescaleDB hypertables | Series temporales |
| UI components | Atomic Design + Cotton | Escalable, reutilizable |
| Data fetching | HTMX | Sin JS grueso |
| Local state | Alpine.js | Minimal, reactivo |
| Testing | pytest + fixtures | Integración con Django |
| Deployment | Docker + Coolify | Self-hosted, reproducible |

---

**Última actualización**: 2026-04-23
