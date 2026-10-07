#!/usr/bin/env python3
"""Upload the exact reviewed Editor ZIP privately. Does not enable downloads or deploy."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.routers.downloads import (  # noqa: E402
    EDITOR_FILENAME, EDITOR_RELEASE, EDITOR_SHA256, EDITOR_SIZE_BYTES,
)
from app.services.admin_apps import store_release  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--upload", action="store_true", help="Upload to private Spaces storage after verification")
    args = parser.parse_args()
    # Hash and upload the same open file. No repackaging or third-party changes.
    with args.archive.open("rb") as archive:
        digest = hashlib.sha256()
        size = 0
        while chunk := archive.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        if size != EDITOR_SIZE_BYTES or digest.hexdigest() != EDITOR_SHA256:
            parser.error(f"Archive differs from the pinned {EDITOR_FILENAME}; nothing uploaded.")
        print(f"Verified {EDITOR_FILENAME} ({size:,} bytes)")
        if not args.upload:
            print("Verification only. No upload, configuration change, or deployment performed.")
            return
        store_release(
            EDITOR_RELEASE,
            archive,
            version=EDITOR_RELEASE.suggested_version,
            filename=EDITOR_FILENAME,
            sha256=EDITOR_SHA256,
            actor="PJ",
        )
        print("Uploaded privately. Public download approval and deployment are separate steps.")


if __name__ == "__main__":
    main()
