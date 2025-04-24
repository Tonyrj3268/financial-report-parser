from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, StrictFloat
from typing import List, Dict, Any

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


class FinancialReport(BaseModel):
    cash_and_petty: StrictFloat = Field(
        ...,
        alias="庫存現金及零用金",
        description="The amount of cash and petty cash after calculations in yuan.",
    )
    current_deposits_twd: StrictFloat = Field(
        ...,
        alias="活期性存款(新台幣)",
        description="The amount of current deposits in New Taiwan dollars after calculations.",
    )
    time_deposits_twd: StrictFloat = Field(
        ...,
        alias="定期性存款(新台幣)",
        description="The amount of time deposits in New Taiwan dollars after calculations.",
    )
    foreign_deposits: List[ForiginDeposit] = Field(
        ...,
        alias="外匯活期和及定期存款",
        description=(
            "List of foreign currency deposits. Each item is a dict with keys: '幣別' (str), '金額清單' (List[float]), '匯率' (float)."
        ),
    )


def upload_file(file_path, purpose="user_data"):
    file = client.files.create(file=open(file_path, "rb"), purpose=purpose)
    return file.id


def chat_with_file(file_id, text):
    response = client.responses.parse(
        model="gpt-4.1",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file_id,
                    },
                    {
                        "type": "input_text",
                        "text": text,
                    },
                ],
            }
        ],
        text_format=FinancialReport,
    )
    return response.output_parsed


if __name__ == "__main__":

    file_id = upload_file("TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf")
    # file_id = "file-Tfj9Xeh7GjrdvaSdbE934E"
    print("File uploaded, id:", file_id)
    # cash_equivalents_prompt = """
    # # 指令：處理 PDF 財務報表資料並僅輸出 JSON

    # ## 1. 主要目標
    # 請分析提供的 PDF 檔案內容，定位到「現金及約當現金明細表」（或具有類似名稱、包含相關現金與銀行存款明細的表格/段落）。

    # ## 2. 資料提取與計算要求
    # 從定位到的表格/段落中，提取以下資訊，並執行必要的計算：

    # * **庫存現金及零用金**: 找到對應的數值。
    # * **國內金融機構存款 - 活期性存款(新台幣)**: 找到明確標示為此項目的數值。
    # * **國內金融機構存款 - 定期性存款(新台幣)**: 找到明確標示為此項目的數值。
    # * **外匯存款**:
    #     * 識別所有列出的外幣幣別及其【原幣金額】（需注意來源可能是活期、定期或其他類型）。
    #     * **必須**使用文本中針對各外幣存款提供的【匯率】（通常標示為 '@' 或在附近說明）來計算其【新台幣 (NTD) 等值金額】。
    #     * **必須**加總【同一幣別】下所有類型存款（例如：活期+定期）的【計算後新台幣金額】。

    # ## 3. 輸出格式與規範 (極重要)

    # * **計算與單位**:
    #     * **必須**執行所有必要的匯率換算。
    #     * **確保**最終 JSON 輸出中的【所有】貨幣數值都以【新台幣 (NTD) 的「元」】為單位。如果來源資料使用「仟元」或其他單位，必須換算為「元」（例如，「仟元」需乘以 1000）。
    # * **輸出內容**:
    #     * 您的回應**必須且只能**是以下結構的 JSON 物件。
    #     * **嚴禁**包含任何 JSON 結構之外的文字，例如：前導說明、解釋、摘要、註解、標題、確認訊息、計算過程等。
    # * **JSON 結構**:
    #     ```json
    #     {
    #     "庫存現金及零用金": [計算後金額_元],
    #     "國內金融機構存款": {
    #         "活期性存款(新台幣)": [計算後金額_元],
    #         "定期性存款(新台幣)": [計算後金額_元],
    #         "外匯存款(折合新台幣)": [
    #         {
    #             "幣別": "幣別1",
    #             "金額(新台幣)": [該幣別所有存款類型加總計算後的新台幣金額_元]
    #         },
    #         {
    #             "幣別": "幣別2",
    #             "金額(新台幣)": [該幣別所有存款類型加總計算後的新台幣金額_元]
    #         }
    #         // ... 其他外幣，若存在則依此格式加入
    #         ]
    #     }
    #     }
    #     ```
    # * **找不到項目處理**: 如果在來源文件中找不到某個明確的項目（例如「定期性存款(新台幣)」），請在對應的 JSON 值中使用 `null`。如果能確定金額為零，則使用 `0`。

    # ## 4. 執行
    # 請嚴格按照以上所有要求進行處理，並僅輸出最終的 JSON 結果。
    # """
    # cash_equivalents_prompt = """
    # # 指令：處理 PDF 財務報表資料並僅輸出 JSON

    # ## 1. 主要目標
    # 請分析提供的 PDF 檔案內容，定位到「現金及約當現金明細表」（或具有類似名稱、包含相關現金與銀行存款明細的表格/段落）。

    # ## 2. 資料提取與計算要求
    # 從定位到的表格/段落中，提取以下資訊，並執行必要的計算：

    # * **庫存現金及零用金**: 找到對應的數值。
    # * **活期性存款(新台幣)**: 找到標示為此項目的數值。
    # * **定期性存款(新台幣)**: 找到標示為此項目的數值。
    # * **外匯活期和及定期存款**：
    #     * 識別所有列出的外幣幣別及其【原幣金額】（需注意來源可能是活期、定期或其他類型）。
    #     * 找出該外幣幣別的匯率（通常標示為 '@' 或在附近說明），不需要幫我換算。
    #     * **請列出同一幣別下所有類型存款的各筆【計算後金額】清單，讓我自己加總。**

    # ## 3. 輸出格式與規範 (極重要)

    # * **計算與單位**：
    #     * **確保**最終 JSON 輸出中的【所有】貨幣數值都以【元】為單位。如果來源資料使用「仟元」或其他單位，必須換算為「元」（例如，「仟元」需乘以 1000）。
    # * **輸出內容**：
    #     * 您的回應**必須且只能**是以下結構的 JSON 物件。
    #     * **嚴禁**包含任何 JSON 結構之外的文字，例如：前導說明、解釋、摘要、註解、標題、確認訊息、計算過程等。
    # * **JSON 結構**：
    #     ```json
    #     {
    #       "庫存現金及零用金": [計算後金額_元],
    #       "國內金融機構存款": {
    #         "活期性存款(新台幣)": [計算後金額_元],
    #         "定期性存款(新台幣)": [計算後金額_元],
    #         "外匯活期和及定期存款": [
    #           {
    #             "幣別": "幣別1",
    #             "金額清單": [該幣別各筆存款計算後金額_元, ...],
    #             "匯率": [該幣別對新台幣的匯率_元]
    #           },
    #           {
    #             "幣別": "幣別2",
    #             "金額清單": [該幣別各筆存款計算後金額_元, ...],
    #             "匯率": [該幣別對新台幣的匯率_元]
    #           }
    #           // ... 其他外幣
    #         ]
    #       }
    #     }
    #     ```
    # * **找不到項目處理**：如果在來源文件中找不到某個明確的項目（例如「定期性存款(新台幣)」），請在對應的 JSON 值中使用 `unfind`。如果能確定金額為零，則使用 `0`。

    # ## 4. 執行
    # 請嚴格按照以上所有要求進行處理，並僅輸出最終的 JSON 結果。
    # """
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
        * **確保**最終輸出中的【所有】貨幣數值都以【元】為單位。如果來源資料使用「仟元」或其他單位，必須換算為「元」（例如，「仟元」需乘以 1000）。
    * **找不到項目處理**：如果在來源文件中找不到某個明確的項目（例如「定期性存款(新台幣)」），請在對應的 JSON 值中使用 `unfind`。如果能確定金額為零，則使用 `0`。

    ## 4. 執行
    請嚴格按照以上所有要求進行處理。
    """
    reply = chat_with_file(file_id, cash_equivalents_prompt)
    print("AI 回覆：", reply)
