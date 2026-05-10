from .base import *

DEBUG = False
DEFAULT_HOST = 'default'

# Coolify / Production settings
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Security (Disabled for now to avoid redirect loops without SSL)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
