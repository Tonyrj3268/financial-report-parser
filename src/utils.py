from models.company_info import PdfInfo
from gemini_client import get_gemini
import os
import requests
from bs4 import BeautifulSoup
import base64
import io
import re

client = get_gemini()

BASE_URL = "https://doc.twse.com.tw/server-java/t57sb01"
PDF_HOST = "https://doc.twse.com.tw"


def download_pdf_as_base64(co_id: str, year: str) -> str:
    """
    下載 TWSE 年報並轉換為 base64 格式。

    參數:
      co_id      TWSE 公司代號，例如 "2330"
      year       民國年，例如 "114"（代表西元2025年）

    回傳:
      base64 編碼的 PDF 內容
    """
    # 1) POST 查詢「股東會相關資料」
    params = {
        "step": "1",
        "colorchg": "1",
        "co_id": co_id,
        "year": year,
        "mtype": "F",  # F = 股東會相關資料
        "seamon": "",  # 股東會資料不需填「季」
    }
    res = requests.post(BASE_URL, data=params, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "lxml")

    # 2) 用正則直接找出 href 或 link.text 以 F04.pdf 結尾的 <a> 標籤
    pdf_link = soup.find(
        "a", href=lambda h: bool(re.search(r"F04\.pdf", h or "", re.IGNORECASE))
    )
    if not pdf_link:
        exit(1)
        raise RuntimeError("找不到檔名以 F04.pdf 結尾的股東會年報連結")

    filename = pdf_link.text.strip()  # e.g. "2021_2330_20220608F04.pdf"

    # 3) POST 下載頁面 (step=9) 取得真正的 PDF 路徑
    params2 = {
        "step": "9",
        "kind": "F",  # 與 mtype 相同
        "co_id": co_id,
        "filename": filename,
    }
    res2 = requests.post(BASE_URL, data=params2, timeout=10)
    res2.raise_for_status()
    soup2 = BeautifulSoup(res2.text, "lxml")
    href = soup2.find("a", href=lambda h: h and h.startswith("/pdf/"))["href"]

    # 4) GET PDF 並儲存
    pdf_url = PDF_HOST + href
    res_pdf = requests.get(pdf_url, timeout=15)
    res_pdf.raise_for_status()

    # 5) 轉換為 base64
    pdf_base64 = base64.b64encode(res_pdf.content).decode("utf-8")
    return pdf_base64


def get_company_info_with_search(company_name: str, pdf_year: int) -> PdfInfo:
    """
    取得公司資訊
    """

    export_ratio_prompt = f"""
    請上網幫我查詢 「{pdf_year} {company_name} 的外銷出口比率」，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)
    """
    export_ratio = client.search(export_ratio_prompt)
    print(export_ratio)
    full_prompt = f"""
    以下資訊是 {pdf_year} 年報的 {company_name} 的外銷出口比率相關資料，外銷出口比率的定義為 外國的營業收入 / (外國的營業收入 + 台灣的營業收入)，請幫我整理一下，若無法獲得相關資料，請回答 0:
    {export_ratio}
    """
    pdf_info: PdfInfo = client.call(full_prompt, schema=PdfInfo)
    if pdf_info.export_ratio is None:
        pdf_info.export_ratio = 0
    else:
        if 100 >= pdf_info.export_ratio >= 1:
            pdf_info.export_ratio = round(pdf_info.export_ratio, 2)
        elif 1 > pdf_info.export_ratio >= 0:
            pdf_info.export_ratio = round(pdf_info.export_ratio * 100, 2)
        else:
            print(f"export_ratio: {pdf_info.export_ratio}")
            pdf_info.export_ratio = 0

    return pdf_info


def get_company_info_with_pdf(company_name: str, pdf_year: int) -> PdfInfo:
    """
    從 TWSE 下載年報 PDF 並分析外銷出口比率

    參數:
      company_id  TWSE 公司代號，例如 "2330"
      pdf_year    西元年，例如 2025
    """
    print(f"get_company_info_with_pdf: {company_name}, {pdf_year}")
    get_company_id_prompt = f"""
    請你上網幫我查詢 {company_name} 的 TWSE 公司代號
    請只回傳數字，不需要其他說明。
    """
    print("查詢公司代號中")
    company_id = client.call(get_company_id_prompt)

    # 轉換西元年為民國年
    # 因為 TWSE 年報是隔年發布，所以需要加 1來獲得正確的年報
    pdf_year += 1
    if pdf_year > 1911:
        roc_year = str(pdf_year - 1911)
    else:
        roc_year = str(pdf_year)

    print("嘗試獲取外銷出口比率")
    try:
        # 下載 PDF 並轉換為 base64
        pdf_base64 = download_pdf_as_base64(company_id, roc_year)

        # 使用 Gemini 分析 PDF 內容
        export_ratio_prompt = f"""
        請分析這份 {pdf_year} 年的年報 PDF，找出該公司的年度銷售量值表中的外銷出口比率。
        
        外銷出口比率的定義為：外國的營業收入(外銷) / (外國的營業收入(外銷) + 台灣的營業收入(內銷))
        
        請仔細查看財報中的營業收入地區分布、市場分布或地理分布等相關資訊。
        如果找到相關資料，請計算出外銷出口比率（以百分比表示，例如 85.5 表示 85.5%）。
        如果沒有找到相關資料，請回答 0。
        
        請只回傳數字，不需要其他說明。
        """

        # 呼叫 Gemini 分析 PDF
        result = client.call(export_ratio_prompt, pdf_base64=pdf_base64)

        # 嘗試解析結果為數字
        try:
            export_ratio = float(result.strip())
            # 如果數字在 0-1 之間，轉換為百分比
            if 0 <= export_ratio <= 1:
                export_ratio = export_ratio * 100
        except ValueError:
            export_ratio = 0

        # 建立 PdfInfo 物件
        pdf_info = PdfInfo(
            company_name=f"公司代號 {company_id}",
            pdf_year=pdf_year,
            export_ratio=round(export_ratio, 2) if export_ratio > 0 else 0,
        )

        return pdf_info

    except Exception as e:
        print(f"處理 PDF 時發生錯誤：{e}")
        # 回傳預設值
        return PdfInfo(
            company_name=f"公司代號 {company_id}", pdf_year=pdf_year, export_ratio=0
        )


if __name__ == "__main__":
    # 測試從網路搜尋
    # pdf_info = get_company_info_with_search("台積電", 2022)
    # print(pdf_info)

    # 測試從 PDF 分析
    pdf_info2 = get_company_info_with_pdf("台積電", 2023)
    print(pdf_info2)
