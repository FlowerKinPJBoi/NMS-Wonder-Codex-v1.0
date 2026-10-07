# Wonder Codex Editor v1.0.0 release review

## Exact file under review

| Field | Value |
| --- | --- |
| Uploaded filename | `Wonder-Codex-Editor-v1.0.0.zip` |
| Edition | Direct UI, Windows x64 |
| Size | 132334940 bytes |
| SHA-256 | `26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9` |
| VirusTotal report | [Existing report for this exact hash](https://www.virustotal.com/gui/file/26e3873c725f9510fcc51652835c33560a5b71efc1ad047722520e7b407aace9) |

The existing public VirusTotal report was inspected on October 7, 2026. It
displayed **0/40 detections**, with last analysis October 7, 2026 at 18:55:26 EDT
(22:55:26 UTC). Other engines reported timeouts, unsupported types or failure.
This is the result for this archive at that time, not a guarantee of safety or
clearance of every component. No upload or rescan was requested during this review.

Nexus Mods quarantined the upload. The warning provided general categories
(executables, automated flags and nested archives); it did not identify a
particular malicious file or detection. The precise quarantine cause has not
been established. Publishing on GitHub does not remove a Nexus quarantine.

## Integrity and provenance checks

- The uploaded archive is byte-for-byte identical to the original Direct UI
  v1.0.0 release; only the uploaded filename differs.
- All 262 ZIP file entries passed CRC checks. No duplicate names, case collisions,
  path traversal, encrypted entries or symlink entries were found.
- All 253 application-manifest entries and all 261 release checksum entries
  matched. There were no unlisted application files.
- All 175 bundled Java runtime files matched the official Eclipse Temurin
  8u504-b01 Windows x64 JRE archive byte-for-byte. The corresponding bundled
  upstream source archive also matched its official checksum.
- The package's 17 Windows executables and 87 DLLs belong to that Java runtime.
  The separate TAZmd optimizer executable is not bundled.

The original release manifests are preserved under [release-evidence](release-evidence).
They describe the complete Windows ZIP, not this smaller source checkout.
[source-snapshot.json](source-snapshot.json) records the files copied unchanged
from that ZIP into this public review snapshot.

These checks establish file identity and dependency provenance. They are not a
substitute for antivirus analysis or a complete independent security audit.

The [public addon rebuild](release-evidence/addon-rebuild-2026-10-07.json) compiled
77 Java 8 production classes, passed launcher verification and all 698 selected
automated checks, and matched the contents of all 90 entries in the released
addon JAR. Archive metadata was excluded from this content comparison. The
build also succeeded with local dependency inputs, and rejected an incorrect
bridge checksum before compilation.

## Components and build limits

| Component | Provenance / build coverage |
| --- | --- |
| Wonder Codex desktop extension 1.0.0 | Source, resources, installer scripts and tests are published here; see [BUILD.md](BUILD.md). |
| CosmosBridge 0.1.0 | Existing compiled compatibility overlay; original source and transformation scripts have not been recovered. Required binary SHA-256: `7cebd0ae928e571fd340543bbc2eb3c9fe3cf6cada4be6e1d4dbd5f9061889e8`. |
| GoatFungus engine 1.21.0 | Downloaded unchanged from a fixed upstream revision; SHA-256: `ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c`. See [provenance](third-party/goatfungus-provenance.json). |
| Eclipse Temurin JRE | Unmodified runtime in the release; notices and corresponding source supplied there. See [runtime provenance](third-party/RUNTIME-PROVENANCE.json). |
| TAZmd Corvette Optimizer | Separately obtained from TAZmd. No executable, implementation or ship library is included. |

CosmosBridge contains Wonder Codex additions and modified native editor classes.
The published addon also uses the native editor API. Upstream credits and the
existing provenance notes are preserved; no new third-party licensing grant is
claimed. A successful addon rebuild does not prove that CosmosBridge is
reproducible from source or that the complete ZIP is reproducible byte-for-byte.

## Relevant installer and integration behavior

The installer verifies package files, downloads the pinned upstream editor
engine over HTTPS, verifies its checksum, and installs into a new user-local
folder. It preserves existing installations and creates a desktop shortcut.
The launcher uses process-scoped PowerShell `ExecutionPolicy Bypass` and a hidden
launcher window. These switches are visible in the published scripts; they do
not change the computer's persistent execution policy.

The TAZmd integration can check the official version feed, help the user obtain
the optimizer, and use Windows UI Automation and the clipboard to operate the
separately installed app. Returned corvette data must pass the editor's
validation before the user stages changes. Passport sign-in and explicit
submission are used for Wonder Codex site contributions. Local editing does not
require Passport.

No user save files, account credentials or private application configuration
are included in this source snapshot. Test credentials and fixtures are
synthetic. The original release's recorded 698 automated checks are retained in
[release-1.0.0-results.json](app/tests/release-1.0.0-results.json); those functional
checks are not malware scans. A new Windows GUI test was not part of that v1.0.0
release validation.
