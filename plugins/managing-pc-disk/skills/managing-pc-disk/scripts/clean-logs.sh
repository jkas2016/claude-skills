#!/usr/bin/env bash
# 이번 달 1일 이전에 수정된 로그 파일을 지운다. 기본은 계획만 출력한다.
# 사용법: clean-logs.sh [--apply]
set -uo pipefail
APPLY=0
[[ ${1-} == --apply ]] && APPLY=1
[[ $# -gt 1 || ( $# -eq 1 && $APPLY -eq 0 ) ]] && { echo "usage: clean-logs.sh [--apply]" >&2; exit 2; }

MONTH_START=$(date +%Y-%m-01)           # 이번 달 로그는 디버깅에 쓰일 수 있어 보존한다
CONFIG_READER="$(dirname "$0")/read-config.py"
LOG_DIRS=("$HOME/Library/Logs/JetBrains" "$HOME/Library/Logs/com.openai.codex")
extra_logs=$(python3 "$CONFIG_READER" log_dirs) || exit 1
while IFS= read -r directory; do
  [[ -n $directory ]] && LOG_DIRS+=("$directory")
done <<< "$extra_logs"

for d in "${LOG_DIRS[@]}"; do
  [[ -d $d ]] || { echo "skip (없음): $d"; continue; }
  before=$(du -sh "$d" | cut -f1)
  n=$(/usr/bin/find "$d" -type f ! -newermt "$MONTH_START" | wc -l | tr -d ' ')
  old=$(/usr/bin/find "$d" -type f ! -newermt "$MONTH_START" -print0 | xargs -0 du -ck 2>/dev/null | tail -1 | awk '{printf "%.1fG", $1/1048576}')
  if (( ! APPLY )); then
    echo "[plan] $d  total=$before  삭제 대상 ${n}개 ${old:-0G} (수정일 < $MONTH_START)"
    continue
  fi
  # 열려 있는 파일은 건너뛴다(실행 중인 서버가 쓰는 로그)
  open=$(lsof +D "$d" 2>/dev/null | awk 'NR>1{print $9}' | sort -u)
  /usr/bin/find "$d" -type f ! -newermt "$MONTH_START" -print0 |
    while IFS= read -r -d '' f; do
      grep -qxF "$f" <<<"$open" && { echo "skip (열림): $f"; continue; }
      rm -f "$f"
    done
  /usr/bin/find "$d" -mindepth 1 -type d -empty -delete
  echo "[done] $d  $before → $(du -sh "$d" | cut -f1)"
done
(( APPLY )) || echo "실행하려면 --apply 를 붙인다."
