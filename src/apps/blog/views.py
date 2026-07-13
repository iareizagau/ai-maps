import json
import logging
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Category, Post, Tag

log = logging.getLogger(__name__)


def post_list(request, category_slug=None, tag_slug=None):
    """List published blog posts, support filtering by category, tag, or keyword search."""
    posts = Post.objects.filter(is_published=True)
    active_category = None
    active_tag = None

    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=active_category)

    if tag_slug:
        active_tag = get_object_or_404(Tag, slug=tag_slug)
        posts = posts.filter(tags=active_tag)

    # Keyword Search
    query = request.GET.get("q", "").strip()
    if query:
        posts = posts.filter(
            Q(title_es__icontains=query)
            | Q(title_eu__icontains=query)
            | Q(title_en__icontains=query)
            | Q(summary_es__icontains=query)
            | Q(summary_eu__icontains=query)
            | Q(summary_en__icontains=query)
            | Q(content_es__icontains=query)
            | Q(content_eu__icontains=query)
            | Q(content_en__icontains=query)
        )

    categories = Category.objects.all()
    tags = Tag.objects.all()
    recent_posts = Post.objects.filter(is_published=True).order_by(
        "-published_at", "-created_at"
    )[:5]

    context = {
        "posts": posts,
        "categories": categories,
        "tags": tags,
        "active_category": active_category,
        "active_tag": active_tag,
        "recent_posts": recent_posts,
        "search_query": query,
        "title": "Blog de Desarrollo & WebGIS - Maps.eus",
        "app_slug": "blog",
    }
    return render(request, "blog/list.html", context)


def post_detail(request, slug):
    """View blog post details, support matching Euskara, Spanish, or English slugs."""
    post = get_object_or_404(
        Post.objects.filter(is_published=True),
        Q(slug_eu=slug) | Q(slug_es=slug) | Q(slug_en=slug),
    )

    categories = Category.objects.all()
    tags = Tag.objects.all()
    recent_posts = (
        Post.objects.filter(is_published=True)
        .exclude(pk=post.pk)
        .order_by("-published_at", "-created_at")[:5]
    )

    context = {
        "post": post,
        "categories": categories,
        "tags": tags,
        "recent_posts": recent_posts,
        "title": post.title,
        "app_slug": "blog",
    }
    return render(request, "blog/detail.html", context)


@csrf_exempt
@require_POST
def blog_chat_api(request):
    """AI chatbot endpoint. Searches relevant blog posts and queries Gemini to answer questions."""
    try:
        data = json.loads(request.body)
        question = data.get("question", "").strip()
    except json.JSONDecodeError:
        question = request.POST.get("question", "").strip()

    if not question:
        return JsonResponse({"error": "Empty question"}, status=400)

    # Keywords-based search to identify relevant posts as context
    keywords = question.split()
    query_filter = Q()
    for kw in keywords[:5]:  # Limit query complexity
        if len(kw) > 2:
            query_filter |= (
                Q(title_es__icontains=kw)
                | Q(title_eu__icontains=kw)
                | Q(title_en__icontains=kw)
                | Q(summary_es__icontains=kw)
                | Q(summary_eu__icontains=kw)
                | Q(summary_en__icontains=kw)
                | Q(content_es__icontains=kw)
                | Q(content_eu__icontains=kw)
                | Q(content_en__icontains=kw)
            )

    relevant_posts = Post.objects.filter(is_published=True)
    if query_filter:
        relevant_posts = relevant_posts.filter(query_filter)[:3]
    else:
        relevant_posts = relevant_posts.order_by("-published_at", "-created_at")[:3]

    # Build prompt context from retrieved articles
    context_str = ""
    for i, p in enumerate(relevant_posts, start=1):
        context_str += f"Post [{i}]: {p.title}\n"
        context_str += f"Link: /blog/{p.slug}/\n"
        context_str += f"Resumen: {p.summary}\n"
        context_str += f"Contenido: {p.content[:1200]}\n\n"

    system_prompt = (
        "Eres el Asistente de IA oficial del blog técnico de Maps.eus (un portal de WebGIS, PostGIS, pgrouting, pgvector, Docker y Django en Euskal Herria). "
        "Tu misión es responder preguntas técnicas basándote en los posts publicados en el blog. "
        "Usa Markdown para tu respuesta. Responde siempre en el mismo idioma en que te pregunta el usuario (euskara, castellano o inglés). "
        "Si los posts proveen información suficiente para responder, úsalos y cítalos enlazándolos con su ruta (por ejemplo: '[Título del Post](/blog/slug/)'). "
        "Si los posts no contienen la respuesta, explícalo cortésmente, y responde utilizando tu conocimiento general sobre desarrollo de software, "
        "pero advirtiendo que esta información no se encuentra en el blog."
    )

    prompt = (
        f"{system_prompt}\n\n"
        f"=== CONTEXTO DE POSTS DISPONIBLES ===\n{context_str}\n"
        f"=== PREGUNTA DEL USUARIO ===\n{question}\n\n"
        "=== RESPUESTA (Markdown) ==="
    )

    if not getattr(settings, "GEMINI_API_KEY", ""):
        return JsonResponse(
            {
                "answer": "El servicio de IA no está configurado (falta la API key de Gemini)."
            }
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Retrieve fallback list
        ladder = getattr(
            settings,
            "GEMINI_GENERATION_FALLBACK_MODELS",
            ["gemini-3.5-flash"],
        )
        model = ladder[0] if ladder else "gemini-3.5-flash"

        cfg = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=1000,
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=cfg,
        )
        answer_text = (response.text or "").strip()

        if not answer_text:
            answer_text = (
                "No he podido formular una respuesta en este momento. "
                "Por favor, reformula tu pregunta."
            )

        return JsonResponse({"answer": answer_text})
    except Exception as e:
        log.exception("Error invoking Gemini for blog assistant: %s", e)
        return JsonResponse(
            {
                "answer": f"Lo siento, ocurrió un error técnico al invocar la IA: {str(e)}"
            },
            status=500,
        )
