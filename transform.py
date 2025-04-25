from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, StrictFloat
from typing import List

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

    @property
    def amount_in_twd(self) -> List[float]:
        """
        Convert the amounts in the original currency to New Taiwan dollars using the exchange rate.
        """
        return sum(self.amount_list) * self.exchange_rate


class CashEquivalents(BaseModel):
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
        alias="外匯活期及定期存款",
        description=(
            "List of foreign currency deposits. Each item is a dict with keys: '幣別' (str), '金額清單' (List[float]), '匯率' (float)."
        ),
    )

    def to_rows(self) -> List[List]:
        """
        Convert the CashEquivalents object to a list of rows for easier display.
        """
        rows: List[List] = []
        rows.append(["一、庫存現金及零用金", self.cash_and_petty])
        rows.append(["二、國內金融機構存款"])
        rows.append(["1.活期性存款(新台幣)", self.current_deposits_twd])
        rows.append(["2.定期性存款(新台幣)", self.time_deposits_twd])
        all_fx = [fd.amount_in_twd for fd in self.foreign_deposits]
        rows.append(["3.外匯活期和及定期存款", *all_fx[:3], sum(all_fx[3:])])

        return rows


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
        text_format=CashEquivalents,
        temperature=0,
    )
    return response.output_parsed


if __name__ == "__main__":

    file_id = upload_file("20240314171909745560928_tc.pdf")
    # file_id = "file-Tfj9Xeh7GjrdvaSdbE934E"
    print("File uploaded, id:", file_id)
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
    print("Origin: ", reply)
    print("AI 回覆：", reply.to_rows())
