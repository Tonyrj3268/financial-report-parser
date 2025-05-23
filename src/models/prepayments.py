from pydantic import BaseModel, Field
from .base import LabeledValue, convert_to_thousand
import pandas as pd


class PrePayments(BaseModel):
    """預付款項"""

    prepayments_for_good: LabeledValue = Field(
        ...,
        description="預付款項",
    )
    prepayments_for_equipment: LabeledValue = Field(
        ...,
        description="預付設備款",
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def to_df(self):
        return pd.DataFrame(
            [
                [
                    "3.企業",
                    "預付貨款",
                    convert_to_thousand(
                        self.prepayments_for_good.value, self.unit_is_thousand
                    ),
                    None,
                    None,
                    None,
                ],
                [
                    "3.企業",
                    "預付設備款",
                    convert_to_thousand(
                        self.prepayments_for_equipment.value, self.unit_is_thousand
                    ),
                    None,
                    None,
                    None,
                ],
            ],
            columns=["部門", "項目", "金額", "", "", ""],
        )


prepayments_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> }  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  
  如果在尋找value時，發現該欄位和其他頁數有關聯，請將該頁數也一併放入 source_page。例如當該數值後面寫了「備註２」，則請將「備註２」所在頁數也放入 source_page。

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
