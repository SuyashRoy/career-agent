from pydantic import BaseModel
from typing import List


class JobSourceOutput(BaseModel):
    company_name: str
    career_page_url: str
    open_position_url: str


class JobSourceState(BaseModel):
    linkedin_url: str = ""
    company_name: str = ""
    company_website: str = ""
    career_page_url: str = ""
    open_position_url: str = ""
    errors: List[str] = []
