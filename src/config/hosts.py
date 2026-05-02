from django.conf import settings
from django_hosts import patterns, host

if settings.DEBUG:
    # Development: use path-based routing (localhost/pintxos/, localhost/bidaiak/, etc.)
    host_patterns = patterns(
        '',
        host(r'localhost', 'config.urls', name='localhost'),
        host(r'127\.0\.0\.1', 'config.urls', name='localhost-ip'),
    )
else:
    # Production: use subdomain-based routing
    host_patterns = patterns(
        '',
        host(r'www', settings.ROOT_URLCONF, name='www'),
        host(r'bidaiak', 'apps.bidaiak.urls', name='bidaiak'),
        host(r'pintxos', 'apps.pintxos.urls', name='pintxos'),
        host(r'sbk', 'apps.sbk.urls', name='sbk'),
        host(r'kultur', 'apps.kultur.urls', name='kultur'),
        host(r'inguru', 'apps.inguru.urls', name='inguru'),
    )
