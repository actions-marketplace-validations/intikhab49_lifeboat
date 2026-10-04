#!/usr/bin/env bash
# Compares two images section by section (container config plus everything manifest.sh prints)
# and writes a Markdown report of every line that only one side has.
# Usage: scripts/parity.sh REFERENCE_IMAGE CANDIDATE_IMAGE [OUT_DIR]
set -euo pipefail
export LC_ALL=C

reference="$1" candidate="$2" out="${3:-parity-report}"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"

config() {
  docker inspect --format '{{range .Config.Env}}{{println "env" .}}{{end}}{{println "user" .Config.User}}{{println "entrypoint" .Config.Entrypoint}}{{println "cmd" .Config.Cmd}}{{println "workdir" .Config.WorkingDir}}{{range $k, $v := .Config.ExposedPorts}}{{println "port" $k}}{{end}}{{range $k, $v := .Config.Volumes}}{{println "volume" $k}}{{end}}' "$1" | sed '/^$/d' | sort
}

for side in reference candidate; do
  image="${!side}"
  {
    echo "## config"
    config "$image"
    docker run --rm -i -u root --entrypoint bash "$image" -s < "$here/manifest.sh"
  } > "$out/$side.manifest"
  rm -rf "${out:?}/$side" && mkdir -p "$out/$side"
  awk -v dir="$out/$side" '/^## /{file = dir "/" $2; printf "" > file; next} {print > file}' "$out/$side.manifest"
done

{
  echo "# Parity report"
  echo
  echo "- reference: \`$reference\`"
  echo "- candidate: \`$candidate\`"
  echo
  echo "| section | lines (ref / cand) | only in reference | only in candidate |"
  echo "|---|---|---|---|"
  for f in "$out"/reference/*; do
    s="$(basename "$f")"
    touch "$out/candidate/$s"
    sort -o "$out/reference/$s" "$out/reference/$s"
    sort -o "$out/candidate/$s" "$out/candidate/$s"
    echo "| $s | $(wc -l < "$out/reference/$s") / $(wc -l < "$out/candidate/$s") | $(comm -23 "$out/reference/$s" "$out/candidate/$s" | wc -l) | $(comm -13 "$out/reference/$s" "$out/candidate/$s" | wc -l) |"
  done
  for f in "$out"/reference/*; do
    s="$(basename "$f")"
    only_ref="$(comm -23 "$out/reference/$s" "$out/candidate/$s")"
    only_cand="$(comm -13 "$out/reference/$s" "$out/candidate/$s")"
    [[ -z "$only_ref$only_cand" ]] && continue
    echo
    echo "## $s"
    echo
    echo '```diff'
    [[ -n "$only_ref" ]] && sed 's/^/- /' <<<"$only_ref"
    [[ -n "$only_cand" ]] && sed 's/^/+ /' <<<"$only_cand"
    echo '```'
  done
} > "$out/report.md"

echo "wrote $out/report.md"
