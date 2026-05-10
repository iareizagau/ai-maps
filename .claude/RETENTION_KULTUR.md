# Plan de retención — `kultur`

**Objetivo:** convertir Kultur de "tablón anónimo" a producto que la gente revisita. Las palancas concretas son tres: URL shareable (regreso natural), favoritos persistentes (memoria personal entre sesiones) y prefs implícitas (la app aprende sin pedir). Una vez consolidada esa base, el feature **diferenciador** (F9) es el que justifica la existencia de Maps.eus frente a cualquier otra agenda: planes culturales públicos abiertos a la coordinación entre desconocidos, sin construir una red social ni una app de citas.

## Punto de partida (auditado)

- **Auth ya en producción:** `django-allauth` con Google/Instagram/Facebook, modelo `core.User` (extiende `AbstractUser` con `phone`, `bio`, `avatar`).
- **Área de usuario:** [`templates/core/profile.html`](src/templates/core/profile.html) con tabs Alpine (`personal` / `account` / `billing` / `social`) + partials en `core/partials/`. Patrón claro a extender.
- **API:** Django Ninja en [`core/api.py`](src/apps/core/api.py) con routers cross-app (`pintxos`, `inguru`). Kultur **aún no tiene** `api.py` ni endpoints — toca crearlo.
- **Kultur actual:** sin awareness de `request.user`, todos los views son públicos. Todas las features de retención van encima desde cero.
- **Lo que ya tienes invertido:**
  - Helpers `readUrlState` / `writeUrlState` / `applyUrlState` y `loadFavs` / `toggleFav` / `favHeartHtml` ya escritos en [`map_scripts.html`](src/templates/kultur/partials/map_scripts.html), pero **sin cablear**. Quedan como base, no rompen nada.

---

## Modelos a crear (en `apps/kultur/models.py`)

```python
class EventFavorite(models.Model):
    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='kultur_favs')
    event = ForeignKey(CulturalEvent, on_delete=CASCADE, related_name='favorited_by')
    created_at = DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [UniqueConstraint(fields=['user', 'event'], name='uniq_user_event_fav')]
        indexes = [Index(fields=['user', '-created_at'])]


class KulturPrefs(models.Model):
    user = OneToOneField(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='kultur_prefs')
    default_categories = JSONField(default=list)        # ["Concierto", "Teatro"]
    default_moods = JSONField(default=list)             # ["free", "family"]
    default_municipality = CharField(max_length=255, blank=True, default='')
    last_view = JSONField(default=dict)                 # {"lat":..,"lng":..,"z":..}
    digest_enabled = BooleanField(default=True)         # email semanal
    digest_day_of_week = SmallIntegerField(default=3)   # 0=Mon..6=Sun, default jueves
    locale_pref = CharField(max_length=8, blank=True)   # 'es'|'eu'
    updated_at = DateTimeField(auto_now=True)
```

Decisiones tomadas:
- `EventFavorite` y `KulturPrefs` viven en `kultur` (no en `core`). Sigue el principio "Source First": cada dominio dueño de sus datos.
- `unique_together(user, event)` impide duplicados sin lógica aplicación.
- Índice `(user, -created_at)` para listar "mis favoritos" ordenados por recientes — query principal.
- `KulturPrefs` con campos JSONB. Tienes Postgres, son baratos y flexibles. No pasarse: solo lo que es realmente preferencia, no estado.

---

## API (`apps/kultur/api.py` — nuevo)

Patrón existente: módulo crea un `router = Router()`, `core/api.py` lo monta con `api.add_router("/kultur", kultur_router)`.

```python
GET    /kultur/api/favs/                  → [event_id, ...]
POST   /kultur/api/favs/{event_id}/        → 201 / 200 idempotente
DELETE /kultur/api/favs/{event_id}/        → 204
POST   /kultur/api/favs/sync/              → body: [ids] → mergea con existentes (para sync localStorage→DB tras login)
GET    /kultur/api/prefs/                  → KulturPrefs serializado
PATCH  /kultur/api/prefs/                  → partial update
```

Cada endpoint requiere `request.user.is_authenticated`, `401` si no.

---

## Frontend — `map_scripts.html`

### Detección de usuario
Inyectar en `map.html`:
```html
{{ request.user.is_authenticated|json_script:"is-authenticated" }}
```
Y en JS leer `IS_AUTH = JSON.parse(document.getElementById("is-authenticated").textContent)`.

### Dual-storage para favoritos
- `IS_AUTH === false` → `toggleFav` → localStorage (lo ya escrito).
- `IS_AUTH === true` → `toggleFav` → `fetch POST/DELETE /kultur/api/favs/{id}/`. Optimistic UI: se pinta el corazón inmediatamente, si la API falla se revierte con toast.
- **Carga inicial autenticado:** `GET /kultur/api/favs/` antes del primer render.
- **Sync al login (frontend):** detectar `IS_AUTH === true` + `localStorage.kultur:favs` no vacío → `POST /kultur/api/favs/sync/` con los ids → vaciar localStorage.

### URL state — cablear los hooks ya escritos
Llamar `writeUrlState()` en:
- `setCategory`, `setDate`, `applyDayFilter`, custom range, `toggleMood`, `updateSearch`, `syncSearch`
- `map.on("moveend", ...)` (debounced ya internamente)
- `marker.on("popupopen")` → `openEventId = fid` + write
- `marker.on("popupclose")` → `openEventId = null` + write
- `openVenueSheet` → `openVenueKey = key` + write
- `closeVenueSheet` → `openVenueKey = null` + write

`applyUrlState(readUrlState())` antes del primer `renderMapAndList`. Si la URL trae `view`, NO ejecutar el `fitBounds` inicial — usar `map.setView(...)`.

### Prefs como defaults
Si autenticado y URL no trae filtros: tras `applyUrlState`, `fetch /kultur/api/prefs/` y mergear lo que falte (cat, moods, municipality, view). Cambios subsiguientes → debounced `PATCH /kultur/api/prefs/` con el último estado.

---

## Página "Mi cultura" en el área de usuario

Patrón: nuevo tab Alpine en [`templates/core/profile.html`](src/templates/core/profile.html), siguiendo el mismo estilo que `personal` / `account` / etc.

```html
<button @click="tab = 'kultur'" ...>{% trans "Mi cultura" %}</button>

<div x-show="tab === 'kultur'">
  {% include 'core/partials/kultur_tab.html' %}
</div>
```

Vista en `core/views.py profile()` precarga `kultur_favs = request.user.kultur_favs.select_related('event__venue').order_by('event__start_date')` y `kultur_prefs = getattr(request.user, 'kultur_prefs', None)`.

`kultur_tab.html` muestra:
1. **Header:** count de favoritos + último vistos
2. **Próximos (timeline):** cards con thumbnail / fecha / venue / link al mapa con `?event=<id>` (deeplink F1)
3. **Pasados (collapsable):** los que ya ocurrieron (histórico, valor sentimental)
4. **Preferencias:** form simple con los campos `KulturPrefs` (igual estética que el profile_form actual)

---

## Plan por fases — costes estimados

| Fase | Qué | Coste | Depende |
|---|---|---|---|
| **F1** | URL state shareable: cablear hooks + apply on load + setView vs fitBounds | 0.5 día | nada |
| **F2** | Modelos `EventFavorite` + `KulturPrefs` + migrations | 0.25 día | nada |
| **F3** | API Ninja kultur: favs CRUD + prefs PATCH + sync | 0.5 día | F2 |
| **F4** | Frontend dual-storage favs + UI hearts en card / popup / venue sheet + mood "Favoritos" | 0.5 día | F3 |
| **F5** | Prefs implícitas: cargar al login, escribir al cambiar filtros | 0.25 día | F3 |
| **F6** | Tab "Mi cultura" en `/profile/` con timeline + form prefs | 1 día | F2-F4 |
| **F7** | Email digest semanal (celery beat task + plantilla + unsubscribe) | 1.5 días | F2 |
| **F8** | Reminder 24h antes de evento favorito (celery beat) | 0.5 día | F7 |
| **F4+** | *(bonus social light)* "Quién que sigues va a esto" reusando `core.Follow` | 1 día | F2-F4 |
| **F9** | **Diferenciador** — Planes públicos abiertos (coordinación entre desconocidos) | 1 sprint | F2-F4 |

**Mínimo viable de retención (F1-F6):** ~3 días repartidos.
**Retención completa con outreach por email (F1-F8):** ~5 días.
**Producto diferenciado (F1-F9):** ~2-3 semanas para llegar a un Maps.eus que **nadie más hace**.

---

## F4+ — Bonus social light: "Quién que sigues va a esto"

Es la dosis mínima de socialidad **sin construir red social ni app de citas**. Aprovecha que [`core.Follow`](src/apps/core/models.py) ya existe (modelo `(follower, followed, app_context)`).

### Modelo

Sin tabla nueva. Sigue siendo `EventFavorite` de F2; solo añadimos consultas.

### UI

En la card del evento y en el popup del marker, mostrar:

```text
"Ane y Mikel también van"  (si N≤3)
"Ane y 4 más"              (si N>3)
```

Con avatares mini si los tiene. Click en el chip → ver lista completa de follows que han marcado el evento.

### Endpoint

`GET /kultur/api/events/{event_id}/following-going/` → lista de `(user.username, avatar)` de gente que el `request.user` sigue (en cualquier `app_context`) y que tiene el evento como favorito.

### Por qué funciona sin masa crítica

No depende de matches estadísticos. Si sigues a 5 personas, basta con que 1 vaya al mismo evento para que veas valor. La señal es alta porque tus follows **ya son una decisión consciente** (no random matching).

### Pega

Si nadie usa el "follow" de la app, F4+ no se ve. Mitigable: en el tab "Mi cultura" añadir un CTA *"Sigue a alguien para descubrir sus planes"* → linkea al search-users existente del profile.

---

## F9 — Diferenciador: Planes culturales públicos

**Esta es la respuesta correcta a "Tinder cultural" sin sus problemas** (cold start, liability, mismatch de intent). El **plan** es el primary citizen, las personas son secundarias.

### Cómo se ve

Cualquier usuario autenticado publica un plan asociado a un evento existente:

> *"Voy al concierto de Mikel Erentxun el sábado en el Kursaal. Sobra una entrada gratis. Plan tranquilo, paso por Tabakalera antes a tomar algo."*  
> Cupos: 1 · Estado: abierto

Otras personas piden unirse → el creador acepta o rechaza → se notifica por email (sin chat propio).

### Modelos (en `apps/kultur/models.py`)

```python
class CulturalPlan(models.Model):
    creator = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='kultur_plans')
    event = ForeignKey(CulturalEvent, on_delete=CASCADE, related_name='plans')
    message = TextField(max_length=500, blank=True)
    max_seats = PositiveSmallIntegerField(default=1)         # 1..N huecos
    is_open = BooleanField(default=True)                     # creator can close
    visibility = CharField(choices=[('public','Public'),('followers','Followers only')], default='public')
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        indexes = [Index(fields=['event', '-created_at']), Index(fields=['creator', '-created_at'])]


class PlanRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELED = 'canceled'

    plan = ForeignKey(CulturalPlan, on_delete=CASCADE, related_name='requests')
    requester = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='plan_requests')
    message = TextField(max_length=300, blank=True)
    status = CharField(max_length=16, choices=[...], default=STATUS_PENDING)
    created_at = DateTimeField(auto_now_add=True)
    decided_at = DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [UniqueConstraint(fields=['plan', 'requester'], name='uniq_plan_requester')]
```

### API

```http
GET    /kultur/api/plans/?event_id=&from=&to=&visibility=    → lista paginada
POST   /kultur/api/plans/                                     → crea plan
PATCH  /kultur/api/plans/{plan_id}/                           → cierra/abre, edita message
DELETE /kultur/api/plans/{plan_id}/                           → cancela
POST   /kultur/api/plans/{plan_id}/requests/                  → pedir unirse
PATCH  /kultur/api/plans/{plan_id}/requests/{request_id}/     → accept/reject (solo creator)
DELETE /kultur/api/plans/{plan_id}/requests/{request_id}/     → cancel (solo requester)
```

### Interacciones (UI)

- En la **card del evento** (sidebar y popup del mapa): chip *"3 planes abiertos"* si hay → click abre bottom-sheet con la lista.
- En el **bottom-sheet del venue**: pestaña adicional "Planes" junto a "Eventos".
- Botón **"Crear un plan"** en la card de cada evento (solo si autenticado).
- Tab **"Mis planes"** en `/profile/` (`kultur_tab.html`): los que creé y los que pedí unirme con su estado.
- Notificación por email al creator cuando alguien pide unirse, y al requester cuando le aceptan/rechazan.

### Por qué es Tinder hecho bien (lo que evita)

- **Asimetría rompe cold start.** 1 plan publicado puede atraer N usuarios. No necesitas dos personas activas en la misma intersección rara.
- **Intent explícito y acotado.** El plan dice qué (evento), cuándo (la fecha del evento), dónde (la ubicación del venue), cuántos (max_seats). Sin la ambigüedad emocional de matching ciego.
- **Liability acotada.** El encuentro es público (un concierto, un museo) en una fecha y lugar ya programados, no un café privado. Reduce drásticamente la responsabilidad operacional.
- **Sin chat propio.** La coordinación pasa por mensaje del plan + email de notificación. No construyes un producto-chat dentro del producto.
- **Aprovecha lo que ya tienes.** Eventos geocodificados (F-Venue), favoritos (F4), tab de área usuario (F6).

### Riesgos identificados

- **Spam / fake plans:** rate-limit por user (max 3 plans abiertos simultáneos al inicio); reporting + soft-delete + ban manual. Suficiente al principio.
- **No-shows:** registro discreto del ratio de planes-cumplidos por user; expuesto opcional al creator antes de aceptar ("este usuario ha cumplido 4/5 planes").
- **Privacidad:** opción `visibility='followers'` — plan solo visible para gente que el creator sigue, para usuarios que prefieren grupos cerrados.
- **Moderación:** terms claros + flag de reporte → cola admin. Suficiente hasta tener volumen.

### Decisiones para arrancar F9

1. **¿Permitir invitar a follows directamente?** (sin pasar por "request"). Mi voto: sí, agiliza para grupos cercanos.
2. **¿Visibilidad por defecto?** `public` o `followers`. Mi voto: `public`, modo abierto por defecto invita a participar.
3. **¿Edad mínima?** Si los eventos pueden ser nocturnos / con bebida, conviene un check 18+ en el plan request. Implica añadir `birth_date` a `core.User`.
4. **¿Tracking de cumplimiento?** Para el "ratio cumplidos" hace falta un step "el plan se cumplió" después del evento (creator confirma). Trabajo extra. Decidir si vale el ROI inicial.

### Por qué F9 al final y no antes

F9 sin F1-F6 es una app vacía: necesitas usuarios autenticados con favoritos publicando planes en eventos que ya descubren via mapa. Es **el techo** del producto, no la base. Si lo construyes antes de tener tracción, no hay quién publique ni quién se una.

---

## Decisiones pendientes (resolver antes de codificar F2)

1. **Permitir favoritos sin login** — ¿sí o no? Mi voto: **sí** (localStorage), reduce fricción y se hereda al loguearse vía `/favs/sync/`. Confirmar.
2. **Backend de email** — ¿Anymail con qué provider (Postmark, Mailgun, SES)? ¿O SMTP plano? Bloquea F7.
3. **Locale del digest** — ¿usar `KulturPrefs.locale_pref`, o el `user.language` global, o el `LANGUAGE_CODE` del último request guardado? Mi voto: campo dedicado en `KulturPrefs`, sobreescribible.
4. **Política de URL muy larga** — si user activa muchos favs y el flag favs en URL serializa todos → URL >2KB. Acotar o hashear. Mi voto: solo serializar IDs cuando el mood "favs" esté activo, hasta máximo 50 ids; si más, mostrar warning UI.
5. **Multi-tab race** — si user tiene 2 pestañas y favorita en una, ¿la otra refresca al cambiar tab? `storage` event de localStorage para anónimos, refetch on `visibilitychange` para autenticados. Lo dejo para F4.

---

## Métricas para validar

- **F1:** % de visitas que llegan via URL con querystring (compartidas) vs raíz limpia. Mira en analytics el referrer.
- **F4:** ratio `usuarios con ≥1 favorito / usuarios totales`. Apuntar a >20% en 4 semanas.
- **F5:** retorno de usuarios con prefs guardadas vs sin (mide impacto de la personalización implícita).
- **F7:** open rate del digest, CTR a deeplinks. <15% de open rate → mata la cadencia o el contenido.

---

## Lo que NO entra en este plan (deliberadamente fuera)

- **Notificaciones push PWA** — necesita service worker + permisos + infra de push. ROI peor que email digest mientras no tengas masa crítica.
- **Recap mensual** — bonito, pero baja prioridad. Después de F7.
- **Compartir favoritos vía URL pública (`/u/<username>/favs/`)** — feature social, no de retención. Después.
- **Aprendizaje real (recomendaciones)** — eso es la fase de pgvector que dejamos en el otro plan; no es retención, es diferenciación.

---

## Próximo paso cuando retomemos

Antes de tocar código, resolver las **5 decisiones pendientes** de arriba. Especialmente la #2 (backend de email) bloquea F7. Para arrancar F1-F6 basta con resolver #1 y #4.

Si solo tenemos 1 sesión: hacer F1 + F2 + F3 + F4 (el corazón funciona, los favs persisten, la URL se comparte). Eso ya es **retención mínima viable** sin gastar en infra de email.
