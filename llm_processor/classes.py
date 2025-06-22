from pydantic import BaseModel
from datetime import datetime

class Article(BaseModel):
    title: str
    published_time: datetime
    source: str
    url: str




