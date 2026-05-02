# Maps.eus - Claude Development Guide

**Tu guía para trabajar eficientemente con Claude Code en este proyecto.**

## 📍 Información Rápida

- **Proyecto**: SaaS Maps - Ecosistema GIS modular para Euskal Herria
- **Stack**: Django 6 + PostGIS + pgvector + HTMX/Alpine
- **Estructura**: Monorepo con subdominios (www, bidaiak, pintxos, sbk, kultur)
- **Solopreneur mode**: Maximizar automatización, minimizar deuda técnica

## 🎯 Arquitectura Principal

### Capas
```
src/
├── core/              # Kernel compartido (modelos, utilidades)
├── www/               # Landing + Global Search
├── bidaiak/           # Routes (Sub-dominio)
├── pintxos/           # Gastro (Sub-dominio)
├── sbk/               # Events (Sub-dominio)
└── kultur/            # Agenda (Sub-dominio)
```

### Pilares de Diseño
1. **Source First**: Todo código en `src/`, nada en raíz excepto config
2. **Atomic UI**: Componentes Cotton siguiendo Atomic Design (Atom → Molecule → Organism)
3. **Geo-Integrity**: PostGIS es fuente de verdad espacial (4326/3857)
4. **Data Semantics**: pgvector para embeddings, TimescaleDB para series temporales

## 🔧 Patrones Técnicos

### PostGIS
- **Índices**: Siempre `GIST` para campos geometry
- **Queries**: Preferir `ST_DWithin` sobre `ST_Distance` (rendimiento)
- **Proyecciones**: EPSG:4326 (almacenamiento) → 3857 (display web)

### Django ORM
- Usar `django.contrib.gis.db.models` para modelos espaciales
- Modelos simples (Point, LineString, Polygon)
- Integrar con GeoEuskadi + OSM cuando sea aplicable

### Frontend
- HTMX para interactividad sin JS grueso
- Alpine.js para state local
- Evitar JavaScript framework completo

## 📋 Cuando Pidas Ayuda

Especifica el **contexto**:
- ¿Qué dominio? (www, bidaiak, etc.)
- ¿Qué tipo de tarea? (feature, bug, refactor, test)
- ¿Restricciones? (performance, compliance, deadline)

**Ejemplo bueno**:
> "En bidaiak, necesito agregar un campo `departure_time` a Route model. Requiere migración, actualizar API, y tests."

**Ejemplo vago**:
> "Arregla el frontend"

## 🚀 Flujo de Trabajo Recomendado

1. **Antes de empezar**: Lee `.claude/PROJECT_STATE.md` para contexto
2. **Especifica claramente**: Qué cambios, por qué, dónde
3. **Iteración**: Claude te propone cambios, tú validas y ejecutas
4. **Termina**: Commit con mensaje descriptivo

## 📚 Referencias Rápidas

| Documento | Propósito |
|-----------|-----------|
| [TECHNICAL_RUNBOOK.md](TECHNICAL_RUNBOOK.md) | Core skills: búsqueda híbrida, atomic design, deployment, tests |
| [PROJECT_STATE.md](PROJECT_STATE.md) | Estado actual (infraestructura, dominios, tareas) |
| [DECISIONS.md](DECISIONS.md) | Por qué cada decisión técnica |
| [MEMORY.md](MEMORY.md) | Índice de memoria persistente |
| [MIGRATION_FROM_AGENTS.md](MIGRATION_FROM_AGENTS.md) | Cómo migramos desde .agents/ |

---

**Última actualización**: 2026-04-23
