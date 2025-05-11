from pydantic import BaseModel
from typing import List


class LabeledValue(BaseModel):
    value: float
    source_page: List[int]
    source_label: List[str]
