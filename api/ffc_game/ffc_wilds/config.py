"""Non-secret settings and a single-instance lock. Bot tokens are never persisted."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "ffc_wilds" / "catalog.json"
CONFIG_PATH = ROOT / "config.json"
DATA_PATH = ROOT / "data"
FFC_GAME_CHANNEL_ID = "1565143548737888326"


def snowflake(value: object, label: str, optional: bool = False) -> str:
    value = str(value or "").strip()
    if not value and optional:
        return ""
    if not re.fullmatch(r"[1-9][0-9]{16,19}", value):
        raise ValueError(f"{label} must be a Discord ID (17–20 digits).")
    if int(value) >= 2**64:
        raise ValueError(f"{label} is outside Discord's ID range.")
    return value


@dataclass(frozen=True)
class Settings:
    guild_id: str
    channel_id: str
    application_id: str = ""
    message_content: bool = True
    mode: str = "community"

    @classmethod
    def from_dict(cls, value: dict) -> "Settings":
        if not isinstance(value, dict):
            raise ValueError("Configuration must be a JSON object.")
        if value.get("mode", "community") not in ("community", "classic"):
            raise ValueError("Mode must be community or classic.")
        if not isinstance(value.get("message_content", True), bool):
            raise ValueError("message_content must be true or false.")
        return cls(
            guild_id=snowflake(value.get("guild_id"), "Server ID"),
            channel_id=snowflake(value.get("channel_id"), "Game channel ID"),
            application_id=snowflake(value.get("application_id"), "Application ID", True),
            message_content=value.get("message_content", True),
            mode=value.get("mode", "community"),
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Settings":
        if not path.is_file():
            raise ValueError("Run Configure-FFC-Wilds.bat first to choose the FFC server and game channel.")
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8-sig")))
        except json.JSONDecodeError as exc:
            raise ValueError("config.json is not valid JSON; run Configure-FFC-Wilds.bat again.") from exc

    def save(self, path: Path = CONFIG_PATH) -> None:
        validated = Settings.from_dict(asdict(self))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(validated), indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def invite_url(self) -> str:
        if not self.application_id:
            return ""
        # View Channel, Send Messages, Embed Links, Attach Files, Read Message History.
        permissions = 1024 + 2048 + 16384 + 32768 + 65536
        return (
            "https://discord.com/oauth2/authorize?client_id=" + self.application_id
            + f"&permissions={permissions}&scope=bot%20applications.commands"
            + "&integration_type=0"
            + f"&guild_id={self.guild_id}&disable_guild_select=true"
        )


class InstanceLock:
    """OS-managed lock released after crashes; never relies on a stale PID file."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError("FFC Wilds is already running for this data folder. Close that instance first.") from exc
        return self

    def __exit__(self, *_args):
        if self.handle:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None
