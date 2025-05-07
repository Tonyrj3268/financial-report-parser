from pydantic import BaseModel


class LabeledValue(BaseModel):
    value: float
    source_page: int
    source_label: str
