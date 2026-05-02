from django.db.models import Avg, Count, Q
from .models import Dish
from apps.core.models import Follow

def get_top_dishes(user=None, limit=10, lense='global'):
    """
    Retrieves top dishes based on different 'lenses' (perspectives).
    """
    queryset = Dish.objects.approved_restaurants().select_related('restaurant')
    
    if lense == 'circle' and user and user.is_authenticated:
        # 1. Get IDs of people the user follows in this app context
        followed_ids = Follow.objects.filter(
            follower=user, 
            app_context='pintxos'
        ).values_list('followed_id', flat=True)
        
        # 2. Annotate with average from those users ONLY
        queryset = queryset.filter(ratings__user_id__in=followed_ids).annotate(
            lense_avg=Avg('ratings__rating', filter=Q(ratings__user_id__in=followed_ids)),
            lense_count=Count('ratings', filter=Q(ratings__user_id__in=followed_ids))
        ).filter(lense_count__gt=0).order_by('-lense_avg', '-lense_count')
        
        # Patch attributes for consistency in templates
        for dish in queryset:
            dish.avg_rating = dish.lense_avg
            dish.rating_count = dish.lense_count
            
        return queryset[:limit]
    
    elif lense == 'experts':
        # TODO: Define who is an 'expert'. For now, people with > 10 ratings.
        # This is a placeholder for the more advanced weighted ranking.
        return queryset.order_by('-avg_rating')[:limit]

    # Global ranking (default)
    return queryset.order_by('-avg_rating')[:limit]
