"""
brownfield_debt_pair_unique_ai_bedrock_streaming_unhandled — locked-failing test.

Pair-unique debt ai-bedrock-streaming-unhandled (D-059, Cohort #1 Pair 1 —
grants-portal-modern).

While debt is locked: app/bedrock_client.py exposes a single blocking
`invoke_model` function. Long generations (multi-section grant_application
drafts) make the UI wait for the full payload. There is no streaming surface.

After W3 fix (agentic UX day):
  - Add `stream_invoke(prompt) -> AsyncIterator[bytes]` (or similar) to
    bedrock_client.py
  - Wire it into a streaming endpoint
  - Test PASSES.

Convention: assertion = what-true-after-modernization. Use module-attribute
introspection — observable without spinning up Bedrock.

See pipeline/T27-debt-enforcement-spec.md.
"""
from __future__ import annotations

import pytest

from app import bedrock_client


@pytest.mark.brownfield_debt
@pytest.mark.brownfield_debt_pair_unique_ai_bedrock_streaming_unhandled
def test_bedrock_client_exposes_streaming_surface_DEBT_LOCKED() -> None:
    """After W3 fix, bedrock_client must expose a streaming function.

    The cohort's accepted shape: a coroutine / async generator named
    `stream_invoke` (or `invoke_model_with_response_stream`) that yields
    chunks. Either name passes — we only assert that *some* streaming
    surface exists.
    """
    streaming_attrs = [
        attr for attr in dir(bedrock_client)
        if "stream" in attr.lower() and not attr.startswith("_")
    ]
    assert streaming_attrs, (
        "Pair-unique debt ai-bedrock-streaming-unhandled: bedrock_client must "
        "expose a streaming surface (e.g. `stream_invoke` or "
        "`invoke_model_with_response_stream`). Currently the module only has "
        "the blocking `invoke_model`. Fix lands W3."
    )
