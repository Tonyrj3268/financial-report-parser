from pydantic import BaseModel, Field
from openpyxl import Workbook
from google.genai.types import Tool
from google.genai import types
from typing import Optional


class PdfInfo(BaseModel):
    company_name: str = Field(..., description="公司名稱")
    pdf_year: int = Field(..., description="年份")
    export_ratio: Optional[float] = Field(None, description="外銷比重")

    def fill_excel(self, wb: Workbook):
        pass


pdf_info_prompt = """
你是一個專業的財報分析師，請你根據以下資料，填寫財報基本資料。
- 公司名稱
- 財報年份: 通常會有今年和去年，請你選擇最新的年份。
- 外銷比重: 如果沒有找到相關資料，請填寫 None。
"""

if __name__ == "__main__":
    from src.utils import call_gemini
    from pathlib import Path
    import base64
    import fitz

    # 讀取pdf的第一頁並轉換為base64
    pdf_path = Path(
        r"C:\Users\TonyLin\Desktop\work-dir\financial-report-parser\assets\pdfs\quartely-results-2024-zh_tcm27-94407.pdf"
    )

    # 使用 with 語句自動管理資源
    with fitz.open(pdf_path) as doc:
        # 創建包含前5頁的新PDF
        with fitz.open() as pdf_writer:  # 創建新的PDF文檔
            page = doc.load_page(0)
            pdf_writer.insert_pdf(doc, from_page=0, to_page=0)

            # 將前5頁轉換為base64
            pdf_bytes = pdf_writer.tobytes()
            base64_content = base64.b64encode(pdf_bytes).decode("utf-8")
    tools = []
    tools.append(Tool(google_search=types.GoogleSearch))
    pdf_info = call_gemini(pdf_info_prompt, base64_content, tools=tools)
    print(pdf_info)
