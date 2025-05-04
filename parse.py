from llama_cloud_services import LlamaParse
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    premium_mode=True,
    output_tables_as_HTML=True,
    target_pages="72",
)

# sync
result = parser.parse(
    "quartely-results-2024-zh_tcm27-94407.pdf",
)

# get the llama-index markdown documents
markdown_documents = result.get_markdown_documents()

markdown_res = []
for doc in markdown_documents:
    print(doc.get_content())
    markdown_res.append(doc.get_content())
# print(markdown_res)
