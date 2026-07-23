# Public Repository Cleanup

After the private repository is created and verified:

1. Delete the `importer-app` directory from the public repository's current branch.
2. Delete `.github/workflows/build-importer.yml` from the public repository.
3. Add a public notice stating that Importer development moved to a private proprietary repository.
4. Keep only public-facing download, security, privacy, release-note, and checksum material.
5. Do not rewrite Git history merely to hide the prototype. Earlier public MIT versions remain public and licensed under MIT.
6. Confirm DigitalOcean is not using or watching `importer-app` or the removed workflow.
7. Confirm the public site's existing build still deploys normally.

Suggested commit message:

`Move Wonder Codex Importer development to private repository`
