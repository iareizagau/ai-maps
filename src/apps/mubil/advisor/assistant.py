"""Advisor AI Assistant — context-aware helper for the TCO wizard.

Receives the current form state (selected vehicles, km/year, profile, etc.)
and either:
  a) Returns a proactive contextual hint for the current step (GET-like).
  b) Answers a free-form question from the user using the form context +
     the RAG corpus (ask.services).

The prompt is tightly scoped: the assistant ONLY discusses topics relevant
to the user's current simulation. It does NOT answer generic questions
(those go to /ask/). Its job is to help the user fill the form correctly
and understand the TCO implications of their choices.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from apps.mubil.ask import embeddings as embed_lib
from apps.mubil.ask.services import (
    _call_gemini_generate,
    retrieve_topk,
)

log = logging.getLogger(__name__)


# ── Prompt fragments ──────────────────────────────────────────────────────────

_ROLE = (
    "Eres el asistente del simulador TCO eStrata. Tu único objetivo es "
    "ayudar al usuario a completar el formulario de comparativa de coste "
    "total de propiedad (TCO) entre su coche actual y un vehículo eléctrico. "
    "Responde SIEMPRE en castellano. Sé conciso (máximo 3 párrafos cortos). "
    "No respondas preguntas que no tengan que ver con la simulación actual. "
    "Si no sabes algo o la pregunta es muy general, di al usuario que use "
    "la sección Ask para consultas amplias. "
    "CONTEXTO IMPORTANTE: MOVES III ha finalizado. El programa vigente en "
    "2026 es el Plan Auto+ (MINTUR, 400 M€) basado en el Criterio EEE (Eléctrico, Económico, Europeo). "
    "El Criterio EEE modula la ayuda máxima (p.ej. 4.500 € para turismos M1) aplicando: "
    "1) Factor Eléctrico (50% BEV, 25% PHEV). "
    "2) Factor Económico (25% si precio sin IVA <= 35.000 €; 15% si <= 45.000 €). "
    "3) Factor Europeo (15% por ensamblado final en la UE y 10% si la batería se fabrica en la UE). "
    "Si un vehículo no se monta en la UE (p.ej. Tesla Model 3 importado de China), pierde el 15% de bonificación por ensamblado final, y si la batería tampoco es europea pierde el 10% adicional, lo que reduce su ayuda total. Explica esto con precisión si el usuario pregunta."
)

_STEP_HINTS = {
    "1a": (
        "El usuario está eligiendo su coche actual (combustión o híbrido). "
        "Ayúdale a buscar el modelo correcto o a decidir si usar 'Coche medio' "
        "si no recuerda el modelo exacto. Explica brevemente qué impacto tiene "
        "el coche actual en el TCO (consumo, DGT label, precio residual)."
    ),
    "1b": (
        "El usuario está eligiendo el coche eléctrico que quiere comparar. "
        "Puedes recomendarle opciones según su coche actual y su perfil. "
        "Menciona autonomía y precio como factores clave. Si el usuario no sabe "
        "qué eléctrico elegir, sugiérele usar el modo 'Recomiéndame'."
    ),
    "2": (
        "El usuario está configurando su perfil de movilidad (km/año y tipo de vía). "
        "Ayúdale a estimar sus km anuales si no los sabe (media española: 12.000-15.000). "
        "Explica cómo el perfil de vía (autovía vs urbano) afecta al consumo real del EV."
    ),
    "3": (
        "El usuario está configurando su perfil de carga e incentivos. "
        "Ayúdale a entender qué mix de carga tiene más sentido para su situación "
        "(wallbox en casa, trabajo, público). Explica los incentivos disponibles "
        "del Programa Auto+ 2026 y la deducción IRPF."
    ),
}


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass
class FormContext:
    """Snapshot of the advisor wizard state sent from the frontend."""
    step: str = "1a"
    cp: str = ""
    current_make: str = ""
    current_model: str = ""
    current_propulsion: str = ""
    current_consumption: str = ""
    target_make: str = ""
    target_model: str = ""
    target_range_km: str = ""
    target_price_eur: str = ""
    km_year: str = ""
    motorway_pct: str = ""
    profile: str = "particular"
    wallbox_state: str = "installed"
    home_pct: str = ""
    scrapping: bool = False
    purchase_mode: str = "switch"
    assembled_in_eu: bool = False
    battery_made_in_eu: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "FormContext":
        return cls(
            step=d.get("step", "1a"),
            cp=d.get("cp", ""),
            current_make=d.get("current_make", ""),
            current_model=d.get("current_model", ""),
            current_propulsion=d.get("current_propulsion", ""),
            current_consumption=d.get("current_consumption", ""),
            target_make=d.get("target_make", ""),
            target_model=d.get("target_model", ""),
            target_range_km=str(d.get("target_range_km", "")),
            target_price_eur=str(d.get("target_price_eur", "")),
            km_year=str(d.get("km_year", "")),
            motorway_pct=str(d.get("motorway_pct", "")),
            profile=d.get("profile", "particular"),
            wallbox_state=d.get("wallbox_state", "installed"),
            home_pct=str(d.get("home_pct", "")),
            scrapping=bool(d.get("scrapping", False)),
            purchase_mode=d.get("purchase_mode", "switch"),
            assembled_in_eu=bool(d.get("assembled_in_eu", False)),
            battery_made_in_eu=bool(d.get("battery_made_in_eu", False)),
        )

    def to_context_block(self) -> str:
        lines = ["=== Estado actual del formulario ==="]
        lines.append(f"Paso actual: {self.step}")
        if self.cp:
            lines.append(f"Código postal: {self.cp}")
        if self.current_make or self.current_model:
            lines.append(f"Coche actual: {self.current_make} {self.current_model} ({self.current_propulsion})")
        if self.current_consumption:
            lines.append(f"Consumo actual: {self.current_consumption} L/100")
        if self.target_make or self.target_model:
            lines.append(f"Eléctrico objetivo: {self.target_make} {self.target_model}")
        if self.target_range_km:
            lines.append(f"Autonomía EV: {self.target_range_km} km WLTP")
        if self.target_price_eur:
            lines.append(f"Precio EV: {self.target_price_eur} €")
        if self.km_year:
            lines.append(f"Km/año estimados: {self.km_year}")
        if self.motorway_pct:
            lines.append(f"% autovía: {self.motorway_pct}%")
        lines.append(f"Perfil fiscal: {self.profile}")
        lines.append(f"Wallbox: {self.wallbox_state}")
        if self.scrapping:
            lines.append("Achatarramiento: Sí")
        lines.append(f"Modo de compra: {self.purchase_mode}")
        lines.append(f"Montado en la UE: {'Sí' if self.assembled_in_eu else 'No'}")
        lines.append(f"Batería fabricada en la UE: {'Sí' if self.battery_made_in_eu else 'No'}")
        return "\n".join(lines)


@dataclass
class AssistantResponse:
    message: str
    hint_type: str = "info"   # "info" | "tip" | "warning" | "action"
    error: Optional[str] = None


# ── Core service ──────────────────────────────────────────────────────────────


def _build_prompt(
    ctx: FormContext,
    user_message: Optional[str],
    rag_docs: str,
) -> str:
    step_instruction = _STEP_HINTS.get(ctx.step, "")
    context_block = ctx.to_context_block()

    if user_message:
        task = (
            f"El usuario te hace la siguiente pregunta sobre su simulación:\n"
            f'"{user_message}"\n\n'
            "Responde usando el contexto del formulario y los documentos de apoyo. "
            "Si la pregunta no tiene relación con la simulación, redirige al usuario "
            "a la sección Ask."
        )
    else:
        task = (
            f"Genera una sugerencia proactiva y concisa para el paso actual ({ctx.step}). "
            f"Contexto del paso: {step_instruction}\n"
            "La sugerencia debe ser específica al contexto del formulario del usuario, "
            "no genérica. Si el usuario ya ha completado selecciones relevantes, "
            "comenta las implicaciones concretas de esas elecciones."
        )

    return (
        f"{_ROLE}\n\n"
        f"{context_block}\n\n"
        f"{rag_docs}\n\n"
        f"=== Tu tarea ===\n{task}"
    )


def get_hint(ctx: FormContext, user_message: Optional[str] = None) -> AssistantResponse:
    """Main entry point — returns a contextual hint or answers a user question."""
    if not getattr(settings, "GEMINI_API_KEY", None):
        return AssistantResponse(
            message="El asistente no está disponible (GEMINI_API_KEY no configurada).",
            hint_type="warning",
            error="no_api_key",
        )

    # Build a focused query for RAG retrieval based on form context
    rag_query_parts = []
    if user_message:
        rag_query_parts.append(user_message)
    if ctx.current_make or ctx.current_model:
        rag_query_parts.append(f"{ctx.current_make} {ctx.current_model}")
    if ctx.target_make or ctx.target_model:
        rag_query_parts.append(f"{ctx.target_make} {ctx.target_model} eléctrico autonomía")
    if ctx.step == "3":
        rag_query_parts.append("incentivos ayudas programa auto+ moves wallbox irpf")
    if ctx.step == "2":
        rag_query_parts.append("consumo real carretera urbano kWh/100")

    rag_query = " ".join(rag_query_parts) or "TCO coche eléctrico Euskadi ayudas"

    # RAG retrieval (top 4 docs, keep it tight for the assistant)
    rag_block = ""
    try:
        query_vec = embed_lib.embed_text(rag_query, task_type="RETRIEVAL_QUERY")
        docs = retrieve_topk(query_vec, k=4)
        if docs:
            snippets = []
            for i, d in enumerate(docs[:4], 1):
                snippets.append(
                    f"[{i}] {d.title} ({d.source_type})\n{d.content[:600].strip()}"
                )
            rag_block = "=== Documentos de apoyo ===\n" + "\n\n".join(snippets)
    except Exception as e:  # noqa: BLE001
        log.warning("Assistant RAG retrieval failed: %s", e)
        rag_block = ""

    prompt = _build_prompt(ctx, user_message, rag_block)

    try:
        text = _call_gemini_generate(prompt)
        hint_type = "info"
        # Heuristic: warnings if key issues detected
        low = text.lower()
        if any(w in low for w in ("ojo", "atención", "cuidado", "riesgo", "incompatible")):
            hint_type = "warning"
        elif any(w in low for w in ("recomiendo", "te sugiero", "podrías", "considera")):
            hint_type = "tip"
        return AssistantResponse(message=text, hint_type=hint_type)
    except Exception as e:  # noqa: BLE001
        log.exception("Advisor assistant generation failed: %s", e)
        return AssistantResponse(
            message="El asistente no está disponible temporalmente. Inténtalo de nuevo.",
            hint_type="warning",
            error="generation_unavailable",
        )
