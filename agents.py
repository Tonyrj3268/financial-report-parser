import PyPDF2
import base64
import io
from typing import Optional, List, Dict, Any, Tuple
from google import genai
import os
from pydantic import BaseModel, Field
import json
from dotenv import load_dotenv

# 導入模型
from src.models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from src.models.prepayments import PrePayments, prepayments_prompt
from src.models.receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from src.models.total_liabilities import TotalLiabilities, total_liabilities_prompt

load_dotenv()

class ProcessingResults(BaseModel):
    """處理結果統計"""

    token_usage: List[int] = Field(default_factory=list, description="Token使用統計")
    model_results: Dict[str, Any] = Field(default_factory=dict, description="模型結果")
    total_tokens: int = Field(default=0, description="總token數")


# 全域結果統計
processing_stats = ProcessingResults()


def record_token_usage(step_name: str, response):
    """記錄token使用量"""
    try:
        if hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            input_tokens = getattr(usage, "prompt_token_count", 0)
            output_tokens = getattr(usage, "candidates_token_count", 0)
            total_tokens = input_tokens + output_tokens

            processing_stats.token_usage.append(total_tokens)
            processing_stats.total_tokens += total_tokens

            print(
                f"📊 {step_name} - Token使用: 輸入={input_tokens}, 輸出={output_tokens}, 總計={total_tokens}"
            )
        else:
            print(f"⚠️ {step_name} - 無法獲取token使用資訊")
    except Exception as e:
        print(f"❌ 記錄token使用時發生錯誤: {str(e)}")


def display_model_result(model_name: str, result: Any):
    """顯示模型結果的詳細內容"""
    print(f"\n📋 {model_name} 詳細結果:")
    print("=" * 50)

    if result is None:
        print("❌ 無結果")
        return

    try:
        # 將Pydantic模型轉換為字典
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        elif hasattr(result, "dict"):
            result_dict = result.dict()
        else:
            result_dict = result

        # 格式化顯示
        def format_value(key, value, indent=0):
            prefix = "  " * indent

            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                for sub_key, sub_value in value.items():
                    format_value(sub_key, sub_value, indent + 1)
            elif isinstance(value, list):
                print(f"{prefix}{key}: {value}")
            elif key == "value" and isinstance(value, (int, float)):
                # 格式化數值顯示
                formatted_value = (
                    f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
                )
                print(f"{prefix}{key}: {formatted_value}")
            else:
                print(f"{prefix}{key}: {value}")

        for key, value in result_dict.items():
            format_value(key, value)

    except Exception as e:
        print(f"❌ 顯示結果時發生錯誤: {str(e)}")
        print(f"原始結果: {result}")


def display_final_summary():
    """顯示最終統計摘要"""
    print("\n" + "=" * 80)
    print("🎯 最終處理摘要")
    print("=" * 80)

    # Token使用統計
    print(f"\n💰 Token使用統計:")
    print(f"總Token數: {processing_stats.total_tokens:,}")

    # 模型結果統計
    print(f"\n📈 模型處理結果:")
    successful_models = 0
    failed_models = 0

    for model_name, result in processing_stats.model_results.items():
        if result is not None:
            print(f"  ✅ {model_name}: 成功")
            successful_models += 1
        else:
            print(f"  ❌ {model_name}: 失敗")
            failed_models += 1

    print(f"\n📋 處理統計:")
    print(f"  成功模型: {successful_models}")
    print(f"  失敗模型: {failed_models}")
    print(
        f"  成功率: {(successful_models/(successful_models+failed_models)*100):.1f}%"
        if (successful_models + failed_models) > 0
        else "N/A"
    )

    print("=" * 80)


class FinancialStatementLocation(BaseModel):
    """財務報表項目位置資訊"""

    item_name: str = Field(description="財務報表項目名稱")
    page_numbers: List[int] = Field(description="該項目所在的頁數列表")
    found: bool = Field(description="是否找到該項目")
    notes: Optional[str] = Field(default=None, description="額外備註")


class FinancialStatementsAnalysis(BaseModel):
    """財務報表分析結果"""

    individual_balance_sheet: FinancialStatementLocation = Field(
        description="個體資產負債表"
    )
    individual_comprehensive_income: FinancialStatementLocation = Field(
        description="個體綜合損益表"
    )
    individual_equity_changes: FinancialStatementLocation = Field(
        description="個體權益變動表"
    )
    individual_cash_flow: FinancialStatementLocation = Field(
        description="個體現金流量表"
    )
    important_accounting_items: FinancialStatementLocation = Field(
        description="重要會計項目明細表"
    )


class TableOfContentsInfo(BaseModel):
    """目錄頁資訊"""

    has_toc: bool = Field(description="是否有目錄頁")
    toc_page_numbers: Optional[List[int]] = Field(description="目錄頁的頁數列表")
    notes: Optional[str] = Field(default=None, description="額外備註")

# 設定Gemini API
def setup_gemini():
    """設定Gemini API"""
    # 請設定您的API金鑰
    api_key = os.getenv("GEMINI_API_KEY")  # 從環境變數讀取API金鑰
    if not api_key:
        print("警告: 請設定GEMINI_API_KEY環境變數")
        return None

    client = genai.Client(api_key=api_key)
    return client


def extract_first_ten_pages_to_base64(pdf_path: str) -> Optional[str]:
    """
    讀取PDF檔案，提取前十頁並轉換為base64編碼

    Args:
        pdf_path (str): PDF檔案路徑

    Returns:
        Optional[str]: base64編碼的PDF內容，如果失敗則返回None
    """
    try:
        # 讀取PDF檔案
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)

            # 建立新的PDF writer
            pdf_writer = PyPDF2.PdfWriter()

            # 取得總頁數
            total_pages = len(pdf_reader.pages)
            pages_to_extract = min(5, total_pages)  # 取前5頁或總頁數（如果少於5頁）

            # 提取前十頁
            for page_num in range(pages_to_extract):
                page = pdf_reader.pages[page_num]
                pdf_writer.add_page(page)

            # 將提取的頁面寫入記憶體
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)

            # 取得PDF的二進制資料
            pdf_bytes = output_buffer.getvalue()

            # 轉換為base64編碼
            base64_encoded = base64.b64encode(pdf_bytes).decode("utf-8")

            print(f"成功提取前 {pages_to_extract} 頁並轉換為base64編碼")
            print(f"base64編碼長度: {len(base64_encoded)} 字元")

            return base64_encoded

    except FileNotFoundError:
        print(f"錯誤: 找不到檔案 {pdf_path}")
        return None
    except Exception as e:
        print(f"處理PDF時發生錯誤: {str(e)}")
        return None


def find_table_of_contents_page(base64_pdf: str) -> Optional[TableOfContentsInfo]:
    """
    找到PDF中的目錄頁位置

    Args:
        base64_pdf (str): base64編碼的PDF內容

    Returns:
        Optional[TableOfContentsInfo]: 目錄頁資訊，如果失敗則返回None
    """
    try:
        client = setup_gemini()
        if not client:
            return None

        prompt = """
        請分析這個PDF文件，找出目錄頁（Table of Contents）的位置。
        
        請告訴我：
        1. 是否有目錄頁？
        2. 如果有，目錄頁在第幾頁？（從1開始計算）
        
        注意：
        - 目錄頁通常包含章節標題和對應的頁數。
        - 目錄頁可能包含多頁，請不要落下任何一頁。
        """

        pdf_part = {"inline_data": {"mime_type": "application/pdf", "data": base64_pdf}}

        print("正在尋找目錄頁位置...")

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt, pdf_part],
            config={
                "response_mime_type": "application/json",
                "response_schema": TableOfContentsInfo,
            },
        )

        # 記錄token使用量
        record_token_usage("尋找目錄頁位置", response)

        result: TableOfContentsInfo = response.parsed
        return result

    except Exception as e:
        print(f"尋找目錄頁時發生錯誤: {str(e)}")
        return None


def extract_specific_page_to_base64(pdf_path: str, page_numbers: List[int]) -> Optional[str]:
    """
    提取PDF的特定頁面並轉換為base64編碼

    Args:
        pdf_path (str): PDF檔案路徑
        page_numbers (List[int]): 要提取的頁數列表（從1開始）

    Returns:
        Optional[str]: base64編碼的PDF頁面，如果失敗則返回None
    """
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)

            total_pages = len(pdf_reader.pages)
            for page_number in page_numbers:
                if page_number < 1 or page_number > total_pages:
                    print(f"錯誤: 頁數 {page_number} 超出範圍 (1-{total_pages})")
                    return None

            # 建立新的PDF writer，只包含指定頁面
            pdf_writer = PyPDF2.PdfWriter()
            for page_number in page_numbers:
                page = pdf_reader.pages[page_number - 1]  # 轉換為0-based索引
                pdf_writer.add_page(page)

            # 將頁面寫入記憶體
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)

            # 取得PDF的二進制資料
            pdf_bytes = output_buffer.getvalue()

            # 轉換為base64編碼
            base64_encoded = base64.b64encode(pdf_bytes).decode("utf-8")

            print(f"成功提取第 {page_numbers} 頁並轉換為base64編碼")
            return base64_encoded

    except FileNotFoundError:
        print(f"錯誤: 找不到檔案 {pdf_path}")
        return None
    except Exception as e:
        print(f"提取頁面時發生錯誤: {str(e)}")
        return None


def ask_gemini_about_toc_content(
    base64_toc_page: str,
) -> Optional[FinancialStatementsAnalysis]:
    """
    分析目錄頁內容，找出財務報表項目的頁數

    Args:
        base64_toc_page (str): base64編碼的目錄頁內容

    Returns:
        Optional[FinancialStatementsAnalysis]: 結構化的分析結果，如果失敗則返回None
    """
    try:
        client = setup_gemini()
        if not client:
            return None

        prompt = """
        請分析這個目錄頁，找出以下財務報表項目在目錄中顯示的頁數：

        1. 個體資產負債表
        2. 個體綜合損益表  
        3. 個體權益變動表
        4. 個體現金流量表
        5. 重要會計項目明細表

        請仔細查看目錄中的項目名稱，可能會有類似的表達方式，例如：
        - "資產負債表"、"Balance Sheet"
        - "綜合損益表"、"Comprehensive Income Statement"
        - "權益變動表"、"Statement of Changes in Equity"
        - "現金流量表"、"Cash Flow Statement"
        - "重要會計項目明細表"、"Notes to Financial Statements"、"附註"

        注意：
        - 請根據目錄中顯示的頁數填寫
        - 如果找不到某個項目，請將found設為false
        - 如果某個報表跨越多頁，請列出所有相關頁數
        - 重要會計項目明細表不等於重要會計項目之說明，請注意區分
        """

        toc_part = {
            "inline_data": {"mime_type": "application/pdf", "data": base64_toc_page}
        }

        print("正在分析目錄頁內容...")

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt, toc_part],
            config={
                "response_mime_type": "application/json",
                "response_schema": FinancialStatementsAnalysis,
            },
        )

        # 記錄token使用量
        record_token_usage("分析目錄頁內容", response)

        result: FinancialStatementsAnalysis = response.parsed
        return result

    except Exception as e:
        print(f"分析目錄頁內容時發生錯誤: {str(e)}")
        return None


def extract_pages_range_to_base64(
    pdf_path: str, page_numbers: List[int]
) -> Optional[str]:
    """
    提取PDF的多個頁面並轉換為base64編碼

    Args:
        pdf_path (str): PDF檔案路徑
        page_numbers (List[int]): 要提取的頁數列表（從1開始）

    Returns:
        Optional[str]: base64編碼的PDF頁面，如果失敗則返回None
    """
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)

            # 建立新的PDF writer
            pdf_writer = PyPDF2.PdfWriter()

            for page_num in page_numbers:
                if page_num < 1 or page_num > total_pages:
                    print(f"警告: 頁數 {page_num} 超出範圍 (1-{total_pages})，跳過")
                    continue

                page = pdf_reader.pages[page_num - 1]  # 轉換為0-based索引
                pdf_writer.add_page(page)

            if len(pdf_writer.pages) == 0:
                print("錯誤: 沒有有效的頁面可提取")
                return None

            # 將頁面寫入記憶體
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)

            # 取得PDF的二進制資料
            pdf_bytes = output_buffer.getvalue()

            # 轉換為base64編碼
            base64_encoded = base64.b64encode(pdf_bytes).decode("utf-8")

            print(f"成功提取頁數 {page_numbers} 並轉換為base64編碼")
            return base64_encoded

    except FileNotFoundError:
        print(f"錯誤: 找不到檔案 {pdf_path}")
        return None
    except Exception as e:
        print(f"提取頁面時發生錯誤: {str(e)}")
        return None

def extract_pages_range_to_base64_with_mapping(
    pdf_path: str,
    page_numbers: List[int],
) -> Tuple[str, Dict[int, int], str]:
    """
    抽取多頁 PDF → 重新編號 → 回傳
    1. base64 編碼後的合併 PDF
    2. 新舊頁碼對照 dict   (key = 新順序, value = 原始頁碼)
    3. 可直接塞到 Gemini prompt 的 system_hint

    Args:
        pdf_path (str): PDF 路徑
        page_numbers (List[int]): 1-based 原始頁碼清單

    Returns:
        Tuple[str, Dict[int,int], str]:
            (pages_base64, page_mapping, system_hint)
        若失敗則 raise Exception
    """
    # 先排序、去重
    unique_pages = sorted(set(page_numbers))
    if not unique_pages:
        raise ValueError("page_numbers 不能為空")

    reader = PyPDF2.PdfReader(pdf_path)
    total_pages = len(reader.pages)

    writer = PyPDF2.PdfWriter()
    page_mapping: Dict[int, int] = {}

    for new_idx, orig_page in enumerate(unique_pages, start=1):
        if orig_page < 1 or orig_page > total_pages:
            raise ValueError(f"頁碼 {orig_page} 超出範圍 1-{total_pages}")
        writer.add_page(reader.pages[orig_page - 1])
        page_mapping[new_idx] = orig_page     # 建立對照表

    # 合併後轉 base64
    out_buf = io.BytesIO()
    writer.write(out_buf)
    pdf_bytes = out_buf.getvalue()
    pages_base64 = base64.b64encode(pdf_bytes).decode()

    # 產生 system hint
    mapping_lines = [
        f"新編號第 {new} 頁 = 原始頁碼第 {orig} 頁"
        for new, orig in page_mapping.items()
    ]
    system_hint = (
        "⚠️ **頁碼對照提醒**：以下 PDF 為節省 token 只抽取部分頁面。\n"
        "請務必使用「原始頁碼」回答。\n\n"
        + "\n".join(mapping_lines)
    )

    return pages_base64, page_mapping, system_hint
def process_financial_models(
    pdf_path: str, financial_analysis: FinancialStatementsAnalysis
):
    """
    處理4個財務模型，根據分析結果提取相關頁數並詢問Gemini

    Args:
        pdf_path (str): PDF檔案路徑
        financial_analysis (FinancialStatementsAnalysis): 財務報表分析結果
    """

    # 定義模型配置 - 每個模型指定所需的財務報表
    models_config = [
        {
            "name": "現金及約當現金",
            "model_class": CashAndEquivalents,
            "prompt": cash_equivalents_prompt,
            "required_statements": [
                "individual_balance_sheet",
                "important_accounting_items",
            ],
        },
        {
            "name": "預付款項",
            "model_class": PrePayments,
            "prompt": prepayments_prompt,
            "required_statements": [
                "individual_balance_sheet",
                "important_accounting_items",
            ],
        },
        {
            "name": "應收關係人款項",
            "model_class": ReceivablesRelatedParties,
            "prompt": receivables_related_parties_prompt,
            "required_statements": [
                "individual_balance_sheet",
                "important_accounting_items",
            ],
        },
        {
            "name": "負債總額",
            "model_class": TotalLiabilities,
            "prompt": total_liabilities_prompt,
            "required_statements": [
                "individual_balance_sheet",
                "important_accounting_items",
            ],
        },
    ]

    # 收集所有需要的頁數（根據所有模型的需求）
    all_required_statements = set()
    for model_config in models_config:
        all_required_statements.update(model_config["required_statements"])

    all_relevant_pages = set()
    for statement_name in all_required_statements:
        statement = getattr(financial_analysis, statement_name)
        if statement.found and statement.page_numbers:
            all_relevant_pages.update(statement.page_numbers)
            print(f"📋 {statement_name}: 頁數 {statement.page_numbers}")

    if not all_relevant_pages:
        print("錯誤: 沒有找到相關的財務報表頁數")
        return

    relevant_pages = sorted(list(all_relevant_pages))
    print(f"📄 總共需要提取的頁數: {relevant_pages}")

    # 提取相關頁面
    pages_base64, page_mapping, system_hint = (
    extract_pages_range_to_base64_with_mapping(pdf_path, relevant_pages)
    )

    pdf_part = {
        "inline_data": {"mime_type": "application/pdf", "data": pages_base64}
    }

    if not pages_base64:
        print("錯誤: 無法提取相關頁面")
        return

    # 處理每個模型
    results = {}

    for model_config in models_config:
        print(f"\n=== 處理 {model_config['name']} 模型 ===")

        # 顯示此模型需要的報表
        print(f"📋 需要的報表: {', '.join(model_config['required_statements'])}")

        # 檢查所需報表是否都找到了
        missing_statements = []
        for req_statement in model_config["required_statements"]:
            statement = getattr(financial_analysis, req_statement)
            if not statement.found:
                missing_statements.append(req_statement)

        if missing_statements:
            print(f"⚠️  警告: 以下必需報表未找到: {', '.join(missing_statements)}")
            print(f"🔄 仍將嘗試處理 {model_config['name']}...")

        try:
            client = setup_gemini()
            if not client:
                print(f"無法設定Gemini客戶端，跳過 {model_config['name']}")
                continue

            # 準備PDF資料
            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": pages_base64}
            }

            print(f"正在向Gemini發送 {model_config['name']} 分析請求...")

            # 發送請求給Gemini
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[system_hint, model_config["prompt"], pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": model_config["model_class"],
                },
            )

            # 記錄token使用量
            record_token_usage(f"處理{model_config['name']}模型", response)

            # 獲取結構化結果
            result = response.parsed
            results[model_config["name"]] = result

            # 儲存到全域統計中
            processing_stats.model_results[model_config["name"]] = result

            print(f"✅ {model_config['name']} 分析完成")

        except Exception as e:
            print(f"❌ 處理 {model_config['name']} 時發生錯誤: {str(e)}")
            results[model_config["name"]] = None
            processing_stats.model_results[model_config["name"]] = None

    # 顯示結果摘要
    print(f"\n=== 處理結果摘要 ===")
    for model_name, result in results.items():
        if result:
            print(f"✅ {model_name}: 成功")
        else:
            print(f"❌ {model_name}: 失敗")

    return results


class ValidationResult(BaseModel):
    """驗證結果"""

    model_name: str = Field(description="模型名稱")
    is_valid: bool = Field(description="數字是否正確")
    errors: List[str] = Field(default_factory=list, description="發現的錯誤列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    confidence_score: float = Field(description="信心分數 (0-1)")
    notes: Optional[str] = Field(default=None, description="額外備註")


class OverallValidationResult(BaseModel):
    """整體驗證結果"""

    validation_results: List[ValidationResult] = Field(description="各模型驗證結果")
    overall_valid: bool = Field(description="整體是否通過驗證")
    total_errors: int = Field(description="總錯誤數")
    total_warnings: int = Field(description="總警告數")
    average_confidence: float = Field(description="平均信心分數")


def validate_extracted_data(
    pdf_path: str,
    financial_analysis: FinancialStatementsAnalysis,
    model_results: Dict[str, Any],
) -> Optional[OverallValidationResult]:
    """
    驗證提取的數據是否正確

    Args:
        pdf_path (str): PDF檔案路徑
        financial_analysis (FinancialStatementsAnalysis): 財務報表分析結果
        model_results (Dict[str, Any]): 模型提取結果

    Returns:
        Optional[OverallValidationResult]: 驗證結果
    """
    print("\n=== 開始數據驗證檢查 ===")

    # 收集所有相關頁數（包含所有找到的財務報表）
    all_relevant_pages = set()
    for attr_name in [
        "individual_balance_sheet",
        "individual_comprehensive_income",
        "individual_equity_changes",
        "individual_cash_flow",
        "important_accounting_items",
    ]:
        statement = getattr(financial_analysis, attr_name)
        if statement.found and statement.page_numbers:
            all_relevant_pages.update(statement.page_numbers)
            print(f"📄 驗證將使用 {attr_name}: 頁數 {statement.page_numbers}")

    if not all_relevant_pages:
        print("錯誤: 沒有找到相關的財務報表頁數進行驗證")
        return None

    relevant_pages = sorted(list(all_relevant_pages))
    print(f"📄 驗證總共使用頁數: {relevant_pages}")
    pages_base64 = extract_pages_range_to_base64(pdf_path, relevant_pages)

    if not pages_base64:
        print("錯誤: 無法提取相關頁面進行驗證")
        return None

    validation_results = []

    for model_name, result in model_results.items():
        if result is None:
            print(f"跳過 {model_name} 驗證（無結果）")
            continue

        print(f"\n🔍 驗證 {model_name} 數據...")

        try:
            client = setup_gemini()
            if not client:
                print(f"無法設定Gemini客戶端，跳過 {model_name} 驗證")
                continue

            # 將結果轉換為JSON字串
            if hasattr(result, "model_dump"):
                result_json = json.dumps(
                    result.model_dump(), ensure_ascii=False, indent=2
                )
            elif hasattr(result, "dict"):
                result_json = json.dumps(result.dict(), ensure_ascii=False, indent=2)
            else:
                result_json = json.dumps(result, ensure_ascii=False, indent=2)

            # 準備驗證提示詞
            validation_prompt = f"""
請你作為一個嚴格的財務數據審核員，仔細檢查以下提取的 {model_name} 數據是否正確。

提取的數據：
{result_json}

請執行以下檢查：

1. **數字準確性檢查**：
   - 仔細對比PDF中的原始數字與提取的數字
   - 檢查是否有數字錯誤、遺漏或多餘的數字
   - 注意小數點位置、千分位符號
   - 檢查負數是否正確識別（括號表示負數）

2. **單位一致性檢查**：
   - 檢查 unit_is_thousand 欄位是否正確
   - 確認數值單位與PDF中的單位說明一致
   - 注意是否有混合單位的情況

3. **頁數和標籤檢查**：
   - 驗證 source_page 是否指向正確的頁面
   - 檢查 source_label 是否準確反映原文表名

4. **邏輯一致性檢查**：
   - 檢查相關數字之間的邏輯關係
   - 驗證合計數是否正確
   - 檢查是否有明顯不合理的數值

5. **完整性檢查**：
   - 確認所有應該填入的欄位都有數據
   - 檢查是否有遺漏的重要項目

請提供：
- is_valid: 數據是否完全正確（布林值）
- errors: 發現的具體錯誤（如果有）
- warnings: 需要注意的問題（如果有）
- confidence_score: 對驗證結果的信心分數（0-1，1表示非常確信）
- notes: 額外的驗證說明

要求：
- 請極其嚴格地檢查每一個數字
- 即使是微小的差異也要指出
- 如果無法確定某個數字是否正確，請在warnings中說明
- 只有在100%確信所有數字都正確時，才將is_valid設為true
"""

            # 準備PDF資料
            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": pages_base64}
            }

            # 發送驗證請求
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[validation_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ValidationResult,
                },
            )

            # 記錄token使用量
            record_token_usage(f"驗證{model_name}數據", response)

            # 獲取驗證結果
            validation_result = response.parsed
            validation_result.model_name = model_name
            validation_results.append(validation_result)

            # 顯示驗證結果
            if validation_result.is_valid:
                print(
                    f"✅ {model_name} 驗證通過 (信心分數: {validation_result.confidence_score:.2f})"
                )
            else:
                print(
                    f"❌ {model_name} 驗證失敗 (信心分數: {validation_result.confidence_score:.2f})"
                )
                if validation_result.errors:
                    print(f"   錯誤: {', '.join(validation_result.errors)}")

            if validation_result.warnings:
                print(f"⚠️  警告: {', '.join(validation_result.warnings)}")

            if validation_result.notes:
                print(f"📝 備註: {validation_result.notes}")

        except Exception as e:
            print(f"❌ 驗證 {model_name} 時發生錯誤: {str(e)}")
            # 創建失敗的驗證結果
            validation_results.append(
                ValidationResult(
                    model_name=model_name,
                    is_valid=False,
                    errors=[f"驗證過程發生錯誤: {str(e)}"],
                    warnings=[],
                    confidence_score=0.0,
                    notes="驗證過程中發生技術錯誤",
                )
            )

    # 計算整體驗證結果
    if validation_results:
        total_errors = sum(len(vr.errors) for vr in validation_results)
        total_warnings = sum(len(vr.warnings) for vr in validation_results)
        average_confidence = sum(
            vr.confidence_score for vr in validation_results
        ) / len(validation_results)
        overall_valid = all(vr.is_valid for vr in validation_results)

        overall_result = OverallValidationResult(
            validation_results=validation_results,
            overall_valid=overall_valid,
            total_errors=total_errors,
            total_warnings=total_warnings,
            average_confidence=average_confidence,
        )

        print(f"\n📊 整體驗證結果:")
        print(f"   通過驗證: {'是' if overall_valid else '否'}")
        print(f"   總錯誤數: {total_errors}")
        print(f"   總警告數: {total_warnings}")
        print(f"   平均信心分數: {average_confidence:.2f}")

        return overall_result

    return None


def display_validation_summary(validation_result: OverallValidationResult):
    """顯示詳細的驗證摘要"""
    print("\n" + "=" * 80)
    print("🔍 數據驗證詳細報告")
    print("=" * 80)

    for vr in validation_result.validation_results:
        print(f"\n📋 {vr.model_name}:")
        print(f"   狀態: {'✅ 通過' if vr.is_valid else '❌ 失敗'}")
        print(f"   信心分數: {vr.confidence_score:.2f}")

        if vr.errors:
            print(f"   錯誤:")
            for error in vr.errors:
                print(f"     • {error}")

        if vr.warnings:
            print(f"   警告:")
            for warning in vr.warnings:
                print(f"     • {warning}")

        if vr.notes:
            print(f"   備註: {vr.notes}")

    print(f"\n📊 總結:")
    print(f"   整體驗證: {'✅ 通過' if validation_result.overall_valid else '❌ 失敗'}")
    print(f"   總錯誤數: {validation_result.total_errors}")
    print(f"   總警告數: {validation_result.total_warnings}")
    print(f"   平均信心分數: {validation_result.average_confidence:.2f}")

    if validation_result.overall_valid:
        print("\n🎉 所有數據都通過了嚴格驗證！")
    else:
        print("\n⚠️  發現數據問題，建議檢查並修正。")

    print("=" * 80)


# 使用範例
if __name__ == "__main__":
    # 重置統計
    processing_stats.token_usage.clear()
    processing_stats.model_results.clear()
    processing_stats.total_tokens = 0

    print("🚀 開始處理財務報表...")

    # 請將 'your_pdf_file.pdf' 替換為實際的PDF檔案路徑
    pdf_file_path = "assets/pdfs/quartely-results-2024-zh_tcm27-94407.pdf"
    print(f"正在處理的PDF檔案路徑: {pdf_file_path}")
    # 步驟1: 提取PDF前5頁並轉換為base64
    result = extract_first_ten_pages_to_base64(pdf_file_path)

    if result:
        print("PDF前5頁已成功轉換為base64編碼")

        # 步驟2: 尋找目錄頁位置
        print("\n=== 尋找目錄頁位置 ===")
        toc_info = find_table_of_contents_page(result)

        if toc_info and toc_info.has_toc and toc_info.toc_page_numbers:
            print(f"Gemini建議目錄頁在第 {toc_info.toc_page_numbers} 頁")
            if toc_info.notes:
                print(f"備註: {toc_info.notes}")

            # 步驟3: 提取目錄頁
            print(f"\n=== 提取第 {toc_info.toc_page_numbers} 頁目錄內容 ===")
            toc_page_base64 = extract_specific_page_to_base64(
                pdf_file_path, toc_info.toc_page_numbers
            )

            if toc_page_base64:
                # 步驟4: 分析目錄頁內容，找出財務報表項目的頁數
                print("\n=== 分析目錄頁中的財務報表項目位置 ===")
                financial_analysis = ask_gemini_about_toc_content(toc_page_base64)

                if financial_analysis:
                    print("根據目錄頁分析的財務報表項目位置:")
                    print(f"\n1. 個體資產負債表:")
                    print(
                        f"   - 找到: {'是' if financial_analysis.individual_balance_sheet.found else '否'}"
                    )
                    print(
                        f"   - 頁數: {financial_analysis.individual_balance_sheet.page_numbers}"
                    )
                    if financial_analysis.individual_balance_sheet.notes:
                        print(
                            f"   - 備註: {financial_analysis.individual_balance_sheet.notes}"
                        )

                    print(f"\n2. 個體綜合損益表:")
                    print(
                        f"   - 找到: {'是' if financial_analysis.individual_comprehensive_income.found else '否'}"
                    )
                    print(
                        f"   - 頁數: {financial_analysis.individual_comprehensive_income.page_numbers}"
                    )
                    if financial_analysis.individual_comprehensive_income.notes:
                        print(
                            f"   - 備註: {financial_analysis.individual_comprehensive_income.notes}"
                        )

                    print(f"\n3. 個體權益變動表:")
                    print(
                        f"   - 找到: {'是' if financial_analysis.individual_equity_changes.found else '否'}"
                    )
                    print(
                        f"   - 頁數: {financial_analysis.individual_equity_changes.page_numbers}"
                    )
                    if financial_analysis.individual_equity_changes.notes:
                        print(
                            f"   - 備註: {financial_analysis.individual_equity_changes.notes}"
                        )

                    print(f"\n4. 個體現金流量表:")
                    print(
                        f"   - 找到: {'是' if financial_analysis.individual_cash_flow.found else '否'}"
                    )
                    print(
                        f"   - 頁數: {financial_analysis.individual_cash_flow.page_numbers}"
                    )
                    if financial_analysis.individual_cash_flow.notes:
                        print(
                            f"   - 備註: {financial_analysis.individual_cash_flow.notes}"
                        )

                    print(f"\n5. 重要會計項目明細表:")
                    print(
                        f"   - 找到: {'是' if financial_analysis.important_accounting_items.found else '否'}"
                    )
                    print(
                        f"   - 頁數: {financial_analysis.important_accounting_items.page_numbers}"
                    )
                    if financial_analysis.important_accounting_items.notes:
                        print(
                            f"   - 備註: {financial_analysis.important_accounting_items.notes}"
                        )

                    # 步驟5: 處理4個財務模型
                    print(f"\n=== 處理財務模型 ===")
                    model_results = process_financial_models(
                        pdf_file_path, financial_analysis
                    )

                    if model_results:
                        print(f"\n=== 財務模型處理完成 ===")
                        for model_name, result in model_results.items():
                            if result:
                                print(f"✅ {model_name}: 資料已成功提取並結構化")
                                display_model_result(model_name, result)
                            else:
                                print(f"❌ {model_name}: 處理失敗")

                        # 步驟6: 驗證提取的數據
                        print(f"\n=== 數據驗證檢查 ===")
                        validation_result = validate_extracted_data(
                            pdf_file_path, financial_analysis, model_results
                        )
                        if validation_result:
                            display_validation_summary(validation_result)
                        else:
                            print("數據驗證失敗")
                    else:
                        print("財務模型處理失敗")
                else:
                    print("目錄頁內容分析失敗")
            else:
                print("提取目錄頁失敗")
        else:
            print("未找到目錄頁或目錄頁資訊不完整")
            if toc_info and toc_info.notes:
                print(f"備註: {toc_info.notes}")
    else:
        print("轉換失敗")

    # 顯示最終統計摘要
    display_final_summary()
