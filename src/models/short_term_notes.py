from pydantic import BaseModel, Field
from .base import LabeledValue, convert_to_thousand
from openpyxl import Workbook


class ShortTermNotesPayableDetail(BaseModel):
    """應付短期票券明細"""

    amount: LabeledValue = Field(..., description="金額")
    counterparty: str = Field(..., description="對象單位名稱")


class ShortTermNotesPayable(BaseModel):
    """應付短期票券"""

    domestic_notes: list[ShortTermNotesPayableDetail] = Field(
        ..., description="應付短期票券 - 國內發行（代號 206000）"
    )
    # 國內短期票券折價金額
    domestic_notes_discount: LabeledValue = Field(
        ..., description="國內短期票券折價金額"
    )

    overseas_notes: list[ShortTermNotesPayableDetail] = Field(
        ...,
        description="應付國外有價證券 - 海外短期票券（代號 208000）",
    )
    # 國外短期票券折價金額
    overseas_notes_discount: LabeledValue = Field(
        ..., description="國外短期票券折價金額"
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        ws_liabilities = wb["負債表 "]

        # 國內短期票券淨額
        domestic_notes_amount = convert_to_thousand(
            sum([note.amount.value for note in self.domestic_notes])
            - self.domestic_notes_discount.value,
            self.unit_is_thousand,
        )

        ws_liabilities["C22"] = (
            domestic_notes_amount if domestic_notes_amount > 0 else None
        )

        # 國外短期票券淨額
        overseas_notes_amount = convert_to_thousand(
            sum([note.amount.value for note in self.overseas_notes])
            - self.overseas_notes_discount.value,
            self.unit_is_thousand,
        )
        ws_liabilities["C24"] = (
            overseas_notes_amount if overseas_notes_amount > 0 else None
        )


short_term_notes_payable_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  

- ShortTermNotesPayableDetail：每筆應付短期票券的詳細資訊，包含：
  - amount: LabeledValue 結構的應付短期票券金額
  - counterparty: 應付短期票券對象名稱（字串）

1. 模型欄位定義  
   - **domestic_notes**（應付短期票券 - 國內發行）

   - **domestic_notes_discount**（國內短期票券折價金額）
     
   - **overseas_notes**（應付國外有價證券 - 海外短期票券）

   - **overseas_notes_discount**（國外短期票券折價金額）

   - **unit_is_thousand**（單位是否為千元）：布林值，True 代表單位為千元，False 代表單位為元

注意事項
每個借款類別都是 ShortTermNotesPayableDetail 的陣列，每筆借款都需要包含 amount、counterparty 和 counterparty_type。
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入空陣列 []。
沒有特別說明幣種的話，默認為新台幣，例如當出現支票存款時且沒有幣別時，則默認為支票存款(新台幣)。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
若同一筆借款同時出現在主表與附註，僅擇一來源為主。
"""
