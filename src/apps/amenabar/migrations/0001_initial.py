import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Promocion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("nombre", models.CharField(max_length=200)),
                ("ciudad", models.CharField(max_length=120)),
                ("provincia", models.CharField(blank=True, max_length=80)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("EN_VENTA", "En venta"),
                            ("EN_CURSO", "En curso"),
                            ("PROXIMA", "Próxima"),
                            ("VENDIDA", "Vendida"),
                            ("FINALIZADA", "Finalizada"),
                        ],
                        db_index=True,
                        default="EN_VENTA",
                        max_length=20,
                    ),
                ),
                (
                    "porcentaje_vendido",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("nota", models.CharField(blank=True, max_length=200)),
                ("source_url", models.URLField()),
                ("detail_url", models.URLField(blank=True)),
                ("image_url", models.URLField(blank=True)),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326),
                ),
            ],
            options={
                "ordering": ["estado", "nombre"],
            },
        ),
        migrations.AddIndex(
            model_name="promocion",
            index=models.Index(fields=["estado"], name="amenabar_pr_estado_idx"),
        ),
        migrations.CreateModel(
            name="POI",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("osm_type", models.CharField(max_length=10)),
                ("osm_id", models.BigIntegerField()),
                ("nombre", models.CharField(blank=True, max_length=200)),
                (
                    "categoria",
                    models.CharField(
                        choices=[
                            ("TRANSPORTE", "Transporte público"),
                            ("VEHICULOS", "Vehículos"),
                            ("COMIDA", "Comida"),
                            ("BEBIDA", "Bebida"),
                            ("ATRACTIVOS", "Atractivos"),
                            ("INFORMACION", "Información"),
                            ("SALUD", "Salud"),
                            ("FINANZAS", "Finanzas"),
                            ("ADMINISTRACION", "Administración"),
                            ("RELIGION", "Religión"),
                            ("VERDES", "Espacios verdes"),
                            ("DEPORTE", "Deporte"),
                            ("CULTURA", "Cultura y ocio"),
                            ("HISTORICO", "Histórico"),
                            ("NATURAL", "Elementos naturales"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("subtipo", models.CharField(blank=True, max_length=80)),
                ("tags", models.JSONField(blank=True, default=dict)),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(srid=4326),
                ),
                (
                    "promocion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pois",
                        to="amenabar.promocion",
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="poi",
            constraint=models.UniqueConstraint(
                fields=("promocion", "osm_type", "osm_id"),
                name="uniq_poi_per_promocion",
            ),
        ),
        migrations.AddIndex(
            model_name="poi",
            index=models.Index(
                fields=["promocion", "categoria"],
                name="amenabar_poi_prom_cat_idx",
            ),
        ),
    ]
