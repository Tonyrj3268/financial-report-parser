from pydantic import BaseModel, Field
from .base import LabeledValue


class ReceivablesRelatedParties(BaseModel):
    """應收帳款及應收票據明細表"""

    # 1. 應收帳款 (或應收款項)
    accounts_receivable: LabeledValue = Field(
        ...,
        alias="應收帳款 (或應收款項)",
    )

    # 2. 應收票據
    notes_receivable: LabeledValue = Field(
        ...,
        alias="應收票據",
    )

    # 3. 其他應收款 (或其他應收帳款)
    other_receivables: LabeledValue = Field(
        ...,
        alias="其他應收款 (或其他應收帳款)",
    )

    # 4. 應收帳款-關係人 (應收關係人帳款)
    accounts_receivable_related_parties: LabeledValue = Field(
        ...,
        alias="應收帳款-關係人 (應收關係人帳款)",
    )

    # 5. 其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)
    other_receivables_related_parties: LabeledValue = Field(
        ...,
        alias="其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)",
    )
    unit_is_thousand: bool = Field(
        None,
        alias="單位是否為千元",
    )


receivables_related_parties_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」和其提到的相關附註或附錄，並回傳對應的純 JSON，欄位名稱請使用以下 alias（中文）：

1. 模型欄位結構  
   - **應收帳款 (或應收款項)**：數值為 { 金額 }，主要為應收客戶的款項
   - **應收票據**：數值為 { 金額 }，主要為應收客戶的票據
   - **其他應收款 (或其他應收帳款)**：數值為 { 金額 }，主要為其他應收款項
   - **應收帳款-關係人 (應收關係人帳款)**：數值為 { 金額 }，主要為應收關係人的帳款
   - **其他應收款-關係人 (其他關係人應收款、其他應收關係人、其他應收關係人款項)**：數值為 { 金額 }，主要為其他應收關係人的款項
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
倘若有組合的項目，例如「應收票據及帳款」，則請將其填入應收帳款，並在應收票據填入0。
有些欄位名稱不一定和我提供的完全一樣，請你根據上下文和數據內容和會計知識，自行判斷。
"""
