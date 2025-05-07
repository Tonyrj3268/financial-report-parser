from pydantic import BaseModel, Field
from .base import LabeledValue


class PrePayments(BaseModel):
    prepayments_for_good: LabeledValue = Field(
        ...,
        alias="預付款項",
    )
    prepayments_for_equipment: LabeledValue = Field(
        ...,
        alias="預付設備款",
    )
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


prepayments_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

1. 模型欄位結構  
   - **預付款項**： 數值為 { 金額 }，主要為預付給供應商的貨款

   - **預付設備款**：數值為 { 金額 }，主要為預付給供應商的設備款

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣，例如當出現預付款項時且沒有幣別時，則默認為預付款項(新台幣)。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
"""
