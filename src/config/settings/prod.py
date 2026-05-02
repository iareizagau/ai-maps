from .base import *

DEBUG = False
DEFAULT_HOST = 'ai'

# Coolify / Production settings
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Security
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
