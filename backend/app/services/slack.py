import httpx
from app.config import settings


def send_approval_message(post_id: str, topic: str, platform: str, body: str, review_notes: str) -> None:
    if not settings.slack_bot_token or not settings.slack_channel_id:
        return
    text = f"New {platform} draft ready for approval: {topic}\n\n{body[:2500]}\n\n{review_notes}"
    payload = {
        "channel": settings.slack_channel_id,
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "action_id": "approve_post", "value": post_id},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "action_id": "reject_post", "value": post_id},
            ]},
        ],
    }
    response = httpx.post("https://slack.com/api/chat.postMessage", json=payload, headers={"Authorization": f"Bearer {settings.slack_bot_token}"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Slack message failed"))
