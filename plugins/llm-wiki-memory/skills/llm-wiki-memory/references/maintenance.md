# Memory lifecycle and bounded context

## Context / hook

`MEMORY.md`는 전체 탐색 인덱스다. 컨텍스트 출력만 별도로 줄인다. 기존 7필드 노트는 active이고 자동 pin되지 않는다. 선택 메타데이터:

```yaml
status: active  # active | archived | superseded
pinned: true
superseded_by: feedback/canonical.md  # superseded일 때만; 다른 active 노트를 직접 참조
```

`context.py`는 활성 pinned 전역 노트 + 현재 프로젝트의 활성 노트 요약만 출력한다. 프로젝트 한정 pin은 다른 프로젝트에서 주입하지 않는다. 기본 4096 UTF-8 bytes; 완전한 요약 행 단위로 제한하고 생략을 알린다. 오래된 노트라고 우선순위를 내리지 않는다. pin이 많아도 예산을 넘기지 않으므로 pin 선정 자체를 간결하게 유지한다. 원문을 읽기 전 요약만으로 규칙을 단정하지 않는다.

원본 노트 수정 없이 기기별 JSON으로 pin과 프로젝트를 지정할 수 있다:

```json
{
  "pinned": ["feedback/answer_in_requested_format.md"],
  "projects": {
    "/absolute/workspace/project-a": "project-a"
  }
}
```

매핑은 절대경로 경계 기준이며 중첩 경로는 가장 긴 매핑을 쓴다. 디렉터리 이름으로 프로젝트를 추측하지 않는다. 경로를 매핑하지 않은 워크트리는 전역 pin만 나온다. pin/매핑이 없으면 검색 안내만 주입하므로 기존 사용자는 핵심 전역 규칙을 먼저 선정한다. 설정 경로는 `--config` 또는 `LLM_WIKI_CONFIG`로 전달한다. JSON은 기기 로컬에 두며 repo에 개인 경로를 커밋하지 않는다.

```bash
python3 scripts/context.py --config /path/to/context.json --cwd /workspace/project-a
python3 scripts/install_hook.py --settings ~/.claude/settings.json --config /path/to/context.json
# dry-run에서 명령을 확인한 다음:
python3 scripts/install_hook.py --settings ~/.claude/settings.json --config /path/to/context.json --apply
```

설치기는 현재 Python과 스크립트의 절대경로를 사용한다. 경로 이동·Python 교체 시 다시 실행한다. 저장소에서 설치했다면 그 경로를 유지한다. 전역 스킬 복사나 plugin cache 수정은 하지 않는다.

기존의 **정확히 일치하는 단독 MEMORY.md cat hook** 또는 설치기가 표시한 hook만 교체한다. 모르는 복합 memory 명령은 실패시키고 수동 검토를 요구한다. 다른 hook은 유지하며 설정 원본을 `.llm-wiki-<id>.bak`으로 백업한다. 동일 설정 재실행은 변경하지 않는다. 플러그인은 별도 자동 hook을 등록하지 않아 이 설치기와 이중 주입되지 않는다. 다른 설정 scope에서 별도로 등록한 memory hook도 설치 전에 확인한다. 설정 백업을 복원할 때는 이후에 생긴 무관한 변경을 덮지 않도록 diff를 확인한다.

SessionStart는 stdin JSON의 `cwd`를 제공하며 성공한 hook의 stdout은 컨텍스트에 추가된다. 이 계약은 [Claude Code 공식 hook 문서](https://code.claude.com/docs/en/hooks#sessionstart)를 따른다. `context.py --hook`은 vault 미설정 시 조용히 종료하며 그 밖의 설정 오류는 stderr/비정상 종료로 드러낸다. 기본값은 비동기 hook이 아니다.

## Audit / review cadence

```bash
python3 scripts/audit.py > /tmp/memory-audit.json
```

외부 API·LLM 호출 없이 Markdown 노트만 검사한다. 후보는 동일 범위의 동일 본문, 유사 설명, 장문(기본 6000 bytes), 완료 표현, 갱신 180일 경과다. HTML 분석 문서는 검색·정리 대상이 아니며 인덱스의 HTML 링크만 lint한다. 임계값은 `--help` 참조. 나이는 재검증 신호이고 효용·진실성·폐기 판정이 아니다. URL 도달 여부나 외부 사실의 유효성은 검사하지 않는다.

정리 주기: 저장 전에는 같은 주제의 기존 정본을 조회한다. 사용자가 정기 점검을 요청하면 audit를 실행하고, 후보를 실제로 읽어 처리한다. 무단 스케줄 등록·세션 시작 시 쓰기는 하지 않는다. 자동 반복 감사는 사용자가 별도 요청할 때만 설정한다.

후보 검토:

1. 두 원문을 읽고 적용 범위·예외·충돌을 비교한다. 같은 단어가 많아도 다른 조건의 규칙은 합치지 않는다.
2. 축약은 결론/이유/적용 조건/출처를 남긴다. 여러 원문을 통합하면 정본에 원문 경로를 남긴다. 불명확한 모순은 확인할 때까지 보존한다.
3. 과거 계획에서 현재 유효한 결정만 정본으로 남기고, 과거 원문은 archived 또는 superseded로 표시한다. 파일을 이동/삭제하지 않아 링크가 유지된다.
4. stale 정보는 공식 자료/실제 코드로 검증한다. 사용하지 않았다는 이유나 날짜만으로 폐기하지 않는다.

## Reviewable plan / apply

`audit.py`의 **원본 bytes SHA-256**을 이용해 다음 JSON을 작성한다. 내용이 바뀌면 해시를 무작정 재생성하지 말고 변경을 재검토한다.

```json
{
  "changes": [
    {
      "path": "feedback/canonical.md",
      "sha256": "<audit의 64자리 해시>",
      "reason": "두 규칙의 예외 조건을 보존해 통합",
      "description": "통합 후 검색 요약",
      "body": "한 문장 결론\n\n**Why:** 근거\n\n**How to apply:** 조건·예외\n\n출처: [원문](old.md)"
    },
    {
      "path": "feedback/old.md",
      "sha256": "<audit의 64자리 해시>",
      "reason": "정본으로 대체; 원문은 이력 보존",
      "status": "superseded",
      "superseded_by": "feedback/canonical.md"
    }
  ]
}
```

`body` 변경 시 `description`도 검토·제공해 현재 내용과 검색 요약을 일치시킨다. `description` 변경은 인덱스 요약도 갱신한다. status는 active/archived/superseded; pinned는 boolean이다. 새 정본이 필요하면 save로 먼저 생성하고 lint한 뒤 기존 노트에 대한 계획을 만든다.

```bash
python3 scripts/maintain.py /tmp/plan.json          # dry-run: 전체 사전검증
python3 scripts/maintain.py /tmp/plan.json --apply  # 승인된 범위의 변경 적용
python3 scripts/lint.py
```

모든 변경을 사전검증한다. 누락 원본·잘못된 해시·외부 경로·symlink·중복 작업·잘못된 대체 관계는 쓰기 전에 거부한다. superseded는 active 정본을 직접 참조해야 하므로 self/cycle/chain은 허용하지 않는다. 정본을 보관하려면 그 정본을 참조하던 노트도 같은 계획에서 처리한다.

## Backup / recovery

save와 maintain은 `.memory-backups/<id>.json`에 변경 전후 내용을 기록한다. 백업은 기본 검색에서 제외하며 자동 삭제하지 않는다. 민감한 원문도 들어 있으므로 vault와 같은 접근 범위로 취급한다.

```bash
python3 scripts/maintain.py --restore .memory-backups/<id>.json
python3 scripts/maintain.py --restore .memory-backups/<id>.json --apply
python3 scripts/lint.py
```

복구 전 모든 대상이 백업의 변경 전 또는 후 상태인지 검사한다. 이후 편집이 있으면 전체 사전검증에서 거부한다. save로 새로 생성된 파일은 복구 시 제거된다. 일반 유지관리는 파일을 삭제하지 않는다.

각 파일은 원자적으로 교체하고 로컬 쓰기는 `.memory-lock`으로 직렬화한다. 적용 중 일반 오류는 이미 쓴 파일을 이전 상태로 되돌린다. 프로세스 강제 종료/전원 중단은 일부 적용 상태를 남길 수 있다. **실행 중인 writer가 없는지 확인 후** 남은 lock을 제거하고 출력된/최근 백업으로 복구한다. 복구 도중 중단되었어도 같은 백업으로 재시도할 수 있다.

iCloud의 다른 기기나 Obsidian의 편집까지 잠글 수는 없다. 해시 검사는 충돌을 감지하지만 분산 트랜잭션은 아니다. 같은 노트를 여러 기기에서 동시에 정리하지 않는다. 백업을 직접 편집하지 않는다.
