#!/usr/bin/env bash
# Usage: ./probe.sh <label> <curl args...>
# Runs one curl, logs IST time, status, latency, request-id, Retry-After and body snippet
# to evidence/log.tsv; full headers/body go to evidence/<label>.{hdr,body}
set -u
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
mkdir -p evidence
label=$1; shift
ts=$(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST')
out=$(curl -s -D "evidence/$label.hdr" -o "evidence/$label.body" \
  -w '%{http_code}\t%{time_starttransfer}\t%{time_total}\t%{size_download}' "$@")
rid=$(grep -i -m1 -E '^x-request-id|^request-id|^x-amzn-requestid|^cf-ray' "evidence/$label.hdr" | tr -d '\r' | cut -d' ' -f2-)
ra=$(grep -i -m1 '^retry-after' "evidence/$label.hdr" | tr -d '\r' | cut -d' ' -f2-)
ctype=$(grep -i -m1 '^content-type' "evidence/$label.hdr" | tr -d '\r' | cut -d' ' -f2-)
if [[ "$ctype" == *json* || "$ctype" == *text* ]]; then body=$(head -c 200 "evidence/$label.body" | tr '\n\t' '  '); else body="<$ctype>"; fi
printf '%s\t%s\t%s\trid=%s\tretry-after=%s\t%s\n' "$ts" "$label" "$out" "${rid:-none}" "${ra:-none}" "$body" | tee -a evidence/log.tsv
