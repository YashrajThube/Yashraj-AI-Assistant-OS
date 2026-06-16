from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import model_validator


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_content(self):
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("content cannot be empty")
        return self


class NoteOut(BaseModel):
    id: int
    user_id: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
