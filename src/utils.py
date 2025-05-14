from pathlib import Path

import pikepdf
from pydantic import BaseModel

# 常見的標準編碼，缺少 ToUnicode 但仍能被閱讀器正確映射
STD_ENCODINGS = {
    "/WinAnsiEncoding",
    "/MacRomanEncoding",
    "/UniGB-UTF16-H",
    "/UniCNS-UTF16-H",
    "/UniJIS-UTF16-H",
}


def has_to_unicode(fontobj: pikepdf.Object) -> bool:
    """
    檢查單一 Font Dictionary（或其子字型）是否含有效的 ToUnicode
    或使用標準編碼。
    """
    # 1. 外層若有 ToUnicode
    if "/ToUnicode" in fontobj:
        return True

    # 2. 若使用的是標準 Encoding，也當作可複製
    encoding = fontobj.get("/Encoding")
    if encoding in STD_ENCODINGS:
        return True

    # 3. 檢查複合字型的子字型（DescendantFonts）
    descendants = fontobj.get("/DescendantFonts")
    if descendants:
        for subref in descendants:
            subfont = subref
            if has_to_unicode(subfont):
                return True

    return False


def fonts_missing_tounicode(pdf_path: str | Path) -> bool:
    """
    傳回 True or False，表示 PDF 中是否有字型缺少 ToUnicode。
    這個函式會檢查 PDF 中的每一頁，並檢查每一頁的字型資源。
    """
    with pikepdf.open(pdf_path) as pdf:
        for _, page in enumerate(pdf.pages, start=1):
            fonts = page.Resources.get("/Font", {})
            for _, font_ref in fonts.items():
                font = font_ref
                if not has_to_unicode(font):
                    return True
    return False


MD_DIR = Path(__file__).parent.parent / "assets/markdowns"


def get_markdown_path(pdf_path):
    return MD_DIR / (pdf_path.stem + ".md")


def get_spec_pages_from_markdown(res: BaseModel, pdf_path: str | Path) -> str:
    # 提取所有相關頁數
    all_pages = set()
    for attr_name in res.__dict__:
        if attr_name.endswith("_related_pages"):
            page_list = getattr(res, attr_name)
            if page_list:  # 確保頁數列表不為空
                all_pages.update(page_list)

    # 按數字順序排列頁數
    sorted_pages = sorted(list(all_pages), key=int)
    # 從原始 markdown 中提取對應頁數的內容
    markdown_path = get_markdown_path(pdf_path)
    with open(markdown_path, "r", encoding="utf-8") as f:
        full_markdown = f.read()

    # 分割 markdown 成頁
    parts = full_markdown.split("START OF PAGE:")
    pages = ["START OF PAGE:" + p for p in parts if p]

    # 提取指定頁數的內容
    extracted_pages = []
    for page_num in sorted_pages:
        for page_content in pages:
            if page_content.startswith(f"START OF PAGE: {page_num}"):
                extracted_pages.append(page_content)
                break

    # 處理第一頁的特殊情況（如果沒有前綴）
    if pages and not pages[0].startswith("START OF PAGE: ") and "1" in sorted_pages:
        extracted_pages.insert(0, pages[0])
    # 生成新的 markdown 文件
    combined_markdown = "\n======\n".join(extracted_pages)
    return combined_markdown


if __name__ == "__main__":
    from pathlib import Path

    PDF_DIR = Path(__file__).parent.parent / "assets/pdfs"

    for pdf in [
        "quartely-results-2024-zh_tcm27-94407.pdf",
        "fin_202503071324328842.pdf",
        "20240314171909745560928_tc.pdf",
        "113Q4 華碩財報(個體).pdf",
        "TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf",
    ]:
        bad_fonts = fonts_missing_tounicode(PDF_DIR / pdf)
        if bad_fonts:
            print(f"偵測到 {pdf} 缺 ToUnicode 的字型")
        else:
            print(f"{pdf} 所有字型皆含 ToUnicode，理論上可正常複製貼上。")
