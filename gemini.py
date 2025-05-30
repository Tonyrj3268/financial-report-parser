from google import genai
from google.genai import types
import pathlib
import httpx
from dotenv import load_dotenv
import os
from src.models.cash_equivalents import CashAndEquivalents, cash_equivalents_prompt
from src.models.prepayments import PrePayments, prepayments_prompt
from src.models.receivables_related_parties import (
    ReceivablesRelatedParties,
    receivables_related_parties_prompt,
)
from src.models.total_liabilities import TotalLiabilities, total_liabilities_prompt

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for p in [
    "assets\\pdfs\\TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf",
    # "assets\\pdfs\\fin_202503071324328842.pdf",
    # "assets\\pdfs\\113Q4 華碩財報(個體).pdf",
]:
    # Retrieve and encode the PDF byte
    filepath = pathlib.Path(p)

    results = {}
    for prompt, model in [
        (cash_equivalents_prompt, CashAndEquivalents),
        (prepayments_prompt, PrePayments),
        (receivables_related_parties_prompt, ReceivablesRelatedParties),
        (total_liabilities_prompt, TotalLiabilities),
    ]:
        pdf_part = {
            "inline_data": {
                "mime_type": "application/pdf",
                "data": filepath.read_bytes(),
            }
        }
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=[prompt, pdf_part],
            config={
                "response_mime_type": "application/json",
                "response_schema": model,
            },
        )
        res = response.parsed
        print(res)
        results[model.__name__] = res.model_dump()

    import json

    with open(f"{filepath.stem}_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
