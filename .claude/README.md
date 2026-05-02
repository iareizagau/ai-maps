# .claude Directory

**Configuration and documentation for Claude Code development.**

This directory contains everything Claude needs to understand your project and work efficiently.

## 📂 Structure

```
.claude/
├── README.md                    # This file
├── CLAUDE.md                    # 👈 START HERE - Main guide
├── QUICK_START.md              # Workflow tutorial
├── EXAMPLES.md                 # How to ask for things (✨ muy importante)
├── PROJECT_STATE.md            # Current status
├── DECISIONS.md                # Architecture decisions & rationale
├── settings.json               # Claude Code configuration
├── MEMORY.md                   # Index of persistent memories
└── memory/                     # Persistent knowledge
    ├── user_solopreneur.md
    ├── project_maps_eus.md
    ├── decision_tech_stack.md
    ├── feedback_code_style.md
    └── feedback_workflow.md
```

## 🚀 How This Works

1. **[CLAUDE.md](CLAUDE.md)** - Read first. Your project overview.
2. **[QUICK_START.md](QUICK_START.md)** - Learn the workflow.
3. **[EXAMPLES.md](EXAMPLES.md)** - See how to ask for things (read this before requesting features!)
4. **[PROJECT_STATE.md](PROJECT_STATE.md)** - Know the current status.
5. **[DECISIONS.md](DECISIONS.md)** - Understand *why* things are as they are.
6. **[MEMORY.md](MEMORY.md)** + `memory/` - Persistent knowledge base.

## 💡 Key Principles

### For Claude
- Every file here is context. Read it when relevant.
- Memory files persist knowledge across sessions.
- Settings control behavior (permissions, model, theme).
- Decisions explain the "why" behind technical choices.

### For You
- Keep [PROJECT_STATE.md](PROJECT_STATE.md) updated as you ship features.
- Add memories when you learn something important.
- Use [QUICK_START.md](QUICK_START.md) as your reference.
- Git-ignore nothing here (it's all config/docs).

## 🔄 Workflow (TL;DR)

```
You: "In www, create Landmark model..."
     ↓
Claude: Reads CLAUDE.md + PROJECT_STATE.md + relevant memories
     ↓
Claude: Proposes approach (where, how, why)
     ↓
You: "Yes, go" or "change this"
     ↓
Claude: Implements, shows diffs
     ↓
You: git diff → pytest → commit
     ↓
Done ✅
```

## 📝 Maintenance

- **After big features**: Update [PROJECT_STATE.md](PROJECT_STATE.md)
- **After architecture decisions**: Add to [DECISIONS.md](DECISIONS.md)
- **Learned something important**: Create memory file + update [MEMORY.md](MEMORY.md)
- **Workflow changes**: Update [QUICK_START.md](QUICK_START.md)

---

**Ready?** → Open [CLAUDE.md](CLAUDE.md)
