from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ForeignDeposit(BaseModel):
    """外幣存款"""

    # 幣別
    currency: str = Field(..., alias="幣別")
    # 金額(外幣)
    foreign_amount: float = Field(..., alias="金額(外幣)")
    # 匯率
    exchange_rate: float = Field(..., alias="匯率")
    # 金額(新台幣)
    twd_amount: Optional[float] = Field(None, alias="金額(新台幣)")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


class ForeignDeposits(BaseModel):

    demand: List[ForeignDeposit] = Field(..., alias="外幣活期存款")
    term: List[ForeignDeposit] = Field(..., alias="外幣定期存款")
    checking: List[ForeignDeposit] = Field(..., alias="外幣支票存款")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


class TWDDeposit(BaseModel):
    """新台幣存款"""

    demand: float = Field(..., alias="活期性存款(新台幣)")
    term: float = Field(..., alias="定期性存款(新台幣)")
    checking: float = Field(..., alias="支票存款(新台幣)")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


class BasicCash(BaseModel):
    """現金項目"""

    on_hand: float = Field(..., alias="庫存現金")
    petty_cash: float = Field(..., alias="零用金")
    # 週轉金
    revolving_fund: float = Field(..., alias="週轉金")
    notes_for_exchange: float = Field(..., alias="待交換票據")
    in_transit: float = Field(..., alias="運送中現金")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


class MarketableInstrument(BaseModel):
    """約當現金–商業本票／附買回交易"""

    # 商業本票
    commercial_paper: float = Field(..., alias="商業本票")
    # 附買回交易
    repurchase_agreement: float = Field(..., alias="附買回交易")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


class CashAndEquivalents(BaseModel):
    """現金及約當現金明細總表"""

    cash: BasicCash = Field(..., alias="現金")
    twd_deposit: TWDDeposit = Field(..., alias="新台幣存款")
    foreign_deposits: ForeignDeposits = Field(..., alias="外幣存款")
    marketable_instruments: MarketableInstrument = Field(..., alias="約當現金")
    allowance_doubtful: float = Field(..., alias="備抵呆帳—存放銀行同業")
    subtotal: Optional[float] = Field(None, alias="小計")
    total: Optional[float] = Field(None, alias="合計")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, alias="單位是否為千元")


cash_equivalents_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「現金及約當現金明細表」，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

指令：抽取並回填「現金及約當現金明細表」

1. 模型欄位結構  
   - **現金**：  
     - 庫存現金  
     - 零用金  
     - 週轉金  
     - 待交換票據  
     - 運送中現金  
     - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
   - **新台幣存款**：  
     - 活期性存款(新台幣)：每項包含 { 金額(新台幣) }  
     - 定期性存款(新台幣)：同上結構  
     - 支票存款(新台幣)：同上結構
     - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
   - **外幣存款** ：  
     - 外幣活期存款：列表，每項包含 { 幣別, 金額(外幣), 匯率, Optional(金額(新台幣)) }，「其他」也屬於一種外幣類別  
     - 外幣定期存款：同上結構  
     - 外幣支票存款：同上結構  
     - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
   - **約當現金**：  
     - 商業本票  
     - 附買回交易  
     - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
   - **備抵呆帳—存放銀行同業** : 如果該數值用()表示，則請返回負數。
   - **小計**  
   - **合計**  

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣，例如當出現支票存款時且沒有幣別時，則默認為支票存款(新台幣)。
倘若有組合的項目，例如「支票存款及活期存款」，則請將其填入活期存款，並在支票存款填入0。
如果該數值用()表示，則請返回負數。
同一個表和註解中並非所有的數值單位都是一樣的，如果整張表默認單位為千元，但是有些項目卻在數值後面加上元，則請記得在該項目的unit_is_thousand回傳False。例如:"USD 47,534,325.95元" 這種情況請在該臂腫的unit_is_thousand回傳False。
"""
