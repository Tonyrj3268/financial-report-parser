import pandas as pd
from pydantic import BaseModel, Field
from openpyxl import Workbook

from .base import LabeledValue, convert_to_thousand
from enum import Enum


class CounterpartyType(str, Enum):
    DOMESTIC_BANK = "金融機構"
    GOVERNMENT = "政府"
    NON_FINANCIAL_INSTITUTION = "企業或關係企業"
    PERSON = "個人及非營利團體"
    OVERSEAS = "國外"
    UNKNOWN = "未知"


class ReceivablesRelatedPartiesDetail(BaseModel):
    """一筆應收帳款或應收票據：依對象分類拆分後的金額明細"""

    amount: LabeledValue = Field(..., description="拆分後的應收帳款或應收票據金額")
    counterparty: str = Field(..., description="對象單位名稱")
    counterparty_type: CounterpartyType = Field(..., description="對象類型")
    is_interest_bearing: bool = Field(
        ...,
        description="是否為計息",
    )


class ReceivablesRelatedParties(BaseModel):
    """應收帳款及應收票據明細表"""

    # 1. 應收帳款 (或應收款項)
    accounts_receivable: list[ReceivablesRelatedPartiesDetail] = Field(
        ...,
        description="應收帳款 (或應收款項)",
    )

    # 2. 應收票據
    notes_receivable: list[ReceivablesRelatedPartiesDetail] = Field(
        ...,
        description="應收票據",
    )

    # 3. 其他應收款 (或其他應收帳款)
    other_receivables: list[ReceivablesRelatedPartiesDetail] = Field(
        ...,
        description="其他應收款 (或其他應收帳款)",
    )

    # 4. 應收帳款-關係人 (應收關係人帳款)
    accounts_receivable_related_parties: list[ReceivablesRelatedPartiesDetail] = Field(
        ...,
        description="應收帳款-關係人 (應收關係人帳款)",
    )

    # 5. 其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)
    other_receivables_related_parties: list[ReceivablesRelatedPartiesDetail] = Field(
        ...,
        description="其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)",
    )
    unit_is_thousand: bool = Field(
        None,
        description="單位是否為千元",
    )

    def fill_excel(self, wb: Workbook):
        ws_receivables = wb["附表1-應收預付及應付預收款項明細表"]

        # 使用迴圈處理應收票據的不同類型
        notes_receivable_cells = {
            "C10": CounterpartyType.GOVERNMENT,  # 政府
            "C19": CounterpartyType.DOMESTIC_BANK,  # 金融機構
            "C27": CounterpartyType.NON_FINANCIAL_INSTITUTION,  # 企業（排除企業或關係企業）
            "C37": CounterpartyType.PERSON,  # 個人及非營利團體
        }

        for cell, counterparty_type in notes_receivable_cells.items():

            total = convert_to_thousand(
                sum(
                    note.amount.value
                    for note in self.notes_receivable
                    if note.counterparty_type == counterparty_type
                ),
                self.unit_is_thousand,
            )
            ws_receivables[cell] = total

        accounts_receivable_cells = {
            "C11": CounterpartyType.GOVERNMENT,
            "C20": CounterpartyType.DOMESTIC_BANK,
            "C38": CounterpartyType.PERSON,
        }

        for cell, counterparty_type in accounts_receivable_cells.items():
            total = convert_to_thousand(
                sum(
                    detail.amount.value
                    for detail in self.accounts_receivable
                    if detail.counterparty_type == counterparty_type
                ),
                self.unit_is_thousand,
            )
            ws_receivables[cell] = total

        # 應收帳款-未知
        accounts_receivable_unknown_total = convert_to_thousand(
            sum(
                [
                    detail.amount.value
                    for detail in self.accounts_receivable
                    if detail.counterparty_type == CounterpartyType.UNKNOWN
                ]
            ),
            self.unit_is_thousand,
        )

        # 應收帳款-企業
        accounts_receivable_total = convert_to_thousand(
            sum(
                [
                    detail.amount.value
                    for detail in self.accounts_receivable
                    if detail.counterparty_type
                    == CounterpartyType.NON_FINANCIAL_INSTITUTION
                ]
            ),
            self.unit_is_thousand,
        )
        ws_receivables["C28"] = (
            f"=ROUND(({accounts_receivable_unknown_total}*(1 - ROUND(('負債表 '!C43)/100,2))+{accounts_receivable_total}),0)"
        )

        # 應收帳款 - 國外
        accounts_receivable_overseas_total = convert_to_thousand(
            sum(
                [
                    detail.amount.value
                    for detail in self.accounts_receivable
                    if detail.counterparty_type == CounterpartyType.OVERSEAS
                ]
            ),
            self.unit_is_thousand,
        )
        ws_receivables["C45"] = (
            f"=ROUND({accounts_receivable_unknown_total}*ROUND(('負債表 '!C43)/100,2)+{accounts_receivable_overseas_total},0)"
        )

        accounts_receivable_related_parties_cells = {
            "C21": CounterpartyType.DOMESTIC_BANK,
            "C29": [
                CounterpartyType.NON_FINANCIAL_INSTITUTION,
                CounterpartyType.UNKNOWN,
            ],
            "C39": CounterpartyType.PERSON,
            "C46": CounterpartyType.OVERSEAS,
        }
        for (
            cell,
            counterparty_type,
        ) in accounts_receivable_related_parties_cells.items():
            total = convert_to_thousand(
                sum(
                    detail.amount.value
                    for detail in self.accounts_receivable_related_parties
                    if detail.counterparty_type in counterparty_type
                ),
                self.unit_is_thousand,
            )
            ws_receivables[cell] = total

        # 其他應收款-關係人(計息)
        ws_assests = wb["資產表"]
        other_receivables_related_parties_with_interest_cells = {
            "C15": CounterpartyType.GOVERNMENT,
            "C16": CounterpartyType.DOMESTIC_BANK,
            "C17": CounterpartyType.NON_FINANCIAL_INSTITUTION,
            "C18": CounterpartyType.PERSON,
            "C19": CounterpartyType.OVERSEAS,
        }
        for (
            cell,
            counterparty_type,
        ) in other_receivables_related_parties_with_interest_cells.items():
            total = convert_to_thousand(
                sum(
                    detail.amount.value
                    for detail in self.other_receivables_related_parties
                    if detail.counterparty_type == counterparty_type
                    and detail.is_interest_bearing
                ),
                self.unit_is_thousand,
            )
            ws_assests[cell] = total
        # 其他應收款-關係人(無計息)
        other_receivables_related_parties_without_interest_cells = {
            "F17": CounterpartyType.GOVERNMENT,
            "F24": CounterpartyType.DOMESTIC_BANK,
            "F31": CounterpartyType.NON_FINANCIAL_INSTITUTION,
            "F42": CounterpartyType.PERSON,
            "F47": CounterpartyType.OVERSEAS,
        }
        for (
            cell,
            counterparty_type,
        ) in other_receivables_related_parties_without_interest_cells.items():
            total = convert_to_thousand(
                sum(
                    detail.amount.value
                    for detail in self.other_receivables_related_parties
                    if detail.counterparty_type == counterparty_type
                    and not detail.is_interest_bearing
                ),
                self.unit_is_thousand,
            )
            ws_receivables[cell] = total


receivables_related_parties_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  
  
1. 模型欄位定義  
   - **應收帳款 (或應收款項)**：指企業因銷售商品或提供勞務等主要營業活動產生，依法向客戶收取款項的債權。通常列為流動資產，並於資產負債表中單獨列示。（IFRS 9）。如果你不確定對方公司是否為國內或海外企業，或是財報上沒有明確的提供公司名稱或地區以供判斷，請回傳CounterpartyType.UNKNOWN。
   - **應收票據**：指企業因銷售商品或提供勞務等，向客戶發出的票據，如支票、匯票等。（IFRS 9）。如果你不確定對方公司是否為國內或海外企業，或是財報上沒有明確的提供公司名稱或地區以供判斷，請回傳CounterpartyType.UNKNOWN。
   - **其他應收款 (或其他應收帳款)**：指除應收帳款以外，因非主要營業活動或非經常性事項產生的各類應收款項，例如員工借支、保險理賠、押金、代墊款項等。（IFRS 9）不包含「存出保證金」。須注意是否計息。
   - **應收帳款-關係人 (應收關係人帳款)**：指企業因銷售商品或提供勞務等，對關係人（如母公司、子公司、關聯企業等）產生的應收款項，需於財報中單獨揭露。（IFRS 24）不包含「應收票據-關係人」。
   - **其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)**：指企業因非主要營業活動或非經常性交易，對關係人產生的其他應收款項，例如借款、代墊款、保證金等，亦須單獨揭露。（IFRS 24）。須注意是否計息。

   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

2. 補充定義
   - 關係人通常包含：母子公司、關聯企業等。定義：若兩個或多個企業受同一個人/企業（或同一群人/企業）直接或間接控制，這些企業彼此間即為關係人（即使該控制人本身不參與經營）
   - 以上五項皆為獨立的項目，請不要重複計算或包含彼此。
注意事項
最終輸出中的【所有】貨幣數值都以資料來源為主。
欄位齊全：即使某些子欄位為 0 或空，也要列出並填入 0 或 null。
沒有特別說明幣種的話，默認為新台幣。
如果該數值用()表示，則請返回負數。
如果有去年和今年的數據，請返回今年的數據。
詳細的數據內容不一定只呈現在資產負債表上，請同時參考附註或附錄中的說明。
有些表的數據可能為合併的數據，可能和其附註或附錄的表的數據重複，請不要重複計算。
同一個表和註解中並非所有的數值單位都是一樣的，如果整張表默認單位為千元，但是有些項目卻在數值後面加上元，則請記得在該項目的unit_is_thousand回傳False。例如:"USD 47,534,325.95元" 這種情況請在該幣種的unit_is_thousand回傳False。
倘若有組合的項目，例如「應收票據及帳款」，則請將其填入應收帳款，並在應收票據填入0。
有些欄位名稱不一定和我提供的完全一樣，請你根據上下文和數據內容和會計知識，自行判斷。
"""
