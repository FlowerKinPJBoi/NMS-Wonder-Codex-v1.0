from __future__ import annotations

import io
import json
import math
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.daedalus_builder import (
    BuildOperation,
    BuildPlan,
    generate_build,
    parse_build,
)


def record(object_id: str, position=None, *, timestamp=1, scale=1.0, user_data=0):
    return {
        "Timestamp": timestamp,
        "ObjectID": object_id,
        "UserData": user_data,
        "Position": position or [0, 0, 0],
        "Up": [0, scale, 0],
        "At": [0, 0, scale],
        "Visible": "true",
    }


def operation(op, *, target_index=None, object_id=None, position=None, up=None, forward=None, scale=None, user_data=None):
    return BuildOperation(
        op=op,
        target_index=target_index,
        object_id=object_id,
        position=position,
        up=up,
        forward=forward,
        scale=scale,
        user_data=user_data,
        visible=True,
        rationale=f"Test {op}",
    )


def plan(*operations):
    return BuildPlan(
        summary="Apply a safe test pass.",
        assistant_message="The validated test pass is ready.",
        operations=list(operations),
        warnings=["Inspect in BBA."],
    )


def settings():
    return Settings(_env_file=None, max_daedalus_operations=400)


def empty_retrieval():
    return {"corpus_version": 3, "items": []}


def base_source(extra=None):
    objects = [
        record("^BASE_FLAG", timestamp=10),
        record("^F_FLOOR", [0, 0, 0], timestamp=11),
        record("^BUILDSOFA2L", [1, 0.2, 0], timestamp=12),
    ]
    objects.extend(extra or [])
    return json.dumps({"Name": "Test Base", "Owner": {"UID": "private"}, "Objects": objects, "Prefabs": []}).encode()


def ship_source(objects):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("objects.json", json.dumps(objects))
        archive.writestr("so.json", b'{"Name":"Identity must remain"}')
        archive.writestr("ccd.json", b'{"Colour":7}')
    return output.getvalue()


def vector_length(value):
    return math.sqrt(sum(number * number for number in value))


def test_nmsbase_writer_preserves_metadata_anchor_and_normalizes_seat_scale():
    parsed = parse_build(base_source(), "NMS 10.NMSBASE")
    generated = generate_build(
        parsed,
        "Add a table and repair the sofa scale.",
        empty_retrieval(),
        [],
        [],
        settings(),
        version=1,
        supplied_plan=plan(
            operation("move", target_index=2, position=[2, 0.2, 0], scale=0.6),
            operation(
                "add",
                object_id="^BUILDTABLE2",
                position=[2, 0.2, 2],
                up=[0, 1, 0],
                forward=[0, 0, 1],
                scale=1,
                user_data=8,
            ),
        ),
    )
    output = json.loads(generated.body)
    source = json.loads(base_source())
    assert output["Owner"] == {"UID": "private"}
    assert output["Objects"][0] == source["Objects"][0]
    assert output["Objects"][2]["Position"] == [2.0, 0.2, 0.0]
    assert vector_length(output["Objects"][2]["Up"]) == pytest.approx(1.0)
    assert vector_length(output["Objects"][2]["At"]) == pytest.approx(1.0)
    assert output["Objects"][-1]["ObjectID"] == "^BUILDTABLE2"
    assert generated.validation["protectedAnchorExact"] is True
    assert generated.validation["roundTripParsed"] is True
    assert generated.plan["status"] == "APPLIED_AND_VALIDATED"


def test_writer_blocks_protected_anchor_mutation():
    parsed = parse_build(base_source(), "base.NMSBASE")
    with pytest.raises(HTTPException, match=r"protected \^BASE_FLAG"):
        generate_build(
            parsed,
            "Move the flag.",
            empty_retrieval(),
            [],
            [],
            settings(),
            version=1,
            supplied_plan=plan(operation("move", target_index=0, position=[5, 5, 5], scale=1)),
        )


def test_writer_rejects_unapproved_object_ids():
    parsed = parse_build(base_source(), "base.NMSBASE")
    with pytest.raises(HTTPException, match="unapproved ObjectID"):
        generate_build(
            parsed,
            "Add an invented object.",
            empty_retrieval(),
            [],
            [],
            settings(),
            version=1,
            supplied_plan=plan(operation(
                "add",
                object_id="^NOT_A_REAL_VERIFIED_PART",
                position=[0, 0, 0],
                up=[0, 1, 0],
                forward=[0, 0, 1],
                scale=1,
            )),
        )


def test_writer_enforces_3000_part_limit():
    extra = [record("^F_FLOOR", [index, 0, 0], timestamp=100 + index) for index in range(2997)]
    parsed = parse_build(base_source(extra), "large.NMSBASE")
    with pytest.raises(HTTPException, match="exceeding the 3,000-part limit"):
        generate_build(
            parsed,
            "Add one more table.",
            empty_retrieval(),
            [],
            [],
            settings(),
            version=1,
            supplied_plan=plan(operation(
                "add",
                object_id="^BUILDTABLE2",
                position=[0, 0, 0],
                up=[0, 1, 0],
                forward=[0, 0, 1],
                scale=1,
            )),
        )


def test_writer_rejects_parallel_orientation_vectors():
    parsed = parse_build(base_source(), "base.NMSBASE")
    with pytest.raises(HTTPException, match="must be perpendicular"):
        generate_build(
            parsed,
            "Add a malformed table.",
            empty_retrieval(),
            [],
            [],
            settings(),
            version=1,
            supplied_plan=plan(operation(
                "add",
                object_id="^BUILDTABLE2",
                position=[0, 0, 0],
                up=[0, 1, 0],
                forward=[0, 1, 0],
                scale=1,
            )),
        )


def test_nmsship_parser_rejects_oversized_uncompressed_member(monkeypatch):
    from app.services import daedalus_builder

    monkeypatch.setattr(daedalus_builder, "MAX_CORVETTE_MEMBER_BYTES", 20)
    source = ship_source([record("^U_PARAGON", timestamp=1)])
    with pytest.raises(HTTPException, match="uncompressed limit"):
        parse_build(source, "ship.nmsship")


def test_nmsship_writer_preserves_identity_members_and_anchor():
    objects = [record("^U_PARAGON", timestamp=1), record("^B_FLOOR", timestamp=2)]
    source = ship_source(objects)
    parsed = parse_build(source, "ship.nmsship")
    generated = generate_build(
        parsed,
        "Move the floor.",
        {"corpus_version": 1, "items": [{"lesson": {"groundTruth": {"partInventory": [{"objectId": "^B_FLOOR", "count": 1}]}}}]},
        [],
        [],
        settings(),
        version=2,
        supplied_plan=plan(operation("move", target_index=1, position=[3, 2, 1], scale=1)),
    )
    with zipfile.ZipFile(io.BytesIO(source)) as before, zipfile.ZipFile(io.BytesIO(generated.body)) as after:
        assert after.read("so.json") == before.read("so.json")
        assert after.read("ccd.json") == before.read("ccd.json")
        output_objects = json.loads(after.read("objects.json"))
    assert output_objects[0] == objects[0]
    assert output_objects[1]["Position"] == [3.0, 2.0, 1.0]
    assert generated.filename == "ship-Daedalus-Pass-2.nmsship"


def test_plan_schema_requires_every_operation_field_for_strict_tool_calling():
    schema = BuildPlan.model_json_schema()
    operation_schema = schema["$defs"]["BuildOperation"]
    assert operation_schema["additionalProperties"] is False
    assert set(operation_schema["required"]) == set(operation_schema["properties"])


def test_provider_connection_forces_one_strict_build_plan_tool_call(monkeypatch):
    import openai

    captured = {}
    provider_plan = plan(operation(
        "add",
        object_id="^BUILDTABLE2",
        position=[1, 0.2, 1],
        up=[0, 1, 0],
        forward=[0, 0, 1],
        scale=1,
    ))

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_test_123",
                output=[SimpleNamespace(
                    type="function_call",
                    name="submit_build_plan",
                    arguments=provider_plan.model_dump_json(),
                )],
            )

    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: SimpleNamespace(responses=Responses()))
    configured = settings()
    configured.openai_api_key = "sk-test"
    parsed = parse_build(base_source(), "base.NMSBASE")
    generated = generate_build(
        parsed,
        "Add one table.",
        empty_retrieval(),
        [],
        [("image/png", b"reference")],
        configured,
        version=1,
    )
    assert captured["store"] is False
    assert captured["parallel_tool_calls"] is False
    assert captured["tool_choice"] == {"type": "function", "name": "submit_build_plan"}
    assert captured["tools"][0]["strict"] is True
    assert captured["tools"][0]["parameters"]["additionalProperties"] is False
    assert captured["input"][1]["content"][1]["type"] == "input_image"
    provider_context = json.loads(captured["input"][1]["content"][0]["text"])
    assert "sourceFilename" not in provider_context
    assert "Owner" not in captured["input"][1]["content"][0]["text"]
    assert "private" not in captured["input"][1]["content"][0]["text"]
    assert generated.provider_response_id == "resp_test_123"
