from typing import Any, Dict, List, Set, Tuple
from pydantic import BaseModel
import fitz  # PyMuPDF
import os
from pathlib import Path
import json
from transform import chat_with_file
import tempfile
import base64

PDF_DIR = Path(__file__).parent.parent / "assets/pdfs"

CHECK_PROMPT = """
請你檢查以下財務報表數據是否正確。我會提供：
1. 一個包含相關頁面的 PDF 文件
2. 一個包含提取數據的 JSON 對象

請你：
1. 仔細閱讀 PDF 中的相關頁面
2. 比對 JSON 中的數據是否與 PDF 中的數據相符．如果相符可以不用回傳
3. 特別注意：
   - 數值是否正確(要完全按照 PDF 中的數字，尤其是小數點和逗號不要搞混)
   - 單位是否正確（是否為千元）
   - 幣別是否正確
   - 匯率是否正確
   - 頁碼是否正確

如果發現任何不一致，請詳細說明：
- 哪個欄位有問題
- PDF 中的實際值是什麼
- JSON 中的值是什麼
- 差異在哪裡

如果所有數據都正確，請回覆「所有數據都正確」。

請以以下格式回覆：
{
    "is_correct": boolean(True or False),  // 是否所有數據都正確
    "issues": [  // 如果有問題，列出所有問題
        {
            "field": string,  // 有問題的欄位名稱
            "pdf_value": any,  // PDF 中的實際值
            "json_value": any,  // JSON 中的值
            "description": string  // 問題描述
        }
    ],
    "fixed_json": {  // 如果有問題，提供修正後的 JSON
        // 修正後的 JSON 數據
    }
}
"""


def _extract_pages_recursive(
    model: BaseModel,
    doc: fitz.Document,
    prefix: str = "",
    saved_pages: Dict[int, Tuple[int, str]] = None,
) -> Dict[str, Tuple[int, str]]:
    """
    遞迴處理嵌套的 Pydantic model 並提取頁面信息。

    Args:
        model: Pydantic model 實例
        doc: 已開啟的 PDF 文件
        prefix: 當前屬性的前綴名稱
        saved_pages: 已保存頁面的字典，key 為頁碼，value 為 (頁碼, 欄位名稱) 的元組

    Returns:
        Dict[str, Tuple[int, str]]: 包含每個欄位對應的頁碼和欄位名稱的字典
    """
    if saved_pages is None:
        saved_pages = {}

    extracted_pages = {}

    for field_name, field_value in model.__dict__.items():
        current_prefix = f"{prefix}_{field_name}" if prefix else field_name

        # 檢查是否有 source_page 屬性
        if hasattr(field_value, "source_page"):
            page_number = field_value.source_page
            if page_number is not None:
                if isinstance(page_number, list):
                    # 如果是列表，則提取所有頁碼
                    for page in page_number:
                        # 將頁碼從 1-based 轉換為 0-based
                        zero_based_page = page - 1
                        # 確保頁碼在有效範圍內
                        if 0 <= zero_based_page < len(doc):
                            # 如果該頁面已經記錄過，直接使用已記錄的信息
                            if page in saved_pages:
                                extracted_pages[current_prefix] = saved_pages[page]
                            else:
                                # 記錄頁面信息
                                extracted_pages[current_prefix] = (page, current_prefix)
                                saved_pages[page] = (page, current_prefix)
                else:
                    # 將頁碼從 1-based 轉換為 0-based
                    zero_based_page = page_number - 1
                    # 確保頁碼在有效範圍內
                    if 0 <= zero_based_page < len(doc):
                        # 如果該頁面已經記錄過，直接使用已記錄的信息
                        if page_number in saved_pages:
                            extracted_pages[current_prefix] = saved_pages[page_number]
                        else:
                            # 記錄頁面信息
                            extracted_pages[current_prefix] = (
                                page_number,
                                current_prefix,
                            )
                            saved_pages[page_number] = (page_number, current_prefix)
        # 遞迴處理嵌套的 Pydantic model
        if isinstance(field_value, BaseModel):
            nested_pages = _extract_pages_recursive(
                field_value, doc, current_prefix, saved_pages
            )
            extracted_pages.update(nested_pages)

        # 處理列表中的 Pydantic model
        elif isinstance(field_value, list):
            for i, item in enumerate(field_value):
                if isinstance(item, BaseModel):
                    nested_pages = _extract_pages_recursive(
                        item, doc, f"{current_prefix}_{i}", saved_pages
                    )
                    extracted_pages.update(nested_pages)

    return extracted_pages


def extract_pages_from_model(
    model: BaseModel, pdf_path: str
) -> Tuple[fitz.Document, Dict[str, Tuple[int, str]]]:
    """
    從 PDF 中提取指定頁面並創建新的 PDF 文件。

    Args:
        model: Pydantic model，其中可能包含 source_page 屬性
        pdf_path: PDF 文件的路徑

    Returns:
        Tuple[fitz.Document, Dict[str, Tuple[int, str]]]: 包含提取的頁面的 PDF 文件和頁面信息的字典
    """
    # 開啟原始 PDF 文件
    doc = fitz.open(pdf_path)

    try:
        # 使用遞迴函數處理 model 並獲取頁面信息
        page_info = _extract_pages_recursive(model, doc)

        # 創建新的 PDF 文件
        new_doc = fitz.open()

        # 按頁碼排序並提取頁面
        sorted_pages = sorted(set(page for page, _ in page_info.values()))
        for page_num in sorted_pages:
            zero_based_page = page_num - 1
            new_doc.insert_pdf(doc, from_page=zero_based_page, to_page=zero_based_page)

        return new_doc, page_info
    finally:
        # 關閉原始 PDF 文件
        doc.close()


def get_base64_pdf(pdf_doc: fitz.Document) -> str:
    """
    將 PDF 文檔轉換為 base64 編碼的字符串。

    Args:
        pdf_doc: PDF 文檔

    Returns:
        str: base64 編碼的 PDF 數據
    """
    # 創建臨時文件
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.close()

    try:
        # 保存 PDF 到臨時文件
        pdf_doc.save(temp_file_path)

        # 讀取文件內容並轉換為 base64
        with open(temp_file_path, "rb") as f:
            pdf_bytes = f.read()
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            return base64_pdf  # 返回純 base64 字符串，不添加 MIME 類型前綴
    finally:
        # 清理臨時文件
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                print(f"警告：無法刪除臨時文件 {temp_file_path}: {str(e)}")


async def check_financial_report(
    pdf_name: str, model: BaseModel, last_build_prompt: str
) -> Dict[str, Any]:
    """
    檢查財務報表數據。

    Args:
        pdf_name: PDF 文件名
        model: 財務報表模型

    Returns:
        Dict[str, Any]: 檢查結果，包含 is_correct 和 issues 字段
    """
    print(f"\n檢查文件: {pdf_name}")
    pdf_path = PDF_DIR / pdf_name

    try:
        # 檢查文件是否存在
        if not pdf_path.exists():
            raise FileNotFoundError(f"找不到 PDF 文件: {pdf_path}")

        # 提取頁面
        extracted_doc, page_info = extract_pages_from_model(model, pdf_path)

        # 將提取的 PDF 保存到臨時文件
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.close()

        try:
            # 保存提取的頁面
            extracted_doc.save(temp_file_path)

            # 讀取提取後的 PDF 文件並轉換為 base64
            with open(temp_file_path, "rb") as f:
                pdf_bytes = f.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

            # 將 model 轉換為 JSON 字符串
            model_json = json.dumps(model.model_dump(), ensure_ascii=False, indent=2)

            prompt = f"{CHECK_PROMPT}\n\n以下是建立該模型時的規則\n\n{last_build_prompt}\n\n以下是要檢查的 JSON 數據:\n```json\n{model_json}\n```"

            # 使用 GPT API 檢查數據
            result = await chat_with_file(pdf_name, base64_pdf, prompt)
            print(result)
            result = json.loads(result)

            # 輸出檢查結果
            if result["is_correct"]:
                print("✓ 所有數據都正確")
            else:
                print("✗ 發現以下問題：")
                for issue in result["issues"]:
                    print(f"\n欄位: {issue['field']}")
                    print(f"PDF 值: {issue['pdf_value']}")
                    print(f"JSON 值: {issue['json_value']}")
                    print(f"問題描述: {issue['description']}")

            return result

        finally:
            # 清理臨時文件
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    print(f"警告：無法刪除臨時文件 {temp_file_path}: {str(e)}")

            # 關閉提取的 PDF 文件
            extracted_doc.close()

    except Exception as e:
        print(f"處理文件 {pdf_name} 時發生錯誤: {str(e)}")
        return {
            "is_correct": False,
            "issues": [
                {
                    "field": "system_error",
                    "pdf_value": None,
                    "json_value": None,
                    "description": str(e),
                }
            ],
        }
