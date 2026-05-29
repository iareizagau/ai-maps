"""Register the daily MINCOTUR fuel-station ingest with django-celery-beat.

Schedule: every day at 06:30 Europe/Madrid. MINCOTUR refreshes ~daily during
the afternoon, so a 06:30 tick reliably picks up the previous day's snapshot.
The :30 offset stays clear of the PVPC ingest at :15.
"""

from django.db import migrations


TASK_NAME = 'mubil-fuel-daily'
TASK = 'mubil.ingest_fuel_stations'


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute='30',
        hour='6',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
        timezone='Europe/Madrid',
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            'task': TASK,
            'crontab': crontab,
            'interval': None,
            'enabled': True,
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mubil', '0003_seed_pvpc_schedule'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
