"""Register the daily automated tech blog post generator with django-celery-beat.

Schedule: daily at 03:00 Europe/Madrid.
"""

from django.db import migrations

TASK_NAME = "blog-generate-daily"
TASK = "blog.generate_daily_post"


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="*",
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
        ("blog", "0002_alter_post_map_center_lat_alter_post_map_center_lng_and_more"),
        ("django_celery_beat", "0016_alter_crontabschedule_timezone"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
