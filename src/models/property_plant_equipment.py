from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from .base import LabeledValue
from openpyxl import Workbook


class PropertyPlantEquipment(BaseModel):
    """不動產、廠房及設備"""

    land_net: LabeledValue = Field(..., description="土地淨額 (110010)")
    bldg_plant_equip_net: LabeledValue = Field(
        ..., description="建築物、廠房及設備淨額 (110020)"
    )
    investment_property: LabeledValue = Field(
        ..., description="國內投資性不動產及閒置資產 (107000)"
    )
    lease_assets: LabeledValue = Field(
        ..., description="無形資產、生物資產、遞延資產及用品盤存 (111000)"
    )
    unit_is_thousand: bool = Field(None, description="單位是否為千元")

    def fill_excel(self, wb: Workbook):
        ws_asset = wb["資產表"]

        # 國內投資性不動產及閒置資產 (107000)
        ws_asset["C39"] = (
            self.investment_property.value
            if self.investment_property.value > 0
            else None
        )
        # 土地淨額 (110010)
        ws_asset["C49"] = self.land_net.value
        # 建築物、廠房及設備淨額 (110020)
        ws_asset["C50"] = self.bldg_plant_equip_net.value
        # 無形資產、生物資產、遞延資產及用品盤存 (111000)
        ws_asset["C51"] = (
            self.lease_assets.value if self.lease_assets.value > 0 else None
        )


property_plant_equipment_prompt = """
請你嚴格遵守以下指令，從提供的 PDF 中定位到「資產負債表」及其「重要會計項目之說明」或相關附註，並回傳對應的純 JSON，欄位名稱與結構請完全對應以下 Pydantic Model：

0. 共同結構說明
- LabeledValue：凡屬金額或匯率欄位，一律使用  
{ "value": <numeric>, "source_page": <list[int]>, "source_label": <list[原文欄位表名或原文頁名]> , "reason": <str>}  
  其中 value 為數值，source_page 為頁碼，source_label 為原文欄位表名或原文頁名，reason 為你從下方[模型欄位定義]中推斷出來的數值，請你嚴格遵守，不要有額外的解釋。  
  source_page 和 source_label 都是 list 型別，當 source_page 有多個頁碼時，請用逗號分隔；當 source_label 有多個欄位時，請用逗號分隔。  
  例如：{ "value": 1000, "source_page": [1,2], "source_label": ["現金及約當現金明細表", "現金明細表"] }  
  若 source_page 和 source_label 都只有一個值，則還是得使用 list，例如：{ "value": 1000, "source_page": [1], "source_label": ["現金"] }  

1. 模型欄位定義  
   - **土地淨額 (110010)**：指企業因銷售商品或提供勞務等主要營業活動產生，依法向客戶收取款項的債權。通常列為流動資產，並於資產負債表中單獨列示。
   - **建築物、廠房及設備淨額 (110020)**：指企業因銷售商品或提供勞務等，向客戶發出的票據，如支票、匯票等。
     「不動產、廠房及設備」項下若有「預付設備款」,應予以扣除。
     「不動產、廠房及設備」項下若有「投資性不動產」,則應列在資產表之「國內投資性不動產及閒置資產」。
     「不動產、廠房及設備」項下若有「租賃資產」,則應列在資產表的「無形資產、生物資產、遞延資產及用品盤存」。
   - **國內投資性不動產及閒置資產 (107000)**：指除應收帳款以外，因非主要營業活動或非經常性事項產生的各類應收款項，例如員工借支、保險理賠、押金、代墊款項等。
    「不動產、廠房及設備」項下若有「投資性不動產」,則應列在資產表之「國內投資性不動產及閒置資產」。
   - **無形資產、生物資產、遞延資產及用品盤存 (111000)**：指除應收帳款以外，因非主要營業活動或非經常性事項產生的各類應收款項，例如員工借支、保險理賠、押金、代墊款項等。
     「不動產、廠房及設備」項下若有「租賃資產」,則應列在資產表的「無形資產、生物資產、遞延資產及用品盤存」。
   - **單位是否為千元**：布林值，True 代表單位為千元，False 代表單位為元

3. 注意事項
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
