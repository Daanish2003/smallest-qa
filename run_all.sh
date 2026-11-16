#!/usr/bin/env bash
# Re-run the whole QA suite, or selected steps:  ./run_all.sh            (all)
#                                                ./run_all.sh 3 4 7      (only those steps)
# Total: ~85 API calls, ~8 min, a few cents of credit. Never more than 5 requests in flight.
cd "$(dirname "$0")"
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(0 1 2 3 4 5 7)
for s in "${steps[@]}"; do
  echo; echo "================ STEP $s  ($(TZ=Asia/Kolkata date '+%F %T IST')) ================"
  case $s in
    0) ./step0_noauth.sh ;;
    1) ./step1_tts.sh; ./step1_stt.sh ;;
    2) ./step2_tts_baseline.sh ;;
    3) ./step3_tts_errors.sh ;;
    4) ./step4_concurrency.sh; ./step4b_concurrency5.sh ;;
    5) ./step5_tts_ws.sh ;;
    7) ./step7_stt_ws.sh ;;
    *) echo "unknown step $s (valid: 0 1 2 3 4 5 7)";;
  esac
done
python3 view_evidence.py
echo; echo "Readable summary: EVIDENCE.md   ·   raw: evidence/log.tsv (REST), evidence/ws.log (WebSocket), evidence/<label>.{hdr,body}"
