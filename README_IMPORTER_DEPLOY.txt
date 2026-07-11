WONDER CODEX WEB IMPORTER ALPHA v0.1
=====================================

DEPLOYMENT
----------
Replace the files in the current Wonder Codex GitHub repository with this package,
commit, and push. DigitalOcean App Platform should automatically redeploy.

The importer will be available at:
https://wondercodex.com/import.html

CURRENT CAPABILITIES
--------------------
- Parses full No Man's Sky character JSON locally in the browser.
- Repairs common non-standard \\xNN escapes.
- Finds populated Pet records, DiscoveryData records, and GenerationID records.
- Matches Pets to Animal DiscoveryData by UA + CreatureSeed + SpeciesSeed + GenusSeed.
- Generates candidate Message IDs for Animal, Flora, and Mineral DiscoveryData.
- Displays summary counts and preview tables.
- Downloads normalized JSON, discoveries CSV, and pet-match CSV.

PRIVACY
-------
The raw character JSON is never uploaded by this static alpha. Processing occurs
inside the contributor's browser.

LIMITATIONS
-----------
- This version does not write to PostgreSQL.
- This version does not submit records to a moderation queue.
- Very large save files may take several seconds to process.
- Generated IDs use the currently confirmed encoder rules and remain subject to
  Wonder Codex verification standards.

NEXT VERSION
------------
Add an authenticated API endpoint and PostgreSQL review queue so contributors can
submit selected normalized records after preview.
