from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kultur', '0005_seed_load_events_schedule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='culturalevent',
            name='start_date',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Fecha Inicio'),
        ),
        migrations.AlterField(
            model_name='culturalevent',
            name='end_date',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Fecha Fin'),
        ),
    ]
