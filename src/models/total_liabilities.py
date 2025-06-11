from enum import Enum
from typing import List

import pandas as pd
from openpyxl import Workbook
from pydantic import BaseModel, Field

from .base import LabeledValue, convert_to_thousand


class LoanDetail(BaseModel):
    """一筆借款：包含金額與借款對象"""

    amount: LabeledValue = Field(..., description="借款金額")
    counterparty: str = Field(..., description="借款對象")

    class CounterpartyType(str, Enum):
        DOMESTIC_BANK = "國內金融機構"
        GOVERNMENT = "政府"
        NON_FINANCIAL_INSTITUTION = "國內非金融機構或其他企業或關係企業"
        PERSON = "個人及非營利團體"
        OVERSEAS_BANK = "國外金融機構或關係企業"

    counterparty_type: CounterpartyType = Field(..., description="借款對象類型")


class TotalLiabilities(BaseModel):
    """負債總額"""

    domestic_bank_short_term_loans: List[LoanDetail] = Field(
        ...,
        description="國內金融機構借款-短期借款 (201000)",
    )
    domestic_bank_long_term_loans: List[LoanDetail] = Field(
        ...,
        description="國內金融機構借款-長期借款 (201000)",
    )
    policy_loans: List[LoanDetail] = Field(..., description="政策性放款 (202010)")
    enterprise_interest_loans: List[LoanDetail] = Field(
        ..., description="向國內其他企業或關係企業有息借款 (202020)"
    )
    personal_nonprofit_loans: List[LoanDetail] = Field(
        ..., description="向個人及非營利團體有息借款 (202030)"
    )
    overseas_financial_loans: List[LoanDetail] = Field(
        ..., description="向國外金融機構或關係企業借款 (203000)"
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        ws_liabilities = wb["負債表 "]

        # 國內金融機構借款-短期借款
        domestic_bank_short_term_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.domestic_bank_short_term_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["C8"] = (
            domestic_bank_short_term_loans_total
            if domestic_bank_short_term_loans_total > 0
            else None
        )

        # 國內金融機構借款-長期借款
        domestic_bank_long_term_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.domestic_bank_long_term_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["D8"] = (
            domestic_bank_long_term_loans_total
            if domestic_bank_long_term_loans_total > 0
            else None
        )

        # 政策性放款
        policy_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.policy_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["C10"] = policy_loans_total if policy_loans_total > 0 else None

        # 向國內其他企業或關係企業有息借款
        enterprise_interest_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.enterprise_interest_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["C11"] = (
            enterprise_interest_loans_total
            if enterprise_interest_loans_total > 0
            else None
        )

        # 向個人及非營利團體有息借款
        personal_nonprofit_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.personal_nonprofit_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["C12"] = (
            personal_nonprofit_loans_total
            if personal_nonprofit_loans_total > 0
            else None
        )

        # 向國外金融機構或關係企業借款
        overseas_financial_loans_total = convert_to_thousand(
            sum(loan.amount.value for loan in self.overseas_financial_loans),
            self.unit_is_thousand,
        )
        ws_liabilities["C13"] = (
            overseas_financial_loans_total
            if overseas_financial_loans_total > 0
            else None
        )


total_liabilities_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  

- LoanDetail：每筆借款的詳細資訊，包含：
  - amount: LabeledValue 結構的借款金額
  - counterparty: 借款對象名稱（字串）
  - counterparty_type: 借款對象類型，必須為以下其中一種：
    * "國內金融機構"
    * "政府"  
    * "國內非金融機構或其他企業或關係企業"
    * "個人及非營利團體"
    * "國外金融機構或關係企業"

1. 模型欄位定義  
   - **domestic_bank_short_term_loans**（國內金融機構借款-短期借款）: 指與國內金融機構簽訂借款合約時，原始借款期間為一年以內，且需支付利息者，歸屬於短期借款。
     應付商業本票通常是金融機構協助發行，可直接列為跟金融機構借款。
     不包含「應付公司債」。
     
   - **domestic_bank_long_term_loans**（國內金融機構借款-長期借款）: 指與國內金融機構簽訂借款合約時，原始借款期間超過一年，且需支付利息者。
     即便該筆借款在資產負債表日距到期日少於一年，財報上列為「一年內到期長期負債」（流動負債）者，仍視為長期借款項目。
     應付商業本票通常是金融機構協助發行，可直接列為跟金融機構借款。
     不包含「應付公司債」。
     
   - **policy_loans**（政策性放款）: 政府提供的政策性借款或補助性借款。
   
   - **enterprise_interest_loans**（向國內其他企業或關係企業有息借款）: 向國內非金融機構、其他企業或關係企業借款且需支付利息者。
   
   - **personal_nonprofit_loans**（向個人及非營利團體有息借款）: 向個人或非營利團體借款且需支付利息者。
   
   - **overseas_financial_loans**（向國外金融機構或關係企業借款）: 向國外金融機構或海外關係企業借款。通常會在財報中明確指出為境外分行。

   - **unit_is_thousand**（單位是否為千元）：布林值，True 代表單位為千元，False 代表單位為元

注意事項
每個借款類別都是 LoanDetail 的陣列，每筆借款都需要包含 amount、counterparty 和 counterparty_type。
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入空陣列 []。
沒有特別說明幣種的話，默認為新台幣，例如當出現支票存款時且沒有幣別時，則默認為支票存款(新台幣)。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
若同一筆借款同時出現在主表與附註，僅擇一來源為主。
「一年內到期長期借款」仍視為長期借款。
若未明確指出為境外分行，通常將位於台灣境內經營的國際銀行視為國內金融機構。
根據借款對象自動判斷 counterparty_type，例如：銀行屬於「國內金融機構」，政府單位屬於「政府」等。
"""
