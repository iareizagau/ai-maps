from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

class LowEmissionZone(models.Model):
    name = models.CharField(_('Nombre de la Zona'), max_length=150)
    description = models.TextField(_('Descripción'), blank=True, null=True)
    geom = models.MultiPolygonField(_('Geometría'), srid=4326)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Zona de Bajas Emisiones')
        verbose_name_plural = _('Zonas de Bajas Emisiones')

    def __str__(self):
        return self.name
