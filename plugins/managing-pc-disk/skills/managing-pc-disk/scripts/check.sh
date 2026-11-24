#!/usr/bin/env bash
# 읽기 전용 PC 디스크 점검. 아무것도 바꾸지 않는다.
# 사용법: check.sh
set -uo pipefail
[[ $# -eq 0 ]] || { echo "usage: check.sh" >&2; exit 2; }

MONTH_START=$(date +%Y-%m-01)           # 로그 보존 기준: 이번 달 1일
CONFIG_READER="$(dirname "$0")/read-config.py"
LOG_DIRS=("$HOME/Library/Logs/JetBrains" "$HOME/Library/Logs/com.openai.codex")
extra_logs=$(python3 "$CONFIG_READER" log_dirs) || exit 1
while IFS= read -r directory; do
  [[ -n $directory ]] && LOG_DIRS+=("$directory")
done <<< "$extra_logs"
CACHE_DIRS=("$HOME/.cache/uv" "$HOME/Library/Caches/JetBrains" "$HOME/.npm" "$HOME/.cache/huggingface"
  "$HOME/Library/Caches/Google" "$HOME/.cache/puppeteer" "$HOME/Library/Caches/ms-playwright"
  "$HOME/Library/Caches/Homebrew" "$HOME/.cache/codex-runtimes")
KEEP_DIRS=("$HOME/Library/Application Support/Claude/vm_bundles")
protected=$(python3 "$CONFIG_READER" protected_dirs) || exit 1
job_roots=$(python3 "$CONFIG_READER" job_state_dirs) || exit 1
workspaces=$(python3 "$CONFIG_READER" workspace_dirs) || exit 1
workspace_note=$(python3 "$CONFIG_READER" workspace_note) || exit 1
while IFS= read -r directory; do
  [[ -n $directory ]] && KEEP_DIRS+=("$directory")
done <<< "$protected"
COLIMA_DISKS=$HOME/.colima/_lima/_disks

size() { [[ -e $1 ]] && du -sh "$1" 2>/dev/null | cut -f1 || echo "-"; }

echo "## 디스크"
df -g /System/Volumes/Data | tail -1 | awk '{print "free=" $4 "GiB used=" $3 "GiB"}'

echo; echo "## [A] 로그: $MONTH_START 이전 파일"
for d in "${LOG_DIRS[@]}"; do
  [[ -d $d ]] || continue
  old=$(/usr/bin/find "$d" -type f ! -newermt "$MONTH_START" -print0 | xargs -0 du -ck 2>/dev/null | tail -1 | awk '{printf "%.1fG", $1/1048576}')
  printf '%-55s total=%-6s old=%s\n' "$d" "$(size "$d")" "${old:-0G}"
done

echo; echo "## [A/B] docker (colima)"
if command -v colima >/dev/null; then
  colima list 2>/dev/null
  echo "-- 호스트 디스크 파일"
  for p in "$COLIMA_DISKS"/*/; do printf '%-50s %s\n' "${p%/}" "$(size "$p")"; done
  if docker info >/dev/null 2>&1; then
    echo "-- docker system df"; docker system df
    vm=$(colima ssh -- df -BG --output=used /var/lib/docker 2>/dev/null | tail -1 | tr -d ' ')
    echo "-- default VM 내부 사용량=${vm:-?} (호스트 디스크 파일보다 훨씬 작으면 sync+fstrim 으로 회수 가능)"
  else
    echo "docker 데몬 응답 없음 — docker 항목 생략"
  fi
else
  echo "colima 없음"
fi

echo; echo "## [B] 작업 스냅샷"
while IFS= read -r state_dir; do
  [[ -d $state_dir ]] || continue
  for j in "$state_dir"/*/state/jobs; do
    [[ -d $j ]] || continue
    n=$(/usr/bin/find "$j" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
    latest=$(stat -f '%Sm' -t '%Y-%m-%d' "$j" 2>/dev/null)
    printf '%-75s size=%-6s jobs=%-4s latest=%s\n' "$j" "$(size "$j")" "$n" "$latest"
  done
  # 작업 상태 디렉터리의 열린 파일을 확인한다.
  users=$(lsof +D "$state_dir" 2>/dev/null | awk 'NR>1{print $2" "$1}' | sort -u)
  [[ -n $users ]] && echo "⚠ 작업 상태 파일을 연 프로세스 있음 — 삭제 금지: $users" || echo "작업 상태 파일을 연 프로세스 없음"
done <<< "$job_roots"

echo; echo "## [C] 개발 캐시 (목록만)"
for d in "${CACHE_DIRS[@]}"; do [[ -e $d ]] && printf '%-55s %s\n' "$d" "$(size "$d")"; done

echo; echo "## [D] 손대지 않음 (참고)"
for d in "${KEEP_DIRS[@]}"; do [[ -e $d ]] && printf '%-75s %s\n' "$d" "$(size "$d")"; done

if [[ -n $workspaces ]]; then
  echo; echo "## 워크스페이스 용량"
  [[ -n $workspace_note ]] && printf '%s\n' "$workspace_note"
  while IFS= read -r directory; do
    printf '%-55s %s\n' "$directory" "$(size "$directory")"
  done <<< "$workspaces"
fi
