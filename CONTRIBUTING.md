# Contributing

Thanks for helping. Most changes here are one of three kinds.

## A version bump

Usually you don't need to do anything: a daily job runs `scripts/sync-from-bitnami.sh`, which reads
the `BUILD.txt` in Bitnami's newest package and opens a pull request with the new versions and
checksums. To run it yourself:

```bash
scripts/sync-from-bitnami.sh images/postgresql/18/debian-12
```

## A fix to an image

Build from the repository root, then run the same checks CI runs:

```bash
docker build -f images/postgresql/18/debian-12/Dockerfile -t lifeboat/postgresql:dev .
scripts/cpu-compat.sh lifeboat/postgresql:dev         # pgvector on older CPUs
scripts/smoke-postgresql.sh lifeboat/postgresql:dev   # 76 behavior checks, expect failures: 0
scripts/build-reference.sh images/postgresql/18/debian-12 bitnami-reference/postgresql:dev
scripts/parity.sh bitnami-reference/postgresql:dev lifeboat/postgresql:dev
```

The full build compiles GDAL, protobuf and PostgreSQL, so give Docker a few GB of memory and expect
about an hour on a laptop. CI does the same on every pull request.

Rules that keep the image honest:

- Every source archive is pinned by SHA-256 in the Dockerfile; `build/fetch` refuses anything else.
- `prebuildfs/` and `rootfs/` are Bitnami's scripts, unmodified. Change behavior in the Dockerfile and
  mark it `Deviation:` with the reason.
- If a change makes lifeboat behave differently from Bitnami's image, the behavior diff in CI will
  show it. Explain why in the pull request.

## A new image

The method is the same for any Bitnami image whose package ships a `BUILD.txt`: vendor the scripts
from `bitnami/containers`, turn the recipe into build stages, and prove parity with the scripts in
`scripts/`. [docs/reverse-engineering.md](docs/reverse-engineering.md) walks through it for
PostgreSQL. Open an issue first so we can agree on the image and versions.
