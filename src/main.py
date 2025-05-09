from utils import fonts_missing_tounicode
from transform import upload_file, parse_with_file, parse_with_markdown
from parse import parse_pdf
from models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from models.total_liabilities import TotalLiabilities, total_liabilities_prompt
from models.prepayments import PrePayments, prepayments_prompt
from models.total import FinancialReport, financial_report_prompt
from models.receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from check import check_financial_report
from pathlib import Path
import json
import asyncio
from pydantic import BaseModel

PDF_DIR = Path(__file__).parent.parent / "assets/pdfs"
MD_DIR = Path(__file__).parent.parent / "assets/markdowns"


pdf_mapping = {
    "quartely-results-2024-zh_tcm27-94407.pdf": "file-KGXtvwDDkZ8wYCMRiAeRQg",  # 長榮航空
    # "113Q4 華碩財報(個體).pdf": "file-FsNfKa6Ydbi2hRHKfW9TTw",  # 華碩
    # "TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf": "file-LQokuRBxkg2CEp3PZiFBMf",  # 台積電
    # "20240314171909745560928_tc.pdf": "file-X269JoL59QfurudTY48adv",  # 中信金
    # "fin_202503071324328842.pdf": "file-4YPtrJes7jpnUSRf7BVAx1",  # 統一
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
    "prepayments": {
        "prompt": prepayments_prompt,
        "model": PrePayments,
    },
    "receivables_related_parties": {
        "prompt": receivables_related_parties_prompt,
        "model": ReceivablesRelatedParties,
    },
    "financial_report": {
        "prompt": financial_report_prompt,
        "model": FinancialReport,
    },
    "table_locations": {
        "prompt": table_locations_prompt,
        "model": FinancialReportPages,
    },
}


def get_markdown_path(pdf_path):
    return MD_DIR / (pdf_path.stem + ".md")


async def process(pdf_path, prompt, model, target_pages=None) -> BaseModel:
    print(f"Processing {pdf_path}...")
    # Check if the PDF has fonts missing ToUnicode
    if not fonts_missing_tounicode(pdf_path):
        print(f"{pdf_path} chat gpt with file。")
        file_id = pdf_mapping.get(pdf_path) or await upload_file(pdf_path)
        reply = await parse_with_file(file_id, prompt, model)
    else:
        print(f"{pdf_path} chat gpt with markdown。")
        markdown_path = get_markdown_path(pdf_path)
        markdown = parse_pdf(
            str(pdf_path),
            target_pages=target_pages,
            save_path=str(markdown_path),
            replace=False,
        )
        reply = await parse_with_markdown(markdown, prompt, model)
    return reply


async def process_wrapper(filename, modelname):
    try:
        prompt = model_prompt_mapping[modelname]["prompt"]
        model = model_prompt_mapping[modelname]["model"]
        res = await process(PDF_DIR / filename, prompt, model)
        return filename, res, None
    except Exception as e:
        return filename, None, str(e)


async def main():
    results, failed = {}, {}
    check_results = {}  # 新增：用於存儲檢查結果
    modelname = "financial_report"
    tasks = [process_wrapper(filename, modelname) for filename in pdf_mapping.keys()]
    for fut in asyncio.as_completed(tasks):
        fn, result, err = await fut
        if err:
            failed[fn] = err
        else:

            # 執行檢查並保存結果
            check_result = await check_financial_report(
                fn,
                result,
                model_prompt_mapping[modelname]["prompt"],
            )
            if check_result["is_correct"]:
                results[fn] = result.model_dump()
            else:
                results[fn] = check_result["fixed_json"]
            check_results[fn] = check_result

    # 保存解析結果
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    # 保存失敗記錄
    if failed:
        with open("failed.json", "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=4)
    # 保存檢查結果
    if check_results:
        with open("check_results.json", "w", encoding="utf-8") as f:
            json.dump(check_results, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    asyncio.run(main())
