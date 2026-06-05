from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from apps.core.api import api
from apps.mubil.urls import api as mubil_api
from django.contrib.sitemaps.views import sitemap
from apps.sbk.sitemaps import SbkCitySitemap, SbkTypeSitemap, SbkStaticSitemap, SbkPersonSitemap
from django.views.generic import TemplateView

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
    # Auth
    path('', include('apps.core.urls')),
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/', api.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

urlpatterns += [
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
    # The mubil API is mounted at the top level so its NinjaAPI namespace
    # (`mubil_api`) stays un-nested — see comment in apps/mubil/urls.py.
    path('estrata/api/', mubil_api.urls),
    path('estrata/', include('apps.mubil.urls')),
]
if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
