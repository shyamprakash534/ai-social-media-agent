import httpx
from app.config import settings


class LinkedInError(RuntimeError):
    pass


def authorization_url(state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": "openid profile w_member_social",
    }
    return "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)


def publish_text(access_token: str, author_urn: str, text: str) -> str:
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": settings.linkedin_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = httpx.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code >= 400:
        raise LinkedInError(f"LinkedIn returned {response.status_code}: {response.text[:1000]}")
    return response.headers.get("x-restli-id", "")
