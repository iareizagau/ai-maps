# Project Review - Maps.eus

**Revisión completa del estado actual del proyecto.**

Fecha: 2026-04-23 | Estado: 🟡 Prototipo Funcional

---

## 📊 Resumen Ejecutivo

| Aspecto | Estado | Nota |
|--------|--------|------|
| **Estructura Django** | ✅ Excelente | Django 6, geodjango, sqlite/postgres ready |
| **Arquitectura Subdominios** | ✅ Configurada | django-hosts correcto, 5 dominios listos |
| **Base de Datos** | 🟡 Incompleto | PostGIS + pgvector + TimescaleDB listos en config, sin modelos aún |
| **Frontend** | 🟡 Placeholder | Templates creados, componentes Cotton vacíos |
| **Modelos** | 🟡 Mínimo | Solo User custom, sin modelos de negocio |
| **APIs** | ⚠️ No existe | Django Ninja instalado, sin endpoints |
| **Tests** | ❌ No existe | Pytest no instalado, sin tests |
| **Deployment** | 🟡 Ready | Docker multi-stage correcto, Coolify ready |

---

## 📁 Estructura del Proyecto

```
.
├── .claude/                    ✅ Setup completo (22 archivos)
├── .env                        ✅ Configurado (básico)
├── .gitignore                  ✅ Correcto
├── Dockerfile                  ✅ Multi-stage, optimizado
├── docker-compose.yml          ✅ PostGIS + pgvector ready
├── requirements.txt            ✅ Dependencias core
└── src/
    ├── manage.py               ✅ Django management
    ├── config/
    │   ├── settings/
    │   │   ├── base.py         ✅ Bien estructurado
    │   │   ├── local.py        ✅ Desarrollo
    │   │   └── prod.py         ✅ Producción
    │   ├── hosts.py            ✅ 5 subdominios configurados
    │   ├── urls.py             ✅ Root urlconf
    │   ├── wsgi.py             ✅ WSGI app
    │   └── asgi.py             ✅ ASGI app (Django 6 async)
    ├── apps/
    │   ├── core/
    │   │   ├── models.py       🟡 Solo User custom
    │   │   ├── views.py        ✅ Existe (vacío)
    │   │   ├── api.py          ✅ Existe (vacío)
    │   │   └── apps.py         ✅ Config
    │   ├── bidaiak/            ✅ Rutas (skeleton)
    │   ├── pintxos/            ✅ Gastro (skeleton)
    │   ├── sbk/                ✅ Eventos (skeleton)
    │   └── kultur/             ✅ Agenda (skeleton)
    └── templates/
        └── cotton/
            ├── atoms/          🟡 Vacíos
            ├── molecules/      🟡 Vacíos
            └── organisms/      ❌ No existen
```

---

## ✅ Lo Que Está Bien

### 1. Django 6 Setup
- ✅ Base settings bien estructurada (base, local, prod)
- ✅ Environment variables con `django-environ`
- ✅ Django Hosts configurado correctamente (5 subdominios)
- ✅ Custom User model en core
- ✅ GIS backend (PostGIS) configurado

### 2. Arquitectura de Subdominios
```python
# config/hosts.py - Correcto
host_patterns = patterns(
    '',
    host(r'www', settings.ROOT_URLCONF, name='www'),
    host(r'bidaiak', 'apps.bidaiak.urls', name='bidaiak'),
    host(r'pintxos', 'apps.pintxos.urls', name='pintxos'),
    host(r'sbk', 'apps.sbk.urls', name='sbk'),
    host(r'kultur', 'apps.kultur.urls', name='kultur'),
)
```
Cada subdominio es independiente, comparten `core`.

### 3. Dockerfile
- ✅ Multi-stage (BUILD + RUNTIME)
- ✅ Dependencias del sistema para GIS (gdal, proj, postgis)
- ✅ Python 3.12-slim
- ✅ Sin hardcode de secrets

### 4. Configuración de Dependencias
```
django>=6.0a1
django-hosts              ✅ Subdominios
django-cotton            ✅ Atomic Design
django-ninja             ✅ APIs modernas
django-environ           ✅ Variables
django-extensions        ✅ Management commands
django-leaflet           ✅ Mapas
psycopg[binary]          ✅ PostgreSQL driver
whitenoise               ✅ Static files
```

Nota: Faltan `pygis`, `pgvector`, `TimescaleDB` en requirements.txt (pero están en docker-compose)

---

## 🟡 Lo Que Falta (Medio Plazo)

### 1. Modelos de Negocio
**Estado**: 🟡 No existen

```python
# Lo que necesita src/apps/core/models.py:
class BaseModel(models.Model):
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

# En www/models.py:
class Landmark(BaseModel):
    name = CharField(max_length=200)
    location = PointField()  # PostGIS
    category = CharField(choices=[...])
    embedding = VectorField(dimensions=768)  # pgvector

# En bidaiak/models.py:
class Route(BaseModel):
    name = CharField()
    start_point = PointField()
    end_point = PointField()
    geom = LineStringField()
```

### 2. APIs (Django Ninja)
**Estado**: ❌ No existen

```python
# core/api.py debería tener:
from ninja import NinjaAPI

api = NinjaAPI(version='1.0')

# En cada app:
@router.get('/landmarks/', response=list[LandmarkOut])
def list_landmarks(request, lat: float, lon: float, radius: int = 5):
    # Hybrid spatial-semantic search
    pass
```

### 3. Frontend - Componentes Cotton
**Estado**: 🟡 Vacíos

Estructura existe:
```
src/templates/cotton/
├── atoms/                  ← Buttons, Inputs (vacíos)
├── molecules/              ← SearchBar, Cards (vacíos)
└── organisms/              ← Navbar, MapWrapper (no existe)
```

Necesita:
- Atoms: button.html, input.html, icon.html
- Molecules: search_bar.html, landmark_card.html
- Organisms: map_wrapper.html, navbar.html

### 4. Tests
**Estado**: ❌ No instalado pytest

```bash
pip install pytest pytest-django pytest-cov
```

Tests necesarios:
- [ ] PostGIS geometry tests
- [ ] API schema tests
- [ ] CSRF isolation (django-hosts)
- [ ] Subdomain routing

---

## ⚠️ Issues & Recomendaciones

### 1. Missing Requirements
**Problema**: `requirements.txt` incompleto

```diff
  django>=6.0a1
+ django-gis-helpers  # Para queries PostGIS comunes
+ pgvector           # Embeddings
+ django-ratelimit  # Rate limiting APIs
+ pytest-django     # Testing
+ faker            # Fixtures
```

### 2. settings/base.py - apps.agents?
**Problema**: Línea 39 en settings

```python
INSTALLED_APPS = [
    ...
    'apps.core',
    'apps.agents',  # ⚠️ ¿Por qué esto aquí?
]
```

**Acción**: Eliminar `apps.agents` (ya no existe, fue .agents/)

### 3. Falta .gitignore en requirements.txt
Debería ignorar: `.venv/`, `*.pyc`, `.env.local`, etc.

Verifica: `.gitignore` existe y está bien

### 4. docker-compose.yml
**Estado**: ✅ Parece correcto, pero hay que validar:
- [ ] Variables de conexión PostGIS
- [ ] Puertos expuestos (5432, 8000)
- [ ] Volúmenes para persistencia

---

## 🚀 Plan Recomendado (Próximas 2 Semanas)

### Week 1: Foundation
- [ ] Arreglar `settings/base.py` - eliminar `apps.agents`
- [ ] Completar `requirements.txt` (pgvector, pytest, etc.)
- [ ] Crear `BaseModel` en `core/models.py`
- [ ] Crear primer modelo: `Landmark` (www)
- [ ] Migración y test básico

### Week 2: APIs & Frontend
- [ ] Endpoints CRUD para Landmark (Django Ninja)
- [ ] Componentes Cotton básicos (Atom, Molecule)
- [ ] Search endpoint (spatial + semantic)
- [ ] Tests unitarios

### Week 3: Integración
- [ ] Frontend + API integration
- [ ] Leaflet map rendering
- [ ] Error handling y validación
- [ ] Documentation

---

## 🔧 Setup Local (Para Desarrollar)

```bash
# 1. Clone y entra
cd maps-eus
python -m venv .venv
source .venv/bin/activate

# 2. Instala dependencies
pip install -r requirements.txt
pip install pytest pytest-django

# 3. Setup DB
python src/manage.py migrate
python src/manage.py createsuperuser

# 4. Run dev server
python src/manage.py runserver

# 5. Access
# www.maps.eus.local:8000 (localhost hack en /etc/hosts)
# admin: 127.0.0.1:8000/admin
```

### Docker Alternative
```bash
docker-compose up
# PostgreSQL en :5432
# Django en :8000
```

---

## 📝 Checklist: ¿Proyecto Listo?

- [x] Django 6 setup correcto
- [x] Subdominios configurados
- [x] Dockerfile optimizado
- [x] .claude/ documentation
- [ ] Modelos de negocio básicos
- [ ] APIs funcionando
- [ ] Frontend componentes
- [ ] Tests
- [ ] Deployment validado

**Status**: 🟡 Prototipo 40% listo

---

## 🎯 Próximo Paso

**Especifica qué haces primero**:

Opción A: Crear primer modelo (Landmark)
Opción B: Crear APIs (endpoints)
Opción C: Frontend componentes
Opción D: Tests setup

Yo recomiendo: **Opción A → B → C → D** (en ese orden)

---

**Última actualización**: 2026-04-23
