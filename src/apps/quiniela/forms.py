"""Formulario de alta de jornada: cabecera + 15 filas (spec datos-jornada)."""

from __future__ import annotations

from types import MappingProxyType

from django import forms
from django.utils import timezone

from .models import Equipo, Jornada, PartidoJornada
from .services_ingest import temporada_de

N_PARTIDOS = 15
CLASE_INPUT = (
    "w-full rounded-lg border border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 "
    "px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
)


class JornadaForm(forms.ModelForm):
    fecha_cierre = forms.DateTimeField(
        label="Cierre del boleto",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": CLASE_INPUT}, format="%Y-%m-%dT%H:%M"),
    )

    class Meta:
        model = Jornada
        fields = ("temporada", "numero", "fecha_cierre")
        widgets = MappingProxyType(
            {
                "temporada": forms.TextInput(attrs={"class": CLASE_INPUT, "inputmode": "numeric", "maxlength": 4}),
                "numero": forms.NumberInput(attrs={"class": CLASE_INPUT, "min": 1}),
            }
        )
        labels = MappingProxyType({"temporada": "Temporada (yyYY)", "numero": "Jornada nº"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("temporada", temporada_de(timezone.localdate()))


class PartidoForm(forms.Form):
    local = forms.ModelChoiceField(queryset=Equipo.objects.none(), required=False, empty_label="— equipo —")
    local_texto = forms.CharField(required=False, max_length=80)
    visitante = forms.ModelChoiceField(queryset=Equipo.objects.none(), required=False, empty_label="— equipo —")
    visitante_texto = forms.CharField(required=False, max_length=80)

    def __init__(self, *args, equipos=None, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in ("local", "visitante"):
            self.fields[nombre].queryset = equipos if equipos is not None else Equipo.objects.all()
            self.fields[nombre].widget.attrs["class"] = CLASE_INPUT
        for nombre in ("local_texto", "visitante_texto"):
            self.fields[nombre].widget.attrs.update(
                {"class": CLASE_INPUT, "placeholder": "o escribe (selección, Copa…)"}
            )

    def clean(self):
        datos = super().clean()
        for lado in ("local", "visitante"):
            if not datos.get(lado) and not (datos.get(f"{lado}_texto") or "").strip():
                self.add_error(lado, "Falta el equipo.")
        local, visitante = datos.get("local"), datos.get("visitante")
        lt = (datos.get("local_texto") or "").strip().casefold()
        vt = (datos.get("visitante_texto") or "").strip().casefold()
        if (local and local == visitante) or (not local and not visitante and lt and lt == vt):
            raise forms.ValidationError("Local y visitante no pueden ser el mismo equipo.")
        return datos


PartidoFormSet = forms.formset_factory(
    PartidoForm, extra=0, min_num=N_PARTIDOS, max_num=N_PARTIDOS, validate_min=True, validate_max=True
)


def crear_formset(data=None):
    equipos = Equipo.objects.order_by("nombre")
    return PartidoFormSet(data, prefix="p", form_kwargs={"equipos": equipos})


def guardar_jornada(form: JornadaForm, formset) -> Jornada:
    jornada = form.save()
    PartidoJornada.objects.bulk_create(
        PartidoJornada(
            jornada=jornada,
            posicion=i + 1,
            local=f.cleaned_data.get("local"),
            visitante=f.cleaned_data.get("visitante"),
            local_texto="" if f.cleaned_data.get("local") else f.cleaned_data.get("local_texto", "").strip(),
            visitante_texto=(
                "" if f.cleaned_data.get("visitante") else f.cleaned_data.get("visitante_texto", "").strip()
            ),
        )
        for i, f in enumerate(formset.forms)
    )
    return jornada
