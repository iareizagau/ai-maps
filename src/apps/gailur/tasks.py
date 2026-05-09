import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(
    name='gailur.import_and_geocode',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def import_and_geocode(self):
    logger.info('gailur.import_and_geocode: starting import_climbing')
    call_command('import_climbing')
    logger.info('gailur.import_and_geocode: starting geocode_crags')
    call_command('geocode_crags')
    logger.info('gailur.import_and_geocode: done')
