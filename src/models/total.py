from .cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from .total_liabilities import TotalLiabilities, total_liabilities_prompt
from .receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from .prepayments import PrePayments, prepayments_prompt
from pydantic import BaseModel, Field
from typing import List


class FinancialReport(BaseModel):
    """財報"""

    cash_equivalents_related_pages: List[int]
    total_liabilities_related_pages: List[int]
    receivables_related_parties_related_pages: List[int]
    prepayments_related_pages: List[int]


financial_report_prompt = """
1. 請你仔細閱讀以上檔案，並且回答以下問題：
  a. 現金及約當現金明細表和其相關數據在哪些頁面有出現？
    - 其相關數據包含：庫存現金 、零用金 、週轉金 、待交換票據 、運送中現金 、新台幣活期存款 、新台幣定期存款 、新台幣支票存款 、外幣活期存款 、外幣定期存款 、外幣支票存款 、商業本票 、附買回交易
  b. 負債總額和其相關數據在哪些頁面有出現？
    - 其相關數據包含：國內金融機構借款-短期借款、國內金融機構借款-長期借款
  c. 應收帳款及應收票據明細表和其相關數據在哪些頁面有出現？
    - 其相關數據包含：應收帳款 (或應收款項)、應收票據、其他應收款 (或其他應收帳款)、應收帳款-關係人 (應收關係人帳款)、其他應收款-關係人 (其他關係人應收款)
  d. 預付款項明細表和其相關數據在哪些頁面有出現？
    - 其相關數據包含：預付款項、預付設備款

請注意
    請盡可能的找出相關的頁面，不要省略任何頁面。
    如果某項數據在多個頁面有出現，請你列出所有頁面。
    如果某項欄位後面寫著[備註]，請你列出該備註存在的頁面。
    通常頁數會在 START OF PAGE: {pageNumber}\n\n 這行，請你注意。
"""
