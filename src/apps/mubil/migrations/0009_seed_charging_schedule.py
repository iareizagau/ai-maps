"""Register the weekly OpenChargeMap charging-station ingest with django-celery-beat.

Schedule: every Monday at 06:45 Europe/Madrid. OCM updates are not announced
on a fixed cadence, so a weekly tick keeps the EH catalog fresh without
hammering the public free-tier endpoint (no quota published but courtesy
applies).

The :45 offset stays clear of PVPC (:15) and MINCOTUR fuel (:30 daily) so the
worker doesn't spike all three at the same minute on Mondays.
"""

from django.db import migrations

TASK_NAME = "mubil-charging-weekly"
TASK = "mubil.ingest_charging_stations"


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="45",
        hour="6",
        day_of_week="1",  # Monday in django-celery-beat (0=Sunday)
        day_of_month="*",
        month_of_year="*",
        timezone="Europe/Madrid",
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "task": TASK,
            "crontab": crontab,
            "interval": None,
            "enabled": True,
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("mubil", "0008_mobilitydocument_hnsw_index"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
