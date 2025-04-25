import os

from dotenv import load_dotenv
from openai import OpenAI

from models.cash_equivalents import CashEquivalents, cash_equivalents_prompt
from models.exp_model import CashAndEquivalents, cash_equivalents_prompt
import os
import logging
from pprint import pformat

# 設定 logging
logging.basicConfig(
    filename="transform.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def upload_file(file_path, purpose="user_data"):
    file = client.files.create(file=open(file_path, "rb"), purpose=purpose)
    return file.id


def chat_with_file(file_id, text, response_format):
    logger.info("與檔案互動，file_id=%s, prompt:\n%s", file_id, text)
    response = client.beta.chat.completions.parse(
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
        "解析結果:\n%s",
        pformat(parsed.model_dump(), indent=2, width=80, sort_dicts=False),
    )
    return parsed


if __name__ == "__main__":

    # file_id = upload_file("TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf")
    # file_id = "file-X269JoL59QfurudTY48adv"  # 中信金
    file_id = "file-LQokuRBxkg2CEp3PZiFBMf"  # 台積電
    print("File uploaded, id:", file_id)
    reply: CashAndEquivalents = chat_with_file(
        file_id, cash_equivalents_prompt, CashAndEquivalents
    )
    print("Origin: ", reply)
