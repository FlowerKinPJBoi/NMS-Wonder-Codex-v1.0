WONDER CODEX — PUBLIC ALPHA LANDING PAGE v0.1

This static launch package can go online immediately. It does not yet connect to PostgreSQL or accept JSON uploads.

FILES
index.html
styles.css
script.js

FASTEST ROUTE
1. Put these files in a GitHub repository.
2. Create a DigitalOcean App and connect the repository.
3. Choose Static Site and use the repository root as the output directory.
4. Deploy.
5. Add wondercodex.com as a custom domain.
6. Set the DNS records exactly as DigitalOcean displays them.

NEXT STACK
Frontend: Next.js or React
Backend: FastAPI
Database: PostgreSQL
Images: DigitalOcean Spaces

SECURITY
Never place PostgreSQL credentials in HTML, JavaScript, or a public repository. Database access must be server-side.
