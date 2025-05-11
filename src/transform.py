import logging
import os
from pprint import pformat

from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI

from models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from models.total_liabilities import TotalLiabilities, total_liabilities_prompt
import asyncio
from pydantic import BaseModel

# 設定 logging
logging.basicConfig(
    filename="transform.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def upload_file(file_path, purpose="user_data"):
    file = await client.files.create(file=open(file_path, "rb"), purpose=purpose)
    return file.id


async def chat_with_file(file_name, file_base64, text) -> str:
    response = await client.responses.create(
        model="gpt-4.1",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": file_name,
                        "file_data": f"data:application/pdf;base64,{file_base64}",
                    },
                    {
                        "type": "input_text",
                        "text": text,
                    },
                ],
            },
        ],
        temperature=0,
    )
    result = response.output_text
    logger.info(
        "花費Token數量: %s",
        response.usage.total_tokens,
    )
    logger.info(
        "解析結果:\n%s",
        pformat(result, indent=2, width=80, sort_dicts=False),
    )
    return result


async def parse_with_file(file_id, text, response_format) -> BaseModel:
    logger.info("與檔案互動，file_id=%s, prompt:\n%s", file_id, text)
    response = await client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "file_id": file_id,
                        },
                    },
                    {
                        "type": "text",
                        "text": text,
                    },
                ],
            }
        ],
        response_format=response_format,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    logger.info(
        "花費Token數量: %s",
        response.usage.total_tokens,
    )
    logger.info(
        "解析結果:\n%s",
        pformat(parsed.model_dump(), indent=2, width=80, sort_dicts=False),
    )
    return parsed


async def parse_with_markdown(markdown, text, response_format):
    logger.info("與Markdown互動，Markdown=%s, prompt:\n%s", markdown, text)
    response = await client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": markdown,
                    },
                    {
                        "type": "text",
                        "text": text,
                    },
                ],
            }
        ],
        response_format=response_format,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    logger.info(
        "花費Token數量: %s",
        response.usage.total_tokens,
    )
    logger.info(
        "解析結果:\n%s",
        pformat(parsed.model_dump(), indent=2, width=80, sort_dicts=False),
    )
    return parsed


async def main():
    # file_id = upload_file("quartely-results-2024-zh_tcm27-94407.pdf")
    # file_id = "file-X269JoL59QfurudTY48adv"  # 中信金
    # file_id = "file-LQokuRBxkg2CEp3PZiFBMf"  # 台積電
    # file_id = "file-FsNfKa6Ydbi2hRHKfW9TTw"  # 華碩
    # file_id = "file-4YPtrJes7jpnUSRf7BVAx1"  # 統一
    file_id = "file-KGXtvwDDkZ8wYCMRiAeRQg"  # 長榮航空
    print("File uploaded, id:", file_id)
    reply = await parse_with_file(file_id, cash_equivalents_prompt, CashAndEquivalents)
    # with open(
    #     "quartely-results-2024-zh_tcm27-94407.pdf.md", "r", encoding="utf-8"
    # ) as f:
    #     markdown = f.read()
    # reply = parse_with_markdown(markdown, cash_equivalents_prompt, CashAndEquivalents)
    print("Origin: ", reply)

    # reply = parse_with_file(file_id, total_liabilities_prompt, TotalLiabilities)
    # print("Origin: ", reply)


if __name__ == "__main__":
    asyncio.run(main())
