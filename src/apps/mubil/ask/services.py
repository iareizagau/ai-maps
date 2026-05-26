"""RAG + Gemini services for `ask`. PROPUESTA.md §3.2.

Pipeline:
  1. Embed query (text-embedding-004, 768d).
  2. pgvector similarity search top-k from MobilityDocument.
  3. Compose prompt with citations + send to Gemini.
  4. Parse structured output → AskAnswerOut.

Fallback: si Gemini > 3s, mostrar "thinking…" partial HTMX (UX) y/o devolver
respuesta cacheada de los 5 prompts gold.
"""
