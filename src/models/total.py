from .cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from .total_liabilities import TotalLiabilities, total_liabilities_prompt
from .receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from .prepayments import PrePayments, prepayments_prompt
from pydantic import BaseModel, Field


class FinancialReport(BaseModel):
    """財報"""

    cash_equivalents: CashAndEquivalents = Field(
        ..., description="現金及約當現金明細表"
    )
    total_liabilities: TotalLiabilities = Field(..., description="負債總額")  # 負債總額
    receivables_related_parties: ReceivablesRelatedParties = Field(
        ..., description="應收帳款及應收票據明細表"
    )
    prepayments: PrePayments = Field(..., description="預付款項明細表")


financial_report_prompt = (
    cash_equivalents_prompt
    + total_liabilities_prompt
    + receivables_related_parties_prompt
    + prepayments_prompt
)
