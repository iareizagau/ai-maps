from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Restaurant, RestaurantClaim


class RestaurantClaimForm(forms.ModelForm):
    class Meta:
        model = RestaurantClaim
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


class RestaurantManageForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = ['name', 'description', 'phone', 'website', 'image_url', 'hours']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'hours': forms.Textarea(attrs={'rows': 3, 'placeholder': '{"mon":"10-22","tue":"10-22"}'}),
        }
