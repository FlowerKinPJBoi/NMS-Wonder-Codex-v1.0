# Dependency Policy

## Allowed by default

Dependencies may be considered when their exact version is licensed under a permissive commercial-compatible license such as:

- MIT
- BSD-2-Clause
- BSD-3-Clause
- Apache-2.0
- ISC

Every dependency still requires notice preservation and version review.

## Prohibited without a separate commercial agreement

- GPL
- AGPL
- SSPL
- source-available licenses that restrict commercial use
- dependencies with unknown or missing license metadata
- copied source or data from incompatible projects

## Current package allowlist

The build currently permits only these direct package references:

- Avalonia
- Avalonia.Desktop
- Avalonia.Themes.Fluent
- Avalonia.Fonts.Inter

Adding any direct package fails the dependency policy check until the allowlist and notices are deliberately updated.

## Release requirement

Before a public release, generate a complete direct and transitive dependency report and verify every license manually.
