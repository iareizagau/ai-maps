# Ejemplos de Uso - Claude Code Workflow

**Cómo pedir cosas a Claude. Ejemplos reales que funcionan bien.**

## Ejemplo 1: Crear un Modelo Espacial

### ❌ Mal
```
"Crea un modelo Landmark"
```

### ✅ Bien
```
"En el dominio www, necesito crear un modelo Landmark que represente 
lugares de interés en Euskal Herria.

Estructura:
- name: CharField (max_length=200)
- description: TextField (opcional)
- location: PointField (PostGIS)
- category: CharField con choices (natural, cultural, gastro, otro)
- created_at: DateTimeField (auto_now_add)

Necesito:
- Modelo Django con GeoDjango
- Migración automática
- Admin registrado
- Test que cree un Landmark y valide la ubicación

¿Propuesta de cómo estructurarlo?"
```

**Por qué es mejor**:
- ✅ Específico (qué campos exactamente)
- ✅ Contexto (para qué sirve)
- ✅ Requisitos (tests, admin)
- ✅ Pide validación antes (¿propuesta?)

---

## Ejemplo 2: Crear una Función Espacial Compleja

### ❌ Mal
```
"Busca landmarks cercanos"
```

### ✅ Bien
```
"En www, necesito una función de búsqueda de Landmarks cercanos.

Requisitos:
- Input: latitude, longitude, radius_km
- Output: Lista de Landmarks ordenados por distancia (cercano primero)
- Performance: Debe completarse en <200ms para 100k registros
- Usar PostGIS ST_DWithin (no ST_Distance)

Casos de test:
1. Sin resultados (radio vacío)
2. Con resultados (múltiples landmarks)
3. Límite de radio (exactamente en el borde)
4. Input inválido (lat fuera de rango)

¿Propuesta de ORM query + test structure?"
```

**Por qué es mejor**:
- ✅ Requisitos funcionales claros
- ✅ Performance mencionado
- ✅ Casos de test explícitos
- ✅ Tecnología específica (ST_DWithin)

---

## Ejemplo 3: Refactor de Código Existente

### ❌ Mal
```
"El código es lento, optimiza"
```

### ✅ Bien
```
"En bidaiak/views.py, la función list_routes() está lenta.

Síntomas:
- Tarda 2 segundos en listar 1000 rutas
- CPU usa 80%, DB queries son N+1

Contexto:
- Estamos usando RouteSerializer con nested LocationSerializer
- Cada ruta tiene ~10 ubicaciones
- Usuarios típicos buscan <100 rutas a la vez

¿Podrías:
1. Diagnosticar con Django Debug Toolbar queries
2. Sugerir optimizaciones (select_related, prefetch_related)
3. Mostrar antes/después de performance
4. Incluir test de performance?"
```

**Por qué es mejor**:
- ✅ Síntomas específicos (no 'lento')
- ✅ Contexto (qué causa el problema)
- ✅ Enfoque (select_related no solo 'optim')

---

## Ejemplo 4: Debuggear un Error

### ❌ Mal
```
"No funciona"
```

### ✅ Bien
```
"En pytest, este test falla en bidaiak/tests/test_models.py:

    def test_route_distance_calculation():
        start = Point(43.2631, -1.9732)  # Bilbao
        end = Point(43.3012, -1.4735)    # Donostia
        route = Route.objects.create(
            name='Bilbao-Donostia',
            start_point=start,
            end_point=end
        )
        assert route.distance_km < 100

Error que sale:
    AttributeError: 'Route' object has no attribute 'distance_km'

He intentado:
1. Agregar property @distance_km en el modelo (falla en migrations)
2. Usar method en lugar de property

¿Cuál es la forma correcta en Django GeoDjango?"
```

**Por qué es mejor**:
- ✅ Stack trace específico
- ✅ Lo que intentaste
- ✅ Lo que esperas

---

## Ejemplo 5: Feature Request con Contexto

### ❌ Mal
```
"Agrega autenticación"
```

### ✅ Bien
```
"Necesito autenticación en www.maps.eus.

Contexto:
- SaaS para usuarios finales (solopreneur business model)
- Necesito guardar 'mis landmarks favoritos'
- Usuarios anónimos = no pueden guardar
- Desplegado en Coolify (auto-hospedado)

Requisitos:
- Login/Signup básico (email/password)
- Token JWT para API mobile (futura)
- Integration con Django admin (manage users)
- Email verification (básico, sin terceros)

Restricciones:
- Mantener simple (no OAuth3 por ahora)
- Integrar con PostGIS (usuario puede tener rol spatial: viewer/editor)

¿Propuesta de librería (django-rest-auth vs custom) y estructura?"
```

**Por qué es mejor**:
- ✅ Business context (solopreneur, SaaS)
- ✅ Requisitos funcionales
- ✅ Restricciones técnicas
- ✅ Pide opinión experta

---

## Ejemplo 6: Pedir Aprendizaje / Explicación

### ❌ Mal
```
"Explica PostGIS"
```

### ✅ Bien
```
"Explica cómo PostgreSQL + PostGIS manejan índices espaciales 
para búsquedas de proximidad.

Específicamente:
1. Diferencia entre índices GIST vs BRIN
2. Cuándo usar ST_DWithin vs ST_Intersects
3. Ejemplo: 10k landmarks, buscar todos a <5km de un punto
   - ¿Qué índice crear?
   - ¿Qué query escribir?
   - ¿Rendimiento esperado?

Quiero entenderlo para poder optimizar mis queries en el futuro."
```

**Por qué es mejor**:
- ✅ Específico (no genérico)
- ✅ Aplicable a tu caso (landmarks, 10k registros)
- ✅ Actionable (qué índice, qué query)

---

## Plantilla Rápida

Copia esta plantilla para peticiones nuevas:

```
**Dominio**: [www/bidaiak/pintxos/sbk/kultur]
**Tipo**: [feature/bug/refactor/learning]

**Qué necesito**:
[Descripción 1 línea]

**Contexto/Por qué**:
[Por qué es importante, qué problema resuelve]

**Requisitos técnicos**:
- [Req 1]
- [Req 2]
- [Restricción 1]

**Casos de éxito/test**:
- [Test 1]
- [Test 2]

**¿Propuesta?**
[Preguntar si no sabe cómo empezar]
```

---

## 📋 Checklist Antes de Pedir

- [ ] Especifique dominio (www, bidaiak, etc.)
- [ ] Tipo de tarea (feature, bug, refactor)
- [ ] Detalle técnico (campos, queries, endpoints)
- [ ] Contexto (por qué, cuándo, para quién)
- [ ] Restricciones (performance, tests, compliance)
- [ ] Ejemplos/casos de test si es posible
- [ ] Pida validación (¿propuesta?, ¿está bien?)

---

**Mejor petición = Mejor resultado. Tómate 2 minutos extra.**
