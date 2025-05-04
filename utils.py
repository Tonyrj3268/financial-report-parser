from pathlib import Path

import pikepdf


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


def fonts_missing_tounicode(pdf_path: str | Path) -> list[tuple[int, str]]:
    """
    傳回 [(page_no, font_tag), …]，表示哪些頁的哪些字型
    最終都沒找到 ToUnicode 也沒有標準編碼可 fallback。
    空陣列 = 理論上可正常複製貼上。
    """
    misses: list[tuple[int, str]] = []
    with pikepdf.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            fonts = page.Resources.get("/Font", {})
            for tag, font_ref in fonts.items():
                font = font_ref
                if not has_to_unicode(font):
                    misses.append((page_no, str(tag)))
    return misses


if __name__ == "__main__":
    for pdf in [
        "quartely-results-2024-zh_tcm27-94407.pdf",
        "fin_202503071324328842.pdf",
        "20240314171909745560928_tc.pdf",
        "113Q4 華碩財報(個體).pdf",
        "TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf",
    ]:
        bad_fonts = fonts_missing_tounicode(pdf)
        if bad_fonts:

            print(f"偵測到{pdf}缺 ToUnicode 的字型：")
            print(bad_fonts)
        else:
            print(f"{pdf}所有字型皆含 ToUnicode，理論上可正常複製貼上。")
