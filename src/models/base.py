from .cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from .total_liabilities import TotalLiabilities, total_liabilities_prompt

from pydantic import BaseModel, Field


class FinancialReport(BaseModel):
    """財報"""

    cash_equivalents: CashAndEquivalents = Field(..., alias="現金及約當現金明細表")
    total_liabilities: TotalLiabilities = Field(..., alias="負債總額")  # 負債總額


financial_report_prompt = cash_equivalents_prompt + total_liabilities_prompt
