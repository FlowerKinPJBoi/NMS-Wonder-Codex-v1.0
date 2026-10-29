"""Scoped desktop actions and separate owner-only cloud handoff operations."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ffc_game.ffc_wilds.cloud_control import ControlError, PROTOCOL, VERSION

from ..config import get_settings
from ..services.ffc_control import get_control_store, import_game_save
from ..services.ffc_preflight import discord_preflight
from ..services.security import OperatorSession, require_owner_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ffc/control", tags=["ffc-wilds-control"])


def _call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except ControlError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    except Exception as exc:
        # Never forward a psycopg exception/DSN into the API's incident tracker.
        logger.warning("FFC control operation is unavailable (%s).", type(exc).__name__)
        raise HTTPException(503, "FFC cloud controls are temporarily unavailable.") from None


def _store():
    if not get_settings().ffc_cloud_prepared:
        raise HTTPException(503, "FFC cloud setup has not been enabled.")
    return _call(get_control_store)


def _bearer(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token or len(token) > 160:
        raise HTTPException(401, "Connect The Wilds Control Hub again.")
    return token


def require_hub(authorization: str | None = Header(default=None)) -> dict:
    token = _bearer(authorization)
    session = _call(_store().validate_session, token, expected_owner=get_settings().analytics_owner_actor)
    return {"actor": session["actor"], "expires_at": session["expires_at"]}


@router.get("/health")
def health():
    result = {"service": "FFC Wilds", "version": VERSION, "protocol": PROTOCOL,
              "prepared": False, "schema_ready": False, "runtime_ready": False, "handoff_required": True}
    if not get_settings().ffc_cloud_prepared:
        return result
    try:
        state = get_control_store().state()
        result.update(prepared=bool(state.get("runtime_ready")), schema_ready=True, runtime_ready=bool(state.get("runtime_ready")),
                      handoff_required=not state["cloud_active"])
    except Exception:
        pass
    return result


@router.post("/session")
def session(owner: OperatorSession = Depends(require_owner_key)):
    return _call(_store().issue_session, owner.actor)


@router.get("/status")
def status(owner: dict = Depends(require_hub)):
    return _call(_store().state)


@router.post("/commands", status_code=202)
async def command(request: Request, owner: dict = Depends(require_hub)):
    try:
        body: Any = await request.json()
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Control request must be JSON.") from None
    if not isinstance(body, dict) or set(body) != {"request_id", "action", "arguments"}:
        raise HTTPException(400, "Supply a request ID, action, and arguments.")
    if not isinstance(body["request_id"], str) or not isinstance(body["action"], str) or not isinstance(body["arguments"], dict):
        raise HTTPException(400, "Control request fields have invalid types.")
    return await run_in_threadpool(_call, _store().enqueue, body["request_id"], body["action"], body["arguments"], owner["actor"])


@router.get("/commands/{request_id}")
def command_status(request_id: str, owner: dict = Depends(require_hub)):
    return _call(_store().get_command, request_id, owner["actor"])


@router.post("/revoke")
def revoke(authorization: str | None = Header(default=None)):
    # Even an expired token or a changed owner must be able to revoke its own
    # narrowly scoped session. This never pauses/stops the Discord game.
    _call(_store().revoke_session, _bearer(authorization))
    return {"ok": True}


async def _object_body(request: Request) -> dict:
    try:
        value = await request.json()
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Handoff request must be JSON.") from None
    if not isinstance(value, dict):
        raise HTTPException(400, "Handoff request must be a JSON object.")
    return value


@router.get("/handoff")
def handoff(owner: OperatorSession = Depends(require_owner_key)):
    return _call(_store().handoff_status)


@router.post("/handoff/preflight")
def preflight(owner: OperatorSession = Depends(require_owner_key)):
    _store()
    return _call(discord_preflight)


@router.post("/handoff/import")
async def import_save(request: Request, owner: OperatorSession = Depends(require_owner_key)):
    # Only a canonical game snapshot is accepted. No SQL, paths, credentials,
    # arbitrary schemas, or a choice of server/channel can be supplied here.
    _store()
    snapshot = await _object_body(request)
    try:
        return await run_in_threadpool(import_game_save, snapshot)
    except ControlError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    except ValueError:
        raise HTTPException(400, "The game save is invalid, belongs to another channel, or conflicts with existing cloud progress.") from None
    except Exception as exc:
        logger.warning("FFC game import is unavailable (%s).", type(exc).__name__)
        raise HTTPException(503, "The game import could not be confirmed. Check handoff status before retrying the same save.") from None


@router.post("/handoff/activate")
async def activate(request: Request, owner: OperatorSession = Depends(require_owner_key)):
    body = await _object_body(request)
    if set(body) != {"sha256", "local_host_stopped"} or not isinstance(body["sha256"], str) or body["local_host_stopped"] is not True:
        raise HTTPException(400, "Supply the verified save digest and explicitly confirm that the PC host has stopped.")
    _store()
    # Recheck the actual configured cloud credential at the final boundary;
    # a previous successful check is not authority after a token rotation.
    await run_in_threadpool(_call, discord_preflight)
    return await run_in_threadpool(_call, _store().set_active, True, body["sha256"], local_host_stopped=True)


@router.post("/handoff/deactivate")
async def deactivate(request: Request, owner: OperatorSession = Depends(require_owner_key)):
    body = await _object_body(request)
    if set(body) != {"confirm"} or body["confirm"] is not True:
        raise HTTPException(400, "Explicit confirmation is required to stop the cloud host.")
    return await run_in_threadpool(_call, _store().set_active, False)
