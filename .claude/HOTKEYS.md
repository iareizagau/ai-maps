# Hotkeys & Quick Commands

**Atajos y comandos rápidos dentro de Claude Code.**

## VSCode Integration

Si usas Claude Code dentro de VSCode:

- **Ctrl+Shift+P** → "Claude: Open Claude Code"
- **Cmd/Ctrl+K** → Focus in conversation
- **Cmd/Ctrl+Enter** → Submit message

## Common Tasks (Copy & Paste Templates)

### Crear Migraçión
```
"En [DOMINIO], necesito crear un migration que agregue [CAMPO] a [MODELO].

Campo: [tipo] (ej: CharField max_length=200)
¿Generas la migración automáticamente?"
```

### Bugfix
```
"En [ARCHIVO], hay un bug:

Error: [STACK TRACE]
Comportamiento esperado: [QUÉ DEBERÍA PASAR]
Comportamiento actual: [QUÉ PASA]

He intentado: [LO QUE INTENTASTE]
¿Qué causa esto?"
```

### Feature Completa
```
"En [DOMINIO], nueva feature:

Nombre: [NOMBRE]
Descripción: [PARA QUÉ]
Modelos: [CAMPOS]
API: [ENDPOINTS]
Frontend: [COMPONENTES]

¿Propuesta paso a paso?"
```

### Test
```
"Crea test para [FUNCIÓN] que valide:
- [CASO 1]
- [CASO 2]
- [CASO ERROR]"
```

## Context Switching

Si pasas de dominio a dominio:

```
"Cambiamos de contexto. Ahora vamos a trabajar en [NUEVO DOMINIO].
Listo? Descríbeme el siguiente cambio."
```

## Debugging Flow

```
"Debug:
1. Corro [COMANDO]
2. Sale error: [ERROR]
3. ¿Qué pasa y cómo lo arreglo?"
```

## Performance Issues

```
"Performance issue en [FUNCIÓN]:
- Tiempo: [TIEMPO ACTUAL] → [TIEMPO OBJETIVO]
- Síntomas: [QUÉ PASA]

¿Diagnóstico y solución?"
```

---

**Tip**: Cuanto más específico seas, mejor respuesta. Usa estos templates como base.
