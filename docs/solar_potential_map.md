# Propuesta Detallada: Mapa de Potencial Solar 3D

Este documento detalla la arquitectura, funcionalidades y flujo de datos para la aplicación de **Mapa de Potencial Solar 3D**, integrando herramientas de visualización avanzada, bases de datos geoespaciales e inteligencia artificial.

## 1. Visión General
La aplicación permite a los usuarios visualizar el potencial de generación fotovoltaica de cualquier edificio en una ciudad, utilizando modelos 3D reales para considerar sombras proyectadas, inclinación de cubiertas y orientación geográfica.

---

## 2. Arquitectura Tecnológica

### A. Visualización (Frontend)
*   **Leaflet**: Base cartográfica interactiva.
*   **OSM Buildings**: Renderizado de edificios en 3D/2.5D. Permite visualizar las sombras en tiempo real según la posición del sol, lo cual es crítico para que el usuario entienda el impacto de edificios colindantes.
*   **UI Dinámica**: Paneles laterales con gráficos de generación mensual (Chart.js) y estimación de ahorros económicos.

### B. Análisis Espacial (PostGIS)
*   **Geometría de Cubiertas**: Extracción de huellas de edificios desde OSM.
*   **Cálculos Geográficos**:
    *   `ST_Area`: Superficie disponible para paneles.
    *   `ST_Azimuth`: Orientación del tejado (esencial para determinar la eficiencia).
    *   **Inclinación (Slope)**: Si se dispone de datos LIDAR (PNOA en España) o etiquetas `roof:shape`, se calcula la pendiente óptima.

### C. Estimación de Generación (PVGIS API)
Utilizaremos el servicio oficial de la Comisión Europea, **PVGIS**, para obtener datos precisos de radiación histórica.
*   **API**: `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`
*   **Parámetros clave**:
    *   `lat` / `lon`: Ubicación exacta.
    *   `angle`: Inclinación del tejado (obtenida de PostGIS o valor por defecto).
    *   `aspect`: Orientación (0=Sur, 90=Oeste, -90=Este) calculada con `ST_Azimuth`.
    *   `peakpower`: Capacidad instalada estimada según el área del tejado.
    *   `mountingplace`: "building" para considerar pérdidas por temperatura.
*   **Resultado**: Generación anual estimada en kWh, desglose mensual y variabilidad interanual.

### D. Inteligencia y Similitud (pgVector)
*   **Perfiles de Edificios**: Almacenar vectores de características (superficie, orientación, sombras promedio, consumo estimado del barrio).
*   **Recomendaciones**: "Encontrar edificios similares que ya han instalado paneles" para mostrar casos de éxito cercanos y realistas.
*   **Búsqueda Semántica**: "Edificios con tejados planos de más de 200m2 en el centro".

### E. Logística Comercial (pgRouting)
*   **Planificación de Visitas**: Una vez identificados los edificios con mayor potencial (Top 10 de una zona), generar la ruta óptima para un agente comercial o técnico instalador utilizando la red de calles de OSM.

---

## 3. Flujo de Datos

1.  **Ingesta**: Descarga de datos de **Geofabrik** e importación a **PostGIS**.
2.  **Pre-procesado**: Cálculo de orientación y área útil para cada edificio.
3.  **Consulta PVGIS**: El backend realiza peticiones a la API de PVGIS y cachea los resultados para evitar latencia (respetando el límite de 30 req/seg).
4.  **Enriquecimiento**: Generación de embeddings con OpenAI o modelos locales y almacenamiento en **pgVector**.
5.  **Entrega**: API REST/GraphQL que sirve los GeoJSON de los edificios con sus metadatos de potencial solar.

---

## 4. Beneficios del Enfoque 3D
A diferencia de los mapas 2D tradicionales, el uso de **OSM Buildings** permite:
*   Visualizar **obstrucciones** de edificios más altos que proyectan sombras.
*   Mostrar al usuario una representación **realista** de su vivienda/negocio, aumentando la confianza en el sistema.
*   Ajustar la inclinación de la cámara para inspeccionar visualmente la cubierta antes de una visita técnica.

---

## 5. Próximos Pasos de Implementación
1.  Configurar un contenedor Docker con **PostgreSQL + PostGIS + pgVector**.
2.  Importar un extracto de ciudad pequeña (ej: San Sebastián o Bilbao) desde Geofabrik.
3.  Crear un script de Python que conecte con la API de PVGIS y pueble una tabla de `solar_potential`.
4.  Desarrollar el prototipo en Leaflet con el plugin de OSM Buildings.

---
*Documentación generada para el ecosistema de mapas de Iareizaga.*
