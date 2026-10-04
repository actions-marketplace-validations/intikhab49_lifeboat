# Security

## Reporting

Please report problems privately through
[GitHub security advisories](https://github.com/intikhab49/lifeboat/security/advisories/new), not as
a public issue. You'll get a first answer within a few days.

## What is in scope

- The build files, scripts and workflows in this repository.
- The images published at `ghcr.io/intikhab49/lifeboat/*`, for example a build that differs from
  what its Dockerfile says, or a source archive that doesn't match its pinned SHA-256.

Vulnerabilities in PostgreSQL, PostGIS, pgvector or the other components belong upstream. Once
upstream ships a fix, it reaches these images through the daily sync with Bitnami's releases or a
manual version bump, and Debian package fixes arrive with the weekly rebuild.

## Verifying an image

Every published tag carries SLSA build provenance and an SBOM:

```bash
gh attestation verify oci://ghcr.io/intikhab49/lifeboat/postgresql:18.6.0 --owner intikhab49
```
