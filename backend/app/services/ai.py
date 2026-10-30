from app.config import settings


def generate_content(topic: str, platform: str, tone: str, brand_voice: str = "") -> str:
    if settings.openai_api_key:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = f"Write a {tone} {platform} social post about: {topic}. Brand voice: {brand_voice or 'clear and useful'}. Produce only the post, no preamble."
        response = client.responses.create(model=settings.openai_model, input=prompt)
        result = getattr(response, "output_text", "").strip()
        if result:
            return result
    voice = f" {brand_voice.strip()}" if brand_voice.strip() else ""
    return f"{topic.strip()} is worth understanding because practical progress comes from clear ideas and consistent execution.\n\nHere are three things to keep in mind:\n• Start with the real problem.\n• Focus on a small, measurable improvement.\n• Share what you learn so others can build on it.\n\nWhat has your experience been?{voice}"


def review_post(body: str, platform: str = "linkedin") -> tuple[str, str]:
    cleaned = "\n".join(line.rstrip() for line in body.strip().splitlines())
    notes = []
    if len(cleaned) < 40:
        notes.append("Draft is quite short; consider adding context.")
    if len(cleaned) > 2800:
        notes.append("Draft is long; review platform character limits.")
    if not any(ch.isalpha() for ch in cleaned):
        notes.append("Draft needs meaningful text.")
    if platform not in {"linkedin", "instagram", "facebook", "x"}:
        notes.append("Unknown platform selected.")
    return cleaned, " ".join(notes) if notes else "Basic checks passed. Verify factual claims before publishing."
