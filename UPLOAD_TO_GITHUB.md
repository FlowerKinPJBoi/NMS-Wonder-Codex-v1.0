# Upload and Build the Wonder Codex Importer

This package is designed to live inside the existing Wonder Codex GitHub repository without disturbing the website or API.

## Upload

Upload these two package items into the repository root:

```text
.github/
importer-app/
```

GitHub should merge the new `.github/workflows` directory with any existing workflow files.

## Build the first trusted-tester executable

1. Commit the upload to `main`.
2. Open the repository's **Actions** tab.
3. Select **Build Wonder Codex Importer**.
4. Click **Run workflow**.
5. Wait for the read-only verification, decoder self-tests, restore, and publish steps to pass.
6. Download the artifact named:

```text
WonderCodexImporter-v0.1.0-win-x64
```

7. Extract the ZIP on a Windows test computer and run `WonderCodexImporter.exe`.

## Important first-build note

The ChatGPT build environment could validate source syntax, XML, the read-only API scan, and package structure, but it does not contain the .NET SDK or a Windows desktop runtime. GitHub Actions performs the first complete compiler and Windows publishing pass.

Do not add the public website download button until the trusted-tester build has launched and PJ's two Xbox / Game Pass accounts have been verified.
