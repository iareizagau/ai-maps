from django.conf import settings
from django_hosts import patterns, host

# Path-based routing for now (every host falls through to config.urls, which
# mounts each app at /<slug>/). When we move to subdomains, replace this with
# per-host routing: host(r'pintxos', 'apps.pintxos.urls', ...), etc.
host_patterns = patterns(
    '',
    host(r'.*', settings.ROOT_URLCONF, name='default'),
)
