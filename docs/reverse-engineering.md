# How the PostgreSQL recipe was recovered

Bitnami's `postgresql` Dockerfile is public (Apache-2.0), but it does not build PostgreSQL. It
downloads two prebuilt tarballs from Broadcom's server and unpacks them:

```dockerfile
ARG DOWNLOADS_URL="https://downloads.bitnami.com/files/stacksmith"
RUN --mount=type=secret,id=downloads_url,env=SECRET_DOWNLOADS_URL \
    DOWNLOADS_URL=${SECRET_DOWNLOADS_URL:-${DOWNLOADS_URL}} ; \
    COMPONENTS=( "nss-wrapper-1.1.16-0-linux-${OS_ARCH}-debian-12" \
                 "postgresql-18.6.0-14-linux-${OS_ARCH}-debian-12" ) ; ...
```

So "build it yourself" only works while `downloads.bitnami.com` keeps serving those files, and the
build secret shows the URL can already be switched to a private server. Everything below is what it
took to build the same thing from upstream source instead. All of it can be checked with the
commands in [Reproduce](#reproduce).

## 1. The recipe ships inside the package

The PostgreSQL package carries its own recipe in two files:

- `BUILD.txt` at the tarball root, which the Dockerfile's `--strip-components=2` throws away. It
  lists the build image (`bitnami/minideb:bookworm`), the apt build dependencies, and every
  download, `configure`/`cmake`/`meson` call and `make` in order, ending with the list of files it
  strips.
- `files/postgresql/.spdx-postgresql.spdx`, which does reach the image. It is an SPDX SBOM listing
  the bundled packages with versions and download locations. The nss_wrapper package has only
  this file, no `BUILD.txt`.

The two packages hold 19 upstream projects. The 52 MB `postgresql-18.6.0-14` package bundles 18
of them, and nss_wrapper ships on its own:

| Component | Version | Built with | Installed into |
|---|---|---|---|
| PostgreSQL | 18.6 | autoconf, `make world-bin` | `/opt/bitnami/postgresql` |
| GEOS | 3.15.0 | CMake | `/opt/bitnami/postgresql` |
| PROJ | 6.3.2 | autoconf | `/opt/bitnami/postgresql` |
| GDAL | 3.13.3 | CMake, internal libs only | `/opt/bitnami/postgresql` |
| json-c | 0.16-20220414 | CMake | `/opt/bitnami/postgresql` |
| PostGIS | 3.6.4 | autoconf | `/opt/bitnami/postgresql` |
| pgvector | 0.8.7 | PGXS | `/opt/bitnami/postgresql` |
| pgAudit | 18.0 | PGXS | `/opt/bitnami/postgresql` |
| orafce | 4.16.13 | PGXS | `/opt/bitnami/postgresql` |
| pg_failover_slots | 1.2.1 | PGXS | `/opt/bitnami/postgresql` |
| wal2json | 2.6 | PGXS | `/opt/bitnami/postgresql` |
| pgBackRest | 2.59.2 | Meson | `/opt/bitnami/postgresql` |
| PL/Java | 1.6.10 | Maven, Java 17 | `/opt/bitnami/postgresql` |
| psqlODBC | 18.00.0004 | autoconf | `/opt/bitnami/postgresql` |
| unixODBC | 2.3.14 | autoconf | `/opt/bitnami/common` |
| protobuf (+ Abseil 20250512.1) | 36.2 | CMake, static | `/opt/bitnami/protobuf` |
| protobuf-c | 1.5.2 | autoconf | `/opt/bitnami/common` |
| nss_wrapper | 1.1.16 | CMake | `/opt/bitnami/common` (separate package) |

## 2. What BUILD.txt leaves out, recovered from the binaries

**The build environment.** BUILD.txt lists commands but not the environment they ran in.
PostgreSQL records it anyway. `pg_config --configure` in Bitnami's build prints:

```
'--prefix=/opt/bitnami/postgresql' '--with-libedit-preferred' '--with-openssl' '--with-libxml'
'--with-libxslt' '--with-readline' '--with-icu' '--with-uuid=e2fs' '--with-ldap' 'CFLAGS=-O2'
'CXXFLAGS=-O2' '--with-lz4' 'CC=gcc'
'LDFLAGS=-Wl,-rpath=/opt/bitnami/protobuf/lib -L/opt/bitnami/protobuf/lib -Wl,-rpath=/opt/bitnami/common/lib -L/opt/bitnami/common/lib -Wl,-rpath=/opt/bitnami/postgresql/lib -L/opt/bitnami/postgresql/lib'
'CPPFLAGS=-I/opt/bitnami/protobuf/include -I/opt/bitnami/common/include -I/opt/bitnami/postgresql/include'
```

`CC`, `LDFLAGS` and `CPPFLAGS` were never passed on the command line, so they were global in the
build environment. The ELF files confirm it: 177 of the package's binaries and libraries share
`RUNPATH=/opt/bitnami/protobuf/lib:/opt/bitnami/common/lib:/opt/bitnami/postgresql/lib`. That is
how the image finds its bundled libraries without `LD_LIBRARY_PATH`.

**The compiler.** The `.comment` section of `postgres`, `postgis-3.so` and `libgdal.so` says
`GCC: (Debian 12.2.0-14+deb12u1) 12.2.0`, the stock Debian 12 compiler.

**The packaging rules.** Comparing the tarball with a plain `make install` shows the post-processing:
no libtool `.la` files, no static libraries except PostgreSQL's own six `libpg*.a`, no man pages or
docs, every ELF file stripped, and one license file per component under `licenses/`.

**The base image.** `bitnami/minideb:bookworm` is Debian 12 with an `install_packages` helper. The
helper is already in the Dockerfile's `prebuildfs`, so the official `debian:bookworm-slim` works
as the runtime base.

## 3. Findings

### pgvector is compiled for Bitnami's build machine

pgvector's Makefile defaults to `OPTFLAGS = -march=native` and says so:

```make
# To compile for portability, run: make OPTFLAGS=""
OPTFLAGS = -march=native
```

BUILD.txt runs `make USE_PGXS=1 --jobs=5`, with no override, so the compiler targets whatever CPU
Bitnami's build host had, everywhere in the library rather than behind runtime CPU checks. In the
amd64 disassembly, AVX and FMA instructions sit in the code of ordinary exported functions such as
`cosine_distance`, `l2_normalize` and `vector_norm`. The arm64 build uses ARMv8.2 half-precision
arithmetic (`fadd v0.8h`, `fabs h0`) in the halfvec functions, including the input parser
`halfvec_in`.

`scripts/cpu-compat.sh` runs PostgreSQL in single-user mode on QEMU CPU models. First a plain
query, then pgvector queries:

| CPU model (amd64) | PostgreSQL | Bitnami's pgvector | pgvector built with `OPTFLAGS=""` |
|---|---|---|---|
| host (Core i5-1135G7) | pass | pass | pass |
| Nehalem (no AVX) | pass | **SIGILL** (illegal instruction) | pass |
| SandyBridge (AVX, no AVX2/FMA) | pass | **SIGILL** | pass |
| Haswell (AVX2, FMA) | pass | pass | pass |

| CPU model (arm64) | PostgreSQL | Bitnami's pgvector | pgvector built with `OPTFLAGS=""` |
|---|---|---|---|
| emulator default (all features) | pass | pass | pass |
| Cortex-A53 (ARMv8.0, no FP16) | pass | **SIGILL** | pass |
| Cortex-A72 (ARMv8.0, no FP16) | pass | **SIGILL** | pass |

The last column is Bitnami's own image with only `vector.so` rebuilt from the same source with the
same compiler. Nothing else changed, so the crash is pgvector's build flag.

It fails at the first step. On the Nehalem model, `CREATE EXTENSION vector` alone dies with SIGILL
(tested on `docker.io/bitnami/postgresql:latest`), so the extension cannot even be installed. In a
running server that takes everyone else down too.
A second, idle connection is dropped while the server recovers:

```
LOG:  client backend (PID 52) was terminated by signal 4: Illegal instruction
LOG:  terminating any other active server processes
LOG:  all server processes terminated; reinitializing
```

The image on Docker Hub today is a different build of the same thing.
`docker.io/bitnami/postgresql:latest`, built 2026-10-02 on Photon OS 5 (revision 20, no `apt`),
fails the same two amd64 rows, Nehalem and SandyBridge, and passes Haswell.
`scripts/cpu-compat.sh` layers a static QEMU onto any image and runs as the image's own user, so it
works on that one too.

CPUs without AVX2 are not exotic: Intel chips before Haswell (2013), Celeron, Pentium and Atom
parts in many NAS boxes and mini PCs, and virtual machines whose CPU type hides AVX2.

### BUILD.txt does not list patches

protobuf 34 removed `FieldDescriptor::label()`, and protobuf-c 1.5.2, still its latest release,
calls it in eight files. Built exactly as BUILD.txt says, against protobuf 36.2, protobuf-c stops
with `'const class google::protobuf::FieldDescriptor' has no member named 'label'`. Bitnami's
package nevertheless ships a working `protoc-c` that reports `libprotoc 36.2` and links protobuf
statically, so their build applies a patch that BUILD.txt does not mention. lifeboat applies
[protobuf-c pull request #797](https://github.com/protobuf-c/protobuf-c/pull/797), the fix Alpine's
packager wrote, vendored with its source commit in
`images/postgresql/18/debian-12/patches/`. The lesson: BUILD.txt is most of the recipe, not all of
it, and only a full build proves the rest.

### Smaller things

- **PROJ 6.3.2** is from May 2020. GDAL 3.13 and PostGIS 3.6 still accept it, and lifeboat keeps it
  for parity. It is the first candidate for an upgrade.
- **Sources are not verified.** BUILD.txt fetches every source with plain `curl` and no checksum.
  lifeboat pins a SHA-256 for all 19 archives. For PostgreSQL the pin matches the checksum
  postgresql.org publishes.
- **License files are thin.** Eight of them, including GPL-licensed PostGIS and LGPL-licensed GEOS,
  are one line naming the license, such as `MIT: https://spdx.org/licenses/MIT.html`, instead of
  the license text. lifeboat ships the upstream license texts.
- **The SBOM has errors.** The package's SPDX file (created by `Tool: Blacksmith-6.67.2`, Bitnami's
  builder) tags protobuf with `cpe:2.3:*:golang:protobuf`, the Go library. NVD files C++ protobuf
  CVEs such as CVE-2022-1941 under `google:protobuf-cpp`, so CPE matching misses them. It also
  labels psqlODBC `LGPL-3.0-only`, while its sources say "either version 2 of the License, or (at
  your option) any later version". And Abseil, compiled into `protoc`, is not listed. lifeboat
  writes the same SPDX files at the same paths, with those three fixed.
- **PL/Java ships without a JVM**, so `CREATE EXTENSION pljava` fails in both images with
  `cannot use PL/Java before successfully completing its setup`.
- **wal2json needs to be allowed on 18.6.** PostgreSQL 18.6 only accepts `pgoutput` and
  `test_decoding` as output plugins (`output_plugin_libraries`). This is upstream behavior and the
  same in both images. Add wal2json to that setting to use it.

## 4. Deviations in lifeboat

The ones that change how something is built are marked `Deviation:` in the Dockerfile.

| What | Bitnami | lifeboat | Why |
|---|---|---|---|
| Prebuilt binaries | from `downloads.bitnami.com` | built from upstream source | the point of the project |
| pgvector | `-march=native` | `OPTFLAGS=""` | runs on every CPU of the architecture |
| Source checks | none | SHA-256 per archive | supply chain |
| PostgreSQL source | GitHub archive of the tag | official release tarball | its checksum is published |
| PROJ source | GitHub archive + `autogen.sh` | release tarball | same code, generated `configure` |
| protobuf-c | an unlisted patch | protobuf-c PR #797, vendored | builds against protobuf 36.2 |
| Runtime base | `bitnami/minideb:bookworm` | `debian:bookworm-slim` | no Broadcom-hosted base |
| Licenses | some empty | upstream texts, Abseil added | Abseil is compiled into `protoc` |
| SPDX files | 3 errors (above) | same paths, errors fixed, supplier lifeboat | scanners read them |
| Startup banner | "Welcome to the Bitnami postgresql container" | names lifeboat | not Bitnami's image |

## Reproduce

```bash
# Bitnami's recipe, straight from their package
curl -fsSLO https://downloads.bitnami.com/files/stacksmith/postgresql-18.6.0-14-linux-amd64-debian-12.tar.gz
tar -xzf postgresql-18.6.0-14-linux-amd64-debian-12.tar.gz postgresql-18.6.0-linux-amd64-debian-12/BUILD.txt -O

# Build lifeboat and Bitnami's image, then compare them
docker build -f images/postgresql/18/debian-12/Dockerfile -t lifeboat/postgresql:18.6.0 .
scripts/build-reference.sh images/postgresql/18/debian-12 bitnami-reference/postgresql:18.6.0
scripts/parity.sh bitnami-reference/postgresql:18.6.0 lifeboat/postgresql:18.6.0
diff <(scripts/smoke-postgresql.sh bitnami-reference/postgresql:18.6.0) \
     <(scripts/smoke-postgresql.sh lifeboat/postgresql:18.6.0)

# The CPU test, on any Bitnami-layout PostgreSQL image, including docker.io/bitnami/postgresql
scripts/cpu-compat.sh bitnami-reference/postgresql:18.6.0
```
