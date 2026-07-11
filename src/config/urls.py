import os
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from apps.core.api import api
from apps.mubil.urls import api as mubil_api
from django.contrib.sitemaps.views import sitemap
from apps.sbk.sitemaps import SbkCitySitemap, SbkTypeSitemap, SbkStaticSitemap, SbkPersonSitemap
from django.views.generic import TemplateView, RedirectView

# Prefijo/Entorno de Mubil (ENV=estrata o ENV=maps).
env_mode = getattr(settings, 'ENV', os.environ.get('ENV', 'mubil'))

sitemaps = {
    'sbk_cities': SbkCitySitemap,
    'sbk_types': SbkTypeSitemap,
    'sbk_static': SbkStaticSitemap,
    'sbk_people': SbkPersonSitemap,
}


def healthz(request):
    # Cheap liveness probe used by deploy.sh post-up. Intentionally avoids DB
    # access — DB readiness is already gated by compose healthcheck.
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path('healthz/', healthz),
    # Service Worker
    path('sw.js', TemplateView.as_view(template_name="adventure/sw.js", content_type='application/javascript'), name='service_worker'),
]

if env_mode == 'estrata':
    urlpatterns += [
        # Mubil montado en la raíz — va ANTES de core.urls para que su path('')
        # (views.index) tenga prioridad sobre el path('') de core (views.home).
        path('', include('apps.mubil.urls')),
        path('', include('apps.core.urls')),
    ]
else:  # ENV=maps
    urlpatterns += [
        path('', include('apps.core.urls')),
        path('estrata/', include('apps.mubil.urls')),
    ]

# Common patterns
urlpatterns += [
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/', api.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('pintxos/', include('apps.pintxos.urls')),
    path('bidaiak/', include('apps.bidaiak.urls')),
    path('sbk/', include('apps.sbk.urls')),
    path('kultur/', include('apps.kultur.urls')),
    path('inguru/', include('apps.inguru.urls')),
    path('gailur/', include('apps.gailur.urls')),
    path('zbe/', include('apps.zbe.urls')),
    path('adventure/', include('apps.adventure.urls')),
    path('solar/', include('apps.solar.urls')),
    path('oceania/', include('apps.oceania.urls')),
    # NinjaAPI de Mubil bajo /api/mubil/ (no colisiona con la core API en /api/).
    path('api/mubil/', mubil_api.urls),
]

# Redirect de compatibilidad: /{ENV}/ (ej. /estrata/) → /. Solo en modo estrata.
if env_mode == 'estrata':
    urlpatterns += [
        path('estrata/', RedirectView.as_view(url='/', permanent=True)),
    ]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
