from utils import fonts_missing_tounicode
from transform import upload_file, chat_with_file, chat_with_markdown
from parse import parse_pdf
from models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from models.total_liabilities import TotalLiabilities, total_liabilities_prompt
from models.base import FinancialReport, financial_report_prompt
from pathlib import Path

PDF_DIR = Path(__file__).parent.parent / "assests/pdfs"
MD_DIR = Path(__file__).parent.parent / "assests/markdowns"

filename = "fin_202503071324328842.pdf"

pdf_mapping = {
    "quartely-results-2024-zh_tcm27-94407.pdf": "file-KGXtvwDDkZ8wYCMRiAeRQg",  # 長榮航空
    "113Q4 華碩財報(個體).pdf": "file-FsNfKa6Ydbi2hRHKfW9TTw",  # 華碩
    "TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf": "file-LQokuRBxkg2CEp3PZiFBMf",  # 台積電
    "20240314171909745560928_tc.pdf": "file-X269JoL59QfurudTY48adv",  # 中信金
    "fin_202503071324328842.pdf": "file-4YPtrJes7jpnUSRf7BVAx1",  # 統一
}

model_prompt_mapping = {
    "cash_equivalents": {
        "prompt": cash_equivalents_prompt,
        "model": CashAndEquivalents,
    },
    "total_liabilities": {
        "prompt": total_liabilities_prompt,
        "model": TotalLiabilities,
    },
    "financial_report": {
        "prompt": financial_report_prompt,
        "model": FinancialReport,
    },
}


def get_markdown_path(pdf_path):
    return MD_DIR / (pdf_path.stem + ".md")


def process(pdf_path, prompt, model, target_pages=None):
    if fonts_missing_tounicode(pdf_path):
        file_id = pdf_mapping.get(pdf_path) or upload_file(pdf_path)
        reply = chat_with_file(file_id, prompt, model)
    else:
        markdown_path = get_markdown_path(pdf_path)
        markdown = parse_pdf(
            str(pdf_path),
            target_pages=target_pages,
            save_path=str(markdown_path),
            replace=False,
        )
        reply = chat_with_markdown(markdown, prompt, model)
    print(f"Result for {model.__name__}:\n{reply}\n")
    return reply


if __name__ == "__main__":
    pdf_path = PDF_DIR / filename
    prompt = model_prompt_mapping["financial_report"]["prompt"]
    model = model_prompt_mapping["financial_report"]["model"]
    process(pdf_path, prompt, model)
