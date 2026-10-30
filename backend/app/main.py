from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlencode, parse_qs
import secrets
import json
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.database import get_db, init_db
from app.models import Post, SocialAccount, OAuthState, AuditEvent
from app.schemas import GeneratePostRequest, EditPostRequest, SchedulePostRequest, PostResponse, StatsResponse, SocialAccountResponse
from app.security import encrypt_secret, verify_slack_signature
from app.agents.content_graph import initialize_graph, create_draft, resume_approval, close_graph
from app.services.slack import send_approval_message
from app.services.ai import review_post
from app.tasks import publish_post

app = FastAPI(title="AI Social Media Agent API", version="1.0.0", description="Generate, review, approve, schedule, and publish social media content.")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    init_db()
    initialize_graph()


@app.on_event("shutdown")
def shutdown():
    close_graph()


def _audit(db: Session, post_id: str, event: str, detail: str = ""):
    db.add(AuditEvent(post_id=post_id, event=event, detail=detail[:3000]))


def _get_post_or_404(db: Session, post_id: str) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


def _approve_or_reject(db: Session, post: Post, decision: str, edited_content: str | None = None):
    if post.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Post cannot be reviewed from status '{post.status}'")
    try:
        graph_state = resume_approval(post.approval_thread_id, decision, edited_content)
        if isinstance(graph_state.get("draft"), str):
            post.body = graph_state["draft"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not resume approval workflow: {exc}") from exc
    post.status = "approved" if decision == "approve" else "rejected"
    _audit(db, post.id, post.status, "Human decision recorded")
    db.commit()
    db.refresh(post)
    return post


@app.get("/api/health")
def health():
    return {"ok": True, "service": "ai-social-media-agent", "publish_mode": settings.publish_mode}


@app.get("/api/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)):
    def count(status: str) -> int:
        return db.query(func.count(Post.id)).filter(Post.status == status).scalar() or 0
    return StatsResponse(total=db.query(func.count(Post.id)).scalar() or 0, pending_approval=count("pending_approval"), scheduled=count("scheduled"), published=count("published"), failed=count("failed"))


@app.get("/api/posts", response_model=list[PostResponse])
def list_posts(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Post).order_by(Post.created_at.desc()).limit(min(max(limit, 1), 250)).all()


@app.post("/api/posts/generate", response_model=PostResponse, status_code=201)
def generate_post(payload: GeneratePostRequest, db: Session = Depends(get_db)):
    thread_id = str(uuid4())
    try:
        state = create_draft(payload.topic, payload.platform, payload.tone, payload.brand_voice, thread_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Content generation failed: {exc}") from exc
    draft = state.get("draft", "").strip()
    if not draft:
        raise HTTPException(status_code=502, detail="Agent returned an empty draft")
    post = Post(id=str(uuid4()), topic=payload.topic, platform=payload.platform, tone=payload.tone, brand_voice=payload.brand_voice, body=draft, review_notes=state.get("review_notes", ""), status="pending_approval", approval_thread_id=thread_id)
    db.add(post)
    db.flush()
    _audit(db, post.id, "generated", "Draft generated and paused for human approval")
    db.commit()
    db.refresh(post)
    try:
        send_approval_message(post.id, post.topic, post.platform, post.body, post.review_notes)
    except Exception as exc:
        _audit(db, post.id, "slack_notification_failed", str(exc))
        db.commit()
    return post


@app.patch("/api/posts/{post_id}", response_model=PostResponse)
def edit_post(post_id: str, payload: EditPostRequest, db: Session = Depends(get_db)):
    post = _get_post_or_404(db, post_id)
    if post.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Only posts awaiting approval can be edited")
    post.body, post.review_notes = review_post(payload.body.strip(), post.platform)
    _audit(db, post.id, "edited", "Draft edited and basic quality checks rerun")
    db.commit()
    db.refresh(post)
    return post


@app.post("/api/posts/{post_id}/approve", response_model=PostResponse)
def approve_post(post_id: str, db: Session = Depends(get_db)):
    return _approve_or_reject(db, _get_post_or_404(db, post_id), "approve")


@app.post("/api/posts/{post_id}/reject", response_model=PostResponse)
def reject_post(post_id: str, db: Session = Depends(get_db)):
    return _approve_or_reject(db, _get_post_or_404(db, post_id), "reject")


@app.post("/api/posts/{post_id}/schedule", response_model=PostResponse)
def schedule_post(post_id: str, payload: SchedulePostRequest, db: Session = Depends(get_db)):
    post = _get_post_or_404(db, post_id)
    if post.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the post before scheduling")
    if post.platform != "linkedin":
        raise HTTPException(status_code=400, detail="V1 scheduling is LinkedIn-only")
    if payload.scheduled_at.tzinfo is None or payload.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="scheduled_at must be a future datetime with timezone")
    post.scheduled_at = payload.scheduled_at.astimezone(timezone.utc)
    post.status = "scheduled"
    _audit(db, post.id, "scheduled", post.scheduled_at.isoformat())
    db.commit()
    db.refresh(post)
    return post


@app.post("/api/posts/{post_id}/publish", response_model=PostResponse)
def publish_now(post_id: str, db: Session = Depends(get_db)):
    post = _get_post_or_404(db, post_id)
    if post.status not in ("approved", "failed"):
        raise HTTPException(status_code=409, detail="Approve the post before publishing")
    if post.platform != "linkedin":
        raise HTTPException(status_code=400, detail="V1 live publishing is LinkedIn-only")
    previous = post.status
    post.status = "publishing"
    post.last_error = ""
    _audit(db, post.id, "publish_queued", "User requested immediate publishing")
    db.commit()
    try:
        publish_post.delay(post.id)
    except Exception as exc:
        post.status = previous
        post.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=503, detail="Could not queue publisher; check Redis/worker") from exc
    db.refresh(post)
    return post


@app.get("/api/social-accounts", response_model=list[SocialAccountResponse])
def social_accounts(db: Session = Depends(get_db)):
    account = db.query(SocialAccount).filter(SocialAccount.platform == "linkedin").first()
    result = [SocialAccountResponse(platform="linkedin", account_name=account.account_name if account else "Not connected", connected=bool(account and account.access_token_encrypted), connected_at=account.connected_at if account else None)]
    result.extend([SocialAccountResponse(platform=p, account_name="Draft only in V1", connected=False, connected_at=None) for p in ("instagram", "facebook", "x")])
    return result


@app.get("/auth/linkedin/start")
def linkedin_start(db: Session = Depends(get_db)):
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise HTTPException(status_code=503, detail="LinkedIn credentials are not configured")
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(state=state, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    params = {"response_type": "code", "client_id": settings.linkedin_client_id, "redirect_uri": settings.linkedin_redirect_uri, "state": state, "scope": "openid profile w_member_social"}
    return RedirectResponse("https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params))


@app.get("/auth/linkedin/callback")
def linkedin_callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    if error:
        raise HTTPException(status_code=400, detail=f"LinkedIn authorization failed: {error}")
    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not code or not oauth_state or oauth_state.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Missing or invalid OAuth state")
    db.delete(oauth_state)
    db.commit()
    try:
        token_response = httpx.post("https://www.linkedin.com/oauth/v2/accessToken", data={"grant_type":"authorization_code","code":code,"redirect_uri":settings.linkedin_redirect_uri,"client_id":settings.linkedin_client_id,"client_secret":settings.linkedin_client_secret}, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=30)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data["access_token"]
        user_response = httpx.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization":f"Bearer {access_token}"}, timeout=20)
        user_response.raise_for_status()
        profile = user_response.json()
    except (httpx.HTTPError, KeyError) as exc:
        raise HTTPException(status_code=502, detail=f"LinkedIn OAuth exchange failed: {exc}") from exc
    account = db.query(SocialAccount).filter(SocialAccount.platform == "linkedin").first()
    member_id = profile.get("sub", "")
    author_urn = settings.linkedin_author_urn or f"urn:li:person:{member_id}"
    if account is None:
        account = SocialAccount(platform="linkedin", account_name=profile.get("name", "LinkedIn member"), author_urn=author_urn, access_token_encrypted=encrypt_secret(access_token))
        db.add(account)
    else:
        account.account_name = profile.get("name", "LinkedIn member")
        account.author_urn = author_urn
        account.access_token_encrypted = encrypt_secret(access_token)
    refresh_token = token_data.get("refresh_token", "")
    if refresh_token:
        account.refresh_token_encrypted = encrypt_secret(refresh_token)
    expires_in = int(token_data.get("expires_in", 0) or 0)
    account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
    db.commit()
    return RedirectResponse(settings.frontend_origin + "/?linkedin=connected")


@app.post("/api/slack/actions")
async def slack_actions(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    if not verify_slack_signature(settings.slack_signing_secret, request.headers.get("X-Slack-Request-Timestamp", ""), raw_body, request.headers.get("X-Slack-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid Slack request signature")
    payload_value = parse_qs(raw_body.decode("utf-8")).get("payload", [""])[0]
    try:
        payload = json.loads(payload_value)
        user_id = payload.get("user", {}).get("id", "")
        if settings.slack_allowed_users and user_id not in settings.slack_allowed_users:
            raise HTTPException(status_code=403, detail="Slack user is not allowed")
        action = payload.get("actions", [])[0]
        post = _get_post_or_404(db, action.get("value", ""))
        decision = "approve" if action.get("action_id") == "approve_post" else "reject"
        _approve_or_reject(db, post, decision, post.body if decision == "approve" else None)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process Slack action: {exc}") from exc
    return PlainTextResponse("Action received")
