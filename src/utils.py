from models.company_info import PdfInfo
from gemini_client import get_gemini

client = get_gemini()


def get_company_info(company_name: str, pdf_year: int) -> PdfInfo:
    """
    取得公司資訊
    """

    export_ratio_prompt = f"""
    請上網告訴我 {pdf_year} {company_name} 的外銷出口比率相關資訊，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)
    """
    export_ratio = client.search(export_ratio_prompt)

    full_prompt = f"""
    以下資訊是 {pdf_year} 年報的 {company_name} 的外銷出口比率相關資料，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)，請幫我整理一下，若無法獲得相關資料，請回答 0:
    {export_ratio}
    """
    pdf_info: PdfInfo = client.call(full_prompt, schema=PdfInfo)
    return pdf_info


if __name__ == "__main__":
    pdf_info = get_company_info("台積電", 2022)
    print(pdf_info)
