import os
from pathlib import Path
import environ

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is src/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file (try multiple locations for local vs docker)
ENV_FILE = os.path.join(BASE_DIR.parent, '.env') # Local
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(BASE_DIR, '.env') # Docker / Alternative

if os.path.exists(ENV_FILE):
    environ.Env.read_env(ENV_FILE)

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['.maps.eus', 'localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    'django_hosts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django.contrib.gis',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    # 3rd party
    'django_cotton',
    'django_extensions',
    'ninja',
    'django_celery_beat',
    'anymail',
    
    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.instagram',
    'allauth.socialaccount.providers.facebook',

    # Local apps
    'apps.core',
    'apps.pintxos',
    'apps.kultur',
    'apps.sbk',
    'apps.inguru',
    'apps.gailur',
    'apps.zbe',
    'apps.adventure',
    'apps.solar',
    'apps.oceania',
    'apps.mubil',
]

MIDDLEWARE = [
    'django_hosts.middleware.HostsRequestMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_hosts.middleware.HostsResponseMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'
ROOT_HOSTCONF = 'config.hosts'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
                'django.template.context_processors.i18n',
                'apps.core.context_processors.app_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL')
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# Auth
AUTH_USER_MODEL = 'core.User'
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Adjust as needed

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    },
    'instagram': {
        'SCOPE': ['user_profile'],
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'INIT_PARAMS': {'cookie': True},
        'FIELDS': [
            'id',
            'first_name',
            'last_name',
            'name',
            'email',
            'picture',
            'short_name',
        ],
        'VERIFIED_EMAIL': False,
        'VERSION': 'v19.0',
        'OAUTH_PKCE_ENABLED': True,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'eu'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('eu', 'Euskara'),
    ('es', 'Español'),
    ('en', 'English'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR.parent / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = 'home'

# Weather APIs
EUSKALMET_API_KEY = env('EUSKALMET_API_KEY', default='')
OPENWEATHERMAP_API_KEY = env('OPENWEATHERMAP_API_KEY', default='')

# Mubil — Gemini (embeddings gemini-embedding-001 @768d + generation gemini-3.5-flash).
# Obtener gratis en https://aistudio.google.com/app/apikey
# Note: text-embedding-004 was deprecated late 2025; gemini-embedding-001 replaces
# it. Native dim is 3072 with MRL — embeddings.py passes output_dimensionality=768
# via the google-genai SDK to keep the existing VectorField(dimensions=768) schema.
# Generation uses gemini-3.5-flash (newest Flash GA as of 2026-05); previous
# default gemini-2.5-flash was free-tier-throttled to 20 RPD, useless for demos.
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_EMBEDDING_MODEL = env('GEMINI_EMBEDDING_MODEL', default='gemini-embedding-001')
GEMINI_GENERATION_MODEL = env('GEMINI_GENERATION_MODEL', default='gemini-3.5-flash')

# Ordered fallback ladder for generation. The advisor RAG iterates this list
# on quota / temp-unavailable / not-found / empty-completion so a depleted
# bucket or safety filter on one model doesn't blank the demo. Order has
# been tuned live: pick by *expected wall-clock to a usable answer*, not
# RPD alone — a model with 1.5K RPD that returns empty in 25 s is worse
# than one with 500 RPD that returns the answer in 3 s.
#
#   - gemini-3.1-flash-lite :   500 RPD, ~3 s answers, citation-friendly
#                               (FIRST: lots of headroom + verified quality
#                               on the demo prompts).
#   - gemini-2.5-flash-lite :    20 RPD, ~3 s answers.
#   - gemini-3-flash        :    20 RPD.
#   - gemini-3.5-flash      :    20 RPD, newest Flash GA.
#   - gemini-2.5-flash      :    20 RPD, oldest, usually drained first.
#   - gemma-4-26b-a4b-it    : 1.5K RPD but observed empty completions on
#                             Spanish gov-policy prompts (safety filter).
#                             Kept as last-resort overflow.
#   - gemma-4-31b-it        : 1.5K RPD shared bucket — overflow companion.
# Names verified against client.models.list() on 2026-05-29.
# Override via env to pin a single model end-to-end.
GEMINI_GENERATION_FALLBACK_MODELS = env.list(
    'GEMINI_GENERATION_FALLBACK_MODELS',
    default=[
        'gemini-3.1-flash-lite',
        'gemini-2.5-flash-lite',
        'gemini-3-flash',
        'gemini-3.5-flash',
        'gemini-2.5-flash',
        'gemma-4-26b-a4b-it',
        'gemma-4-31b-it',
    ],
)

# Mubil — ESIOS (Red Eléctrica) for PVPC hourly prices, indicator 1001.
# Token obtained via email to consultasios@ree.es; sent in `x-api-key` header.
ESIOS_TOKEN = env('ESIOS_TOKEN', default='')

# Mubil — OpenChargeMap, weekly refresh of EV charging POIs for the EH bbox.
# Free key, instant signup at https://openchargemap.org/site/develop/api .
# Sent in the `X-API-Key` header. Empty → weekly cron logs a warning and noops
# so a missing key never crashes the demo.
OPENCHARGEMAP_API_KEY = env('OPENCHARGEMAP_API_KEY', default='')

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://redis:6379/1')
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 30  # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 25
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Email & Anymail (Brevo)
ANYMAIL = {
    "BREVO_API_KEY": env("BREVO_API_KEY", default=""),
}
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Maps.eus <noreply@maps.eus>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
