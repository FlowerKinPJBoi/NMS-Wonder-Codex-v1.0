#!/usr/bin/env python3
"""Rebuild both release ZIPs from a complete setup package; requires Java and ECJ.

Example: python build-release.py --ecj /path/ecj.jar
  --engine /path/NMSSaveEditor.jar --output /path/new-release
The engine is used for compilation/verification and is not bundled in the ZIPs.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

VERSION = "1.0.0"
ENGINE_SHA = "ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c"


def package_ignored(directory, names):
    """Exclude superseded internal reports; previous archives preserve their evidence."""
    folder = Path(directory)
    ignored = {n for n in names if n in {
        "TAZmd-REVIEW.txt", "VALIDATION-WINDOWS.json", "__pycache__",
        "verify-clean-start.py", "launcher-preflight-regression.py"}}
    ignored.update(n for n in names if n.startswith("RELEASE-NOTES-") and n != "RELEASE-NOTES-1.0.0.txt")
    if folder.name == "tests":
        ignored.update(n for n in names if n.endswith(".json") and n != "release-1.0.0-results.json")
    return ignored


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecj", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    template = Path(__file__).resolve().parents[2]
    app = template / "app"
    output = args.output.resolve()
    if output == template or template in output.parents:
        parser.error("Choose an output folder outside the setup template.")
    output.mkdir(parents=True, exist_ok=True)
    assert digest(args.engine) == ENGINE_SHA, "Engine must match the supported pin."
    import os
    cp = os.pathsep.join([str(app / "CosmosBridge.jar"), str(args.engine.resolve())])
    with tempfile.TemporaryDirectory(prefix="wc-release-") as work:
        classes = Path(work) / "classes"
        classes.mkdir()
        compile_command = ["java", "-jar", str(args.ecj.resolve()), "-1.8", "-nowarn",
                           "-encoding", "UTF-8", "-cp", cp, "-d", str(classes)]
        subprocess.run(compile_command + [str(p) for p in sorted((app / "source").glob("*.java"))], check=True)
        compiled = sorted(classes.rglob("*.class"))
        assert compiled and all(struct.unpack(">H", p.read_bytes()[6:8])[0] == 52 for p in compiled)
        assert not any(any(x in p.name for x in ("Test", "Probe", "Smoke", "Application.class")) for p in compiled)
        reports = []
        for mode, label, slug in [("direct", "Direct UI", "Direct-UI"), ("handoff", "App Handoff", "App-Handoff")]:
            folder = output / ("Wonder-Codex-Editor-" + slug)
            archive = output / ("Wonder-Codex-Editor-v" + VERSION + "-" + slug + "-Windows-Setup.zip")
            if folder.exists() or archive.exists():
                raise RuntimeError("Refusing to overwrite an existing release: " + str(folder))
            shutil.copytree(template, folder, ignore=package_ignored)
            target = folder / "app"
            for name in ("START-HERE.txt", "app/README.txt"):
                p = folder / name
                text = p.read_text(encoding="utf-8")
                text = text.replace("EDITION: Direct UI", "EDITION: " + label)
                text = text.replace("1.0.0-direct", VERSION + "-" + mode)
                text = text.replace("Wonder Codex Editor 1.0.0 Direct UI Desktop shortcut", "Wonder Codex Editor 1.0.0 " + label + " Desktop shortcut")
                p.write_text(text, encoding="utf-8")
            installer = folder / "Install-Wonder-Codex.ps1"
            installer.write_text(installer.read_text(encoding="utf-8").replace(
                "1.0.0-direct", VERSION + "-" + mode).replace(
                "1.0.0 Direct UI", "1.0.0 " + label), encoding="utf-8")
            (target / "optimizer-mode.properties").write_text("mode=" + mode + "\n", encoding="ascii")
            manifest = ("Manifest-Version: 1.0\r\nMain-Class: nomanssave.WCEditorLauncher\r\n"
                        "Implementation-Version: " + VERSION + "\r\n"
                        "Class-Path: CosmosBridge.jar engine/NMSSaveEditor.jar\r\n\r\n")
            jar = target / "WonderCodexEditor.jar"
            with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("META-INF/MANIFEST.MF", manifest)
                for p in compiled:
                    bundle.write(p, p.relative_to(classes).as_posix())
                bundle.write(target / "source/mission-profile.json", "mission-profile.json")
                bundle.write(target / "optimizer-mode.properties", "optimizer-mode.properties")
                for category in ("assets", "integrations"):
                    for p in sorted((target / category).rglob("*")):
                        if p.is_file():
                            bundle.write(p, p.relative_to(target).as_posix())
            # Provision a temporary engine only for packaged launcher verification.
            engine_dir = target / "engine"
            engine_dir.mkdir(exist_ok=True)
            engine = engine_dir / "NMSSaveEditor.jar"
            if engine.exists():
                raise RuntimeError("Setup template unexpectedly contains an engine binary.")
            shutil.copyfile(args.engine, engine)
            try:
                verified = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "--verify"],
                                          text=True, capture_output=True, check=True)
            finally:
                engine.unlink()
                if not any(engine_dir.iterdir()):
                    engine_dir.rmdir()
            entries = [{"path": p.relative_to(target).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
                       for p in sorted(target.rglob("*")) if p.is_file()]
            (folder / "PACKAGE-CHECKSUMS.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
            files = [p for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.txt"]
            (folder / "SHA256SUMS.txt").write_text("".join(digest(p) + "  " + p.relative_to(folder).as_posix() + "\n" for p in files), encoding="utf-8")
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                for p in sorted(folder.rglob("*")):
                    if p.is_file():
                        bundle.write(p, folder.name + "/" + p.relative_to(folder).as_posix())
            with zipfile.ZipFile(archive) as bundle:
                assert bundle.testzip() is None, "ZIP CRC verification failed."
            reports.append({"edition": label, "archive": archive.name, "bytes": archive.stat().st_size,
                            "sha256": digest(archive), "production_classes": len(compiled),
                            "java_class_version": 52, "launcher_verification": verified.stdout.strip(),
                            "zip_crc_verified": True, "app_manifest_files": len(entries)})
            print(json.dumps(reports[-1]), flush=True)
        (output / "release-package-results.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
