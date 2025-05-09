from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class FinancialReportPages(BaseModel):
    """記錄財務報表中所有重要表格的頁碼"""

    company_name: str = Field(..., description="公司名稱")
    report_period: str = Field(..., description="報表期間")

    # 各種表格的頁碼列表
    balance_sheet_pages: List[int] = Field(
        default_factory=list, description="資產負債表頁碼"
    )
    income_statement_pages: List[int] = Field(
        default_factory=list, description="損益表頁碼"
    )
    cash_flow_pages: List[int] = Field(
        default_factory=list, description="現金流量表頁碼"
    )
    equity_changes_pages: List[int] = Field(
        default_factory=list, description="股東權益變動表頁碼"
    )
    prepayments_pages: List[int] = Field(
        default_factory=list, description="預付款項明細表頁碼"
    )
    cash_equivalents_pages: List[int] = Field(
        default_factory=list, description="現金及約當現金明細表頁碼"
    )
    total_liabilities_pages: List[int] = Field(
        default_factory=list, description="負債總額明細表頁碼"
    )

    def get_pages_for_table(self, table_type: str) -> List[int]:
        """根據表格類型獲取頁碼列表"""
        page_mapping = {
            "balance_sheet": self.balance_sheet_pages,
            "income_statement": self.income_statement_pages,
            "cash_flow": self.cash_flow_pages,
            "equity_changes": self.equity_changes_pages,
            "prepayments": self.prepayments_pages,
            "cash_equivalents": self.cash_equivalents_pages,
            "total_liabilities": self.total_liabilities_pages,
        }
        return page_mapping.get(table_type, [])


# 用於 GPT 的提示模板
table_locations_prompt = """
請分析財務報表，找出以下重要表格的頁碼：

1. 資產負債表（balance_sheet_pages）
2. 損益表（income_statement_pages）
3. 現金流量表（cash_flow_pages）
4. 股東權益變動表（equity_changes_pages）
5. 預付款項明細表（prepayments_pages）
6. 現金及約當現金明細表（cash_equivalents_pages）
7. 負債總額明細表（total_liabilities_pages）

請提供以下資訊：
- 公司名稱
- 報表期間
- 每個表格的頁碼列表（如果表格跨越多頁，請列出所有相關頁碼）

請以結構化的方式回答，確保包含所有必要資訊。如果某個表格不存在，請將對應的頁碼列表設為空列表。
"""
