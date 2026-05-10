from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_appregistry_is_featured'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_slug', models.CharField(db_index=True, help_text="App slug or '*' for the cross-app bundle", max_length=50)),
                ('tier', models.CharField(choices=[('free', 'Free'), ('plus', 'Plus'), ('pro', 'Pro')], default='free', max_length=16)),
                ('status', models.CharField(choices=[('active', 'Active'), ('past_due', 'Past due'), ('canceled', 'Canceled')], default='active', max_length=16)),
                ('stripe_customer_id', models.CharField(blank=True, max_length=64)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=64)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name='subscriptions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('user', 'app_slug'), name='uniq_user_app_sub'),
                ],
                'indexes': [
                    models.Index(fields=['user', 'status'], name='core_subscr_user_status_idx'),
                ],
            },
        ),
    ]
