import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(
    name='sbk.load_events',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def load_events(self):
    logger.info('sbk.load_events: starting')
    call_command('load_sbk_events')
    logger.info('sbk.load_events: done')
