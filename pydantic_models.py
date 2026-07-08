from pydantic import BaseModel, Field

class BrainOutput(BaseModel):
    image_prompt: str
    candidates: list[str] = Field(..., min_length=3, max_length=3)

class JudgeOutput(BaseModel):
    winning_tweet: str
    reasoning: str

class VisionOutput(BaseModel):
    is_clean: bool
    reason: str = ""

class BouncerOutput(BaseModel):
    is_relevant: bool
