"""Modelos de la app quiniela (openspec/changes/quiniela-asistente-v1/design.md D7)."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

SIGNOS_1X2 = ("1", "X", "2")
SIGNOS_PLENO = ("0", "1", "2", "M")


def normalizar_alias(texto: str) -> str:
    """Clave de búsqueda de alias: sin espacios sobrantes y en minúsculas."""
    return " ".join((texto or "").split()).casefold()


# --------------------------------------------------------------------------- #
# Catálogo de equipos
# --------------------------------------------------------------------------- #


class Equipo(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ("nombre",)

    def __str__(self) -> str:
        return self.nombre


class EquipoAlias(models.Model):
    """Nombre con el que una fuente identifica a un equipo ("Ath Bilbao")."""

    texto = models.CharField(max_length=80, unique=True, help_text="Normalizado con normalizar_alias().")
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name="aliases")

    class Meta:
        verbose_name_plural = "equipo aliases"

    def __str__(self) -> str:
        return f"{self.texto} → {self.equipo}"

    def save(self, *args, **kwargs):
        self.texto = normalizar_alias(self.texto)
        super().save(*args, **kwargs)


def resolver_equipo(texto: str, crear: bool = True) -> Equipo | None:
    """Devuelve el equipo para ``texto`` (por alias o nombre).

    Si no existe y ``crear`` es True, crea el equipo con ese nombre y su alias
    (spec datos-jornada: «Nombre desconocido en una ingesta»).
    """
    from .equipos_seed import EQUIPOS

    clave = normalizar_alias(texto)
    if not clave:
        return None
    alias = EquipoAlias.objects.select_related("equipo").filter(texto=clave).first()
    if alias:
        return alias.equipo
    semilla = {normalizar_alias(k): (k, v) for k, v in EQUIPOS.items()}.get(clave)
    if semilla is not None:
        if not crear:
            return None
        nombre_fd, (canonico, alias_prensa) = semilla
        equipo, _ = Equipo.objects.get_or_create(nombre=canonico)
        for texto_alias in (nombre_fd, canonico, *alias_prensa):
            EquipoAlias.objects.get_or_create(texto=normalizar_alias(texto_alias), defaults={"equipo": equipo})
        return equipo
    equipo = Equipo.objects.filter(nombre__iexact=texto.strip()).first()
    if equipo is None:
        if not crear:
            return None
        equipo = Equipo.objects.create(nombre=" ".join(texto.split()))
    EquipoAlias.objects.get_or_create(texto=clave, defaults={"equipo": equipo})
    return equipo


def cargar_catalogo() -> int:
    """Crea todos los equipos de ``equipos_seed`` con sus alias. Idempotente."""
    from .equipos_seed import EQUIPOS

    for nombre_fd in EQUIPOS:
        resolver_equipo(nombre_fd)
    return len(EQUIPOS)


# --------------------------------------------------------------------------- #
# Histórico
# --------------------------------------------------------------------------- #


class Division(models.TextChoices):
    PRIMERA = "SP1", "Primera"
    SEGUNDA = "SP2", "Segunda"


class PartidoHistorico(models.Model):
    division = models.CharField(max_length=4, choices=Division.choices)
    temporada = models.CharField(max_length=4, help_text="Código yyYY, p. ej. 2627.")
    fecha = models.DateField()
    local = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="+")
    visitante = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="+")
    goles_local = models.PositiveSmallIntegerField()
    goles_visitante = models.PositiveSmallIntegerField()
    cuota_1 = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_x = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_2 = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_tipo = models.CharField(
        max_length=8, blank=True, help_text="Columna origen de las cuotas: AvgC, B365C o Avg."
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["fecha", "local", "visitante"], name="quiniela_hist_unico"),
        )
        indexes = (
            models.Index(fields=["division", "temporada"]),
            models.Index(fields=["fecha"]),
        )
        ordering = ("fecha", "id")

    def __str__(self) -> str:
        return f"{self.fecha} {self.local} {self.goles_local}-{self.goles_visitante} {self.visitante}"

    @property
    def signo(self) -> str:
        return signo_desde_goles(self.goles_local, self.goles_visitante)


def signo_desde_goles(gl: int, gv: int) -> str:
    if gl > gv:
        return "1"
    if gl < gv:
        return "2"
    return "X"


def categoria_pleno(goles: int) -> str:
    return "M" if goles >= 3 else str(goles)


# --------------------------------------------------------------------------- #
# Jornada
# --------------------------------------------------------------------------- #


class Jornada(models.Model):
    temporada = models.CharField(max_length=4)
    numero = models.PositiveSmallIntegerField()
    fecha_cierre = models.DateTimeField(help_text="Hora límite para validar el boleto.")
    creada_at = models.DateTimeField(auto_now_add=True)
    avisos_at = models.DateTimeField(null=True, blank=True, help_text="Última extracción de avisos con IA.")
    avisos_error = models.CharField(
        max_length=300, blank=True, help_text="Vacío si la última extracción fue bien; si no, el motivo."
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["temporada", "numero"], name="quiniela_jornada_unica"),
        )
        ordering = ("-fecha_cierre",)

    def __str__(self) -> str:
        return f"Jornada {self.numero} ({self.temporada})"

    @property
    def cerrada(self) -> bool:
        return timezone.now() >= self.fecha_cierre

    @property
    def tiene_resultados(self) -> bool:
        partidos = list(self.partidos.all())
        return len(partidos) == 15 and all(p.tiene_resultado for p in partidos)


class PartidoJornada(models.Model):
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name="partidos")
    posicion = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(15)],
        help_text="1-14 combinables; 15 = Pleno al 15.",
    )
    local = models.ForeignKey(Equipo, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    visitante = models.ForeignKey(Equipo, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    local_texto = models.CharField(max_length=80, blank=True, help_text="Equipo fuera del catálogo.")
    visitante_texto = models.CharField(max_length=80, blank=True)
    fecha = models.DateTimeField(null=True, blank=True)
    cuota_1 = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_x = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_2 = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuotas_capturadas_at = models.DateTimeField(null=True, blank=True)
    goles_local = models.PositiveSmallIntegerField(null=True, blank=True)
    goles_visitante = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["jornada", "posicion"], name="quiniela_partido_posicion_unica"),
            models.CheckConstraint(
                condition=models.Q(posicion__gte=1, posicion__lte=15), name="quiniela_partido_posicion_rango"
            ),
        )
        ordering = ("jornada", "posicion")

    def __str__(self) -> str:
        return f"{self.posicion}. {self.nombre_local} - {self.nombre_visitante}"

    def clean(self):
        if not (self.local_id or self.local_texto.strip()):
            raise ValidationError({"local": "Falta el equipo local."})
        if not (self.visitante_id or self.visitante_texto.strip()):
            raise ValidationError({"visitante": "Falta el equipo visitante."})
        if self.local_id and self.local_id == self.visitante_id:
            raise ValidationError("Local y visitante no pueden ser el mismo equipo.")
        if (
            not self.local_id
            and not self.visitante_id
            and self.local_texto.strip().casefold() == self.visitante_texto.strip().casefold()
        ):
            raise ValidationError("Local y visitante no pueden ser el mismo equipo.")

    @property
    def nombre_local(self) -> str:
        return str(self.local) if self.local_id else self.local_texto

    @property
    def nombre_visitante(self) -> str:
        return str(self.visitante) if self.visitante_id else self.visitante_texto

    @property
    def es_pleno(self) -> bool:
        return self.posicion == 15

    @property
    def sin_historico(self) -> bool:
        """Algún equipo está fuera del catálogo (selecciones, Copa…)."""
        return not (self.local_id and self.visitante_id)

    @property
    def tiene_cuotas(self) -> bool:
        return None not in (self.cuota_1, self.cuota_x, self.cuota_2)

    @property
    def tiene_resultado(self) -> bool:
        return self.goles_local is not None and self.goles_visitante is not None

    @property
    def signo_resultado(self) -> str | None:
        if not self.tiene_resultado:
            return None
        return signo_desde_goles(self.goles_local, self.goles_visitante)

    @property
    def pleno_resultado(self) -> str | None:
        if not self.tiene_resultado:
            return None
        return f"{categoria_pleno(self.goles_local)}-{categoria_pleno(self.goles_visitante)}"

    @property
    def pronostico_elegido(self) -> Pronostico | None:
        """Precedencia fija cuotas > modelo > uniforme (spec pronostico)."""
        por_fuente = {p.fuente: p for p in self.pronosticos.all()}
        for fuente in Pronostico.PRECEDENCIA:
            if fuente in por_fuente:
                return por_fuente[fuente]
        return None


# --------------------------------------------------------------------------- #
# Pronóstico
# --------------------------------------------------------------------------- #


class Pronostico(models.Model):
    class Fuente(models.TextChoices):
        CUOTAS = "cuotas", "Cuotas"
        MODELO = "modelo", "Modelo"
        UNIFORME = "uniforme", "Sin datos"

    PRECEDENCIA = (Fuente.CUOTAS, Fuente.MODELO, Fuente.UNIFORME)

    partido = models.ForeignKey(PartidoJornada, on_delete=models.CASCADE, related_name="pronosticos")
    fuente = models.CharField(max_length=10, choices=Fuente.choices)
    p1 = models.FloatField()
    px = models.FloatField()
    p2 = models.FloatField()
    pleno_dist = models.JSONField(
        null=True, blank=True, help_text='Solo partido 15: {"0-0": p, …, "M-M": p} (16 claves).'
    )
    calculado_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["partido", "fuente"], name="quiniela_pronostico_unico"),
        )

    def __str__(self) -> str:
        return f"{self.partido} [{self.fuente}] {self.p1:.2f}/{self.px:.2f}/{self.p2:.2f}"

    @property
    def probs(self) -> dict[str, float]:
        return {"1": self.p1, "X": self.px, "2": self.p2}

    @property
    def signo_favorito(self) -> str:
        probs = self.probs
        return max(SIGNOS_1X2, key=lambda s: probs[s])


# --------------------------------------------------------------------------- #
# Noticias y avisos
# --------------------------------------------------------------------------- #


class Noticia(models.Model):
    url = models.URLField(max_length=1000, unique=True)
    titulo = models.CharField(max_length=500)
    publicada_at = models.DateTimeField()
    feed = models.CharField(max_length=300, blank=True)
    equipos = models.ManyToManyField(Equipo, related_name="noticias", blank=True)

    class Meta:
        ordering = ("-publicada_at",)

    def __str__(self) -> str:
        return self.titulo


class Aviso(models.Model):
    class Tipo(models.TextChoices):
        LESION = "lesion", "Lesión"
        SANCION = "sancion", "Sanción"
        DUDA = "duda", "Duda"
        ROTACION = "rotacion", "Rotación"
        OTRO = "otro", "Otro"

    partido = models.ForeignKey(PartidoJornada, on_delete=models.CASCADE, related_name="avisos")
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name="+")
    jugador = models.CharField(max_length=120, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.OTRO)
    resumen = models.CharField(max_length=300)
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="avisos")
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("partido", "equipo", "tipo")

    def __str__(self) -> str:
        return f"{self.equipo}: {self.get_tipo_display()} {self.jugador}".strip()


# --------------------------------------------------------------------------- #
# Boleto
# --------------------------------------------------------------------------- #


class BoletoConfirmadoError(Exception):
    """Se intentó modificar un boleto ya confirmado."""


class Boleto(models.Model):
    jornada = models.OneToOneField(Jornada, on_delete=models.CASCADE, related_name="boleto")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    lineas = models.JSONField(
        default=list,
        help_text='Partidos 1-14: [{"posicion": 1, "signos": "1X", "origen": "modelo|usuario"}, …]',
    )
    pleno = models.CharField(max_length=3, blank=True, help_text='Un signo por equipo, p. ej. "1-M".')
    configuracion = models.CharField(max_length=20, blank=True, help_text='Ej.: "1T+1D".')
    num_apuestas = models.PositiveSmallIntegerField(default=0)
    coste = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    p10 = models.FloatField(null=True, blank=True)
    p11 = models.FloatField(null=True, blank=True)
    p12 = models.FloatField(null=True, blank=True)
    p14 = models.FloatField(null=True, blank=True)
    probabilidades_snapshot = models.JSONField(
        null=True, blank=True, help_text="Probabilidades por partido en el momento de confirmar."
    )
    explicacion = models.TextField(blank=True)
    confirmado_at = models.DateTimeField(null=True, blank=True)
    aciertos = models.PositiveSmallIntegerField(null=True, blank=True)
    pleno_acertado = models.BooleanField(null=True, blank=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    # Campos que se pueden escribir después de confirmar (evaluación).
    CAMPOS_POST_CONFIRMACION = frozenset({"aciertos", "pleno_acertado", "actualizado_at"})

    class Meta:
        ordering = ("-jornada__fecha_cierre",)

    def __str__(self) -> str:
        return f"Boleto {self.jornada} ({self.configuracion or 'sin configurar'})"

    def save(self, *args, **kwargs):
        if self.pk:
            previo = Boleto.objects.filter(pk=self.pk).values_list("confirmado_at", flat=True).first()
            if previo is not None:
                update_fields = kwargs.get("update_fields")
                if update_fields is None or not set(update_fields) <= self.CAMPOS_POST_CONFIRMACION:
                    raise BoletoConfirmadoError("El boleto ya está confirmado y no se puede modificar.")
        super().save(*args, **kwargs)

    @property
    def confirmado(self) -> bool:
        return self.confirmado_at is not None
