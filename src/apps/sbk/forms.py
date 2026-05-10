from django import forms
from django.utils.translation import gettext_lazy as _

from .models import DanceVenue, DanceVenueClaim


class DanceVenueClaimForm(forms.ModelForm):
    class Meta:
        model = DanceVenueClaim
        fields = ['method', 'evidence', 'contact_phone', 'contact_email']
        widgets = {
            'evidence': forms.Textarea(attrs={'rows': 4, 'class': 'w-full'}),
        }
        labels = {
            'method': _('Verification method'),
            'evidence': _('Evidence and notes'),
            'contact_phone': _('Best contact phone'),
            'contact_email': _('Best contact email'),
        }
        help_texts = {
            'evidence': _("Tell us your role at the venue and any details that help us verify ownership."),
        }


class DanceVenueManageForm(forms.ModelForm):
    class Meta:
        model = DanceVenue
        fields = [
            'name', 'description', 'address', 'city',
            'venue_type', 'styles', 'weekly_schedule',
            'website', 'instagram', 'image_url',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'styles': forms.Textarea(attrs={'rows': 2, 'placeholder': '["salsa", "bachata", "kizomba"]'}),
            'weekly_schedule': forms.Textarea(attrs={'rows': 4, 'placeholder': '{"mon": {"class": ["bachata-19h"]}, "wed": {"social": ["21h-2h"]}}'}),
        }
