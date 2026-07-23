# Windows Code Signing Setup — Public Release Blocker

The current workflow creates internal trusted-tester artifacts only.

Before public release:

1. Purchase an organization-validated or extended-validation Windows code-signing certificate from a reputable certificate authority.
2. Store the certificate and password as GitHub Actions secrets or use a supported cloud signing service.
3. Add a signing job that runs only in a protected release environment.
4. Sign the final executable after publishing and before packaging.
5. Run `signtool verify /pa /v WonderCodexImporter.exe`.
6. Generate SHA-256 after signing.
7. Upload only the signed package.

Never commit certificate files or passwords. GitHub repository secrets should be used for sensitive workflow values.
