"""Register the hourly PVPC ingest with django-celery-beat.

The Celery beat scheduler runs from the DB (`DatabaseScheduler`), so the
`@shared_task` in `tasks.py` only fires once a `PeriodicTask` row references
it. Seeding it via migration keeps fresh environments self-bootstrapping.

Schedule: every hour at :15 Europe/Madrid. The :15 offset avoids the top-of-
hour spike when other crons fire, and ESIOS day-ahead PVPC is published
around 20:00 Madrid — an hourly tick picks it up without cursor tracking.
"""

from django.db import migrations


TASK_NAME = 'mubil-pvpc-hourly'
TASK = 'mubil.ingest_pvpc_hourly'


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute='15',
        hour='*',
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
        ('mubil', '0002_timescale_pgvector'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
