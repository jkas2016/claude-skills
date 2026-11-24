#!/usr/bin/env bash
# colima default VM 의 docker 미사용 리소스를 지우고 sync+fstrim 으로 Mac 디스크에 반환한다.
# 기본은 계획만 출력한다. --volumes 를 주면 미연결 볼륨도 대상에 넣는다.
# 사용법: docker-reclaim.sh [--volumes] [--apply]
set -uo pipefail
APPLY=0 VOLUMES=0
for a in "$@"; do
  case $a in
    --apply) APPLY=1 ;;
    --volumes) VOLUMES=1 ;;
    *) echo "usage: docker-reclaim.sh [--volumes] [--apply]" >&2; exit 2 ;;
  esac
done

DISK=$HOME/.colima/_lima/_disks/colima    # default 프로필의 데이터 디스크
docker info >/dev/null 2>&1 || { echo "docker 데몬 응답 없음 (colima status 확인)" >&2; exit 1; }

free_gib() { df -g /System/Volumes/Data | tail -1 | awk '{print $4}'; }
disk_size() { du -sh "$DISK" 2>/dev/null | cut -f1; }

if (( ! APPLY )); then
  echo "## 사용 중 이미지 (남는다)"
  docker ps -a --format '{{.Image}}' | sort -u
  echo; echo "## 정지 컨테이너 (삭제)"
  docker ps -a --filter status=exited --filter status=created --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
  echo; echo "## docker system df"
  docker system df
  if (( VOLUMES )); then
    echo; echo "## 미연결 볼륨 (삭제, 복구 불가) — 정지 컨테이너 삭제 후에는 그 컨테이너 볼륨도 여기에 포함된다"
    docker system df -v | sed -n '/Local Volumes space usage/,/Build cache usage/p' | awk 'NR<=3 || $2=="0"'
  fi
  echo; echo "colima 디스크=$(disk_size) free=$(free_gib)GiB"
  echo "실행하려면 같은 인자에 --apply 를 붙인다."
  exit 0
fi

before_free=$(free_gib) before_disk=$(disk_size)
set -x
docker container prune -f
docker image prune -a -f
docker builder prune -a -f
(( VOLUMES )) && docker volume prune -a -f
set +x
# sync 없이 trim 하면 아직 디스크에 반영되지 않은 삭제분이 빠져 거의 반환되지 않는다
colima ssh -- sh -c 'sync; sleep 5; sudo fstrim -av'
sleep 3   # 호스트 쪽 sparse 파일 크기 반영 대기
echo "colima 디스크 $before_disk → $(disk_size), free ${before_free}GiB → $(free_gib)GiB"
docker ps --format '{{.Names}}\t{{.Status}}'
