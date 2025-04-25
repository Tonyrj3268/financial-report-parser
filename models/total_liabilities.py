from typing import List

from pydantic import BaseModel, Field, StrictFloat


class ForiginDeposit(BaseModel):
    currency: str = Field(
        ...,
        alias="幣別",
        description="The currency type of the deposit.",
    )
    amount_list: List[float] = Field(
        ...,
        alias="金額清單",
        description="List of amounts in the original currency.",
    )
    exchange_rate: float = Field(
        ...,
        alias="匯率",
        description="The exchange rate to New Taiwan dollars.",
    )

    @property
    def amount_in_twd(self) -> List[float]:
        """
        Convert the amounts in the original currency to New Taiwan dollars using the exchange rate.
        """
        return sum(self.amount_list) * self.exchange_rate


class TotalLiabilities(BaseModel):
    domestic_bank_short_term_loans: List[StrictFloat] = Field(
        ...,
        alias="國內金融機構借款 - 短期借款",
        description="The amount of short-term loans from domestic financial institutions.",
    )
    domestic_bank_long_term_loans: List[StrictFloat] = Field(
        ...,
        alias="國內金融機構借款 - 長期借款",
        description="The amount of long-term loans from domestic financial institutions.",
    )

    def to_rows(self) -> List[List]:
        """
        Convert the CashEquivalents object to a list of rows for easier display.
        """
        rows: List[List] = []
        rows.append(["負債合計"])
        rows.append(
            [
                "一、國內金融機構借款",
                self.domestic_bank_short_term_loans,
                self.domestic_bank_long_term_loans,
            ]
        )

        return rows


cash_equivalents_prompt = """
    # 指令：處理 PDF 財務報表資料

    ## 1. 主要目標
    請分析提供的 PDF 檔案內容，定位到「現金及約當現金明細表」（或具有類似名稱、包含相關現金與銀行存款明細的表格/段落）。

    ## 2. 資料提取與計算要求
    從定位到的表格/段落中，提取以下資訊，並執行必要的計算：

    * **庫存現金及零用金**: 找到對應的數值。
    * **活期性存款(新台幣)**: 找到標示為此項目的數值。
    * **定期性存款(新台幣)**: 找到標示為此項目的數值。
    * **外匯活期和及定期存款**：
        * 識別所有列出的外幣幣別及其【原幣金額】（需注意來源可能是活期、定期或其他類型）。
        * 找出該外幣幣別的匯率（通常標示為 '@' 或在附近說明），不需要幫我換算。
        * **請列出同一幣別下所有類型存款的各筆【計算後金額】清單，讓我自己加總。**

    ## 3. 輸出格式與規範 (極重要)

    * **計算與單位**：
        * **確保**最終輸出中的【所有】貨幣數值都以【元】為單位。如果資料來源使用「仟元」或其他單位，必須換算為「元」（例如，「仟元」需乘以 1000）。
    * **找不到項目處理**：如果在來源文件中找不到某個明確的項目（例如「定期性存款(新台幣)」），請在對應的 JSON 值中使用 `unfind`。

    ## 4. 執行
    請嚴格按照以上所有要求進行處理。
    """
