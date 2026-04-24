from pydantic import BaseModel


class TagOut(BaseModel):
    id: int
    name: str
    count: int = 0
