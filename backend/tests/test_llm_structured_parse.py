"""`backend.llm.client.parse_structured_output` tests.

The two-stage structured-output parse mandated by docs/architecture.md
(LLM 介接): strict `model_validate_json` on the full content first, then —
when an upstream provider emits extra characters after the first JSON object
(known OpenRouter failure mode: two concatenated objects, `trailing
characters`) — extract the first complete JSON value via
`json.JSONDecoder().raw_decode` and validate it. No transport is involved,
so no HTTP mocking is needed; the parse logic itself is never mocked.
"""

import json

import pytest
from pydantic import BaseModel

from backend.llm.client import LLMResponseError, parse_structured_output


class Animal(BaseModel):
    name: str
    legs: int


def test_clean_single_object_parses_normally() -> None:
    content = json.dumps({"name": "Cat", "legs": 4})

    assert parse_structured_output(Animal, content) == Animal(name="Cat", legs=4)


def test_trailing_second_object_recovers_first_object() -> None:
    # the production failure: two concatenated JSON objects
    content = json.dumps({"name": "Cat", "legs": 4}) + json.dumps(
        {"name": "Dog", "legs": 4}
    )

    assert parse_structured_output(Animal, content) == Animal(name="Cat", legs=4)


def test_trailing_prose_recovers_first_object() -> None:
    content = json.dumps({"name": "Cat", "legs": 4}) + " — hope that helps!"

    assert parse_structured_output(Animal, content) == Animal(name="Cat", legs=4)


def test_leading_whitespace_before_object() -> None:
    content = "  \n\t" + json.dumps({"name": "Cat", "legs": 4})

    assert parse_structured_output(Animal, content) == Animal(name="Cat", legs=4)


def test_no_json_at_all_raises() -> None:
    with pytest.raises(LLMResponseError):
        parse_structured_output(Animal, "no json here at all")


def test_first_object_schema_invalid_raises() -> None:
    # stage 1 fails (missing `legs` + trailing second object); the first
    # object is extracted but still fails the schema — must not fall through
    # to the (valid) second object.
    content = json.dumps({"name": "Cat"}) + json.dumps({"name": "Dog", "legs": 4})

    with pytest.raises(LLMResponseError):
        parse_structured_output(Animal, content)


def test_unterminated_json_raises() -> None:
    with pytest.raises(LLMResponseError):
        parse_structured_output(Animal, '{"name": "Cat"')