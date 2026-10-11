# Building the Wonder Codex Editor v1.0.1 addon

This directory publishes the Wonder Codex addon source, resources, scripts and tests for the v1.0.1 Direct UI update. The build below compiles the addon and verifies it against the same pinned dependencies used by v1.0.0.

**This is not a complete application build from source.** Original source and build instructions for the earlier `CosmosBridge.jar` have not yet been recovered. The build therefore uses the exact existing bridge binary from the release. The GoatFungus engine is also a pinned binary dependency. The addon build does not reproduce the entire original Windows setup ZIP. The packaging command below assembles a new update from that exact ZIP; it does not rebuild its binary dependencies.

## Requirements

- Python 3.8 or newer; standard library only.
- Java 17 or newer on `PATH`, needed by Eclipse ECJ 3.40.0. The compiled addon targets Java 8 bytecode. Use `--java /path/to/java` if needed.
- Either the exact published v1.0.0 Direct UI ZIP or its `CosmosBridge.jar`.
- Internet access for the first download of the compiler and engine, unless both are supplied locally.

No existing editor installation, account, game save, Passport login or TAZmd executable is needed for this build. It does not run the installer or open the editor UI.

## Build and verify

Run from this directory, substituting the path to your downloaded release:

```sh
python build-addon.py --release-zip /path/to/Wonder-Codex-Editor-v1.0.0.zip --output build/review --tests
```

On Windows, `py -3` can replace `python`; quote paths containing spaces. The ZIP may have a different filename, but its bytes must match this SHA-256:

```text
26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9
```

The script checks the ZIP hash before reading its bridge and reference addon. It extracts no other archive members. To use a bridge already on disk instead:

```sh
python build-addon.py --bridge /path/to/CosmosBridge.jar --output build/review --tests
```

The output directory must not already exist. This prevents overwriting an installed editor or a previous build. The output contains:

- `WonderCodexEditor.jar`, rebuilt from `app/source/*.java` and the shipped resources.
- `CosmosBridge.jar` and `engine/NMSSaveEditor.jar`, checked copies for local verification.
- `build-report.json`, recording source hashes, dependency hashes, class count, Java bytecode version and verification/test output.

The launcher is invoked only with `--verify` and headless mode. That path checks component hashes, addon version, mission profile and class loading without opening or writing a game save. It executes the checked Java components; it is not an antivirus scan. When a release ZIP is supplied, the report also compares the content of every rebuilt addon entry against the shipped addon. ZIP timestamps and compression metadata are not part of that comparison.

Resources packaged in the addon are `mission-profile.json`, `optimizer-mode.properties`, `assets/` and `integrations/`. `feature-coverage.json` is shipped as a separate source-side reference, as in the original release. Test classes and the engine's `Application.class` overlay are excluded from the addon.

## Dependency pins and offline build

Every supplied, cached or downloaded dependency is checked by SHA-256 before use. A mismatch stops the build; the script does not silently accept a different version.

| Dependency | SHA-256 |
| --- | --- |
| CosmosBridge 0.1.0 | `7cebd0ae928e571fd340543bbc2eb3c9fe3cf6cada4be6e1d4dbd5f9061889e8` |
| GoatFungus NMSSaveEditor 1.21.0 | `ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c` |
| Eclipse ECJ 3.40.0 | `05cc22a24e7982970f63a405fc6c820bc80b806f27f3c5a6236fc475f8f7152b` |

The compiler is fetched from [Maven Central](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.40.0/ecj-3.40.0.jar). The engine is fetched from [GoatFungus's fixed repository commit](https://raw.githubusercontent.com/goatfungus/NMSSaveEditor/6047315f47321e2a8400d38bf8d904bcca88bb8d/NMSSaveEditor.jar), not a moving latest-version URL. See `third-party/goatfungus-provenance.json` for the recorded provenance. Neither dependency is committed in this source directory.

Downloads are cached under `build/dependencies/` by default; `--cache` changes that directory. To build without making any download requests, supply both binaries explicitly:

```sh
python build-addon.py --bridge /path/to/CosmosBridge.jar --ecj /path/to/ecj-3.40.0.jar --engine /path/to/NMSSaveEditor.jar --output build/offline-review --tests
```

## Optional tests and scope

`--tests` runs eight test classes in headless mode: TAZmd run preference, optimizer validation, executable recognition, bases, inventory actions, discovery scanning, the Codex client and native save-error feedback. They use synthetic data, temporary files, isolated preference nodes and scripted transport; they do not launch the optimizer, send contribution requests or read/write real game saves. The original seven suites contain 698 checks; the new save-error suite adds 24, for 722 headless checks in v1.0.1. The base fixture is `app/tests/fixtures/synthetic-bases.json`.

These checks do not establish Windows GUI, installer, live API or in-game behavior, and do not establish malware clearance. The archived `app/tests/release-1.0.0-results.json` describes the original release validation; each new build writes its own report.

`app/tests/build-release.py` is the historical Windows-package assembly script. It expects a complete release template, including the Java runtime, source archive and bridge; this source directory deliberately does not bundle those binary dependencies. Use the addon build above for review of the published Java changes. See `app/THIRD-PARTY.txt` and `third-party/` for component attribution and notices; publication here does not relicense third-party components.

## Assemble the v1.0.1 Direct UI Windows setup

After `build-addon.py --tests` succeeds, run:

```sh
python app/tests/package-save-fix.py --template /path/to/Wonder-Codex-Editor-v1.0.0.zip --build-dir build/review --output /path/to/new-package-output
```

The output directory must not exist. This command verifies the original ZIP hash,
the tested addon hash/version, source hashes, Java bytecode and packaged resources.
It includes the current public source, scripts, documentation and test evidence;
keeps the original bridge, runtime and matching upstream source archive; and
regenerates `PACKAGE-CHECKSUMS.json` and `SHA256SUMS.txt`. The pinned engine is used
only for launcher verification and remains an installation-time download.

It creates `Wonder-Codex-Editor-v1.0.1-Direct-UI-Windows-Setup.zip`, an extracted
package and `release-package-results.json`. The installer targets a new
`1.0.1-direct` folder and creates a separate desktop shortcut. It does not replace
an open editor, transfer unsaved edits, or modify any game save. Finish saving
staged work in the old editor before switching versions.
