import logging
import os
from pprint import pformat
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from dotenv import load_dotenv
from google import genai
from google.genai import types
import pathlib
from PyPDF2 import PdfReader, PdfWriter

from models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from models.total_liabilities import TotalLiabilities, total_liabilities_prompt
from models.total import FinancialReport, financial_report_prompt

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


def extract_pdf_pages(
    pdf_path: str, model: BaseModel, output_dir: str = "extracted_pages"
) -> Dict[str, str]:
    """
    從 PDF 中提取指定頁面並保存。

    Args:
        pdf_path: PDF 檔案路徑
        model: Pydantic 模型，包含 source_page 屬性
        output_dir: 輸出目錄，預設為 'extracted_pages'

    Returns:
        Dict[str, str]: 包含每個屬性的頁面檔案路徑
    """
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)

    # 讀取 PDF
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # 收集所有需要提取的頁碼
    pages_to_extract = set()
    field_pages = {}

    def process_field(field_name: str, field_value: Any):
        if hasattr(field_value, "source_page"):
            page_num = field_value.source_page
            if page_num is not None:
                pages_to_extract.add(page_num)
                field_pages[field_name] = page_num

    # 遍歷模型的所有屬性
    for field_name, field_value in model.model_dump().items():
        if isinstance(field_value, dict):
            # 處理嵌套字典
            for sub_field_name, sub_field_value in field_value.items():
                process_field(f"{field_name}.{sub_field_name}", sub_field_value)
        else:
            process_field(field_name, field_value)

    # 提取頁面
    for page_num in sorted(pages_to_extract):
        writer.add_page(reader.pages[page_num - 1])  # PDF 頁碼從 1 開始

    # 保存提取的頁面
    output_path = os.path.join(output_dir, f"extracted_pages.pdf")
    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    # 為每個頁面創建單獨的 PDF
    page_files = {}
    for field_name, page_num in field_pages.items():
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num - 1])
        page_file = os.path.join(
            output_dir, f"{field_name.replace('.', '_')}_page_{page_num}.pdf"
        )
        with open(page_file, "wb") as output_file:
            writer.write(output_file)
        page_files[field_name] = page_file

    return page_files


def main():
    file_path = "assets\pdfs\TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf"
    print("Processing file:", file_path)
    reply = parse_with_file(file_path, financial_report_prompt, FinancialReport)
    print("Origin: ", reply)

    # 提取頁面
    page_files = extract_pdf_pages(file_path, reply)
    print("Extracted pages:", page_files)


if __name__ == "__main__":
    main()
