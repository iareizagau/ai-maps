from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

class CulturalEvent(models.Model):
    source_id = models.CharField(_("ID Origen"), max_length=255, unique=True, help_text=_("ID from the Euskadi API"))
    title_es = models.CharField(_("Título (ES)"), max_length=500, blank=True, null=True)
    title_eu = models.CharField(_("Título (EU)"), max_length=500, blank=True, null=True)
    description_es = models.TextField(_("Descripción (ES)"), blank=True, null=True)
    description_eu = models.TextField(_("Descripción (EU)"), blank=True, null=True)
    
    start_date = models.DateTimeField(_("Fecha Inicio"), blank=True, null=True, db_index=True)
    end_date = models.DateTimeField(_("Fecha Fin"), blank=True, null=True, db_index=True)
    
    venue_name_es = models.CharField(_("Lugar (ES)"), max_length=500, blank=True, null=True)
    venue_name_eu = models.CharField(_("Lugar (EU)"), max_length=500, blank=True, null=True)
    municipality_es = models.CharField(_("Municipio (ES)"), max_length=255, blank=True, null=True)
    municipality_eu = models.CharField(_("Municipio (EU)"), max_length=255, blank=True, null=True)
    province = models.CharField(_("Provincia"), max_length=255, blank=True, null=True)
    event_type_es = models.CharField(_("Tipo/Categoría (ES)"), max_length=255, blank=True, null=True)
    event_type_eu = models.CharField(_("Tipo/Categoría (EU)"), max_length=255, blank=True, null=True)
    
    opening_hours_es = models.CharField(_("Horario (ES)"), max_length=500, blank=True, null=True)
    opening_hours_eu = models.CharField(_("Horario (EU)"), max_length=500, blank=True, null=True)
    price_es = models.CharField(_("Precio (ES)"), max_length=500, blank=True, null=True)
    price_eu = models.CharField(_("Precio (EU)"), max_length=500, blank=True, null=True)
    
    # URL to the event page
    url_es = models.URLField(_("URL (ES)"), max_length=1000, blank=True, null=True)
    url_eu = models.URLField(_("URL (EU)"), max_length=1000, blank=True, null=True)
    
    purchase_url_es = models.URLField(_("URL Compra (ES)"), max_length=1000, blank=True, null=True)
    purchase_url_eu = models.URLField(_("URL Compra (EU)"), max_length=1000, blank=True, null=True)
    
    # Image URL
    image_url = models.URLField(_("Imagen"), max_length=1000, blank=True, null=True)

    # GeoDjango PointField for location
    location = models.PointField(_("Ubicación"), srid=4326, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Evento Cultural")
        verbose_name_plural = _("Eventos Culturales")
        ordering = ['start_date']

    def __str__(self):
        return self.title_es or self.title_eu or self.source_id

    @property
    def lat(self):
        return self.location.y if self.location else None

    @property
    def lng(self):
        return self.location.x if self.location else None
