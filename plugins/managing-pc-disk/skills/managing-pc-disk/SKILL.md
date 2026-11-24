---
name: managing-pc-disk
description: Manually inspect and reclaim macOS disk space from old logs, Docker and Colima, developer caches, and locally configured job snapshots.
disable-model-invocation: true
---

# PC 전체 디스크 관리

Git 이력·서브모듈·워크트리는 정리 대상에서 제외한다.

## 로컬 설정

Python 3을 사용한다. 설정 파일은 `~/.config/managing-pc-disk/config.json`에 둔다. `XDG_CONFIG_HOME`이 지정되면 그 디렉터리를 기준으로 읽는다. 파일이 없으면 기본 macOS 항목만 점검한다.

```json
{
  "log_dirs": ["~/example/logs"],
  "protected_dirs": ["~/example/cache"],
  "job_state_dirs": ["~/example/job-state"],
  "workspace_dirs": ["~/example"],
  "workspace_note": "저장소 정리는 별도로 진행"
}
```

`log_dirs`는 점검과 정리 양쪽에 추가된다. `protected_dirs`와 `workspace_dirs`는 용량만 보고한다. `job_state_dirs` 아래의 `*/state/jobs`는 개별 승인 후 수동으로 정리한다.

## 작업 흐름
이 체크리스트를 복사해 진행한다.

```
- [ ] 1. 점검: scripts/check.sh 실행 (백그라운드, 수 분 걸림)
- [ ] 2. 후보를 등급별 표로 보고하고 승인 받기
- [ ] 3. 승인된 항목만 dry-run → --apply
- [ ] 4. scripts/check.sh 재실행, 전후 free 용량 보고
```

**1. 점검** — 읽기 전용. 아무것도 지우지 않는다.
```bash
bash "${CLAUDE_SKILL_DIR}/scripts/check.sh"
```

**2. 등급** — 표의 등급을 넘어서 처리하지 않는다.

| 등급 | 대상 | 처리 |
|---|---|---|
| A. 한 번 승인으로 수행 | 이번 달 1일 이전 로그 | `scripts/clean-logs.sh` |
| A. 한 번 승인으로 수행 | docker 미사용 이미지·build cache·정지 컨테이너 | `scripts/docker-reclaim.sh` |
| B. 내용 보고 후 개별 승인 | docker 미연결 볼륨 | `scripts/docker-reclaim.sh --volumes` (아래 "볼륨" 확인 먼저) |
| B. 내용 보고 후 개별 승인 | 정지된 colima 프로필 | 아래 "colima 프로필" |
| B. 내용 보고 후 개별 승인 | 로컬 설정의 작업 스냅샷 | 아래 "작업 스냅샷" |
| C. 목록만 보고 | 개발 캐시(uv, JetBrains, npm, huggingface, Chrome, puppeteer, playwright, Homebrew, codex-runtimes) | 사용자가 지목한 것만 해당 도구의 정리 명령으로 지운다 |
| D. 손대지 않음 | colima `default` 프로필(정지·삭제 금지), Unity `Library`(재임포트 수 시간), Claude 앱 `vm_bundles` | 보고만 한다 |

**3. 실행** — 스크립트는 인자 없이 실행하면 계획만 출력한다. 출력을 보고한 뒤 같은 명령에 `--apply` 를 붙인다.
```bash
S="${CLAUDE_SKILL_DIR}/scripts"
bash "$S/clean-logs.sh" [--apply]
bash "$S/docker-reclaim.sh" [--volumes] [--apply]
```

## 볼륨
`--volumes` 전에 실행 중인 DB 컨테이너가 데이터를 어디에 두는지 확인한다.
```bash
docker ps --format '{{.Names}}' | xargs -n1 docker inspect -f '{{.Name}} {{range .Mounts}}{{.Type}}:{{.Name}}{{.Source}}->{{.Destination}} {{end}}'
```
실행 중 컨테이너가 쓰는 볼륨은 prune 되지 않는다. 지워지는 것은 연결된 컨테이너가 없는 볼륨 전체(옛 테스트 DB 데이터 포함)이며 복구할 수 없다. `docker-reclaim.sh` dry-run 이 그 목록과 크기를 보여 준다.

## colima 프로필
`colima list` 에서 **Stopped** 이고 `default` 가 아닌 프로필만 대상이다. 그 VM 안의 이미지·볼륨도 함께 사라진다는 점을 보고하고 승인 받는다.
```bash
colima list
colima delete --force <프로필>
ls ~/.colima/_lima/_disks/        # 삭제한 프로필 디스크가 없어야 한다
```

## 작업 스냅샷

1. 설정에 지정된 상태 디렉터리마다 `lsof +D "<상태 디렉터리>"`로 열린 파일을 확인한다. 열린 파일이 있으면 정리하지 않는다.
2. 각 `jobs/` 아래 스냅샷 개수·크기·최근 수정일을 보고하고 삭제 대상 또는 보존 기간을 승인받는다.
3. 승인 범위에 해당하는 `jobs/` 바로 아래의 스냅샷 디렉터리만 지운다. 상위 상태 파일과 백업은 보존한다.

## 알려진 함정
- **docker 로 지운 용량은 Mac 디스크로 바로 돌아오지 않는다.** colima VM 디스크 파일은 줄지 않으므로 `sync` 후 `fstrim` 이 필요하다. `sync` 없이 trim 하면 거의 반환되지 않는다. `docker-reclaim.sh --apply` 가 처리한다.
- `docker image prune` 이 표시하는 회수량은 레이어 공유 때문에 실제보다 작다. 판단은 `~/.colima/_lima/_disks/colima` 크기와 `df` 로 한다.
- 정지 컨테이너를 지우면 그 컨테이너의 볼륨이 미연결 볼륨으로 바뀐다. 그래서 볼륨 단계는 컨테이너 정리 뒤에 다시 판단한다.
