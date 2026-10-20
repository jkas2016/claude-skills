# Worked example: save without accumulating another rule

사용자가 "PR을 만들 때 검증 결과를 적는 걸 기억해"라고 요청했다.

1. `python3 scripts/recall.py PR 검증`으로 요약을 찾는다.
2. 관련 결과를 `python3 scripts/recall.py --read feedback/pr_workflow.md`로 읽는다. 잘림 표시가 있으면 예산을 늘린다.
3. 동일 주제를 다루는 정본이 있다면 그 노트에 조건을 추가한다. 이름만 비슷한 다른 규칙은 덮지 않는다.
4. `save.py --type feedback --name pr_workflow --desc "PR 검증 규칙" --hook "PR 작성: 실행한 검증과 결과를 기록" --check`로 후보를 확인한다.
5. 검토한 전체 본문을 같은 명령의 stdin으로 주고 `--check`를 빼서 저장한다. `lint.py`로 검증한다.

두 노트를 통합해야 한다면 파일을 직접 삭제하지 않는다. `maintenance.md`의 plan으로 정본 갱신 + 원문 superseded를 한 번에 적용한다. 백업 경로를 결과에 남긴다.

사용자가 "README.md를 만들어줘"라고만 요청했다면 지정된 저장소 파일을 만든다. 그것은 LLM-Wiki 저장 요청이 아니다.
