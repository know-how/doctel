import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from openai import OpenAI


API_KEY_ENV = "DEEPSEEK_API_KEY"
MODEL_ENV = "DEEPSEEK_MODEL"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
EXIT_COMMANDS = {"exit", "quit"}


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str


def load_dotenv(dotenv_path: str = ".env") -> Dict[str, str]:
    path = Path(dotenv_path)
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merge_environment(dotenv_values: Dict[str, str]) -> Dict[str, str]:
    merged = dict(dotenv_values)
    merged.update(os.environ)
    return merged


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    suffix = "/chat/completions"
    if normalized.endswith(suffix):
        return normalized[: -len(suffix)]
    return normalized


def load_settings(env: Dict[str, str]) -> Settings:
    api_key = env.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise ValueError(f"Missing {API_KEY_ENV}. Add it to your environment or .env file.")

    model = env.get(MODEL_ENV, DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = env.get(BASE_URL_ENV, DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    base_url = normalize_base_url(base_url)
    return Settings(api_key=api_key, model=model, base_url=base_url)


def build_client(settings: Settings) -> OpenAI:
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def extract_content(response_payload: dict) -> str:
    choices = response_payload.get("choices", [])
    if not choices:
        raise RuntimeError("The API response did not include any choices.")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        raise RuntimeError("The API response did not include assistant content.")
    return content


def request_completion(settings: Settings, messages: List[Dict[str, str]]) -> str:
    client = build_client(settings)
    try:
        response = client.chat.completions.create(model=settings.model, messages=messages)
        payload = json.loads(response.model_dump_json())
    except openai.AuthenticationError as error:
        raise RuntimeError(f"Authentication failed: {error}") from error
    except openai.APIConnectionError as error:
        raise RuntimeError(f"Could not reach the API: {error}") from error
    except openai.APIStatusError as error:
        detail = error.response.text if error.response is not None else str(error)
        raise RuntimeError(f"API request failed with status {error.status_code}: {detail}") from error
    return extract_content(payload)


def request_completion_stream(settings: Settings, messages: List[Dict[str, str]]) -> str:
    client = build_client(settings)
    full_text = ""
    try:
        stream = client.chat.completions.create(
            model=settings.model,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_text += delta.content
                    print(delta.content, end="", flush=True)
    except openai.AuthenticationError as error:
        raise RuntimeError(f"Authentication failed: {error}") from error
    except openai.APIConnectionError as error:
        raise RuntimeError(f"Could not reach the API: {error}") from error
    except openai.APIStatusError as error:
        detail = error.response.text if error.response is not None else str(error)
        raise RuntimeError(f"API request failed with status {error.status_code}: {detail}") from error
    return full_text


def should_exit(user_input: str) -> bool:
    return user_input.strip().lower() in EXIT_COMMANDS


def run_chat(settings: Settings, use_stream: bool = False) -> None:
    print("Terminal chat ready. Type 'exit' or 'quit' to stop.")
    if use_stream:
        print("Streaming mode ON\n")
    messages: List[Dict[str, str]] = []

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if should_exit(user_input):
            print("Goodbye.")
            return

        messages.append({"role": "user", "content": user_input})

        if use_stream:
            print("Assistant: ", end="", flush=True)
            reply = request_completion_stream(settings, messages)
            print()
        else:
            reply = request_completion(settings, messages)
            print(f"Assistant: {reply}")

        messages.append({"role": "assistant", "content": reply})


def main() -> None:
    dotenv_values = load_dotenv()
    env = merge_environment(dotenv_values)
    settings = load_settings(env)

    use_stream = "--stream" in sys.argv
    run_chat(settings, use_stream=use_stream)


if __name__ == "__main__":
    main()
