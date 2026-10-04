#!/usr/bin/env bash
# Runs pgvector's SQL functions on emulated older CPUs to catch binaries built with -march=native.
#   amd64: Nehalem (no AVX), SandyBridge (AVX, no AVX2/FMA) and Haswell (AVX2 and FMA, no
#          AVX-512). QEMU never emulates AVX-512.
#   arm64: Cortex-A53 and Cortex-A72 (ARMv8.0 without FP16, as in Raspberry Pi 3 and 4).
# A portable build passes every row; the postgres row proves the server itself runs on that CPU.
# Works on any Bitnami-layout PostgreSQL image (Debian or Photon): it layers a static QEMU on top
# and runs as the image's own user, faking the passwd entry with nss_wrapper like the entrypoint.
# Usage: scripts/cpu-compat.sh IMAGE
set -euo pipefail
export MSYS_NO_PATHCONV=1

image="$1"
arch="$(docker image inspect -f '{{.Architecture}}' "$image")"
case "$arch" in
  amd64) qemu=qemu-x86_64-static cpus="Nehalem SandyBridge Haswell" ;;
  arm64) qemu=qemu-aarch64-static cpus="cortex-a53 cortex-a72" ;;
  *) echo "cpu-compat: unsupported architecture $arch" >&2; exit 1 ;;
esac

tag="lifeboat-cpu-compat:$$"
trap 'docker rmi -f "$tag" >/dev/null 2>&1 || true' EXIT
docker build -q --platform "linux/$arch" -t "$tag" - >/dev/null <<EOF
FROM debian:bookworm-slim AS qemu
RUN apt-get -o Acquire::Retries=5 update \
 && apt-get -o Acquire::Retries=5 install -y --no-install-recommends qemu-user-static \
 && rm -rf /var/lib/apt/lists/*
FROM $image
COPY --from=qemu /usr/bin/$qemu /usr/local/bin/qemu
EOF

docker run --rm -i --platform "linux/$arch" -e CPUS="$cpus" --entrypoint bash "$tag" -s <<'EOS'
set -uo pipefail
pg_bin=/opt/bitnami/postgresql/bin
data="$(mktemp -d)"
printf 'cpucompat:x:%s:0::%s:/bin/sh\n' "$(id -u)" "$data" > /tmp/cpu-compat.passwd
printf 'root:x:0:\n' > /tmp/cpu-compat.group
export LD_PRELOAD="${NSS_WRAPPER_LIB:-/opt/bitnami/common/lib/libnss_wrapper.so}" \
       NSS_WRAPPER_PASSWD=/tmp/cpu-compat.passwd NSS_WRAPPER_GROUP=/tmp/cpu-compat.group
"$pg_bin/initdb" -D "$data" -U postgres --auth=trust >/dev/null || { echo "FAIL  initdb"; exit 1; }

baseline="SELECT 'ok'::text AS baseline;"
pgvector="CREATE EXTENSION IF NOT EXISTS vector;
SELECT ('[1,2,3]'::vector <-> '[4,5,6]')::numeric(10,4) AS l2;
SELECT cosine_distance('[1,2,3]'::vector, '[3,2,1]')::numeric(10,4) AS cosine;
SELECT l2_normalize('[3,4]'::vector) AS normalized;
SELECT ('[1,2,3]'::halfvec <-> '[4,5,6]'::halfvec)::numeric(10,4) AS l2_half;
DROP TABLE IF EXISTS cc_items;
CREATE TABLE cc_items (id int, e vector(3));
INSERT INTO cc_items SELECT g, ARRAY[g, g % 7, g % 3]::vector FROM generate_series(1, 300) g;
CREATE INDEX ON cc_items USING hnsw (e vector_l2_ops);
CREATE INDEX ON cc_items USING ivfflat (e vector_l2_ops) WITH (lists = 4);
SELECT 'built' AS indexes;"

failed=0
check() { # check CPU NAME SQL EXPECTED...
  local cpu="$1" name="$2" sql="$3" out rc missing="" runner=()
  shift 3
  [[ "$cpu" == native ]] || runner=(qemu -cpu "$cpu")
  out="$(printf '%s\n' "$sql" | "${runner[@]}" "$pg_bin/postgres" --single -D "$data" postgres 2>&1)"
  rc=$?
  for expected in "$@"; do grep -qF "$expected" <<<"$out" || missing="$expected"; done
  if [[ $rc -eq 0 && -z "$missing" ]]; then
    printf 'PASS  %-11s %s\n' "$cpu" "$name"
  else
    failed=1
    printf 'FAIL  %-11s %s  exit=%s  %s\n' "$cpu" "$name" "$rc" \
      "$(grep -m1 -oE 'uncaught target signal [0-9]+ \([^)]*\)' <<<"$out" || grep -m1 -oE 'ERROR: .*' <<<"$out" \
         || echo "missing: $missing")"
  fi
}
for cpu in native $CPUS; do
  check "$cpu" postgres "$baseline" 'baseline = "ok"'
  check "$cpu" pgvector "$pgvector" 'normalized = "[0.6,0.8]"' 'l2_half = "5.1962"' 'indexes = "built"'
done
exit "$failed"
EOS
