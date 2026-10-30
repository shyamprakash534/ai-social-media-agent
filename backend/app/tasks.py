from datetime import datetime, timezone
from app.worker import celery_app
from app.database import SessionLocal
from app.models import Post, SocialAccount
from app.config import settings
from app.security import decrypt_secret
from app.services.linkedin import publish_text


@celery_app.task(name="app.tasks.dispatch_due_posts")
def dispatch_due_posts():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due = db.query(Post).filter(Post.status == "scheduled", Post.scheduled_at <= now).all()
        for post in due:
            post.status = "publishing"
            db.commit()
            publish_post.delay(post.id)
    finally:
        db.close()


@celery_app.task(name="app.tasks.publish_post", bind=True, max_retries=2, default_retry_delay=30)
def publish_post(self, post_id: str):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        try:
            if settings.publish_mode == "demo":
                platform_id = f"demo-{post.id[:8]}"
            elif settings.publish_mode == "linkedin" and post.platform == "linkedin":
                account = db.query(SocialAccount).filter(SocialAccount.platform == "linkedin").first()
                if not account or not account.access_token_encrypted:
                    raise RuntimeError("LinkedIn account is not connected")
                platform_id = publish_text(decrypt_secret(account.access_token_encrypted), account.author_urn, post.body)
            else:
                raise RuntimeError("Publishing mode/platform is not configured")
            post.platform_post_id = platform_id
            post.status = "published"
            post.published_at = datetime.now(timezone.utc)
            post.last_error = ""
        except Exception as exc:
            post.status = "failed"
            post.last_error = str(exc)[:2000]
            db.commit()
            raise
        db.commit()
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        db.close()
