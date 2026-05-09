import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(
    name='kultur.load_events',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def load_events(self):
    logger.info('kultur.load_events: starting load_events')
    call_command('load_events')
    logger.info('kultur.load_events: starting geocode_venues')
    call_command('geocode_venues')
    logger.info('kultur.load_events: done')
