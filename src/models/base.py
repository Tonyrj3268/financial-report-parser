from pydantic import BaseModel
from typing import List


class LabeledValue(BaseModel):
    value: float
    source_page: List[int]
    source_label: List[str]
    reason: str


def convert_to_thousand(value, is_thousand):
    """
    將數值轉換為千元單位

    Args:
        value: 原始數值
        is_thousand: 是否已經是千元單位

    Returns:
        千元單位的數值
    """
    if value is None:
        return None

    # 如果單位是元（is_thousand=False），則除以1000轉換為千元
    if is_thousand is False:
        return value / 1000
    # 如果已經是千元或未指定單位，則不轉換
    return value
