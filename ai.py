import re
import asyncio
import json
from typing import Any, TypeVar, TypeAlias, List, get_origin, get_args
from pydantic import BaseModel, ValidationError
from google.genai.types import GenerateContentConfig, ThinkingConfig, Part
from google.genai import Client
import os
import dotenv

dotenv.load_dotenv(".env")
client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
T = TypeVar("T")
P = TypeVar("P")
LLMDict: TypeAlias = dict[str, Any]
"""
Indicates that response schema validation was not requested or failed, and the raw JSON content from the LLM has been parsed into a standard Python dictionary.
"""
LLMStr: TypeAlias = str
"""
Indicates that API call did not return a valid JSON and the raw text response from the LLM is returned as a string.
"""

import threading
import time

_global_llm_semaphore = None
_semaphore_lock = threading.Lock()


def semaphore(limit: int = None) -> threading.Semaphore:
    global _global_llm_semaphore

    if _global_llm_semaphore is None:
        with _semaphore_lock:
            if _global_llm_semaphore is None:
                _global_llm_semaphore = threading.Semaphore(limit or 10)

    return _global_llm_semaphore


def call_llm(
    prompt: str,
    contents: list[P | Part] = None,
    response_schema: type[T] = None,
    temperature: float = 0.0,
    thinking_budget: int = 0,
    sanitize: bool = True,
    **kwargs,
) -> T | LLMDict | LLMStr:
    if not prompt:
        raise ValueError("Prompt cannot be empty for LLM call.")

    is_list_schema = False
    validation_schema = response_schema

    if response_schema:
        origin = get_origin(response_schema)
        if origin in (list, List):
            is_list_schema = True
            args = get_args(response_schema)
            if args:
                inner_type = args[0]

                if not (
                    isinstance(inner_type, type) and issubclass(inner_type, BaseModel)
                ):
                    raise TypeError(
                        f"List response_schema must contain a Pydantic BaseModel, got {inner_type}"
                    )

                from pydantic import create_model

                validation_schema = create_model(
                    f"ListResponseWrapper_{inner_type.__name__}",
                    items=(list[inner_type], ...),
                )
            else:
                validation_schema = None

    json_schema = (
        validation_schema.model_json_schema()
        if validation_schema and hasattr(validation_schema, "model_json_schema")
        else None
    )

    config_params = {
        "system_instruction": prompt,
        "response_json_schema": json_schema,
        "response_mime_type": "application/json",
        "temperature": temperature,
        **kwargs,
    }

    if thinking_budget > 0:
        config_params["thinking_config"] = ThinkingConfig(
            thinking_budget=thinking_budget
        )

    sem = semaphore()
    retries = 3
    retry_delay = 10

    with sem:
        while retries >= 0:
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=GenerateContentConfig(**config_params),
                )
                break
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise
                time.sleep(retry_delay)

    text = response.text
    if not text:
        raise ValueError("Empty response from LLM")

    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE)

    if sanitize:
        if response_schema:
            try:
                validated = validation_schema.model_validate_json(text)
                if is_list_schema:
                    return validated.items
                return validated
            except ValidationError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    return text
