from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from apps.core.api import api

urlpatterns = [
    # Auth
    path('', include('apps.core.urls')),
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/', api.urls),
]

urlpatterns += [
    path('pintxos/', include('apps.pintxos.urls')),
    path('bidaiak/', include('apps.bidaiak.urls')),
    path('sbk/', include('apps.sbk.urls')),
    path('kultur/', include('apps.kultur.urls')),
    path('inguru/', include('apps.inguru.urls')),
]
if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
