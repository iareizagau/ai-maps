from ninja import NinjaAPI, Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from .models import User, Follow
from apps.pintxos.api import router as pintxos_router
from apps.inguru.api import router as inguru_router
from apps.kultur.api import router as kultur_router
from apps.adventure.api import router as adventure_router
from apps.solar.api import router as solar_router

api = NinjaAPI(title="Maps.eus API", version="1.0.0")

@api.get("/status")
def status(request):
    return {
        "status": "online",
        "ecosystem": "Maps.eus",
        "version": "6.0-alpha"
    }

@api.post("/follow/{user_id}/{app_context}")
def toggle_follow(request, user_id: int, app_context: str):
    if not request.user.is_authenticated:
        raise HttpError(401, "Login required")
    
    followed = get_object_or_404(User, id=user_id)
    if followed == request.user:
        raise HttpError(400, "You cannot follow yourself")

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        followed=followed,
        app_context=app_context
    )
    if not created:
        follow.delete()
        return {"status": "unfollowed"}
    return {"status": "followed"}

# Mount app-specific routers
api.add_router("/pintxos", pintxos_router)
api.add_router("/inguru", inguru_router)
api.add_router("/kultur", kultur_router)
api.add_router("/adventure", adventure_router)
api.add_router("/solar", solar_router)
