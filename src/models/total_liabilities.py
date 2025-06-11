import pandas as pd
from pydantic import BaseModel, Field
from openpyxl import Workbook

from .base import LabeledValue, convert_to_thousand


class TotalLiabilities(BaseModel):
    """負債總額"""

    domestic_bank_short_term_loans: LabeledValue = Field(
        ...,
        description="國內金融機構借款-短期借款",
    )
    domestic_bank_long_term_loans: LabeledValue = Field(
        ...,
        description="國內金融機構借款-長期借款",
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        pass
        # return pd.DataFrame(
        #     [
        #         ["負債合計", "200000", None, None, None, None],
        #         [
        #             "一、國內金融機構借款",
        #             "201000",
        #             convert_to_thousand(
        #                 self.domestic_bank_short_term_loans.value,
        #                 self.unit_is_thousand,
        #             ),
        #             convert_to_thousand(
        #                 self.domestic_bank_long_term_loans.value,
        #                 self.unit_is_thousand,
        #             ),
        #             None,
        #             None,
        #         ],
        #     ],
        #     columns=["項目", "電腦代號", "時間", "", "", ""],
        # )


total_liabilities_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  

1. 模型欄位定義  
   - **借款**：  
     - 國內金融機構借款-短期借款: 指與國內金融機構簽訂借款合約時，原始借款期間為一年以內，且需支付利息者，歸屬於短期借款。
        應付商業本票通常是金融機構協助發行，可直接列為跟金融機構借款。
        不包含「應付公司債」。
     - 國內金融機構借款-長期借款: 指與國內金融機構簽訂借款合約時，原始借款期間超過一年，且需支付利息者。
        即便該筆借款在資產負債表日距到期日少於一年，財報上列為「一年內到期長期負債」（流動負債）者，仍視為長期借款項目。
        應付商業本票通常是金融機構協助發行，可直接列為跟金融機構借款。
        不包含「應付公司債」。

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣，例如當出現支票存款時且沒有幣別時，則默認為支票存款(新台幣)。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
"""
