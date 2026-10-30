from app.services.ai import generate_content, review_post


def test_demo_generation_returns_content(monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "openai_api_key", "")
    draft = generate_content("Using AI responsibly", "linkedin", "professional")
    assert "Using AI responsibly" in draft
    assert len(draft) > 40


def test_review_normalizes_and_reports():
    body, notes = review_post("A useful idea.   \n\nMore detail.", "linkedin")
    assert body == "A useful idea.\n\nMore detail."
    assert "checks" in notes.lower()
