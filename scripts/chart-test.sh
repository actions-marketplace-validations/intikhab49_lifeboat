#!/usr/bin/env bash
# Installs Bitnami's own PostgreSQL Helm chart with a Bitnami-layout image swapped in, in
# replication mode, and checks that the primary takes writes and the read replica streams them.
# Needs a kind cluster, helm and kubectl.
# Usage: scripts/chart-test.sh IMAGE [KIND_CLUSTER]
set -euo pipefail

image="$1" cluster="${2:-kind}"
chart_version="${CHART_VERSION:-18.12.4}"
repository="${image%:*}" tag="${image##*:}"

kind load docker-image "$image" --name "$cluster"
helm install db oci://registry-1.docker.io/bitnamicharts/postgresql --version "$chart_version" \
  --set image.registry=docker.io --set image.repository="$repository" --set image.tag="$tag" \
  --set image.pullPolicy=Never --set global.security.allowInsecureImages=true \
  --set architecture=replication --set auth.postgresPassword=chartpw --set auth.replicationPassword=replpw \
  --wait --timeout 10m

sql() { kubectl exec "$1" -c postgresql -- env PGPASSWORD=chartpw psql -h 127.0.0.1 -U postgres -XtAq -c "$2"; }
sql db-postgresql-primary-0 "create table chart_check (v text); insert into chart_check values ('replicated')"
replicated=""
for _ in $(seq 1 30); do
  replicated="$(sql db-postgresql-read-0 'select v from chart_check' 2>/dev/null || true)"
  [[ "$replicated" == replicated ]] && break
  sleep 2
done

echo "chart: bitnamicharts/postgresql $chart_version, image $image"
echo "primary: $(sql db-postgresql-primary-0 'show server_version')"
echo "replica in recovery: $(sql db-postgresql-read-0 'select pg_is_in_recovery()')"
echo "replicated row: ${replicated:-none}"
[[ "$replicated" == replicated ]]
