 """
基於 LangChain 的智能財務報表解析 Agent 系統

這個系統使用 LangChain 框架構建了一個多 Agent 協作的財務報表解析系統，
能夠智能地處理 PDF 財務報表，自動發現引用，並提取結構化的財務數據。
"""

import PyPDF2
import base64
import io
import json
import os
from typing import Optional, List, Dict, Any, Type, Union
from dotenv import load_dotenv
from google.genai import Client

# LangChain imports
from langchain.tools import BaseTool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler

# Pydantic imports
from pydantic import BaseModel, Field

# 導入原有的模型定義
from src.models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from src.models.prepayments import PrePayments, prepayments_prompt
from src.models.receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from src.models.total_liabilities import TotalLiabilities, total_liabilities_prompt

load_dotenv()


# ===============================
# 數據模型定義
# ===============================


class PDFProcessingState(BaseModel):
    """PDF 處理狀態追蹤"""

    pdf_path: str
    current_step: str = "初始化"
    pages_extracted: List[int] = Field(default_factory=list)
    toc_pages: Optional[List[int]] = None
    financial_statement_pages: Dict[str, List[int]] = Field(default_factory=dict)
    toc_analysis_result: Optional[Dict[str, Any]] = None  # 新增：存儲目錄分析結果
    discovered_references: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # 新增：存儲發現的引用
    additional_referenced_pages: List[int] = Field(default_factory=list)
    all_pages_base64: Optional[str] = None
    page_mapping: Dict[int, int] = Field(default_factory=dict)
    extraction_results: Dict[str, Any] = Field(default_factory=dict)
    incomplete_extractions: Dict[str, Any] = Field(
        default_factory=dict
    )  # 新增：存儲需要補充的提取結果
    errors: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class TableOfContentsInfo(BaseModel):
    """目錄頁資訊"""

    has_toc: bool = Field(description="是否有目錄頁")
    toc_page_numbers: Optional[List[int]] = Field(description="目錄頁的頁數列表")
    notes: Optional[str] = Field(default=None, description="額外備註")


class ReferenceLocationResult(BaseModel):
    """引用位置結果"""

    found: bool = Field(description="是否找到引用")
    section_name: str = Field(description="章節名稱")
    page_numbers: List[int] = Field(description="該章節所在的頁數列表")
    confidence_score: float = Field(description="查找的信心分數（0-1）")


class DiscoveredReferenceItem(BaseModel):
    """發現的引用項目"""

    reference_text: str = Field(description="引用文本")
    context: str = Field(description="引用上下文")
    reference_type: Optional[str] = Field(
        default=None, description="引用類型：附註、明細表、說明等"
    )
    page_numbers: Optional[List[int]] = Field(
        default=None, description="引用所在的頁數列表"
    )


class ExtractionResultWithReferences(BaseModel):
    """包含引用信息的提取結果"""

    extracted_data: Optional[
        Union[
            CashAndEquivalents, PrePayments, ReceivablesRelatedParties, TotalLiabilities
        ]
    ] = None
    discovered_references: Optional[List[DiscoveredReferenceItem]] = Field(
        default=None, description="發現的引用列表"
    )
    is_complete: bool = Field(description="數據是否完整")
    missing_info_description: Optional[str] = Field(
        default=None, description="如果不完整，描述缺失的信息"
    )


class FinancialStatementLocation(BaseModel):
    """財務報表項目位置資訊"""

    item_name: str = Field(description="財務報表項目名稱")
    page_numbers: List[int] = Field(description="該項目所在的頁數列表")
    found: bool = Field(description="是否找到該項目")
    notes: Optional[str] = Field(default=None, description="額外備註")


class DetailSectionLocation(BaseModel):
    """從目錄中解析出的詳細章節位置資訊（例如附註一、某某明細表）"""

    section_name: str = Field(
        description="章節名稱，例如 '附註一'、'現金及約當現金明細表'"
    )
    page_numbers: List[int] = Field(description="該章節所在的頁數列表")
    found: bool = Field(description="是否找到該章節")
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
    detailed_sections: List[DetailSectionLocation] = Field(
        default_factory=list,
        description="詳細的附註章節列表或其他重要明細章節，例如 '附註一'、'預付款項明細表' 及其頁碼",
    )


class ReferenceLocationSchema(BaseModel):
    reference_text: str = Field(..., description="要查找的引用文本")
    context: str = Field(default="", description="引用出現的上下文")


class PageReference(BaseModel):
    """頁面引用資訊"""

    source_page: int = Field(description="引用來源頁面")
    referenced_pages: List[int] = Field(description="被引用的頁面列表")
    reference_text: str = Field(description="引用的原文")
    reference_type: str = Field(description="引用類型：附註、明細表、說明等")


class ReferenceAnalysisResult(BaseModel):
    """引用分析結果"""

    has_references: bool = Field(description="是否發現引用")
    references: List[PageReference] = Field(
        default_factory=list, description="發現的引用列表"
    )
    additional_pages_needed: List[int] = Field(
        default_factory=list, description="需要額外提取的頁面"
    )
    notes: Optional[str] = Field(default=None, description="分析備註")


class DataValidationResult(BaseModel):
    is_valid: bool = Field(description="是否驗證成功")
    errors: List[str] = Field(default_factory=list, description="驗證錯誤列表")
    warnings: List[str] = Field(default_factory=list, description="驗證警告列表")
    confidence_score: float = Field(description="驗證信心分數，0-1 之間")
    notes: Optional[str] = Field(default=None, description="驗證備註")


class PDFPageExtractionSchema(BaseModel):
    pdf_path: str = Field(..., description="PDF 檔案路徑")
    page_numbers: Optional[List[int]] = Field(
        default=None, description="要擷取的頁面（1-based）"
    )
    first_n_pages: Optional[int] = Field(
        default=None, description="若未指定 page_numbers，擷取前 N 頁"
    )


class TOCAnalysisSchema(BaseModel):
    pass


class FinancialDataExtractionSchema(BaseModel):
    model_name: str = Field(..., description="要提取的財務模型名稱")
    page_mapping: str = Field(default="", description="頁面映射信息（可選）")


class DataValidationSchema(BaseModel):
    extracted_data: str = Field(..., description="提取的數據 JSON 字串")
    model_name: str = Field(..., description="模型名稱")


# ===============================
# 工具輔助函數
# ===============================


class CustomLogCallbackHandler(BaseCallbackHandler):
    """自定義日誌回調處理器，避免打印過長的 base64 內容"""

    def __init__(self):
        super().__init__()
        self.max_content_length = 200  # 最大顯示長度

    def on_tool_start(self, serialized, input_str, **kwargs):
        """工具開始時的回調"""
        tool_name = serialized.get("name", "Unknown Tool")
        print(f"\n🔧 正在執行工具: {tool_name}")

        # 處理輸入參數的顯示
        if isinstance(input_str, dict):
            clean_input = {}
            for key, value in input_str.items():
                if isinstance(value, str) and len(value) > self.max_content_length:
                    if "base64" in key.lower():
                        clean_input[key] = f"[BASE64_DATA_{len(value)}_CHARS]"
                    else:
                        clean_input[key] = value[: self.max_content_length] + "..."
                else:
                    clean_input[key] = value
            print(f"   輸入參數: {clean_input}")
        else:
            if isinstance(input_str, str) and len(input_str) > self.max_content_length:
                print(f"   輸入: {input_str[:self.max_content_length]}...")
            else:
                print(f"   輸入: {input_str}")

    def on_tool_end(self, output, **kwargs):
        """工具結束時的回調"""
        if isinstance(output, str):
            try:
                import json

                output_data = json.loads(output)
                # 處理 base64 內容
                if "base64_content" in output_data:
                    base64_length = len(output_data["base64_content"])
                    output_data["base64_content"] = (
                        f"[BASE64_DATA_{base64_length}_CHARS]"
                    )
                print(f"✅ 工具執行完成")
                print(
                    f"   輸出: {json.dumps(output_data, ensure_ascii=False, indent=2)}"
                )
            except:
                # 如果不是 JSON，則直接截斷顯示
                if len(output) > self.max_content_length:
                    print(f"✅ 工具執行完成")
                    print(f"   輸出: {output[:self.max_content_length]}...")
                else:
                    print(f"✅ 工具執行完成")
                    print(f"   輸出: {output}")
        else:
            print(f"✅ 工具執行完成")
            print(f"   輸出: {output}")

    def on_tool_error(self, error, **kwargs):
        """工具出錯時的回調"""
        print(f"❌ 工具執行出錯: {error}")

    def on_agent_action(self, action, **kwargs):
        """Agent 行動時的回調"""
        print(f"\n🤖 Agent 決定: {action.log}")

    def on_agent_finish(self, finish, **kwargs):
        """Agent 完成時的回調"""
        print(f"\n🎯 Agent 完成: {finish.log}")


def setup_genai_client() -> Client:
    """設定 Gemini API 客戶端的輔助函數"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定 GEMINI_API_KEY 環境變數")

    return Client(api_key=api_key)


# ===============================
# LangChain Tools 定義
# ===============================


class PDFPageExtractionTool(BaseTool):
    """PDF 頁面提取工具"""

    name: str = "pdf_page_extraction"
    description: str = (
        "從 PDF 文件中提取指定頁面並轉換為 base64 編碼。可以提取前幾頁用於初始分析，或提取特定頁面。"
        "**此工具會將請求的頁面與先前已提取的頁面合併，並更新 Agent 狀態中的所有頁面內容。**"
    )
    args_schema: Type[BaseModel] = PDFPageExtractionSchema
    # 新增一個屬性來接收 Agent 的狀態對象
    agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

    def __init__(self, agent_state: Optional[PDFProcessingState] = None):
        super().__init__()
        self.agent_state = agent_state  # 接收 agent_state

    def _run(
        self,
        pdf_path: str,
        page_numbers: Optional[List[int]] = None,
        first_n_pages: Optional[int] = None,
    ) -> str:
        """
        提取 PDF 頁面

        Args:
            pdf_path: PDF 檔案路徑
            page_numbers: 要提取的頁面列表（1-based），如果為空則提取前幾頁
            first_n_pages: 提取前幾頁，預設為 5
        """
        try:
            if page_numbers is None and first_n_pages is None:
                first_n_pages = 5

            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                # 獲取目前已提取的頁面，如果沒有則初始化
                current_extracted_pages_set = set(self.agent_state.pages_extracted)

                # 確定本次要新增的頁面
                pages_to_add_this_run = set()
                if page_numbers:
                    pages_to_add_this_run.update(page_numbers)
                elif first_n_pages is not None and not current_extracted_pages_set:
                    # 只有在初次提取且沒有指定特定頁面時才使用 first_n_pages
                    pages_to_add_this_run.update(
                        range(1, min(first_n_pages, total_pages) + 1)
                    )
                else:
                    # 如果沒有指定 page_numbers 且不是初次提取，則本次沒有新頁面要加
                    pass

                # 合併所有要提取的獨特頁面
                all_pages_to_extract_set = current_extracted_pages_set.union(
                    pages_to_add_this_run
                )
                all_pages_to_extract_list = sorted(list(all_pages_to_extract_set))

                if not all_pages_to_extract_list:
                    return json.dumps(
                        {
                            "success": False,
                            "error": "沒有頁面被指定或已提取，無法創建 PDF 內容。",
                        }
                    )

                pdf_writer = PyPDF2.PdfWriter()
                actual_extracted_pages = []
                for page_num in all_pages_to_extract_list:
                    if 1 <= page_num <= total_pages:
                        pdf_writer.add_page(pdf_reader.pages[page_num - 1])
                        actual_extracted_pages.append(page_num)
                    else:
                        print(
                            f"警告：頁碼 {page_num} 超出文件範圍 (1-{total_pages})，已跳過。"
                        )
                        self.agent_state.errors.append(
                            f"提取頁面 {page_num} 超出範圍。"
                        )

                # 轉換為 base64
                output_buffer = io.BytesIO()
                pdf_writer.write(output_buffer)
                pdf_bytes = output_buffer.getvalue()
                base64_encoded = base64.b64encode(pdf_bytes).decode("utf-8")

                self.agent_state.all_pages_base64 = base64_encoded
                self.agent_state.pages_extracted = (
                    actual_extracted_pages  # 更新為實際提取的頁面列表
                )
                self.agent_state.current_step = (
                    f"已提取PDF頁面 {actual_extracted_pages}"
                )

                result = {
                    "success": True,
                    "extracted_pages": actual_extracted_pages,
                    "newly_added_pages": sorted(
                        list(
                            pages_to_add_this_run.difference(
                                current_extracted_pages_set
                            )
                        )
                    ),
                    "base64_length": len(base64_encoded),
                    "message": f"成功提取並合併頁面 {actual_extracted_pages}。Base64 內容已存儲在 Agent 狀態中，長度: {len(base64_encoded):,} 字符。",
                    "next_action_hint": "現在可以根據需求，呼叫 toc_analysis 或 reference_detection 工具。",
                }

                return json.dumps(result)

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"提取頁面時發生錯誤: {str(e)}",
                }
            )


class TOCAnalysisTool(BaseTool):
    """目錄分析工具"""

    name: str = "toc_analysis"
    description: str = (
        "分析 PDF 的前幾頁，找出目錄頁位置，然後分析目錄內容找出各財務報表的頁數位置。"
    )
    args_schema: Type[BaseModel] = TOCAnalysisSchema

    genai_client: Client = Field(..., exclude=True)
    agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

    def __init__(
        self, genai_client: Client, agent_state: Optional[PDFProcessingState] = None
    ):
        super().__init__(genai_client=genai_client)
        self.genai_client = genai_client
        self.agent_state = agent_state

    def _run(self) -> str:
        """
        分析目錄並找出財務報表位置

        Args:
            base64_pdf: PDF 的 base64 編碼內容（通常是前幾頁）
        """
        try:
            if not self.agent_state or not self.agent_state.all_pages_base64:
                return json.dumps(
                    {
                        "success": False,
                        "error": "PDF Base64 內容未在 Agent 狀態中找到。",
                        "message": "請確保已運行 pdf_page_extraction 工具並成功存儲內容。",
                    }
                )

            base64_pdf = (
                self.agent_state.all_pages_base64
            )  # 從 Agent 狀態中獲取 PDF 內容
            self.agent_state.current_step = "正在分析目錄頁"
            # 第一步：找到目錄頁
            toc_prompt = """
            請分析這個PDF文件的前幾頁，找出目錄頁（Table of Contents）的位置。

            請告訴我：
            1. 是否有目錄頁？
            2. 如果有，目錄頁在第幾頁？（可能有多頁）

            注意：目錄頁通常包含章節標題和對應的頁數。
            """

            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": base64_pdf}
            }
            # 找目錄頁位置
            toc_response = self.genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[toc_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": TableOfContentsInfo,
                },
            )

            # 第二步：分析目錄內容找財務報表
            analysis_prompt = """
            請分析這個PDF的目錄頁，找出以下財務報表項目在目錄中顯示的頁數：

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

            analysis_response = self.genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[analysis_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": FinancialStatementsAnalysis,
                },
            )

            # 解析結果
            toc_result = toc_response.parsed
            analysis_result = analysis_response.parsed

            return json.dumps(
                {
                    "success": True,
                    "toc_analysis": toc_result.model_dump(),
                    "financial_statements": analysis_result.model_dump(),
                    "message": "目錄分析完成",
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"目錄分析時發生錯誤: {str(e)}",
                }
            )

            # class ReferenceDetectionTool(BaseTool):
            #     """頁面引用檢測工具"""

            #     name: str = "reference_detection"
            #     description: str = (
            #         "檢測 PDF 頁面中的交叉引用，找出需要額外提取的頁面。能識別附註引用、頁面引用等。"
            #     )

            #     # 正確聲明屬性
            #     genai_client: Client = Field(..., exclude=True)
            #     args_schema: Type[BaseModel] = ReferenceDetectionSchema
            #     agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

            #     def __init__(
            #         self, genai_client: Client, agent_state: Optional[PDFProcessingState] = None
            #     ):
            #         super().__init__(genai_client=genai_client)
            #         self.genai_client = genai_client
            #         self.agent_state = agent_state

            #     def _run(self, current_pages: str) -> str:
            #         """
            #         檢測頁面引用

            #         Args:
            #             base64_pdf: PDF 的 base64 編碼內容
            #             current_pages: 當前已提取的頁面列表，格式為 "1,2,3"
            #         """
            #         try:
            #             # 解析頁面列表
            #             if current_pages.startswith("[") and current_pages.endswith("]"):
            #                 current_pages = current_pages[1:-1]
            #             current_pages_list = [
            #                 int(x.strip()) for x in current_pages.split(",") if x.strip()
            #             ]

            #             prompt = f"""
            #             請仔細分析這些PDF頁面中的文字內容，找出所有提到其他頁面的引用。

            #             當前分析的頁面範圍：{current_pages_list}

            #             請特別注意以下類型的引用：
            #             1. 附註引用：「附註X」、「詳見附註X」、「Note X」
            #             2. 頁面引用：「第X頁」、「見第X頁」、「Page X」
            #             3. 明細表引用：「明細表」、「詳細資料」、「breakdown」
            #             4. 會計政策引用：「會計政策說明」、「重要會計項目之說明」

            #             注意：
            #             - 請只提取明確提到具體頁面數字的引用
            #             - 如果引用的頁面已經在當前頁面範圍內，不需要列為額外需要的頁面
            #             """

            #             base64_pdf = (
            #                 self.agent_state.all_pages_base64
            #             )  # 從 Agent 狀態中獲取 PDF 內容
            #             self.agent_state.current_step = "正在分析頁面引用"
            #             pdf_part = {
            #                 "inline_data": {"mime_type": "application/pdf", "data": base64_pdf}
            #             }

            #             response = self.genai_client.models.generate_content(
            #                 model="gemini-2.5-flash-preview-05-20",
            #                 contents=[prompt, pdf_part],
            #                 config={
            #                     "response_mime_type": "application/json",
            #                     "response_schema": ReferenceAnalysisResult,
            #                 },
            #             )

            #             # 解析結果
            #             reference_result = response.parsed

            #             return json.dumps(
            #                 {
            #                     "success": True,
            #                     "reference_analysis": reference_result.model_dump(),
            #                     "message": f"引用檢測完成，發現 {len(reference_result.get('references', []))} 個引用",
            #                 }
            #             )

            #         except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"引用檢測時發生錯誤: {str(e)}",
                }
            )


class ReferenceLocationTool(BaseTool):
    """根據引用文本在目錄中查找對應頁面的工具"""

    name: str = "reference_location_lookup"
    description: str = (
        "根據在財務數據提取過程中發現的引用文本（如'附註六'、'明細表'等），"
        "在已分析的目錄中查找對應的頁面位置。"
    )

    genai_client: Client = Field(..., exclude=True)
    args_schema: Type[BaseModel] = ReferenceLocationSchema
    agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

    def __init__(
        self, genai_client: Client, agent_state: Optional[PDFProcessingState] = None
    ):
        super().__init__(genai_client=genai_client)
        self.genai_client = genai_client
        self.agent_state = agent_state

    def _run(self, reference_text: str, context: str = "") -> str:
        """
        在目錄中查找引用對應的頁面

        Args:
            reference_text: 引用文本，如 "附註六"、"現金及約當現金明細表"
            context: 引用出現的上下文，幫助更準確定位
        """
        try:
            if not self.agent_state or not self.agent_state.toc_analysis_result:
                return json.dumps(
                    {
                        "success": False,
                        "error": "目錄分析結果未找到，請先執行目錄分析。",
                    }
                )

            # 使用目錄頁面內容進行查找
            base64_pdf = self.agent_state.all_pages_base64
            self.agent_state.current_step = f"正在查找引用: {reference_text}"

            lookup_prompt = f"""
            根據以下引用文本，在這個PDF的目錄中查找對應的頁面位置：
            
            引用文本：{reference_text}
            上下文：{context}
            
            請在目錄中查找可能對應的章節，舉例：
            - "現金及約當現金(附註六)" 可能對應目錄中 "個體財務報告附註(六)"或類似章節
            
            請提供：
            1. 是否在目錄中找到對應章節
            2. 對應的章節名稱
            3. 該章節的頁面範圍
            4. 查找的信心分數（0-1）
            
            注意：要仔細比對引用文本與目錄中的章節標題。
            """

            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": base64_pdf}
            }

            response = self.genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[lookup_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ReferenceLocationResult,
                },
            )

            result = response.parsed

            return json.dumps(
                {
                    "success": True,
                    "reference_lookup": result.model_dump(),
                    "message": f"引用查找完成: {reference_text}",
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"查找引用 {reference_text} 時發生錯誤: {str(e)}",
                }
            )


class EnhancedFinancialDataExtractionTool(BaseTool):
    """增強版財務數據提取工具 - 支援引用發現和回報"""

    name: str = "enhanced_financial_data_extraction"
    description: str = (
        "從財務報表頁面中提取結構化的財務數據，並在提取過程中主動發現和回報引用。"
        "如果發現數據不完整或有引用到其他頁面，會返回發現的引用信息。"
    )

    genai_client: Client = Field(..., exclude=True)
    models_config: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    args_schema: Type[BaseModel] = FinancialDataExtractionSchema
    agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

    def __init__(
        self, genai_client: Client, agent_state: Optional[PDFProcessingState] = None
    ):
        super().__init__(genai_client=genai_client, models_config={})
        self.genai_client = genai_client
        self.agent_state = agent_state

        # 財務模型配置
        self.models_config = {
            "現金及約當現金": {
                "model_class": CashAndEquivalents,
                "prompt": cash_equivalents_prompt,
            },
            "預付款項": {
                "model_class": PrePayments,
                "prompt": prepayments_prompt,
            },
            "應收關係人款項": {
                "model_class": ReceivablesRelatedParties,
                "prompt": receivables_related_parties_prompt,
            },
            "負債總額": {
                "model_class": TotalLiabilities,
                "prompt": total_liabilities_prompt,
            },
        }

    def _run(self, model_name: str, page_mapping: str = "") -> str:
        """
        提取特定財務數據並發現引用

        Args:
            model_name: 要提取的財務模型名稱
            page_mapping: 頁面映射信息（可選）
        """
        try:
            if model_name not in self.models_config:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"不支援的模型名稱: {model_name}",
                        "message": f"支援的模型: {list(self.models_config.keys())}",
                    }
                )

            config = self.models_config[model_name]

            # 修改提示詞，加入引用發現指令
            enhanced_prompt = f"""
            將提取的數據記錄在 extracted_data 中。
            {config["prompt"]}
            
            **重要補充指令：在提取數據的過程中，請特別注意以下情況：**
            
            1. **引用發現**：如果在當前頁面中看到任何引用其他頁數的文字，如：
               - "詳見附註X"
               - "見第X頁明細表"  
               - "參考附註說明"
               - "明細如下表"
               請將這些引用記錄下來。
               如果該引用就在同一頁，則不需記錄。
            
            2. **數據完整性評估**：  
                - 若在當前頁面看到「詳見附註X」、「見第X頁明細表」、「如明細表所示」等參照文字，
                  或該欄位旁明確顯示需要查看其他頁面才能取得數值，請標記為 **不完整**，並說明缺失原因。  
                - 如果該表格根本沒有列出某些子欄位（例如零用金、待交換票據、商業本票等），且也沒有任何「詳見附註」字樣，
                  就 **直接填入 null**，但這不視為資料不完整，因為本來就不存在該資訊。  

            
            3. **返回格式**：除了 extracted_data 外，還需要包含：
               - discovered_references: 發現的引用列表
               - is_complete: 數據是否完整
               - missing_info_description: 如果不完整，描述缺失的信息
            
            注意事項
               - 如果某個子欄位完全沒有出現，也沒出現任何參照文字，就請回傳 `"該欄位": null`，並且 `is_complete: True`。
            """

            # 準備系統提示
            system_hint = ""
            if page_mapping:
                system_hint = f"⚠️ **頁碼對照提醒**：{page_mapping}"

            if system_hint:
                enhanced_prompt = system_hint + "\n\n" + enhanced_prompt

            base64_pdf = self.agent_state.all_pages_base64
            self.agent_state.current_step = f"正在提取 {model_name} 數據並檢測引用"

            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": base64_pdf}
            }

            # 發送請求 - 使用新的回應結構
            response = self.genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[enhanced_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ExtractionResultWithReferences,
                },
            )

            result = response.parsed
            print(result.model_dump())
            import sys

            # 將發現的引用存儲到狀態中
            if result.discovered_references and not result.is_complete:
                for ref in result.discovered_references:
                    self.agent_state.discovered_references.append(
                        {
                            "reference_text": ref.reference_text,
                            "reference_type": ref.reference_type,
                            "context": ref.context,
                            "page_numbers": ref.page_numbers,
                        }
                    )

            # 如果數據不完整，記錄到狀態中
            if not result.is_complete:
                self.agent_state.incomplete_extractions[model_name] = {
                    "extracted_data": result.extracted_data,
                    "missing_info": result.missing_info_description,
                    "references": [
                        ref.model_dump() for ref in result.discovered_references
                    ],
                }

            return json.dumps(
                {
                    "success": True,
                    "model_name": model_name,
                    "extraction_result": result.extracted_data,
                    "has_references": (
                        len(result.discovered_references)
                        if not result.is_complete
                        else 0
                    ),
                    "is_complete": result.is_complete,
                    "message": f"{model_name} 數據提取完成"
                    + (
                        f"，發現 {len(result.discovered_references)} 個引用"
                        if result.discovered_references and not result.is_complete
                        else ""
                    ),
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"提取 {model_name} 數據時發生錯誤: {str(e)}",
                }
            )


class DataValidationTool(BaseTool):
    """數據驗證工具"""

    name: str = "data_validation"
    description: str = "驗證提取的財務數據是否正確，檢查數字準確性、單位一致性等。"

    # 正確聲明屬性
    genai_client: Client = Field(..., exclude=True)
    args_schema: Type[BaseModel] = DataValidationSchema
    agent_state: Optional[PDFProcessingState] = Field(default=None, exclude=True)

    def __init__(
        self, genai_client: Client, agent_state: Optional[PDFProcessingState] = None
    ):
        super().__init__(genai_client=genai_client)
        self.genai_client = genai_client
        self.agent_state = agent_state

    def _run(self, extracted_data: str, model_name: str) -> str:
        """
        驗證提取的數據

        Args:
            base64_pdf: PDF 的 base64 編碼內容
            extracted_data: 提取的數據 JSON 字串
            model_name: 模型名稱
        """
        try:
            validation_prompt = f"""
            請你作為一個嚴格的財務數據審核員，仔細檢查以下提取的 {model_name} 數據是否正確。

            提取的數據：
            {extracted_data}

            請執行以下檢查：
            1. **數字準確性檢查**：對比PDF中的原始數字與提取的數字
            2. **單位一致性檢查**：檢查單位是否正確
            3. **頁數和標籤檢查**：驗證來源頁面和標籤
            4. **邏輯一致性檢查**：檢查數字間的邏輯關係
            5. **完整性檢查**：確認所有欄位都有數據

            """
            base64_pdf = self.agent_state.all_pages_base64
            self.agent_state.current_step = f"正在驗證 {model_name} 數據"
            pdf_part = {
                "inline_data": {"mime_type": "application/pdf", "data": base64_pdf}
            }

            response = self.genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[validation_prompt, pdf_part],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": DataValidationResult,
                },
            )

            validation_result = response.parsed

            return json.dumps(
                {
                    "success": True,
                    "model_name": model_name,
                    "validation_result": validation_result.model_dump(),
                    "message": f"{model_name} 驗證完成",
                }
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"驗證 {model_name} 時發生錯誤: {str(e)}",
                }
            )


# ===============================
# 主要的 Agent 類別
# ===============================


class FinancialReportAnalysisAgent:
    """財務報表分析主 Agent"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.genai_client = self._setup_genai_client()
        self.llm = self._setup_llm()
        self.state: Optional[PDFProcessingState] = None
        self.tools = []
        self.agent = None

    def _setup_llm(self):
        """設定語言模型 - 使用 OpenAI"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("請設定 OPENAI_API_KEY 環境變數")

        return ChatOpenAI(
            model="gpt-4.1-2025-04-14",  # 使用支援函數調用的模型
            api_key=api_key,
            temperature=0,
        )

    def _setup_tools(self, state: PDFProcessingState):
        """設定工具"""
        return [
            PDFPageExtractionTool(agent_state=state),
            TOCAnalysisTool(genai_client=self.genai_client, agent_state=state),
            EnhancedFinancialDataExtractionTool(
                genai_client=self.genai_client, agent_state=state
            ),  # 使用增強版
            ReferenceLocationTool(
                genai_client=self.genai_client, agent_state=state
            ),  # 新增
            DataValidationTool(genai_client=self.genai_client, agent_state=state),
        ]

    def _setup_agent(self):
        """設定 Agent"""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的財務報表分析專家，擅長解析 PDF 格式的財務報告。

                    你的任務是：
                    1. 分析 PDF 財務報表的結構。
                    2. 找出各財務報表的頁面位置。
                    3. **在提取財務數據的過程中**檢測引用，並動態查找和提取額外頁面。
                    4. 提取完整的結構化財務數據。
                    5. 驗證提取數據的準確性。

                    你有以下工具可以使用：
                    - pdf_page_extraction: 提取 PDF 頁面
                    - toc_analysis: 分析目錄找出財務報表位置  
                    - enhanced_financial_data_extraction: **增強版財務數據提取，會自動發現引用**
                    - reference_location_lookup: **根據引用文本在目錄中查找對應頁面**
                    - data_validation: 驗證數據準確性

                    請按照以下邏輯順序使用這些工具，並在每一步都提供清晰的說明：

                    1. **初始頁面提取**: 提取前 5 頁進行結構分析。
                    2. **目錄分析**: 識別所有主要財務報表的頁面位置。
                    3. **核心報表頁面提取**: 提取目錄中識別出的財務報表頁面。
                    4. **智能財務數據提取循環**: 對每個財務模型執行以下循環：
                        a. 使用 `enhanced_financial_data_extraction` 提取數據
                        b. **檢查回應**: 如果 `has_references: true`，表示發現了引用
                        c. **動態引用解析**: 對每個發現的引用：
                            - 使用 `reference_location_lookup` 在目錄中查找對應頁面
                            - 如果找到新頁面，使用 `pdf_page_extraction` 提取這些頁面
                            - 重新執行該模型的數據提取（現在包含更多頁面）
                        d. 重複直到該模型的數據完整為止
                    5. **數據驗證**: 驗證所有提取的數據。

                    **關鍵邏輯**：
                    - 只有在實際提取數據時發現引用，才去查找和提取額外頁面
                    - 每個財務模型都可能觸發自己的頁面擴展
                    - 確保數據完整性，避免遺漏重要的附註或明細

                    請在每一步都提供詳細的進度報告。最終目標是提取出準確、完整的財務數據。
                    回答請使用繁體中文。""",
                ),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_functions_agent(
            self.llm,
            self.tools,
            prompt,
        )

        custom_callback = CustomLogCallbackHandler()
        callbacks = [custom_callback]

        return AgentExecutor(
            agent=agent, tools=self.tools, verbose=False, callbacks=callbacks
        )

    def _setup_genai_client(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("請設定 GEMINI_API_KEY 環境變數")
        return Client(api_key=api_key)

    def analyze_financial_report(self, pdf_path: str) -> Dict[str, Any]:
        """
        分析財務報表的主要入口

        Args:
            pdf_path: PDF 檔案路徑

        Returns:
            分析結果字典
        """
        self.state = PDFProcessingState(pdf_path=pdf_path)
        self.tools = self._setup_tools(self.state)
        self.agent = self._setup_agent()

        task = f"""
        請分析這個財務報表 PDF 檔案：{pdf_path}

        請按照以下步驟進行：

        1.  **提取前 5 頁**以進行初步分析和目錄檢測。
        2.  **分析目錄**，找出所有主要財務報表（個體資產負債表、個體綜合損益表、個體權益變動表、個體現金流量表、重要會計項目明細表）的頁面位置。
        3.  **提取所有已識別的財務報表頁面**。
        4.  **檢測頁面中的交叉引用**。如果 `reference_detection` 工具的回應中 `additional_pages_needed` 列表不為空，則 **立即使用 `pdf_page_extraction` 工具提取這些額外頁面**，然後再進行下一步。確保所有這些頁面都已包含在 Agent 的狀態中。
        5.  對每個財務模型提取數據：
            - 現金及約當現金
            - 預付款項
            - 應收關係人款項
            - 負債總額
        6.  驗證提取的數據準確性。

        請在每一步都提供詳細的進度報告，並在最後彙總所有提取的財務數據。
        """

        try:
            if not self.agent:
                raise RuntimeError("Agent not initialized. This should not happen.")
            result = self.agent.invoke({"input": task})
            return {
                "success": True,
                "result": result,
                "state": self.state.model_dump() if self.state else None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "state": self.state.model_dump() if self.state else None,
            }


# ===============================
# 使用範例
# ===============================


def main():
    """主函數"""
    print("🚀 啟動基於 LangChain 的財務報表分析 Agent")

    # 初始化 Agent
    agent = FinancialReportAnalysisAgent()

    # 分析財務報表
    pdf_path = "assets\pdfs\quartely-results-2024-zh_tcm27-94407.pdf"
    print(f"📄 開始分析：{pdf_path}")

    result = agent.analyze_financial_report(pdf_path)

    if result["success"]:
        print("✅ 分析完成")
        print(f"結果：{result['result']}")
    else:
        print("❌ 分析失敗")
        print(f"錯誤：{result['error']}")


if __name__ == "__main__":
    main()
