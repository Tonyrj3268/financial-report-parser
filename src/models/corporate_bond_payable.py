from typing import List
from pydantic import BaseModel, Field
from .base import LabeledValue, convert_to_thousand
from enum import Enum
from openpyxl import Workbook


class CounterpartyType(str, Enum):
    DOMESTIC_BANK = "金融機構"
    GOVERNMENT = "政府"
    NON_FINANCIAL_INSTITUTION = "企業或關係企業"
    PERSON = "個人及非營利團體"
    OVERSEAS = "國外"


class CorporateBondDetail(BaseModel):
    """
    個別公司債金額與對象和類型
    """

    amount: LabeledValue = Field(..., description="公司債金額")
    counterparty: str = Field(..., description="對象")
    counterparty_type: CounterpartyType = Field(..., description="對象類型")


class CorporateBondPayable(BaseModel):
    """
    15. 應付公司債（短期 + 長期）
    """

    due_within_one_year: List[CorporateBondDetail] = Field(
        description="一年內到期公司債"
    )
    domestic_bonds: List[CorporateBondDetail] = Field(
        description="應付國內公司債（207000）"
    )
    foreign_bonds: List[CorporateBondDetail] = Field(
        description="應付國外有價證券（208000）"
    )

    # 報表是否以千元為單位
    unit_is_thousand: bool = Field(
        description="True 表示報表金額已除以 1,000；False 則為元"
    )

    def fill_excel(self, wb: Workbook):
        ws_liabilities = wb["負債表 "]
        # 一年內到期公司債
        due_within_one_year_total = convert_to_thousand(
            sum(detail.amount.value for detail in self.due_within_one_year),
            self.unit_is_thousand,
        )
        ws_liabilities["C23"] = (
            due_within_one_year_total if due_within_one_year_total > 0 else None
        )
        # 應付國內公司債（207000）
        domestic_bonds_total = convert_to_thousand(
            sum(detail.amount.value for detail in self.domestic_bonds),
            self.unit_is_thousand,
        )
        ws_liabilities["D23"] = (
            domestic_bonds_total if domestic_bonds_total > 0 else None
        )
        # 應付國外有價證券（208000）
        foreign_bonds_total = convert_to_thousand(
            sum(detail.amount.value for detail in self.foreign_bonds),
            self.unit_is_thousand,
        )
        ws_liabilities["C24"] = foreign_bonds_total if foreign_bonds_total > 0 else None


corporate_bond_payable_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」的「一年內到期公司債」、「一年內到期長期負債」或「應付公司債」科目，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：
企業資產負債表的「一年內到期公司債」，發行地若在國內，應填在「一年內到期公司債」;「一年內到期長期負債」中的公司債或「應付公司債」,發行地若在國內,應填在「應付國內公司債（207000）」;發行地若在國外,則填在「應付國外有價證券（208000）」。

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  
  
1. 模型欄位定義  
   - **一年內到期公司債**：指企業因銷售商品或提供勞務等主要營業活動產生，依法向客戶收取款項的債權。通常列為流動資產，並於資產負債表中單獨列示。
   - **應付國內公司債（207000）**：指企業因銷售商品或提供勞務等，向客戶發出的票據，如支票、匯票等。
   - **應付國外有價證券（208000）**：指除應收帳款以外，因非主要營業活動或非經常性事項產生的各類應收款項，例如員工借支、保險理賠、押金、代墊款項等。
   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
同一個表和註解中並非所有的數值單位都是一樣的，如果整張表默認單位為千元，但是有些項目卻在數值後面加上元，則請記得在該項目的unit_is_thousand回傳False。例如:"USD 47,534,325.95元" 這種情況請在該幣種的unit_is_thousand回傳False。
有些欄位名稱不一定和我提供的完全一樣，請你根據上下文和數據內容和會計知識，自行判斷。
"""
