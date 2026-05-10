from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Count
from .models import Event, Person

class SbkCitySitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        # Only cities with >= 3 upcoming events (anti-empty-page threshold)
        return (Event.objects
                .filter(end_date__gte=timezone.now(), moderation_status__in=['pending', 'verified'])
                .values('city')
                .annotate(c=Count('id'))
                .filter(c__gte=3, city__isnull=False)
                .exclude(city=''))

    def location(self, item):
        return reverse('sbk:city', args=[slugify(item['city'])])

class SbkTypeSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ['festivales', 'socials', 'talleres']

    def location(self, item):
        return reverse('sbk:type', args=[item])

class SbkStaticSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return ['sbk:map', 'sbk:tonight', 'sbk:practice', 'sbk:person_directory']

    def location(self, item):
        return reverse(item)

class SbkPersonSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Person.objects.filter(is_verified=True)

    def location(self, obj):
        return reverse('sbk:person_detail', args=[obj.slug])
