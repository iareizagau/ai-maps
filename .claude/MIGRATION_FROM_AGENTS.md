# Migración desde .agents/ a .claude/

**Cómo hemos consolidado el antiguo sistema de agents en la nueva estructura.**

---

## 🔄 Qué Pasó

El directorio `.agents/` contenía una **estructura jerárquica** (L0→L4) con especialistas y skills. Era innovador pero:

- ❌ **Demasiado complejo**: 4 capas de indirección
- ❌ **No ejecutable**: Los `.md` no se ejecutaban, solo documentaban
- ❌ **Disperso**: Información estaba repartida en 7+ archivos
- ❌ **Redundante**: Repetía contexto

## ✅ Qué Hicimos

Consolidamos `.agents/` en `.claude/` con:

### De `.agents/00_AOS_KERNEL.md` → `.claude/CLAUDE.md`
- ✅ Kernel de oro → Guía principal
- ✅ Arquitectura clara y directa

### De `.agents/specialists.md`, `data.md`, `frontend.md` → `.claude/TECHNICAL_RUNBOOK.md`
- ✅ Fusionamos especialistas en Skills concretos:
  - **Data & AI** → SKILL 1: Hybrid Spatial-Semantic Search
  - **Frontend** → SKILL 2: Atomic Design System
  - **GIS** → Integrado en busqueda espacial

### De `.agents/skills.md` → `.claude/TECHNICAL_RUNBOOK.md`
- ✅ Strategic runbooks → Implementaciones reales con código
- ✅ Capacidades críticas documentadas con ejemplos

### De `.agents/state/PROJECT_STATUS.md` → `.claude/PROJECT_STATE.md`
- ✅ Estado vivo del proyecto en una fuente única

---

## 📍 Mapping Completo

| Archivo `.agents/` | Migrado a `.claude/` | Nota |
|-------------------|-------------------|------|
| `00_AOS_KERNEL.md` | `CLAUDE.md` | Kernel → Guía principal |
| `specialists.md` | `TECHNICAL_RUNBOOK.md` | Geo specialist → implementación |
| `data.md` | `TECHNICAL_RUNBOOK.md` - SKILL 1 | Data specialist → código real |
| `frontend.md` | `TECHNICAL_RUNBOOK.md` - SKILL 2 | Frontend specialist → componentes |
| `skills.md` | `TECHNICAL_RUNBOOK.md` | SOPs → implementaciones |
| `state/PROJECT_STATUS.md` | `PROJECT_STATE.md` | Estado → documento vivo |
| `state/JOURNAL.md` | Git log | Historial → git history |

---

## 🎯 Ventajas de la Nueva Estructura

### Antes (Agents)
```
.agents/
├── 00_AOS_KERNEL.md
├── specialists/
│   ├── geo.md
│   ├── data.md
│   └── frontend.md
├── skills/
│   ├── tree.md
│   └── varios/
├── state/
│   ├── JOURNAL.md
│   └── PROJECT_STATUS.md
```
⚠️ **Problema**: 7 archivos, jerarquía compleja, documentación vs código

### Después (Claude)
```
.claude/
├── START_HERE.md          ← Orientación rápida
├── EXAMPLES.md            ← Cómo pedir cosas
├── QUICK_START.md         ← Workflow
├── CLAUDE.md              ← Guía completa
├── PROJECT_STATE.md       ← Estado
├── TECHNICAL_RUNBOOK.md   ← Skills + código
├── DECISIONS.md           ← Por qué
├── HOTKEYS.md             ← Templates
├── memory/                ← Conocimiento persistente
```
✅ **Ventaja**: 11 archivos organizados, enfoque sobre implementación

---

## 🚀 Puedes Prescindir de `.agents/`

Después de esta migración, **el directorio `.agents/` es redundante**. 

### Opciones:

#### 1️⃣ **Eliminar completamente** (Recomendado)
```bash
rm -rf .agents/
```
✅ Limpio, una fuente única de verdad (.claude/)
✅ Menos confusión (un directorio, no dos)
✅ Git no tendrá archivos muertos

#### 2️⃣ **Mantener como archivo** (Si quieres historial)
```bash
# Convertir a archivo ZIP para referencia histórica
zip -r .agents.backup.zip .agents/
rm -rf .agents/
```
Puedes volver a revisar si necesitas algo.

#### 3️⃣ **Mantener en Git pero deprecated**
```bash
# Agregar a .gitignore
echo ".agents/" >> .gitignore
git rm -r --cached .agents/
git commit -m "Archive: move .agents content to .claude, mark as deprecated"
```

---

## 📝 Recomendación Final

**Elimina `.agents/` completamente.**

Razones:
1. ✅ Todo lo valioso está en `.claude/` ahora
2. ✅ Evitas confusión (¿cuál uso?)
3. ✅ `.claude/` es estándar de Claude Code
4. ✅ Memory system (.claude/memory/) es más potente
5. ✅ Código en TECHNICAL_RUNBOOK.md es ejecutable/testeable

Si en futuro quieres volver a un contenido específico:
- Git history tiene todos los commits de `.agents/`
- Las ideas mejores están en `.claude/TECHNICAL_RUNBOOK.md`

---

## ✨ Próximos Pasos

```bash
# 1. Verifica que todo está en .claude/
ls -la .claude/ | grep TECHNICAL_RUNBOOK.md

# 2. Review: Lee TECHNICAL_RUNBOOK.md
# para asegurarte que tiene todo lo que necesitas

# 3. Elimina (cuando estés seguro)
rm -rf .agents/

# 4. Commit
git add -A
git commit -m "Consolidate: Archive .agents, use .claude as single source of truth"
```

---

**Estatus**: ✅ Migración completa. Listo para prescindir de `.agents/`.
