from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from .base import LabeledValue, convert_to_thousand, BaseModelWithDefault
from openpyxl import Workbook


class ForeignDeposit(BaseModelWithDefault):
    """外幣存款"""

    # 幣別
    currency: str = Field(..., description="幣別")
    # 金額(外幣)
    foreign_amount: Optional[LabeledValue] = Field(..., description="金額(外幣)")
    # 匯率
    exchange_rate: LabeledValue = Field(..., description="匯率")
    # 金額(新台幣)
    twd_amount: Optional[LabeledValue] = Field(..., description="金額(新台幣)")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")


class ForeignDeposits(BaseModelWithDefault):
    """外幣存款"""

    demand_deposit: List[ForeignDeposit] = Field(..., description="外幣活期存款")
    time_deposit: List[ForeignDeposit] = Field(..., description="外幣定期存款")
    checking_deposit: List[ForeignDeposit] = Field(..., description="外幣支票存款")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")


class TWDDeposit(BaseModelWithDefault):
    """新台幣存款"""

    demand_deposit: Optional[LabeledValue] = Field(
        ..., description="活期性存款(新台幣)"
    )
    time_deposit: Optional[LabeledValue] = Field(..., description="定期性存款(新台幣)")
    checking_deposit: Optional[LabeledValue] = Field(
        ..., description="支票存款(新台幣)"
    )
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")


class BasicCash(BaseModelWithDefault):
    """現金項目"""

    on_hand: Optional[LabeledValue] = Field(..., description="庫存現金")
    petty_cash: Optional[LabeledValue] = Field(..., description="零用金")
    # 週轉金
    revolving_fund: Optional[LabeledValue] = Field(..., description="週轉金")
    notes_for_exchange: Optional[LabeledValue] = Field(..., description="待交換票據")
    in_transit: Optional[LabeledValue] = Field(..., description="運送中現金")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")


class MarketableInstrument(BaseModelWithDefault):
    """約當現金–商業本票／附買回交易"""

    # 商業本票
    commercial_paper: Optional[LabeledValue] = Field(..., description="商業本票")
    # 附買回交易
    repurchase_agreement: Optional[LabeledValue] = Field(..., description="附買回交易")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")


class CashAndEquivalents(BaseModel):
    """現金及約當現金明細總表"""

    cash: BasicCash = Field(..., description="現金")
    twd_deposit: TWDDeposit = Field(..., description="新台幣存款")
    foreign_deposits: ForeignDeposits = Field(..., description="外幣存款")
    marketable_instruments: MarketableInstrument = Field(..., description="約當現金")
    allowance_doubtful: Optional[LabeledValue] = Field(
        ..., description="備抵呆帳—存放銀行同業"
    )
    total: Optional[LabeledValue] = Field(None, description="合計")
    # 單位是否為１０００
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        # 資產表
        ws_asset = wb["資產表"]

        # 庫存現金及零用金
        ws_asset["C8"] = (
            convert_to_thousand(
                self.cash.on_hand.value + self.cash.petty_cash.value,
                self.cash.unit_is_thousand,
            )
            if (self.cash.on_hand.value + self.cash.petty_cash.value) > 0
            else None
        )
        # 活期性存款(新台幣) 支票存款
        ws_asset["C10"] = (
            convert_to_thousand(
                self.twd_deposit.checking_deposit.value,
                self.twd_deposit.unit_is_thousand,
            )
            if self.twd_deposit.checking_deposit.value > 0
            else convert_to_thousand(
                self.twd_deposit.demand_deposit.value,
                self.twd_deposit.unit_is_thousand,
            )
        )
        # 活期性存款(新台幣) 活期存款
        ws_asset["D10"] = (
            convert_to_thousand(
                self.twd_deposit.demand_deposit.value,
                self.twd_deposit.unit_is_thousand,
            )
            if self.twd_deposit.checking_deposit.value > 0
            else None
        )
        # 定期性存款(新台幣)
        ws_asset["C11"] = (
            convert_to_thousand(
                self.twd_deposit.time_deposit.value,
                self.twd_deposit.unit_is_thousand,
            )
            if self.twd_deposit.time_deposit.value > 0
            else None
        )

        # 外匯活期及定期存款
        def amount_in_twd(fd) -> float:
            """將存款折算為台幣並做千元單位轉換。"""
            raw = (
                fd.twd_amount.value
                if fd.twd_amount and fd.twd_amount.value > 0
                else fd.foreign_amount.value * fd.exchange_rate.value
            )
            return convert_to_thousand(raw, fd.unit_is_thousand)

        demand = self.foreign_deposits.demand_deposit
        top_three = sorted(demand, key=amount_in_twd, reverse=True)[:3]
        top_values = [amount_in_twd(fd) for fd in top_three] + [None] * (
            3 - len(top_three)
        )

        # 計算剩餘的活期存款、全部支票存款和定期存款的總和
        remaining_sum = sum(
            amount_in_twd(fd)
            for fd in (
                demand[3:]
                + self.foreign_deposits.checking_deposit
                + self.foreign_deposits.time_deposit
            )
        )
        ws_asset["F12"] = None

        # 填入前三大外幣活期存款
        for col, val in zip(("C12", "D12", "E12"), top_values):
            ws_asset[col] = val

        # 找第一個空位放 remaining_sum
        if remaining_sum > 0:
            for col in ("C12", "D12", "E12", "F12"):
                if ws_asset[col].value is None:
                    ws_asset[col] = remaining_sum
                    break


cash_equivalents_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到 「重要會計項目明細表」 中的「現金及約當現金明細表」，並回傳對應的純 JSON：

指令：抽取並回填「現金及約當現金明細表」

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  
  
1. 模型欄位定義 
   - **現金**：  
     - 庫存現金  
     - 零用金  
     - 週轉金  
     - 待交換票據  
     - 運送中現金  
     - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
   - **新台幣存款**(不包含外幣存款)：  
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
   - **合計**  

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元
注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣，例如當出現支票存款時且沒有幣別時，則默認為支票存款(新台幣)。
倘若有組合的項目，例如「支票存款及活期存款」，則請將其填入活期存款，並在支票存款填入0。「庫存現金及週轉金」的情況下，則請將其填入庫存現金，並在週轉金填入0。
除非有明確說出某外幣換算成新台幣的金額，否則請將金額(新台幣)設為 null，不要幫我做任何換算或加總。若沒有明確說出為何種外幣但是有提供金額(新台幣)，則請將金額(外幣), 匯率設為 null，填上提供的金額(新台幣)並在幣別中填入「其他」。
請注意台幣存款(不包含外幣存款)。
如果該數值用()表示，則請返回負數。
同一個表和註解中並非所有的數值單位都是一樣的，如果整張表默認單位為千元，但是有些項目卻在數值後面加上元，則請記得在該項目的unit_is_thousand回傳False。例如:"USD 47,534,325.95元" 這種情況請在該幣種的unit_is_thousand回傳False。
請仔細查看符號，不要把「,」誤認為「.」

其他
若資料來源為markdown，請注意"---"之間代表為同一頁的資料，通常第二個"---"之上的數字代表為頁碼。
"""
