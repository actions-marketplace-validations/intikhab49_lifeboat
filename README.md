# lifeboat

**Bitnami's PostgreSQL image, rebuilt from upstream source.** Same paths, scripts, environment
variables and tags, so it drops into Bitnami's Helm chart and your compose files. Free to pull,
amd64 and arm64, and none of its binaries come from Broadcom.

If you are here because of this:

```
Error response from daemon: failed to resolve reference "docker.io/bitnami/postgresql:17.6.0-debian-12-r0": docker.io/bitnami/postgresql:17.6.0-debian-12-r0: not found
```

Broadcom removed the versioned `bitnami/*` tags from Docker Hub in 2025. `bitnami/postgresql` now
only has `latest`, and the copies in `bitnamilegacy` stopped getting updates in August 2025.
Change the image and keep the rest of your setup.

## Use it

```bash
docker run -d -p 5432:5432 -e POSTGRESQL_PASSWORD=secret ghcr.io/intikhab49/lifeboat/postgresql:18.6.0
```

```yaml
# docker-compose.yml
services:
  db:
    image: ghcr.io/intikhab49/lifeboat/postgresql:18
    environment:
      POSTGRESQL_PASSWORD: secret
    volumes:
      - db:/bitnami/postgresql
volumes:
  db:
```

With Bitnami's Helm chart:

```bash
helm install db oci://registry-1.docker.io/bitnamicharts/postgresql \
  --set image.registry=ghcr.io \
  --set image.repository=intikhab49/lifeboat/postgresql \
  --set image.tag=18.6.0 \
  --set global.security.allowInsecureImages=true
```

The last flag is needed because the chart blocks images it doesn't know with
`Original containers have been substituted for unrecognized ones`.

| Tag | Meaning |
|---|---|
| `18.6.0-debian-12-r14` | same version, OS and scripts revision as Bitnami's tag of that name |
| `18.6.0`, `18.6`, `18`, `latest` | moving tags, as on Bitnami |

Every `POSTGRESQL_*` variable, `/docker-entrypoint-initdb.d`, the `/bitnami/postgresql` volume,
UID 1001, replication mode and arbitrary-UID support (OpenShift) work the same way, because
they are Bitnami's own scripts.

## Why not just build Bitnami's Dockerfile?

Because it doesn't build PostgreSQL. It downloads a 52 MB prebuilt package from
`downloads.bitnami.com` and unpacks it, and it already has a build secret for pointing that
download at a private server. The day Broadcom closes the public one, every "build it yourself"
fork stops building.

lifeboat compiles all of it from upstream source: PostgreSQL plus the 18 components Bitnami
bundles with it (PostGIS, GDAL, GEOS, PROJ, pgvector, pgAudit, pgBackRest, orafce, PL/Java,
psqlODBC, wal2json, pg_failover_slots, protobuf, nss_wrapper and the rest). Every source archive is
pinned by SHA-256 in the [Dockerfile](images/postgresql/18/debian-12/Dockerfile).

## How the recipe was recovered

Bitnami's PostgreSQL package carries its own build log. The tarball on `downloads.bitnami.com` has a
`BUILD.txt` with the exact sources, versions and `configure` flags, and `pg_config` inside the
package records the build environment (`CC`, `LDFLAGS`, `CPPFLAGS`) that `BUILD.txt` leaves out.
The binaries fill in the rest: the RUNPATH they share, the GCC version in `.comment`, and
which files get stripped or deleted. The full walkthrough, with commands to check every claim, is in
[docs/reverse-engineering.md](docs/reverse-engineering.md).

## A bug this build fixes

Bitnami compiles pgvector with `-march=native`, the default in pgvector's Makefile that its own
comment says to turn off for portable builds. Their `vector.so` only runs on CPUs like their build
servers. PostgreSQL itself runs on every CPU in the table below; pgvector does not. On amd64 even
`CREATE EXTENSION vector` kills the backend, and the server drops every other connection while it
recovers:

```
LOG:  client backend (PID 52) was terminated by signal 4: Illegal instruction
LOG:  terminating any other active server processes
LOG:  all server processes terminated; reinitializing
```

| CPU (QEMU model) | PostgreSQL | Bitnami's pgvector | lifeboat's pgvector |
|---|---|---|---|
| amd64 Nehalem, no AVX | runs | **illegal instruction** | runs |
| amd64 Sandy Bridge, AVX without AVX2/FMA | runs | **illegal instruction** | runs |
| amd64 Haswell, AVX2 and FMA | runs | runs | runs |
| arm64 Cortex-A53 (Raspberry Pi 3 class) | runs | **illegal instruction** | runs |
| arm64 Cortex-A72 (Raspberry Pi 4 class) | runs | **illegal instruction** | runs |

That includes the image you can still pull: `docker.io/bitnami/postgresql:latest` (built
2026-10-02, Photon OS) crashes the same way on both amd64 models. Older Intel chips, many Celeron
and Atom NAS boxes, VMs whose CPU type hides AVX2, and ARM boards without FP16 are affected. Check
any copy with `scripts/cpu-compat.sh IMAGE`.

## Proof it's the same image

Every CI run also builds Bitnami's own image from the same `bitnami/containers` commit and
compares the two. Results for 18.6.0 on amd64, checked on 2026-10-04:

| Check | Result |
|---|---|
| Container config: env, user, entrypoint, command, ports, volumes | identical |
| Behavior, 76 checks: env-var setup, init scripts, all 56 extensions, PostGIS build info, pgvector HNSW, wal2json, restart, arbitrary UID, streaming replication | identical (CI fails if not) |
| Extensions and their versions | 56 of 56 identical |
| GDAL formats | 121 of 121 identical |
| Libraries linked by each of the 196 binaries and shared libraries | identical |
| Unresolved libraries | none in either image |

Each run's summary on the Actions tab has the full file-level diff and the components Trivy finds
in both images. Every difference that remains is listed below.

## Differences from Bitnami's image

The ones that change how something is built are marked `Deviation:` in the Dockerfile.

- Everything is compiled from upstream source, nothing is downloaded prebuilt.
- pgvector is built with `OPTFLAGS=""` so it runs on any CPU of its architecture.
- Every source archive is checked against a pinned SHA-256.
- The runtime base is the official `debian:bookworm-slim` instead of `bitnami/minideb`. Perl is
  not installed: minideb pulls it in through `usrmerge`, and Bitnami's package list never asks for
  it.
- License files hold the full upstream texts, including Abseil, which Bitnami's omit.
- The SPDX files scanners read sit at the same paths with the same component names, minus three
  errors in Bitnami's: protobuf's CPE, psqlODBC's license and the missing Abseil entry.
- The startup banner says lifeboat instead of "Welcome to the Bitnami postgresql container".

## FAQ

**Is this Bitnami's image?** No. It runs Bitnami's Apache-2.0 container scripts, unmodified, on
top of components built here. Not affiliated with Broadcom or Bitnami.

**How do I verify an image?** Every tag carries SLSA build provenance and an SBOM:
`gh attestation verify oci://ghcr.io/intikhab49/lifeboat/postgresql:18.6.0 --owner intikhab49`

**Does it get updates?** It is rebuilt every week, which picks up Debian security fixes. Version
bumps land as pull requests that must pass the CPU and behavior checks, with the parity report
attached.

**Can I keep using `bitnamilegacy/postgresql`?** It works, but it has been frozen since August
2025, so nothing fixed since then has reached it.

**What about Redis, MongoDB, Kafka and the others?** PostgreSQL is first. The same method works
for any image whose package ships a `BUILD.txt`.

## License

Build files and tests: Apache-2.0 ([LICENSE](LICENSE)). The vendored Bitnami scripts are
Apache-2.0, © Broadcom. Each component in the image keeps its own license, see [NOTICE](NOTICE).
