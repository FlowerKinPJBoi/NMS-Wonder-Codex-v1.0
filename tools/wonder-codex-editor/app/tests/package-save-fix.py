#!/usr/bin/env python3
"""Assemble public 1.0.1 Direct UI from the exact 1.0.0 ZIP and a tested addon.

No compilation, installer execution, game-save access or network requests occur.
The original bridge, runtime and runtime source archive remain byte-for-byte intact.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import tempfile
import zipfile

VERSION = "1.0.1"
TEMPLATE_SHA = "26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9"
BRIDGE_SHA = "7cebd0ae928e571fd340543bbc2eb3c9fe3cf6cada4be6e1d4dbd5f9061889e8"
ENGINE_SHA = "ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c"
PACKAGE_NAME = "Wonder-Codex-Editor-Direct-UI"
ARCHIVE_NAME = "Wonder-Codex-Editor-v1.0.1-Direct-UI-Windows-Setup.zip"
REQUIRED_TESTS = {
    "WCEditorTazRunPreferenceTest", "WCEditorTazOptimizerTest", "WCEditorTazToolTest",
    "WCEditorBasesTest", "WCEditorInventoryActionsTest", "WCEditorCodexScanTest",
    "WCEditorCodexClientTest", "WCEditorSaveErrorsTest",
}
ROOT_FILES = (
    "Install-Wonder-Codex.ps1", "SETUP.bat", "START-HERE.txt", "README.md", "BUILD.md",
    "build-addon.py", "RELEASE-REVIEW.md", "source-snapshot.json",
    "release-evidence/save-feedback-1.0.1-headful.log",
    "release-evidence/save-feedback-1.0.1-headless.log",
)
APP_FILES = (
    "BUILD.txt", "Dependency-Tools.ps1", "FEATURE-COVERAGE.txt", "Launch-Wonder-Codex.ps1",
    "README.txt", "RELEASE-NOTES-1.0.0.txt", "RELEASE-NOTES-1.0.1.txt",
    "START-WONDER-CODEX-EDITOR.bat", "Start Wonder Codex.bat", "THIRD-PARTY.txt",
    "optimizer-mode.properties",
)


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def source_files(root):
    """Explicit public-source allowlist; never sweep a checkout or installed app."""
    files = [root / name for name in ROOT_FILES]
    files += [root / "app" / name for name in APP_FILES]
    for subtree, suffixes in (
        ("app/source", {".java", ".json"}),
        ("app/tests", {".java", ".py", ".ps1", ".json"}),
        ("app/assets", {".png", ".ico", ".svg"}),
        ("app/integrations", {".ps1"}),
        ("release-evidence", {".json", ".txt"}),
        ("third-party", {".json", ".txt"}),
    ):
        for path in sorted((root / subtree).rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if "fixtures" in relative.parts and not path.name.startswith("synthetic-"):
                raise RuntimeError("Only explicitly synthetic fixtures may be packaged: " + str(relative))
            # New build evidence is copied separately from the verified build directory.
            if subtree == "app/tests" and path.suffix == ".json" and "fixtures" not in relative.parts:
                if path.name != "release-1.0.0-results.json":
                    continue
            files.append(path)
    for path in files:
        require(path.is_file() and not path.is_symlink(), "Missing or linked public source file: " + str(path))
        require("gifter" not in path.relative_to(root).as_posix().lower(), "Private build content is excluded")
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def validate_build(source, build):
    addon = build / "WonderCodexEditor.jar"
    report = json.loads((build / "build-report.json").read_text(encoding="utf-8"))
    require(report.get("version") == VERSION, "Build report version must be " + VERSION)
    require(report.get("addon_sha256") == digest(addon), "Tested addon hash does not match")
    require(report.get("java_class_version") == 52, "Addon must target Java 8")
    passed = {test["test"] for test in report.get("tests", []) if test.get("exit_code") == 0}
    require(REQUIRED_TESTS.issubset(passed), "All eight regression suites must pass before packaging")
    expected_sources = {p.relative_to(source).as_posix(): digest(p)
                        for p in sorted((source / "app/source").glob("*.java"))}
    require(report.get("source_files") == expected_sources, "Source changed after the tested addon was built")
    require(report.get("dependencies", {}).get("CosmosBridge.jar") == BRIDGE_SHA, "Unexpected tested bridge")
    require(report.get("dependencies", {}).get("NMSSaveEditor.jar") == ENGINE_SHA, "Unexpected tested engine")
    with zipfile.ZipFile(addon) as jar:
        require(jar.testzip() is None, "Addon CRC check failed")
        manifest = jar.read("META-INF/MANIFEST.MF").decode("ascii")
        require("Implementation-Version: " + VERSION + "\r\n" in manifest, "Addon manifest version mismatch")
        classes = [name for name in jar.namelist() if name.endswith(".class")]
        require(len(classes) == report.get("production_classes"), "Addon class count differs from tested build")
        for name in classes:
            require(not any(word in name for word in ("Test", "Probe", "Smoke", "Gifter"))
                    and name != "nomanssave/Application.class", "Unexpected production class: " + name)
            require(struct.unpack(">H", jar.read(name)[6:8])[0] == 52, "Unexpected Java bytecode: " + name)
        resources = {"mission-profile.json": source / "app/source/mission-profile.json",
                     "optimizer-mode.properties": source / "app/optimizer-mode.properties"}
        for subtree in ("assets", "integrations"):
            for path in sorted((source / "app" / subtree).rglob("*")):
                if path.is_file():
                    resources[path.relative_to(source / "app").as_posix()] = path
        for name, path in resources.items():
            require(jar.read(name) == path.read_bytes(), "Packaged resource differs from tested addon: " + name)
        require(jar.read("optimizer-mode.properties").strip() == b"mode=direct", "Expected Direct UI addon")
    return report


def zip_tree(folder, destination):
    """Stable names, dates and permissions across local/Windows assembly."""
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix()):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(folder.name + "/" + path.relative_to(folder).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=6)
    with zipfile.ZipFile(destination) as archive:
        require(archive.testzip() is None, "ZIP CRC verification failed")


def json_file(path, data):
    path.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True, help="Exact public v1.0.0 Direct UI ZIP")
    parser.add_argument("--build-dir", type=Path, required=True, help="Successful build-addon.py --tests output")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--engine", type=Path, help="Pinned engine; defaults to build-dir/engine/NMSSaveEditor.jar")
    parser.add_argument("--java", default="java", help="Java executable used only for launcher verification")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; must not exist")
    parser.add_argument("--overlay-output", type=Path, help="Optional compact source/addon input ZIP for offline assembly")
    args = parser.parse_args()
    source, build, output = args.source_root.resolve(), args.build_dir.resolve(), args.output.resolve()
    require(not output.exists(), "Refusing to overwrite an existing output directory")
    require(output != source and source not in output.parents, "Output must be outside the source tree")
    if args.overlay_output:
        require(not args.overlay_output.exists(), "Refusing to overwrite an existing overlay archive")
        require(args.overlay_output.resolve() != args.template.resolve(), "Overlay cannot overwrite the template")
        require(output not in args.overlay_output.resolve().parents,
                "Place the optional overlay archive outside the package output directory")
    require(digest(args.template) == TEMPLATE_SHA, "Template SHA-256 does not match the original public release")
    report = validate_build(source, build)
    public_files = source_files(source)
    engine = (args.engine or build / "engine/NMSSaveEditor.jar").resolve()
    require(digest(engine) == ENGINE_SHA, "Launcher verification requires the pinned engine")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wc-save-fix-package-", dir=str(output.parent)) as temporary:
        work = Path(temporary)
        result = work / "result"
        result.mkdir()
        with zipfile.ZipFile(args.template) as original:
            for member in original.infolist():
                parts = PurePosixPath(member.filename).parts
                require(parts and parts[0] == PACKAGE_NAME and ".." not in parts and "\\" not in member.filename,
                        "Unexpected template entry: " + member.filename)
            original.extractall(result)
        folder = result / PACKAGE_NAME
        app = folder / "app"
        # Do not carry a previous launch log or stale source/test files into the update.
        for name in ("source", "tests", "reports"):
            shutil.rmtree(app / name, ignore_errors=True)
        for path in public_files:
            destination = folder / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        shutil.copyfile(build / "WonderCodexEditor.jar", app / "WonderCodexEditor.jar")
        json_file(app / "tests/build-1.0.1-results.json", report)
        require(digest(app / "CosmosBridge.jar") == BRIDGE_SHA, "Bridge changed during assembly")
        installer = (folder / "Install-Wonder-Codex.ps1").read_text(encoding="utf-8")
        require("WonderCodexEditor\\1.0.1-direct" in installer and "1.0.0" not in installer,
                "Installer must target side-by-side 1.0.1")
        engine_dir = app / "engine"
        require(not engine_dir.exists(), "Template unexpectedly contains an engine directory")
        engine_dir.mkdir()
        try:
            shutil.copyfile(engine, engine_dir / "NMSSaveEditor.jar")
            verified = subprocess.run([args.java, "-Djava.awt.headless=true", "-jar",
                                       str(app / "WonderCodexEditor.jar"), "--verify"],
                                      text=True, capture_output=True, check=True)
        finally:
            shutil.rmtree(engine_dir)
        entries = [{"path": path.relative_to(app).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
                   for path in sorted(app.rglob("*"), key=lambda p: p.relative_to(app).as_posix()) if path.is_file()]
        json_file(folder / "PACKAGE-CHECKSUMS.json", entries)
        files = [path for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix())
                 if path.is_file() and path != folder / "SHA256SUMS.txt"]
        (folder / "SHA256SUMS.txt").write_bytes("".join(
            digest(path) + "  " + path.relative_to(folder).as_posix() + "\n" for path in files).encode("utf-8"))
        archive = result / ARCHIVE_NAME
        zip_tree(folder, archive)
        # Verify every manifest reference against the final ZIP, not just staging files.
        with zipfile.ZipFile(archive) as packaged:
            for entry in entries:
                data = packaged.read(PACKAGE_NAME + "/app/" + entry["path"])
                require(len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"],
                        "Package manifest mismatch: " + entry["path"])
            for path in files:
                name = path.relative_to(folder).as_posix()
                require(hashlib.sha256(packaged.read(PACKAGE_NAME + "/" + name)).hexdigest() == digest(path),
                        "SHA256SUMS mismatch: " + name)
        package_report = {"version": VERSION, "edition": "Direct UI", "archive": ARCHIVE_NAME,
                          "bytes": archive.stat().st_size, "sha256": digest(archive),
                          "template_sha256": TEMPLATE_SHA, "addon_sha256": report["addon_sha256"],
                          "launcher_verification": verified.stdout.strip(), "zip_crc_verified": True,
                          "app_manifest_files": len(entries), "all_manifest_files_verified": True,
                          "game_saves_accessed": False}
        json_file(result / "release-package-results.json", package_report)
        if args.overlay_output:
            overlay = work / "save-fix-input"
            for path in public_files:
                destination = overlay / "source" / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
            (overlay / "build").mkdir()
            for name in ("WonderCodexEditor.jar", "build-report.json"):
                shutil.copyfile(build / name, overlay / "build" / name)
            args.overlay_output.parent.mkdir(parents=True, exist_ok=True)
            zip_tree(overlay, args.overlay_output)
        result.rename(output)
    print(json.dumps(package_report, indent=2))


if __name__ == "__main__":
    main()
