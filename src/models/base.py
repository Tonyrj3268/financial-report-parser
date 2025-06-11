from pydantic import BaseModel, Field, field_validator, FieldValidationInfo
from typing import List, Union, get_origin, get_args


class LabeledValue(BaseModel):
    value: float
    source_page: List[int]
    source_label: List[str]
    reason: str


def make_default_lv() -> LabeledValue:
    """產生全新的預設 LabeledValue（避免共用同一物件）"""
    return LabeledValue(value=0, source_page=[], source_label=[], reason="default")


def _is_labeled_value_type(tp) -> bool:
    """判斷 tp 是否為 LabeledValue 或 Optional[LabeledValue]"""
    if tp is LabeledValue:
        return True
    if get_origin(tp) is Union and LabeledValue in get_args(tp):
        return True
    return False


class BaseModelWithDefault(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def replace_none_with_default(cls, v, info: FieldValidationInfo):
        """
        只在欄位型別屬於 LabeledValue 系列 **且** 值為 None 時，
        替換成新的預設 LabeledValue。
        """
        if v is not None:
            return v

        # 透過 field_name 取得目前欄位的型別註解
        field = cls.model_fields[info.field_name]
        if _is_labeled_value_type(field.annotation):
            return make_default_lv()

        # 其他型別維持 None，不做改動
        return None


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

    # 如果明確指定已經是千元單位（is_thousand=True），則不轉換
    if is_thousand is True:
        return value
    # 默認假設單位是元，需要除以1000轉換為千元
    return value / 1000


if __name__ == "__main__":
    from typing import Optional

    class Test(BaseModelWithDefault):
        a: Optional[LabeledValue] = None

    test = Test(a=None)
    print(test)
