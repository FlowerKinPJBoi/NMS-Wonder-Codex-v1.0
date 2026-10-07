#!/usr/bin/env python3
"""Build the published v1 addon, using hash-pinned binary bridge/engine inputs.

This does not rebuild CosmosBridge.jar or the complete Windows distribution.
See BUILD.md for scope, provenance, prerequisites and offline use.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

VERSION = "1.0.0"
RELEASE_SHA = "26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9"
BRIDGE_SHA = "7cebd0ae928e571fd340543bbc2eb3c9fe3cf6cada4be6e1d4dbd5f9061889e8"
ENGINE_SHA = "ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c"
ENGINE_URL = ("https://raw.githubusercontent.com/goatfungus/NMSSaveEditor/"
              "6047315f47321e2a8400d38bf8d904bcca88bb8d/NMSSaveEditor.jar")
ECJ_SHA = "05cc22a24e7982970f63a405fc6c820bc80b806f27f3c5a6236fc475f8f7152b"
ECJ_URL = "https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.40.0/ecj-3.40.0.jar"
TEST_NAMES = (
    "WCEditorTazRunPreferenceTest", "WCEditorTazOptimizerTest", "WCEditorTazToolTest",
    "WCEditorBasesTest", "WCEditorInventoryActionsTest", "WCEditorCodexScanTest",
    "WCEditorCodexClientTest",
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checked(path, expected):
    path = Path(path).resolve()
    actual = digest(path)
    if actual != expected:
        raise RuntimeError("SHA-256 mismatch for {}: expected {}, got {}".format(path, expected, actual))
    return path


def dependency(provided, cache, filename, url, expected):
    if provided:
        return checked(provided, expected)
    cached = cache / filename
    if cached.exists():
        return checked(cached, expected)
    cache.mkdir(parents=True, exist_ok=True)
    print("Downloading pinned dependency: " + url, flush=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(cache), prefix=filename + ".", delete=False) as target:
            temporary = Path(target.name)
            request = urllib.request.Request(url, headers={"User-Agent": "WonderCodexEditor-source-build/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                if not response.geturl().startswith("https://"):
                    raise RuntimeError("Refusing a dependency download redirected away from HTTPS")
                shutil.copyfileobj(response, target)
        checked(temporary, expected)
        temporary.replace(cached)
        temporary = None
        return cached.resolve()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def release_member(bundle, suffix):
    matches = [entry for entry in bundle.infolist()
               if not entry.is_dir() and (entry.filename == suffix or entry.filename.endswith("/" + suffix))]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one release member ending in " + suffix)
    return bundle.read(matches[0])


def input_bridge(args):
    reference = None
    if args.release_zip:
        release = checked(args.release_zip, RELEASE_SHA)
        with zipfile.ZipFile(release) as bundle:
            bridge_bytes = release_member(bundle, "app/CosmosBridge.jar")
            # Read the released addon for entry-content comparison; do not execute it.
            reference = release_member(bundle, "app/WonderCodexEditor.jar")
    else:
        bridge_bytes = checked(args.bridge, BRIDGE_SHA).read_bytes()
    if hashlib.sha256(bridge_bytes).hexdigest() != BRIDGE_SHA:
        raise RuntimeError("The release contains a bridge with an unexpected SHA-256")
    return bridge_bytes, reference


def run(command, cwd):
    result = subprocess.run(command, cwd=str(cwd), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.returncode:
        raise RuntimeError("Command failed (exit {}): {}".format(result.returncode, command[0]))
    return result.stdout.strip()


def write_jar(destination, entries):
    # Stable entry ordering/timestamps. This is not a claim about the original ZIP's bytes.
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(entries, key=lambda value: (value != "META-INF/MANIFEST.MF", value)):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, entries[name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--release-zip", type=Path, help="Exact published Direct UI v1.0.0 ZIP (hash checked)")
    source.add_argument("--bridge", type=Path, help="Existing CosmosBridge.jar (hash checked)")
    parser.add_argument("--ecj", type=Path, help="Pinned ECJ JAR; otherwise fetch/cache it")
    parser.add_argument("--engine", type=Path, help="Pinned GoatFungus engine JAR; otherwise fetch/cache it")
    parser.add_argument("--java", default="java", help="Java 17+ executable for ECJ and verification")
    parser.add_argument("--output", type=Path, required=True, help="New build directory; must not already exist")
    parser.add_argument("--cache", type=Path, default=Path(__file__).resolve().parent / "build" / "dependencies")
    parser.add_argument("--tests", action="store_true", help="Run seven synthetic/headless offline test suites")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    app = root / "app"
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; choose a new directory. No installed editor is overwritten.")
    if output == root or output in root.parents or app == output or app in output.parents:
        parser.error("Output must not replace the source tree or be within app/.")
    if args.cache.resolve() == output or output in args.cache.resolve().parents:
        parser.error("Dependency cache must be outside the output directory.")
    sources = sorted((app / "source").glob("*.java"))
    if not sources:
        parser.error("No app/source/*.java files found next to this script.")
    bridge_bytes, reference = input_bridge(args)
    ecj = dependency(args.ecj, args.cache.resolve(), "ecj-3.40.0.jar", ECJ_URL, ECJ_SHA)
    engine = dependency(args.engine, args.cache.resolve(), "NMSSaveEditor.jar", ENGINE_URL, ENGINE_SHA)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wc-addon-build-", dir=str(output.parent)) as temporary:
        work = Path(temporary)
        built = work / "output"
        built.mkdir()
        (built / "CosmosBridge.jar").write_bytes(bridge_bytes)
        (built / "engine").mkdir()
        shutil.copyfile(engine, built / "engine" / "NMSSaveEditor.jar")
        classes = work / "classes"
        classes.mkdir()
        cp = os.pathsep.join([str(built / "CosmosBridge.jar"), str(built / "engine" / "NMSSaveEditor.jar")])
        compiler = [args.java, "-jar", str(ecj), "-1.8", "-nowarn", "-encoding", "UTF-8"]
        run(compiler + ["-cp", cp, "-d", str(classes)] + [str(path) for path in sources], work)
        compiled = sorted(classes.rglob("*.class"))
        if not compiled or any(struct.unpack(">H", path.read_bytes()[6:8])[0] != 52 for path in compiled):
            raise RuntimeError("Production classes must target Java 8 (major version 52)")
        if any(path.name == "Application.class" or any(token in path.name for token in ("Test", "Probe", "Smoke"))
               for path in compiled):
            raise RuntimeError("Unexpected engine overlay/test class in addon production output")
        manifest = ("Manifest-Version: 1.0\r\nMain-Class: nomanssave.WCEditorLauncher\r\n"
                    "Implementation-Version: " + VERSION + "\r\n"
                    "Class-Path: CosmosBridge.jar engine/NMSSaveEditor.jar\r\n\r\n")
        entries = {path.relative_to(classes).as_posix(): path.read_bytes() for path in compiled}
        entries["META-INF/MANIFEST.MF"] = manifest.encode("ascii")
        entries["mission-profile.json"] = (app / "source" / "mission-profile.json").read_bytes()
        entries["optimizer-mode.properties"] = (app / "optimizer-mode.properties").read_bytes()
        for category in ("assets", "integrations"):
            for path in sorted((app / category).rglob("*")):
                if path.is_file():
                    entries[path.relative_to(app).as_posix()] = path.read_bytes()
        jar = built / "WonderCodexEditor.jar"
        write_jar(jar, entries)
        # Only the launcher's verification path is invoked; the editor UI is not opened.
        verification = run([args.java, "-Djava.awt.headless=true", "-jar", str(jar), "--verify"], work)
        report = {"version": VERSION, "scope": "addon build; prebuilt bridge and engine dependencies",
                  "production_classes": len(compiled), "java_class_version": 52,
                  "source_files": {path.relative_to(root).as_posix(): digest(path) for path in sources},
                  "dependencies": {"CosmosBridge.jar": BRIDGE_SHA, "NMSSaveEditor.jar": ENGINE_SHA,
                                   "ecj-3.40.0.jar": ECJ_SHA},
                  "addon_sha256": digest(jar), "launcher_verification": verification, "tests": []}
        if reference is not None:
            with zipfile.ZipFile(io.BytesIO(reference)) as original:
                original_entries = {entry.filename: original.read(entry) for entry in original.infolist()
                                    if not entry.is_dir()}
            differences = sorted(name for name in set(entries) | set(original_entries)
                                 if entries.get(name) != original_entries.get(name))
            report["release_comparison"] = {"zip_sha256": RELEASE_SHA,
                                            "compared_addon_entries": len(entries),
                                            "all_entry_contents_match": not differences,
                                            "differing_entries": differences}
        if args.tests:
            test_classes = work / "test-classes"
            test_classes.mkdir()
            test_cp = os.pathsep.join([str(test_classes), str(jar), cp])
            test_sources = [str(app / "tests" / (name + ".java")) for name in TEST_NAMES]
            run(compiler + ["-cp", test_cp, "-d", str(test_classes)] + test_sources, work)
            isolated = work / "test-state"
            isolated.mkdir()
            for name in TEST_NAMES:
                command = [args.java, "-Djava.awt.headless=true", "-Duser.home=" + str(isolated),
                           "-Djava.util.prefs.userRoot=" + str(isolated / "preferences"),
                           "-Djava.io.tmpdir=" + str(isolated), "-cp", test_cp, "nomanssave." + name]
                if name == "WCEditorBasesTest":
                    command.append(str(app / "tests" / "fixtures" / "synthetic-bases.json"))
                report["tests"].append({"test": name, "stdout": run(command, work), "exit_code": 0})
        (built / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        # Publish the local output only after compilation, verification and requested tests pass.
        built.rename(output)
    print("Built and verified addon: " + str(output / "WonderCodexEditor.jar"))
    print("Build evidence: " + str(output / "build-report.json"))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, zipfile.BadZipFile) as failure:
        print("Build failed: " + str(failure), file=sys.stderr)
        sys.exit(1)
