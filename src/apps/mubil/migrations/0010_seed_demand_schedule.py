"""Register the monthly demand-score recompute with django-celery-beat.

Schedule: 1st of each month, 07:00 Europe/Madrid. The score depends on
:class:`ChargingStation` density, which OCM refreshes weekly — once per
month catches the supply drift without burning compute on stable data.

The :00 minute is fine here: PVPC :15 / fuel :30 / charging :45 / demand
:00 are all on different exact times so beat doesn't fire concurrently on
the same minute.
"""

from django.db import migrations


TASK_NAME = 'mubil-demand-monthly'
TASK = 'mubil.compute_demand_scores'


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='7',
        day_of_week='*',
        day_of_month='1',
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
        ('mubil', '0009_seed_charging_schedule'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
