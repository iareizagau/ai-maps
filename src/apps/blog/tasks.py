import logging
from celery import shared_task
from apps.blog.services import create_daily_post

logger = logging.getLogger(__name__)


@shared_task(
    name="blog.generate_daily_post",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def generate_daily_post(self):
    logger.info("blog.generate_daily_post: starting automated daily blog post generation")
    post = create_daily_post()
    if post:
        logger.info("blog.generate_daily_post: successfully created draft post ID %d", post.id)
        return f"Post ID {post.id} created successfully"
    else:
        logger.warning("blog.generate_daily_post: no post was created")
        return "No post created"
