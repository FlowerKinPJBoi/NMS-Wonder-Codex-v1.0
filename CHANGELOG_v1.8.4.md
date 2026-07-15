# Wonder Codex v1.8.4 — In-page Testing Briefs

## Added

- Expandable testing brief on both `/admin/apps/` release cards.
- Importer beta steps for safe download verification, normal non-admin launch, account/character detection, analysis comparison, WCCP export, screenshots, and return files.
- Separate Pegasus Transit instructions for the validated Xbox / Game Pass handoff and Boots' first Steam matched-pair validation.
- Explicit screenshots, evidence files, privacy rules, and stop conditions for each application.
- **Copy checklist** action for pasting the full test brief into a private message.
- **Download test report (.txt)** action containing a fill-in result template for each application.

## Safety

- Importer testers are told never to return raw saves, local paths, platform account identifiers, or administrator keys.
- Pegasus raw evidence is explicitly restricted to private PJ/Boots review and must never be published to Discord, GitHub, or the public site.
- Unexpected malware alerts, zero/materially wrong Importer totals, Pegasus write failures, cloud conflicts, or missing newer-cloud confirmation are stop conditions.

No database migration or new environment variable is required.
