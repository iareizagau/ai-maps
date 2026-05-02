# Configuración de Google Auth con Django Allauth

Este documento detalla los pasos necesarios para configurar la autenticación de Google en el proyecto Maps.eus utilizando Docker.

## 1. Google Cloud Console

1.  Ve a [Google Cloud Console](https://console.cloud.google.com/).
2.  Crea un nuevo proyecto o selecciona uno existente.
3.  **Pantalla de consentimiento de OAuth**:
    *   Configura el "User Type" (normalmente "External" para pruebas).
    *   Añade los datos de la aplicación y tu email de soporte.
    *   En "Scopes", añade `.../auth/userinfo.email` y `.../auth/userinfo.profile`.
4.  **Credenciales**:
    *   Haz clic en "Crear credenciales" -> "ID de cliente de OAuth".
    *   Tipo de aplicación: **Aplicación web**.
    *   Nombre: `Maps.eus Local`.
    *   Orígenes de JavaScript autorizados: `http://localhost:8000`.
    *   URIs de redireccionamiento autorizados: `http://localhost:8000/accounts/google/login/callback/`.
5.  Copia el **Client ID** y el **Client Secret**.

## 2. Django Admin Setup

1.  Inicia el proyecto: `docker compose up -d`.
2.  Accede a `http://localhost:8000/admin/`.
3.  **Sitios (Sites)**:
    *   Ve a la sección "Sites".
    *   Edita el sitio existente (normalmente con ID 1).
    *   Domain name: `localhost:8000`.
    *   Display name: `Maps Local`.
4.  **Aplicaciones Sociales (Social Applications)**:
    *   Añade una nueva aplicación.
    *   Provider: `Google`.
    *   Name: `Google Login`.
    *   Client id: (Pega el ID de Google).
    *   Secret key: (Pega el Secret de Google).
    *   Sites: Selecciona `localhost:8000` y muévelo a "Chosen sites".

## 3. Pruebas

1.  Ve a `http://localhost:8000/accounts/login/`.
2.  Deberías ver un enlace para entrar con Google.
3.  Al hacer clic, te redirigirá a Google para autorizar la cuenta.

---

## Comandos Útiles

*   **Reconstruir contenedores**: `docker compose build`
*   **Ejecutar migraciones**: `docker compose exec web python manage.py migrate`
*   **Crear superusuario**: `docker compose exec web python manage.py createsuperuser`
