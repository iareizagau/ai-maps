# Generated for AppRegistry "Novedades" home section.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_add_display_priority_and_launch_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="appregistry",
            name="latest_update",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="appregistry",
            name="latest_update_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
