import json
from openai import OpenAI

from ..config import env
from .prompts import SYSTEM_PROMPT, build_user_prompt


def get_client():
    kwargs = {"api_key": env("OPENAI_API_KEY")}

    base_url = env("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def analyze_item(item, max_chars=4000):
    client = get_client()

    response = client.chat.completions.create(
        model=env("OPENAI_MODEL", "gpt-5-mini"),
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(item, max_chars)},
        ],
    )

    text = response.choices[0].message.content
    return json.loads(text)
