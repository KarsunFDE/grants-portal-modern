"""
brownfield_debt_4 — locked-failing test.

Item 4 (docs/brownfield-debt.md#item-4): /draft-grant-application returns the raw
stub dict with no Pydantic response model. 1-in-3 calls return {"clause_id":
null, ...} which breaks downstream Spring. Scheduled unlock: W1-Fri (LLM
Essentials Day 2 — output validation).

Convention: assertion = what-true-after-modernization.

After fix:
  - DraftResponse Pydantic model defined
  - /draft-grant-application declares response_model=DraftResponse (strict mode)
  - clause_id is typed as non-Optional + non-empty string
  - 60 successive calls return no null clause_id

While debt present:
  - response_model not declared on the endpoint
  - 1-in-3 calls returns null clause_id
  - test FAILS

When fix lands -> test passes -> CI flips lockfile.

See pipeline/T27-debt-enforcement-spec.md.
"""
from __future__ import annotations

import inspect
import random
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app


@pytest.mark.brownfield_debt_4
def test_draft_grant_application_has_pydantic_response_model_DEBT_LOCKED() -> None:
    """When item 4 is modernized, /draft-grant-application declares a Pydantic BaseModel response_model.

    FastAPI auto-derives `response_model` from the function return-type hint;
    a hint of `dict[str, Any]` yields a non-None response_model that is NOT a
    BaseModel subclass. The locked-failing assertion is that response_model
    is a *Pydantic BaseModel subclass* — i.e., real structured-output schema.
    """
    found_route = None
    for route in app.routes:
        if getattr(route, "path", None) == "/draft-grant-application":
            found_route = route
            break
    assert found_route is not None, "/draft-grant-application route not registered"
    response_model = getattr(found_route, "response_model", None)
    is_pydantic_model = (
        response_model is not None
        and inspect.isclass(response_model)
        and issubclass(response_model, BaseModel)
    )
    assert is_pydantic_model, (
        f"Item 4 modernized — /draft-grant-application must declare a Pydantic "
        f"BaseModel as response_model (e.g., DraftResponse). Got "
        f"{response_model!r}. After adding the model, update "
        f"docs/debt-lockfile.yml and apply the debt-touch-approved label."
    )


@pytest.mark.brownfield_debt_4
def test_draft_grant_application_never_returns_null_clause_id_DEBT_LOCKED() -> None:
    """When item 4 is modernized, no call returns null clause_id."""
    random.seed(42)  # deterministic — covers the 1-in-3 null path within 60 calls
    client = TestClient(app)
    null_responses: list[dict[str, Any]] = []
    for _ in range(60):
        resp = client.post(
            "/draft-grant-application",
            json={"topic": "supplies", "constraints": "small business set-aside"},
        )
        if resp.status_code != 200:
            continue
        payload = resp.json()
        if payload.get("clause_id") is None:
            null_responses.append(payload)
    assert null_responses == [], (
        f"Item 4 modernized — {len(null_responses)}/60 calls still return null "
        f"clause_id. Add Pydantic response model with strict validation, then "
        f"update docs/debt-lockfile.yml + apply the debt-touch-approved label."
    )
