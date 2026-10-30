import hashlib
import hmac
import time
from app.security import verify_slack_signature


def test_valid_slack_signature():
    secret = "test-secret"
    timestamp = str(int(time.time()))
    body = b"payload=test"
    base = b"v0:" + timestamp.encode() + b":" + body
    signature = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    assert verify_slack_signature(secret, timestamp, body, signature)


def test_rejects_old_timestamp():
    assert not verify_slack_signature("secret", "1", b"payload", "v0=bad")
