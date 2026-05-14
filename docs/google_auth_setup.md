# Configuración de Google Auth con Django Allauth

Setup idempotente: las credenciales viven en `.env` (local) y `.env.prod` (VPS).
El comando `init_oauth` crea/actualiza el `Site` y el `SocialApp` automáticamente
en cada deploy, así que un wipe de DB no rompe el login.

## 1. Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto o selecciona uno existente.
3. **Pantalla de consentimiento de OAuth**:
   - "User Type": External (para pruebas).
   - Email de soporte y datos de la app.
   - Scopes: `.../auth/userinfo.email` y `.../auth/userinfo.profile`.
4. **Credenciales** → "Crear credenciales" → "ID de cliente de OAuth":
   - Tipo: **Aplicación web**.
   - Orígenes JS autorizados:
     - Local: `http://localhost:9000`
     - Prod: `https://ai.maps.eus`
   - URIs de redirección:
     - Local: `http://localhost:9000/accounts/google/login/callback/`
     - Prod: `https://ai.maps.eus/accounts/google/login/callback/`
5. Copia el **Client ID** y el **Client Secret**.

## 2. Variables de entorno

Añade a tu `.env` (local) y `.env.prod` (VPS):

```bash
# Local
SITE_DOMAIN=localhost:9000
SITE_NAME=Maps Local
GOOGLE_OAUTH_ID_CLIENTE=...
GOOGLE_OAUTH_SECRET_KEY=...

# Prod
SITE_DOMAIN=ai.maps.eus
SITE_NAME=Maps
GOOGLE_OAUTH_ID_CLIENTE=...
GOOGLE_OAUTH_SECRET_KEY=...
```

## 3. Aplicar

```bash
# Local
docker compose exec web python manage.py init_oauth

# Prod (se ejecuta solo en cada deploy via scripts/deploy.sh)
```

El comando es idempotente: puedes correrlo tantas veces como quieras.

## 4. Probar

1. Ve a `http://localhost:9000/accounts/login/` (o el dominio de prod).
2. Click en "Sign in with Google".
3. Autoriza la cuenta en Google y vuelves logueado.

## Restaurar tras un wipe de DB

Solo: `docker compose exec web python manage.py init_oauth`. Las credenciales se
recrean a partir del `.env`. No hace falta entrar al admin.
