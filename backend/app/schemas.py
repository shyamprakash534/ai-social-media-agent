from datetime import datetime
from pydantic import BaseModel, Field


class GeneratePostRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    platform: str = "linkedin"
    tone: str = "professional"
    brand_voice: str = ""


class EditPostRequest(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


class SchedulePostRequest(BaseModel):
    scheduled_at: datetime


class PostResponse(BaseModel):
    id: str
    topic: str
    platform: str
    tone: str
    brand_voice: str
    body: str
    review_notes: str
    status: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    platform_post_id: str = ""
    last_error: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    total: int
    pending_approval: int
    scheduled: int
    published: int
    failed: int


class SocialAccountResponse(BaseModel):
    platform: str
    account_name: str
    connected: bool
    connected_at: datetime | None = None
