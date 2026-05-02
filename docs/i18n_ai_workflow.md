# Flujo de Internacionalización (I18n) Asistido por IA

Este documento describe el flujo de trabajo estándar ("Smart I18n Pipeline") para gestionar las traducciones en el proyecto **Maps.eus**. Utiliza las herramientas de Django para la extracción y compilación de cadenas, y se apoya en un Agente de IA para automatizar la laboriosa tarea de la traducción.

---

## Paso 1: Extracción Inteligente (`makemessages`)

Extrae las nuevas cadenas de texto del código fuente sin contaminar los archivos `.po` con traducciones de librerías externas o entornos virtuales.

Ejecuta el siguiente comando DOCKER COMPOSE en la raíz del proyecto:

```bash
docker compose exec web python manage.py makemessages -l es -l eu -l en -i venv -i node_modules --no-wrap
```

**Explicación de las banderas (flags):**
- `-l es -l eu -l en`: Genera o actualiza los archivos para Castellano, Euskera e Inglés.
- `-i venv -i node_modules`: Ignora directorios pesados que no pertenecen a nuestro código fuente.
- `--no-wrap`: Evita que las líneas largas se dividan. Facilita enormemente que la IA lea y parsee el archivo de forma correcta.

---

## Paso 2: Traducción Automática (Prompting)

En lugar de rellenar los `msgstr` a mano o usar editores visuales, pídele al Agente de IA (Antigravity u otro LLM) que lo haga por ti utilizando este **Prompt Estándar**:

> **Prompt para la IA:**
> 
> "He ejecutado el comando `makemessages` y se han actualizado mis archivos `.po` en `src/locale/`.
> Quiero que leas el archivo `src/locale/[IDIOMA_OBJETIVO]/LC_MESSAGES/django.po` y lo traduzcas completo.
> 
> Reglas críticas que debes seguir:
> 1. Actúa como un traductor profesional experto en aplicaciones web y cultura gastronómica del País Vasco.
> 2. Mantén exactamente la estructura del archivo `.po` original. No modifiques ni elimines los encabezados, ni los comentarios de ruta (ej. `#: apps/pintxos/models.py:23`).
> 3. Traduce únicamente el contenido de `msgid` y colócalo en `msgstr`.
> 4. Respeta variables y etiquetas HTML (ej. `%(provider_name)s`, `{{ user.username }}`). Deben quedar idénticas en la traducción.
> 5. Para el **Euskera (eu)**, utiliza un vocabulario natural, unificado (Batua) pero cercano. Utiliza términos gastronómicos locales (ej. *pintxoa*, *txokoa*, *Alde Zaharra*).
> 6. Para el **Castellano (es)**, utiliza un tono amigable e informal (tratar de 'tú').
> 
> Cuando termines, sobrescribe el archivo `.po` completo con tu resultado."

*(Nota: Cambia `[IDIOMA_OBJETIVO]` por `eu`, `es` o `en` según corresponda, o pídele que haga todos secuencialmente).*

---

## Paso 3: Revisión y Compilación (`compilemessages`)

Una vez la IA haya sobrescrito los archivos `.po`, es **obligatorio** compilarlos para que Django genere los `.mo` (archivos binarios que lee el servidor) y aplique los cambios.

```bash
docker compose exec web python manage.py compilemessages
```

Si todo ha ido bien, no verás errores en la consola y las nuevas traducciones estarán disponibles al recargar el navegador.

---

## Consejos Adicionales

- **Archivos JavaScript**: Si en el futuro añades cadenas traducibles directamente dentro de archivos `.js` externos, deberás ejecutar una pasada adicional indicando el dominio: 
  `docker compose exec web python manage.py makemessages -d djangojs -l es -l eu -l en -i venv -i node_modules --no-wrap`
- **Etiquetas en Django**: Recuerda usar siempre `{% trans "Texto" %}` en los templates y `gettext_lazy('Texto')` en Python (`models.py`, `forms.py`, etc.) para que el `makemessages` detecte las cadenas inicialmente.
