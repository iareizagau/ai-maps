import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(
    name='inguru.ingest',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def ingest(self):
    logger.info('inguru.ingest: starting')
    call_command('ingest_inguru')
    logger.info('inguru.ingest: done')
