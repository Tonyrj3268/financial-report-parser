from pydantic import BaseModel, Field
from .base import LabeledValue, convert_to_thousand
from typing import List
from openpyxl import Workbook
from enum import Enum


class CounterpartyType(str, Enum):
    DOMESTIC_BANK = "金融機構"
    GOVERNMENT = "政府"
    NON_FINANCIAL_INSTITUTION = "企業或關係企業"
    PERSON = "個人及非營利團體"
    OVERSEAS = "國外"


class PrePaymentDetail(BaseModel):
    """一筆預付款：依對象分類拆分後的金額明細"""

    amount: LabeledValue = Field(..., description="拆分後的預付款金額")
    counterparty: str = Field(..., description="對象單位名稱")
    counterparty_type: CounterpartyType = Field(..., description="對象類型")


class PrePayments(BaseModel):
    """預付款項"""

    prepayments_for_good: List[PrePaymentDetail] = Field(
        ...,
        description="預付款項",
    )
    prepayments_for_equipment: List[PrePaymentDetail] = Field(
        ...,
        description="預付設備款",
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        ws_prepayment = wb["附表1-應收預付及應付預收款項明細表"]

        # 企業預付貨款
        prepayments_for_good_total = convert_to_thousand(
            sum(
                detail.amount.value
                for detail in self.prepayments_for_good
                if detail.counterparty_type
                == CounterpartyType.NON_FINANCIAL_INSTITUTION
            ),
            self.unit_is_thousand,
        )
        ws_prepayment["C31"] = (
            prepayments_for_good_total if prepayments_for_good_total > 0 else None
        )
        # 企業預付設備款
        prepayments_for_equipment_total = convert_to_thousand(
            sum(
                detail.amount.value
                for detail in self.prepayments_for_equipment
                if detail.counterparty_type
                == CounterpartyType.NON_FINANCIAL_INSTITUTION
            ),
            self.unit_is_thousand,
        )
        ws_prepayment["C33"] = (
            prepayments_for_equipment_total
            if prepayments_for_equipment_total > 0
            else None
        )
        # 國外預付貨款
        prepayments_for_good_overseas_total = convert_to_thousand(
            sum(
                detail.amount.value
                for detail in self.prepayments_for_good
                if detail.counterparty_type == CounterpartyType.OVERSEAS
            ),
            self.unit_is_thousand,
        )
        ws_prepayment["C47"] = (
            prepayments_for_good_overseas_total
            if prepayments_for_good_overseas_total > 0
            else None
        )


prepayments_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  

1. 模型欄位定義  
   - **預付款項**：是一個列表，包含多筆預付款明細，每筆明細都必須依對象分類。是指企業預先支付的各項成本或費用，包括預付費用及預付購料款等，通常屬於未來12個月內會實現者，列為流動資產。
        如果預付款項的效益超過一年，例如長期預付租金、保險費、投資款、退休金等，則歸類為其他非流動資產。
        若無特別標註，通常預付款項是位於[其他流動資產]或[其他非流動資產]下的一個子項目，但不表示流動資產或非流動資產一定為預付款項。
        若無特別說明對象類型，以我國產業生產的情況,請自行判斷該公司產品可能的對象類型。
        每筆預付款明細包含：
        * amount: LabeledValue格式的金額
        * counterparty: 對象單位名稱(字串)
        * counterparty_type: 對象類型，必須為以下五種之一：
          - "金融機構"：銀行、信用合作社等金融機構
          - "政府"：政府機關、國營事業等
          - "企業或關係企業"：一般企業、子公司、關係企業等
          - "個人及非營利團體"：個人、非營利組織等
          - "國外"：國外企業

   - **預付設備款**：是一個列表，包含多筆預付設備款明細，每筆明細都必須依對象分類。預付設備款是企業依合約條款，為購置設備而預先支付的款項。
        依IFRS規範，應依其性質分類為「其他非流動資產」項下（如預付設備款）。
        若無特別標註，通常預付設備款是位於[其他非流動資產]下的一個子項目，但不表示非流動資產一定為預付設備款。
        若無特別說明對象類型，以我國產業生產的情況,大部分預付設備款,多是預付訂金給國外機器設備廠商訂購機器較為普遍。因此,若無從判別「預付設備款」之對象,可視為「國外」。
        每筆預付設備款明細包含：
        * amount: LabeledValue格式的金額
        * counterparty: 對象單位名稱(字串)
        * counterparty_type: 對象類型，必須為以下五種之一：
          - "金融機構"：銀行、信用合作社等金融機構
          - "政府"：政府機關、國營事業等
          - "企業或關係企業"：一般企業、子公司、關係企業等
          - "個人及非營利團體"：個人、非營利組織等
          - "國外"：國外企業

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣，例如當出現預付款項時且沒有幣別時，則默認為預付款項(新台幣)。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
必須將每筆預付款項和預付設備款按照對象進行分類，如果附註中沒有明確說明對象，請根據上下文推斷最合適的對象類型。
如果某個類別沒有相關數據，請返回空陣列[]，而不是省略該欄位。
請盡可能的填充完整，不要漏掉任何公司預付款項和預付設備款的相關數據。
"""
