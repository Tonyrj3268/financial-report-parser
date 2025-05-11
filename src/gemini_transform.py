import logging
import os
from pprint import pformat
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from dotenv import load_dotenv
from google import genai
from google.genai import types
import pathlib

from models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from models.total_liabilities import TotalLiabilities, total_liabilities_prompt
from models.total import FinancialReport, financial_report_prompt
import json

# 設定 logging
logging.basicConfig(
    filename="gemini_transform.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def parse_with_file(file_path, text, response_format):
    logger.info("與檔案互動，file_path=%s, prompt:\n%s", file_path, text)

    filepath = pathlib.Path(file_path)

    # 設定模型
    response = client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25",
        contents=[
            types.Part.from_bytes(
                data=filepath.read_bytes(),
                mime_type="application/pdf",
            ),
            text,
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": response_format,
        },
    )
    return response.parsed


def parse_with_markdown(markdown, text, response_format):
    logger.info("與Markdown互動，Markdown=%s, prompt:\n%s", markdown, text)
    response = client.models.generate_content(
        model="gemini-2.5-pro-preview-05-06",
        contents=[markdown, text],
        config={
            "response_mime_type": "application/json",
            "response_schema": response_format,
        },
    )
    return response.parsed


def main():
    file_path = "assets\pdfs\TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf"
    print("Processing file:", file_path)
    reply = parse_with_file(file_path, financial_report_prompt, FinancialReport)
    print("Origin: ", reply)

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(reply, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
