from pathlib import Path

import pikepdf


def fonts_missing_tounicode(pdf_path: str | Path) -> bool:
    """
    傳回 [(page_no, font_tag), …]，表示哪些頁的哪些字型缺 /ToUnicode。
    空陣列 = 理論上可正常複製貼上。
    """
    misses = []
    with pikepdf.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            fonts = page.Resources.get("/Font", {})
            for tag, font_ref in fonts.items():
                font = font_ref
                print(font)
                if "/ToUnicode" not in font:
                    misses.append((page_no, str(tag)))
    return misses


if __name__ == "__main__":
    for pdf in [
        # "quartely-results-2024-zh_tcm27-94407.pdf",
        "fin_202503071324328842.pdf",
        # "20240314171909745560928_tc.pdf",
        # "113Q4 華碩財報(個體).pdf",
        # "TSMC 2024Q4 Unconsolidated Financial Statements_C.pdf",
    ]:
        bad_fonts = fonts_missing_tounicode(pdf)
        if bad_fonts:

            print(f"偵測到{pdf}缺 ToUnicode 的字型：")
            print(bad_fonts)
        else:
            print(f"{pdf}所有字型皆含 ToUnicode，理論上可正常複製貼上。")
