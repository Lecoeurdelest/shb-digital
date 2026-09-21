from __future__ import annotations

import pytest
from mcp.types import ListToolsRequest


async def _listed(server: dict) -> dict:
    handler = server["instance"].request_handlers[ListToolsRequest]
    result = await handler(ListToolsRequest())
    return {item.name: item for item in result.root.tools}


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["credit", "legal", "products", "operations"])
async def test_role_annotations_round_trip_through_tools_list(role: str):
    from app.mount.mount_role import mount_role

    module = __import__(f"roles.{role}.functions", fromlist=["functions"])
    _, server, _ = mount_role(role)
    listed = await _listed(server)

    assert set(module.ANNOTATIONS) <= set(listed)
    for name, expected in module.ANNOTATIONS.items():
        assert listed[name].annotations is not None
        assert listed[name].annotations.model_dump(exclude_none=True) == expected


@pytest.mark.asyncio
async def test_retrieval_annotations_round_trip_through_common_tools_list():
    from roles._retrieval.functions import ANNOTATIONS_RETRIEVAL

    from app.orch.common_tools import COMMON_SERVER

    listed = await _listed(COMMON_SERVER)
    expected_common = {name: meta for name, meta in ANNOTATIONS_RETRIEVAL.items() if name in listed}

    assert set(expected_common) == {"wiki_lookup", "wiki_search", "wiki_related_docs", "notes_search"}
    for name, expected in expected_common.items():
        assert listed[name].annotations is not None
        assert listed[name].annotations.model_dump(exclude_none=True) == expected


@pytest.mark.asyncio
async def test_disburse_is_advertised_as_destructive():
    from app.mount.mount_role import mount_role

    _, server, _ = mount_role("operations")
    listed = await _listed(server)

    assert listed["disburse"].annotations.destructiveHint is True
