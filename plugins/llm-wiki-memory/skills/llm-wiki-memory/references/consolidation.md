# Consolidation: 저장된 기억 자체를 정리하기

0.2의 출력 제한·status 필터는 정리가 아니다. 이 흐름의 결과는 **정본 갱신 + 중복/낡은 파일 제거 + MEMORY.md 재구성**이다. 의미 판단은 이 스킬을 실행하는 호스트 에이전트가 담당하고, CLI는 그 판단의 적용·충돌 검사·복구를 맡는다. 외부 LLM API나 숨은 백그라운드 에이전트를 실행하지 않는다.

## 저장부터 누적 방지

기억의 사건/날짜가 아닌 재사용 가능한 **개념**을 정본으로 삼는다. `save.py --key answer-format` 같은 안정적인 key를 사용한다. 같은 프로젝트·type에서 key가 이미 있으면 `--name`이 달라도 그 정본을 갱신한다. merge된 원문의 key도 정본의 `memory_keys`로 계승한다.

새 파일에 관련 후보가 있으면 `RELATED_MEMORY_EXISTS`로 쓰기를 거부한다. 후보 원문을 읽어 기존 정본에 통합하거나, 정말 별개 조건이면 `--distinct-reason`으로 차이를 명시한다. 빈 설명·날짜를 바꾼 이름을 우회 수단으로 쓰지 않는다. 기존 본문을 확인하고 유효한 예외를 보존한 **전체 갱신 본문**을 stdin으로 준다.

정리 필요 조건은 `.memory-state.json`과 실제 파일로 계산한다:

- 마지막 정리 후 쓰기 10회
- 노트 수가 `max(80, 직전 검토 수 + 10)` 초과
- `MEMORY.md`가 12KiB 초과
- 최초 마이그레이션에서 inactive 노트가 남아 있음

필요 상태에서는 새 파일 저장이 `CONSOLIDATION_REQUIRED`로 중단된다. 정본 갱신은 가능하나 완료로 끝내기 전에 아래 통합 절차를 수행한다. hook도 필요 상태를 안내한다. 시간만 보고 삭제하지 않으며 무단 스케줄도 등록하지 않는다. 평소 저장 전 회상, 저장 후 due 처리, 사용자의 명시적 정리 요청이 이 흐름의 진입점이다.

## 호스트가 수행할 판단 절차

```bash
python3 scripts/consolidate.py > /tmp/memory-packet.json
```

packet에는 현재 파일/index/state 해시, scope별 그룹, 설명/상태/크기와 직전 검토 후 변경 여부가 있다. audit의 장문 후보 몇 개만 읽고 전체 정리했다고 하지 않는다.

1. **전체 scope를 검토한다.** 프로젝트끼리 섞지 않는다. 처음에는 원문을 모두 읽는다. 이후에는 변경된 원문과 그 주제의 기존 정본을 읽고, 변경 없는 기억의 이전 판단을 재사용할 수 있다.
2. **규칙을 추출한다.** 사건 경과·로그·코드 복제에서 지속적으로 쓸 결론, 이유, 적용 조건, 예외, 검증 근거를 분리한다. 코드/문서에 이미 있는 상세는 정본 위치를 가리킨다.
3. **개념별 정본을 고른다.** 같은 의미의 노트는 하나의 기존 노트를 정본으로 정하고 merge한다. 조건/예외가 다르면 구분해서 남긴다. 충돌은 최신 날짜만으로 해결하지 말고 근거를 검증한다.
4. **죽은 기억을 제거한다.** 더 이상 적용되지 않음을 확인한 내용·완료된 일회성 계획·정본으로 완전히 대체된 내용은 drop한다. `reason`과 `evidence`를 적는다. 원문이 계속 필요한 독립 기록이면 keep할 수 있지만, 단순히 삭제가 불안하다는 이유로 매번 보관 문서를 추가하지 않는다.
5. 모든 노트를 keep/update/merge/drop 중 하나로 분류한다. 미해결 모순은 keep 이유로 명시하고 추측으로 합치지 않는다. 전체 검토를 가장한 기계적인 keep 목록을 만들지 않는다.

## 계획 형식

packet의 `snapshot`을 **그대로** 복사한다. 최상위 `actions`는 각 원본을 정확히 한 번 다뤄야 한다. merge의 target과 sources 모두 이 조건에 포함된다.

```json
{
  "snapshot": {"...": "packet에서 복사한 실제 해시"},
  "actions": [
    {
      "op": "merge",
      "target": "feedback/answer_format.md",
      "sources": ["feedback/sql_output.md"],
      "description": "요청한 형식을 보존하고 설명은 뒤에 덧붙인다",
      "body": "결론\n\n**Why:** 근거\n\n**How to apply:** 두 원문의 적용 범위·예외를 모두 보존한 규칙",
      "reason": "동일 원칙이므로 SQL 사례의 예외까지 정본에 통합"
    },
    {"op": "drop", "path": "project/old_plan.md", "reason": "현재 행동에 필요 없는 과거 계획", "evidence": "확인한 완료 근거와 현행 정본 위치"},
    {"op": "keep", "path": "reference/current.md", "reason": "현재도 쓰는 별개 근거"}
  ]
}
```

- update: `path, body, description, reason`. 불필요한 사건 기록을 축약할 때 사용한다.
- merge: 동일 프로젝트/type의 기존 target에 통합하고 sources를 **실제로 삭제**한다. 별도 archived 문서를 만들지 않는다. 대상의 key/pin을 계승한다.
- drop: 해당 파일을 **실제로 삭제**한다. 다른 기억이 참조 중이면 먼저 그 참조를 갱신하는 update를 같은 계획에 넣는다.
- keep: 원문을 보존한다. merge로 참조 대상이 바뀌면 링크만 자동 갱신될 수 있다.

```bash
python3 scripts/consolidate.py --plan /tmp/plan.json
python3 scripts/consolidate.py --plan /tmp/plan.json --apply
python3 scripts/lint.py
```

dry-run의 `deleted`, `rewritten`, `index_preview`, 전후 개수를 검토한다. 사용자에게 이미 승인된 정리 범위면 반복 승인 없이 적용한다. 새 사실/중요한 선택이 불확실하면 그 항목을 유지하고 확인한다.

## 실제 파일·인덱스 처리

- merge는 남은 기억의 Markdown 링크(제목/angle destination 포함), reference-style 링크, HTML href/src, Obsidian wikilink/alias를 정본으로 바꾼다. 애매한 wikilink는 실패시킨다. 섹션 anchor는 보존하므로 정본에서도 해당 섹션을 유지하거나 참조를 함께 고친다.
- root 및 하위 README/MEMORY, HTML 자료처럼 일반 노트가 아닌 문서의 참조는 자동 수정하지 않는다. 삭제 예정 파일을 가리키면 적용을 거부한다. 먼저 해당 문서의 소유 범위에 맞춰 수정한다.
- `MEMORY.md`는 활성 정본의 작은 핵심 목록과 scope별 디렉터리 탐색 지도로 재생성한다. 전체 파일별 포인터를 계속 붙이지 않는다. 전체 검색은 recall이 파일에서 수행한다. 기존 HTML 분석 자료 포인터는 보존한다. 추가 index 문서를 매번 만들지 않는다.
- 생성 인덱스는 8192 bytes 상한이다. 범위가 너무 많아 넘으면 적용을 거부한다. 중요한 범위를 잘라내고 성공했다고 하지 않는다.
- 기존 key는 정본에 계승하며 기기별 pin 유지를 위한 작은 redirect 메타데이터를 state에 남긴다. 옛 경로에 대한 recall --read 호출은 지원하지 않으므로 새 정본 경로를 사용한다. 삭제된 문서 전문은 활성 폴더나 MEMORY.md에 남기지 않는다.

## 복구와 보관 상한

적용 전 전체 snapshot을 검사하고, 파일 생성/갱신/삭제·인덱스·state를 한 백업 bundle로 기록한다. 충돌이면 중단한다. 파일 단위 교체와 로컬 lock을 쓰지만 iCloud의 다른 기기까지 분산 잠금하지는 못한다.

```bash
python3 scripts/maintain.py --restore .memory-backups/<id>.json
python3 scripts/maintain.py --restore .memory-backups/<id>.json --apply
```

0.3에서 생성한 정상 완료 백업은 **최근 20개**만 유지하며 저장/정리 성공 후 오래된 것을 지운다. 따라서 복구 가능 기간은 횟수 기준이며 무기한이 아니다. 기존 0.2 백업과 중단된 prepared bundle은 자동 삭제하지 않는다. 기존 보관본을 무단으로 날리지 않으면서 새 백업의 무한 누적을 막는다.

0.2의 `maintain.py` 상태 변경은 호환용이다. 축적 문제 해결에 `status: superseded` 표시만 사용하지 말고 위 consolidation 경로를 쓴다.

## 검증할 결과

출력 바이트 감소와 별개로, 실제 남은 파일 수·통합/삭제 수·MEMORY.md 항목과 크기를 확인한다. 나머지 원문 hash, 링크 정합성, 복구 dry-run도 확인한다. keep만 정당한 경우 파일 수는 줄지 않을 수 있으며, 이를 병합 성과라고 보고하지 않는다.

## 참고한 구조와 차이

[OpenAI Sandbox Agents의 memory 문서](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)는 추출과 통합을 분리하고 raw memory를 인덱스/요약으로 정리하는 흐름을 설명한다. [Claude Code memory 문서](https://code.claude.com/docs/en/memory)는 짧은 MEMORY.md와 필요할 때 읽는 주제 파일을 구분한다. 여기서는 그 분리를 참고해 자체 관리 흐름을 구현했다. Codex/Claude 내부의 비공개 알고리즘이나 백그라운드 스케줄러를 복제했다고 주장하지 않는다.
