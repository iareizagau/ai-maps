# 🚀 START HERE

**Bienvenido. Aquí es cómo tu setup de Claude Code funciona.**

---

## 📍 Qué Acabas de Crear

Has creado una **estructura completa para trabajar eficientemente con Claude**:

- ✅ **Guía principal** - Entiende la arquitectura y cómo trabajar
- ✅ **Ejemplos** - Ve cómo pedir cosas correctamente (CRUCIAL)
- ✅ **Estado del proyecto** - Sabe dónde estamos ahora
- ✅ **Decisiones documentadas** - Entiende el "por qué"
- ✅ **Memory system** - Claude recuerda contexto entre sesiones
- ✅ **Settings** - Configuración lista (Claude Opus 4.7)

---

## ⚡ Las 3 Cosas Más Importantes

### 1️⃣ LEE ESTO PRIMERO: [EXAMPLES.md](EXAMPLES.md)

**Muestra ejemplos BAD vs GOOD de cómo pedir cosas.**

Ejemplos de peticiones buenas:
```
"En www, necesito modelo Landmark con campos X, Y, Z.
Requiere migración, admin, tests. ¿Propuesta?"
```

Ejemplos de peticiones malas:
```
"Crea un modelo"
```

**Invertir 5 minutos aquí = 10 horas ahorradas después.**

### 2️⃣ LEE ESTO SEGUNDO: [QUICK_START.md](QUICK_START.md)

El flujo básico:
1. Tú: Describes qué quieres (específico)
2. Claude: Propone abordaje
3. Tú: Validas
4. Claude: Implementa
5. Tú: Pruebas y commits

### 3️⃣ CONSULTA CUANDO NECESITES: [PROJECT_STATE.md](PROJECT_STATE.md)

Sabe dónde está el proyecto (qué está hecho, qué falta).

---

## 🎯 Tu Primer Workflow (5 min)

```
1. Abre EXAMPLES.md ← Lee BAD vs GOOD
2. Abre QUICK_START.md ← Entiende el flujo
3. Abre PROJECT_STATE.md ← Sabe dónde estamos
4. Describe tu primera tarea (usando EXAMPLES como referencia)
5. Claude propone → tú validas → implementa → haces commit
6. Si aprendiste algo importante → actualiza memory/
```

---

## 📚 Estructura Completa

| Archivo | Para qué |
|---------|----------|
| **CLAUDE.md** | Guía principal (arquitectura, patrones, contexto) |
| **QUICK_START.md** | Cómo es el flujo de trabajo |
| **EXAMPLES.md** | ⭐ Cómo pedir cosas correctamente (LEE ESTO) |
| **PROJECT_STATE.md** | Dónde estamos ahora (DB, backend, frontend, tasks) |
| **DECISIONS.md** | Por qué PostGIS, por qué Django, etc. |
| **HOTKEYS.md** | Comandos rápidos y templates |
| **VALIDATION.md** | Checklist para verificar setup |
| **settings.json** | Configuración Claude Code |
| **memory/** | Tus recuerdos persistentes (user, project, feedback) |

---

## 💡 El Secreto del Setup

**Las personas que trabajan mejor con Claude:**

1. ✅ Especifican claramente (ven EXAMPLES.md)
2. ✅ Proporcionan contexto (ves PROJECT_STATE.md)
3. ✅ Hacen preguntas antes de implementar (propuesta → validar)
4. ✅ Actualizan memory cuando aprenden algo (memory/)
5. ✅ Documentan decisiones (DECISIONS.md)

**Las personas que no:**

1. ❌ Piden vagamente ("arregla esto")
2. ❌ No dan contexto (no sabe dónde estamos)
3. ❌ Esperan que Claude adivine (no propone/valida)
4. ❌ Pierden learning entre sesiones (no actualiza memory)
5. ❌ Olvidan por qué hicieron cosas (no documenta)

---

## 🎓 Aprendizaje Progresivo

### Semana 1: Aprende el Setup
- [ ] Lee CLAUDE.md
- [ ] Lee QUICK_START.md
- [ ] Lee EXAMPLES.md (2-3 ejemplos hasta entender)
- [ ] Haz 1 tarea pequeña (feature, bugfix, refactor)

### Semana 2: Optimiza Peticiones
- [ ] Usa EXAMPLES.md como referencia
- [ ] Especifica mejor cada petición
- [ ] Nota qué respuestas son mejores

### Semana 3: Usa Memory
- [ ] Documenta decisiones en memory/
- [ ] Crea nuevos memories si necesario
- [ ] Actualiza MEMORY.md con índice

### Semana 4+: Experto
- [ ] Workflow fluido y automático
- [ ] Sabes exactamente qué información dar
- [ ] Maximizas productividad con Claude

---

## ❓ FAQ Rápido

**P: ¿Por qué el directorio `.claude`?**  
R: Es dónde Claude Code busca automáticamente configuración y documentación.

**P: ¿Tengo que seguir este setup exactamente?**  
R: No, pero cuanto más lo hagas, mejor funcionará. Puedes adaptarlo.

**P: ¿Qué pasa con la carpeta `.agents` vieja?**  
R: Puedes mantenerla como referencia, pero `.claude` es la fuente de verdad.

**P: ¿Cómo actualizo memory?**  
R: Edita archivos en `memory/` o crea nuevos. Luego actualiza `MEMORY.md`.

**P: ¿Cuál es el siguiente paso?**  
R: Lee EXAMPLES.md (5 min), luego describe qué quieres hacer.

---

## 🚀 Siguiente Paso

1. **Abre [EXAMPLES.md](EXAMPLES.md)** (5 minutos)
2. **Lee BAD vs GOOD ejemplos**
3. **Vuelve aquí**
4. **Describe tu próxima tarea**

---

**Estás listo. ¡Vamos!**

---

Última actualización: 2026-04-23
