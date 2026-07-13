# Plan de Resolución de Errores de Ruff (Linting)

Al ejecutar `make lint-fix` (que invoca `uv run ruff check . --fix`), se han corregido los errores seguros automáticamente. Sin embargo, todavía quedan **962 errores**. A continuación se detalla la planificación para abordarlos de forma estructurada, categorizada por tipo de error y prioridad.

## Análisis de Errores Restantes (Top 10)

| Código | Frecuencia | Descripción | Estrategia de Resolución |
| :--- | :--- | :--- | :--- |
| **E501** | 427 | `line-too-long` | La mayoría son consultas SQL o cadenas largas. **Plan**: Ejecutar `make format` (`ruff format`). Si no resuelve el problema en consultas embebidas, añadiremos `E501` al bloque `ignore` de `[tool.ruff.lint]` en `pyproject.toml` (o lo aumentaremos a 120 caracteres), ya que el código en Python moderno a menudo favorece legibilidad sobre un límite estricto de 88 caracteres. |
| **RUF012** | 227 | `mutable-class-default` | Común en clases o variables por defecto mutables. **Plan**: Revisar. Si es en modelos de Django/Tipos, añadir `typing.ClassVar` en las variables de clase, o añadir RUF012 al `ignore` de `pyproject.toml` temporalmente si requiere un refactor mayor del código existente. |
| **W291** / **W293** | 112 | `trailing-whitespace` y `blank-line-with-whitespace` | **Plan**: Se pueden arreglar automáticamente ejecutando `uv run ruff check . --fix --unsafe-fixes` o mediante el formateador (`make format`). |
| **E402** | 43 | `module-import-not-at-top-of-file` | Generalmente sucede en scripts de prueba (ej. `django.setup()` que requiere ser ejecutado antes de los imports de los modelos). **Plan**: Añadir comentarios `# noqa: E402` o excluir los tests del check `E402` en la configuración de `pyproject.toml`. |
| **RUF002** / **RUF003** | 43 | `ambiguous-unicode-character` | Caracteres no estándar en comentarios (ej. tildes mal codificadas, espacios irrompibles). **Plan**: Corregir automáticamente con `--unsafe-fixes`. |
| **RUF059** | 16 | `unused-unpacked-variable` | Variables desempaquetadas que no se usan (ej. `a, b = func()`). **Plan**: Cambiar los nombres de las variables no usadas por `_`. `--unsafe-fixes` o fix seguro puede abordarlo. |
| **DJ001** | 12 | `django-nullable-model-string-field` | Campos CharField/TextField en Django con `null=True, blank=True`. **Plan**: Eliminar `null=True` manualmente, ya que Django usa `""` (string vacío) por defecto en base de datos para campos de texto. |
| **C408** | 11 | `unnecessary-collection-call` | Uso de `dict()` en lugar de `{}`. **Plan**: `--unsafe-fixes` lo corregirá automáticamente. |
| **DJ012** | 9 | `django-unordered-body-content-in-model` | Métodos `__str__` o clase `Meta` fuera de orden convencional en modelos Django. **Plan**: Se puede corregir usando fix inseguro o simplemente moviendo los métodos `Meta` debajo de los campos y el `__str__` después. |
| **Resto (Varios)** | ~62 | Miscelánea (variables no usadas, imports no usados `F401`, class names `N801`). | **Plan**: Abordarlos de forma manual y sistemática bloque por bloque. |

## Plan de Acción (Siguientes Pasos)

1. **Paso 1: Aplicar Autocorrecciones y Formato (Fácil victoria)**
   - Ejecutar `make format` para corregir las líneas y espacios que se puedan.
   - Ejecutar `uv run ruff check . --fix --unsafe-fixes` para que Ruff arregle automáticamente todos los `W291`, `W293`, `C408`, `RUF002` y otros que sabe corregir pero que por precaución no aplica por defecto.

2. **Paso 2: Ajuste en la Configuración (`pyproject.toml`)**
   - Para no bloquear el CI, podemos relajar el estricto `E501` ignorando `E501` si consideramos que no aporta valor o aumentaremos el límite `line-length`.
   - Ignorar `E402` explícitamente en el directorio de `src/test/` donde se requiere el `django.setup()` antes de importar los módulos de base de datos.

3. **Paso 3: Refactorización Manual de Django (DJ001, DJ012, RUF012)**
   - Modificar modelos de Django buscando y corrigiendo los CharFields/TextFields nulos (`null=True, blank=True`).
   - Aplicar `ClassVar` a las propiedades de clase en modelos/formularios donde RUF012 es alertado, o decidir ignorar la regla globalmente.

¿Te parece bien el plan? ¿Quieres que empiece a ejecutar el **Paso 1** y **Paso 2** para reducir drásticamente esta lista de errores de inmediato?
