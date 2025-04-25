import os

from dotenv import load_dotenv
from openai import OpenAI

from models.cash_equivalents import CashEquivalents, cash_equivalents_prompt
from models.exp_model import CashAndEquivalents, cash_equivalents_prompt

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def upload_file(file_path, purpose="user_data"):
    file = client.files.create(file=open(file_path, "rb"), purpose=purpose)
    return file.id


def chat_with_file(file_id, text):
    response = client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "file_id": file_id,
                        },
                    },
                    {
                        "type": "text",
                        "text": text,
                    },
                ],
            }
        ],
        response_format=CashAndEquivalents,
        # temperature=0,
    )
    return response.choices[0].message.parsed


if __name__ == "__main__":

    # file_id = upload_file("20240314171909745560928_tc.pdf")
    file_id = "file-X269JoL59QfurudTY48adv"
    print("File uploaded, id:", file_id)
    reply = chat_with_file(file_id, cash_equivalents_prompt)
    print("Origin: ", reply)
