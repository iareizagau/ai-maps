# Plan de crecimiento — `sbk`

**Objetivo:** convertir SBK Hub de "mapa con eventos" en un agregador con tráfico orgánico real y revenue medible. La tesis es doble: (1) cada **click de afiliado** que dejamos sobre la mesa por no rendir UX es dinero perdido, ya estamos midiendo eso desde 2026-05-10; (2) el verdadero apalancamiento no es construir más features dentro del mapa, sino **multiplicar las superficies SEO** (páginas por ciudad, por tipo, "esta noche", directorios de personas) para que Google indexe queries long-tail concretas. La referencia competitiva es [bachatacalendar.co.uk](https://www.bachatacalendar.co.uk/) — un solo nicho (Bachata + Londres), pero ~14 superficies SEO distintas en sitemap.

## Punto de partida (auditado)

- **Stack y data:** Django 6 + PostGIS + HTMX. Modelo `Event` con `lat/lng`, `event_type` (festival/party/workshop), `primary_style`, `city`, `country`, `ticket_url`, `price_info`. Carga vía `load_sbk_events` desde feed GoAndDance.
- **Mapa:** [`templates/sbk/pages/home/map.html`](src/templates/sbk/pages/home/map.html) con Leaflet, sidebar de cards, filtros por tipo/estilo/fecha. Cards se renderizan client-side desde [`api/events/`](src/apps/sbk/views.py) JSON.
- **Auth:** allauth global a nivel `core`. SBK tiene flujo "Pasaporte Bailador" con XP, streaks, check-ins, vibe reports, matchmaking (roommate/dance partner) — feature potente pero **enterrada** dentro del modal de comunidad por evento.
- **Monetización ya cableada (2026-05-10):**
  - `Event.ticket_clicks` (`PositiveIntegerField`, default=0).
  - Vista [`ticket_redirect`](src/apps/sbk/views.py) en `/sbk/go/<event_id>/`, atomic con `F('ticket_clicks') + 1`.
  - Botón **`🎟 Entrada`** (gradient esmeralda) + badge de precio en cards y popup del mapa, sólo si `ticket_url` existe.
  - Admin con columna `ticket_clicks` ordenable y filtro `has_ticket_url` para detectar eventos sin afiliado.
  - URLs afiliadas vienen pre-tagged desde GoAndDance (no hace falta wrapper de inyección).
- **URLs hoy:** `/`, `/api/events/...`, `/pasaporte/`, `/go/<id>/`. **Cero superficies SEO específicas** — todo el tráfico cae en la home.
- **Lo que ya tienes invertido sin cablear:**
  - Modelo de datos rico (DanceProfile, EventReview, EventNotice, CheckIn, VibeReport) — base sobrada para directorios de personas y reputación.
  - El feed de GoAndDance ya trae `address`, `city`, `country` por evento — todas las páginas de ciudad son auto-generables.

---

## Análisis competitivo: bachatacalendar.co.uk

Stack inferido (del HTML shell, no se pudo renderizar JS): Vite + React + Supabase + TanStack Query + framer-motion. Tipografía **Fraunces** (serif premium). Tema oscuro #141519 default.

**Sitemap = mapa de oportunidades SEO** (extraído de `/sitemap.xml`):

| URL | Función | Aplicabilidad SBK |
|---|---|---|
| `/parties`, `/classes`, `/festivals` | Vertical por tipo de evento | ✅ Aliases del mapa con filtro pre-aplicado |
| `/tonight` | Solo eventos de hoy | ✅ Trivial, gran retorno SEO ("bailar bachata hoy donostia") |
| `/cities` + `/city/<slug>` | Landing por ciudad | ✅ Auto-generable desde `Event.city` |
| `/venues` | Directorio de salas | ⏳ Requiere modelo `Venue` (hoy es texto libre en `Event.address`) |
| `/teachers`, `/djs`, `/organisers`, `/dancers`, `/videographers` | Directorios de personas | ⏳ Requiere modelo `Person`/`Profile` con roles |
| `/practice-partners` | Matchmaking dedicado | ✅ Ya tienes la lógica enterrada en modal — solo promover |
| `/discounts` | Códigos descuento | ⏸️ Premature sin relaciones con organizadores |
| `/event/<uuid>?occurrenceId=<uuid>` | Evento canónico + ocurrencias | ⚠️ Requiere refactor de modelo de datos |

**Modelo de monetización detectado** (de fuentes externas):
- Afiliados de tickets — igual que tú, ya cableado.
- **Sorteos de ~14 tickets/semana** — captación viral, organizadores ceden tickets a cambio de visibilidad.
- **Códigos descuento** — eje paralelo, posible revenue por placement.
- **Newsletter** como activo central de retención.
- Chat comunitario "sin censura" — moat de retención (descartado para nosotros, ver decisiones).

---

## Fase 1 — SEO foundations (esta semana, ~4h)

Tres páginas thin que multiplican el number of indexed surfaces sin tocar arquitectura. Todas reusan `map.html` con contexto distinto.

### 1.1 — `/sbk/esta-noche/` (urgencia)

```python
# apps/sbk/views.py
def tonight_view(request):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    count = Event.objects.filter(
        start_date__date__gte=today,
        start_date__date__lt=tomorrow,
        moderation_status__in=['pending', 'verified'],
    ).count()
    return render(request, 'sbk/pages/home/map.html', {
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY,
        'page_filter': 'tonight',
        'page_title': 'Eventos de bachata, salsa y kizomba esta noche',
        'page_h1': f'{count} eventos esta noche',
        'meta_description': f'{count} eventos SBK esta noche en Euskal Herria. Festivales, socials y talleres con entradas disponibles.',
    })
```

Frontend: `map.html` lee `page_filter` y, si es `'tonight'`, hace `setDate('today')` en el `init()` JS y oculta el filtro de fecha. Indicador en navbar con dot rojo pulsante cuando `count > 0`.

**SEO:** `<title>` y `<meta description>` server-rendered con cuenta dinámica. Schema.org `ItemList` opcional fase 2.

### 1.2 — `/sbk/festivales/`, `/sbk/socials/`, `/sbk/talleres/` (vertical por tipo)

Una sola vista parametrizada:

```python
TYPE_CONFIG = {
    'festivales': {'type': EventType.FESTIVAL, 'h1': 'Festivales SBK', 'meta': 'Calendario de festivales...'},
    'socials':    {'type': EventType.PARTY,    'h1': 'Socials y fiestas', 'meta': '...'},
    'talleres':   {'type': EventType.WORKSHOP, 'h1': 'Talleres y bootcamps', 'meta': '...'},
}

def type_view(request, type_slug):
    cfg = TYPE_CONFIG.get(type_slug)
    if not cfg:
        raise Http404
    return render(request, 'sbk/pages/home/map.html', {
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY,
        'page_filter': cfg['type'],
        'page_h1': cfg['h1'],
        'meta_description': cfg['meta'],
    })
```

URLs: `path('<slug:type_slug>/', type_view, name='type')` — pero ojo orden, debe ir **después** de las rutas literales (`pasaporte/`, `esta-noche/`, `go/...`) o capturará todo.

### 1.3 — `/sbk/ciudad/<slug>/` (landing local)

Hoy `Event.city` es CharField libre. Para slugs estables:

```python
# Nuevo helper
from django.utils.text import slugify

def city_view(request, city_slug):
    # Match case-insensitive contra slug normalizado
    events = Event.objects.filter(
        moderation_status__in=['pending', 'verified'],
        end_date__gte=timezone.now() - timedelta(days=1),
    )
    matches = [e for e in events if slugify(e.city or '') == city_slug]
    if not matches:
        raise Http404
    canonical_city = matches[0].city
    avg_lat = sum(float(e.lat) for e in matches if e.lat) / len([e for e in matches if e.lat])
    avg_lng = sum(float(e.lng) for e in matches if e.lng) / len([e for e in matches if e.lng])
    return render(request, 'sbk/pages/home/map.html', {
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY,
        'page_filter': f'city:{city_slug}',
        'initial_center': [avg_lat, avg_lng],
        'initial_zoom': 12,
        'page_h1': f'Eventos SBK en {canonical_city}',
        'meta_description': f'{len(matches)} eventos próximos en {canonical_city}: festivales, socials y talleres de bachata, salsa y kizomba.',
    })
```

**Sitemap dinámico** (`apps/sbk/sitemaps.py` — nuevo):

```python
class SbkCitySitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        # Solo ciudades con ≥3 eventos próximos (umbral anti-página-vacía)
        from django.db.models import Count
        return (Event.objects
                .filter(end_date__gte=timezone.now())
                .values('city')
                .annotate(c=Count('id'))
                .filter(c__gte=3, city__isnull=False)
                .exclude(city=''))

    def location(self, item):
        return reverse('sbk:city', args=[slugify(item['city'])])
```

Registrar en `config/urls.py` global. Mismo patrón aplica a `SbkTypeSitemap` y `SbkTonightSitemap`.

**Decisiones tomadas en Fase 1:**
- **No fragmentar la app:** todas las páginas SEO son aliases del mapa. Una sola UX, una sola codebase. La diferenciación es server-side (title, h1, meta, contexto inicial).
- **Threshold de 3 eventos** para generar página de ciudad — evita páginas semivacías que dañan SEO.
- **Sin migración de datos:** se trabaja sobre el `Event.city` text-libre actual. Cuando crezca el catálogo, se puede normalizar a un modelo `City` con FK, pero hoy es premature.
- **Indicador "esta noche" en navbar** sólo se computa si el navbar templates lo necesita — no añadir context processor global hasta que valga la pena (cache implícito de fragment Django si se vuelve hot).

---

## Fase 2 — Foundation para crecer (próximas 2-4 semanas, condicionada a señal SEO)

**No empezar Fase 2 sin esperar 2-3 semanas de Fase 1.** Si Search Console no muestra impresiones crecientes en las nuevas URLs, el problema no es falta de superficies — es otra cosa (autoridad de dominio, contenido, geo). Construir directorios sin tráfico es construir un cementerio.

### 2.1 — Directorios de personas (`Person` con roles)

El verdadero moat de bachatacalendar: cada DJ/profe/organizador comparte su perfil → backlinks orgánicos gratis.

```python
class Person(models.Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = CharField(max_length=255)
    slug = SlugField(max_length=255, unique=True)
    bio = TextField(blank=True)
    photo = ImageField(upload_to='sbk/people/', blank=True, null=True)
    instagram = CharField(max_length=100, blank=True)
    country = CharField(max_length=100, blank=True)
    city = CharField(max_length=100, blank=True)

    ROLES = [('dj', 'DJ'), ('teacher', 'Teacher'), ('organizer', 'Organizer'),
             ('dancer', 'Dancer'), ('videographer', 'Videographer')]
    roles = ArrayField(CharField(max_length=20, choices=ROLES), default=list)

    # Claim flow
    claimed_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True)
    is_verified = BooleanField(default=False)
```

`Event.djs = M2M(Person)`, `Event.teachers = M2M(Person)`, `Event.organizer = FK(Person, null=True)`.

URLs: `/sbk/djs/`, `/sbk/profes/`, `/sbk/organizadores/` (índice) + `/sbk/persona/<slug>/` (detalle).

**Decisión a tomar antes de implementar:** ¿modelo único `Person` con `roles=ArrayField` (recomendado, flexible, una sola tabla) o tablas separadas `Dj`/`Teacher`/`Organizer` (más explícito, joins más claros)? Recomiendo `Person` único — los roles se solapan en el dominio (un DJ que también es profe es muy común).

**Claim flow:** una persona aparece automáticamente cuando se la asocia a un evento. El admin puede luego permitir que la persona reclame su perfil con auth. Sin claim, perfil mínimo (solo nombre + eventos asociados).

### 2.2 — Modelo de eventos recurrentes

Hoy: 1 Event = 1 fecha. "Jueves Salsero en The Host" semanal = 52 filas/año duplicadas, fragmenta reviews/checkins.

Patrón bachatacalendar (canónico):

```python
class Event(models.Model):
    # ... campos canónicos sin start_date/end_date
    is_recurring = BooleanField(default=False)
    recurrence_rule = CharField(max_length=255, blank=True)  # iCalendar RRULE

class EventOccurrence(models.Model):
    event = ForeignKey(Event, on_delete=CASCADE, related_name='occurrences')
    start_date = DateTimeField()
    end_date = DateTimeField(null=True, blank=True)
    cancelled = BooleanField(default=False)
    override_venue = CharField(max_length=255, blank=True)  # cambio puntual

    class Meta:
        indexes = [Index(fields=['event', 'start_date'])]
        constraints = [UniqueConstraint(fields=['event', 'start_date'], name='uniq_occurrence')]
```

**Migración:** convertir cada Event existente a `Event + EventOccurrence(start=Event.start_date)`. Mantener `Event.start_date` deprecated unos meses para no romper queries existentes, luego retirarlo. Backfill data migration.

**Beneficio SEO:** una URL canónica acumula reviews, checkins, vibes durante meses → mejor ranking que 52 URLs huérfanas.

**Coste:** 4-6h. Es la decisión más cara de este plan, pero la deuda crece exponencial con el catálogo.

### 2.3 — `/sbk/practica/` (matchmaking promovido)

Ya tienes `UserEvent.looking_for_dance_partner` y `looking_for_roommate`. Hoy enterrado en modal por evento. Sacarlo a página propia:

```python
def practice_view(request):
    seekers = UserEvent.objects.filter(
        looking_for_dance_partner=True,
        event__end_date__gte=timezone.now(),
    ).select_related('user', 'event').order_by('event__start_date')
    # Agrupar por ciudad para que sea browsable
    return render(request, 'sbk/pages/practice.html', {'seekers': seekers})
```

Filtros: ciudad, estilo, próximos 30 días. Sin features nuevas — solo superficie distinta sobre datos existentes.

---

## Fase 3 — Parking lot (NO hacer ahora)

Cada item lleva la condición concreta para activarlo, no fechas.

| Feature | Por qué no ahora | Cuándo activar |
|---|---|---|
| **`/sbk/descuentos/`** — agregador de códigos | Sin relaciones con organizadores, página vacía es señal mala | ≥10 organizadores con afiliado activo + alguno dispuesto a dar código |
| **Sorteos semanales de tickets** | Operación pesada (email + sorteo + entrega + fraud-prevention). Requiere relación organizador. | Cuando los `ticket_clicks` actuales den ≥500 clicks/mes consistentes (datos para negociar) |
| **Chat comunitario** | Coste moderación brutal para un solopreneur | **Nunca dentro de la app**. Crear grupo Telegram/WhatsApp Community público y linkar desde navbar. Externaliza el problema. |
| **Modelo `Venue` normalizado** | Hoy `address` es texto libre y suficiente | Cuando haya >100 eventos en la misma ciudad (entonces dedup de venues = ahorro real) |
| **Tipografía premium (Fraunces)** | Diferenciador real, pero no urgente | Próximo refresh visual general (no antes) |

---

## Métricas de éxito

**Fase 1 (medible en 2-4 semanas):**
- Search Console: impresiones en URLs `/sbk/ciudad/*`, `/sbk/esta-noche/`, `/sbk/{festivales,socials,talleres}/`. Target: ≥100 impresiones/semana en alguna de ellas.
- `Event.ticket_clicks` total semanal — comparar baseline (semana del 2026-05-10 con sólo home) vs. semanas posteriores.

**Fase 2 (medible en 2-3 meses):**
- Páginas de personas indexadas en Google (`site:maps.eus/sbk/persona/`).
- Backlinks orgánicos a perfiles (Search Console → Links).
- Para recurrentes: número de reviews/checkins por evento canónico (debe crecer vs. el modelo fragmentado).

**Anti-métrica (señal de overengineering):**
- Si Fase 1 no genera tráfico SEO en 6 semanas, **no construir Fase 2**. Significa que el problema es otro (autoridad de dominio, contenido escaso, mercado pequeño) y más superficies sólo aumentan complejidad.

---

## Decisiones explícitas

**Qué SÍ haremos:**
- Multiplicar superficies SEO server-side reusando `map.html`.
- Mantener stack actual (HTMX/Django/Cotton). Cero JS framework.
- Indexar todas las superficies vía sitemap dinámico con threshold anti-página-vacía.
- Esperar señal de Fase 1 antes de invertir en Fase 2.

**Qué NO haremos (y por qué):**
- **No SPA.** Tu stack es el correcto para solopreneur. bachatacalendar paga el coste de SPA con un equipo, tú no puedes.
- **No chat propio.** Telegram/WhatsApp gratis hacen el trabajo sin moderación.
- **No `/discounts/` sin organizadores.** Construir contenedores vacíos daña SEO y confianza.
- **No sorteos sin tracción demostrada.** Sin datos no negocias tickets gratis con organizadores.
- **No directorios sin esperar señal SEO.** Cementerio de páginas indexed sin tráfico = anti-SEO.
- **No top-converting API endpoint todavía.** El admin con `ticket_clicks` ordenable ya da la misma info, sin código nuevo. Endpoint sale en 10 min cuando exista consumidor real (email marketing, sección destacados).

---

**Última actualización:** 2026-05-10