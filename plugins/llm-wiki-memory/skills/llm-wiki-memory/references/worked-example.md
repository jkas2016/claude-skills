# Worked example: save without accumulating another rule

사용자가 "PR을 만들 때 검증 결과를 적는 걸 기억해"라고 요청했다.

1. `python3 scripts/recall.py PR 검증`으로 요약을 찾는다.
2. 관련 결과를 `python3 scripts/recall.py --read feedback/pr_workflow.md`로 읽는다. 잘림 표시가 있으면 예산을 늘린다.
3. 동일 주제를 다루는 정본이 있다면 그 노트에 조건을 추가한다. 이름만 비슷한 다른 규칙은 덮지 않는다.
4. `save.py --type feedback --name pr_workflow --key pr-workflow --desc "PR 검증 규칙" --hook "PR 작성: 실행한 검증과 결과를 기록" --check`로 후보를 확인한다.
5. 검토한 전체 본문을 같은 명령의 stdin으로 주고 `--check`를 빼서 저장한다. `lint.py`로 검증한다.

저장 결과가 `consolidation_due=True`이면 완료로 끝내지 않는다. `consolidate.py`로 전체 inventory를 받고 `consolidation.md`의 절차로 검토한다.

예를 들어 PR 검증 규칙과 PR 체크리스트가 중복이면, 두 원문에서 유효한 조건·예외를 모아 기존 정본을 target으로 하는 merge를 계획한다. 완료된 일회성 PR 계획은 완료 근거를 확인해 drop하고, 독립적인 현재 규칙은 keep한다. 모든 원본이 한 번씩 분류되어야 한다.

`consolidate.py --plan /tmp/plan.json`으로 삭제 목록·갱신 본문·인덱스를 확인한 뒤 `--apply`한다. 이때 중복 원문 파일은 실제 삭제되고, 남은 참조는 정본으로 바뀌며, MEMORY.md는 짧은 탐색 지도로 재생성된다. `lint.py`와 전후 파일 수를 확인하고 실제 병합/삭제 수 및 복구 백업 경로를 보고한다. superseded 표시만 하고 정리했다고 하지 않는다.

사용자가 "README.md를 만들어줘"라고만 요청했다면 지정된 저장소 파일을 만든다. 그것은 LLM-Wiki 저장 요청이 아니다.
