from django.db.models import Count, Avg, Q
from .models import User, Follow

def get_top_experts(app_context='pintxos', limit=6, exclude_user=None):
    """
    Finds top contributors for a specific app context.
    Expertise is measured by:
    1. Number of approved reviews in that app.
    2. Average rating of their reviews (quality).
    """
    # Note: This requires joining with the app-specific rating models.
    # For now, let's look at users who have the most followers in this app
    # and some base activity.
    
    queryset = User.objects.annotate(
        follower_count=Count('follower_set', filter=Q(follower_set__app_context=app_context)),
        # In a real scenario, we'd join with apps.pintxos.DishRating here.
        # But core shouldn't depend on pintxos models directly to avoid circularity.
        # We'll use follower count as the primary 'authority' metric for now.
    ).filter(is_active=True).order_by('-follower_count')
    
    if exclude_user:
        queryset = queryset.exclude(id=exclude_user.id)
        
    return queryset[:limit]

def get_suggested_users(user, app_context='pintxos', limit=6):
    """
    Network effect: People followed by the people you follow.
    """
    if not user.is_authenticated:
        return User.objects.none()
        
    followed_by_me = Follow.objects.filter(
        follower=user, 
        app_context=app_context
    ).values_list('followed_id', flat=True)
    
    suggestions = User.objects.filter(
        follower_set__follower_id__in=followed_by_me,
        follower_set__app_context=app_context
    ).exclude(
        id__in=followed_by_me
    ).exclude(
        id=user.id
    ).annotate(
        mutual_count=Count('follower_set', filter=Q(follower_set__follower_id__in=followed_by_me))
    ).order_by('-mutual_count')
    
    return suggestions[:limit]
