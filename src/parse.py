from llama_cloud_services import LlamaParse

import os
from typing import Optional


def parse_pdf(
    pdf_path: str,
    target_pages: Optional[str] = None,
    save_path: Optional[str] = None,
    replace: bool = False,
) -> str:
    """
    Parse a PDF file and convert it to markdown using LlamaParse.

    Args:
        pdf_path (str): Path to the PDF file.
        target_pages (str, optional): Pages to parse. Defaults to None.
        save_path (str, optional): Path to save the markdown file. Defaults to None.
        replace (bool, optional): Whether to replace the existing file. Defaults to False.


    Returns:
        str: Parsed markdown content.

    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File {pdf_path} does not exist.")

    if os.path.exists(save_path) and not replace:
        with open(save_path, "r", encoding="utf-8") as f:
            return f.read()

    parser = LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        premium_mode=True,
        output_tables_as_HTML=True,
        target_pages=target_pages,
        page_separator=str("\n======\nSTART OF PAGE: {pageNumber} \n\n"),
    )

    # sync
    result = parser.parse(
        file_path=pdf_path,
    )

    # get the llama-index markdown documents
    markdown_documents = result.get_markdown_documents()

    markdown_res = [doc.get_content() for doc in markdown_documents]

    md_str = "\n\n".join(markdown_res)
    if save_path:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(md_str)
    return md_str


if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path

    PDF_DIR = Path(__file__).parent.parent / "assets/pdfs"
    MD_DIR = Path(__file__).parent.parent / "assets/markdowns"
    # Load environment variables from .env file
    load_dotenv()
    pdf_path = PDF_DIR / "fin_202503071324328842.pdf"
    res = parse_pdf(
        pdf_path,
        target_pages="0-2",
        save_path=MD_DIR / (pdf_path.stem + ".md"),
        replace=True,
    )
    print(res)
