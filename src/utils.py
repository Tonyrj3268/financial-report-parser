from pathlib import Path
import os
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from pydantic import BaseModel
from dotenv import load_dotenv
from models.company_info import PdfInfo, pdf_info_prompt
import fitz
import base64

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_company_info(pdf_path: str | Path) -> BaseModel:
    """
    取得公司資訊
    """
    with fitz.open(pdf_path) as doc:
        with fitz.open() as pdf_writer:
            pdf_writer.insert_pdf(doc, from_page=0, to_page=0)
            pdf_bytes = pdf_writer.tobytes()
            base64_content = base64.b64encode(pdf_bytes).decode("utf-8")

    pdf_info: PdfInfo = call_gemini(pdf_info_prompt, base64_content, schema=PdfInfo)
    export_ratio_prompt = f"""
    請上網告訴我 {pdf_info.pdf_year} {pdf_info.company_name} 的外銷出口比率相關資訊，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)
    """
    export_ratio = gemini_web_search(export_ratio_prompt)
    print(export_ratio)
    full_prompt = f"""
    以下資訊是 {pdf_info.pdf_year} 年報的 {pdf_info.company_name} 的外銷出口比率相關資料，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)，請幫我整理一下:
    {export_ratio}
    """
    pdf_info: PdfInfo = call_gemini(full_prompt, schema=PdfInfo)
    return pdf_info


def gemini_web_search(query: str) -> str:
    model_id = "gemini-2.5-flash-preview-05-20"
    google_search_tool = Tool(google_search=GoogleSearch())
    response = client.models.generate_content(
        model=model_id,
        contents=query,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            response_modalities=["TEXT"],
        ),
    )
    return response.text


def call_gemini(
    prompt: str,
    pdf_base64: str | None = None,
    schema: BaseModel | None = None,
    call_type: str = "unknown",
) -> BaseModel | str:
    if pdf_base64:
        payload = {"inline_data": {"mime_type": "application/pdf", "data": pdf_base64}}
        contents = [prompt, payload]
    else:
        contents = [prompt]
    cfg = {}
    if schema:
        cfg = {"response_mime_type": "application/json"}
        cfg["response_schema"] = schema
    response = client.models.generate_content(
        model=("gemini-2.5-flash-preview-05-20"),
        contents=contents,
        config=cfg,
    )

    return response.parsed if schema else response.text


if __name__ == "__main__":
    pdf_path = Path(
        r"C:\Users\TonyLin\Desktop\work-dir\financial-report-parser\assets\pdfs\TSMC 2023Q4 Unconsolidated Financial Statements_C_converted.pdf"
    )
    pdf_info = get_company_info(pdf_path)
    print(pdf_info)
