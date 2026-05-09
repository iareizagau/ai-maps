from django.db import migrations


TASK_NAME = 'gailur-import-weekly'
TASK = 'gailur.import_and_geocode'


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='5',
        day_of_week='0',
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
        ('gailur', '0001_initial'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
