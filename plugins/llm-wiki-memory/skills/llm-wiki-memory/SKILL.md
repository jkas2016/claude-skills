---
name: llm-wiki-memory
description: Use when saving, updating, recalling, consolidating, archiving, or removing agent memory, or when the user explicitly requests persistence in the shared Obsidian LLM-Wiki. Ordinary repository files and generic document creation do not request memory persistence.
---

# LLM Wiki Memory

메모리는 `$LLM_WIKI_PATH`에 둔다. 미설정/없음이면 알린다. 아래 스크립트 경로는 이 스킬 디렉터리 기준이다. 일반 파일 저장·코드 분석 요청을 메모리 저장으로 확대하지 않는다.

## 회상

기억이 필요한 작업과 저장 전에 관련 **주제·산출물 형태**로 검색한다. hook 요약은 전체 기억이 아니다.

```bash
python3 scripts/recall.py 키워드 --project 프로젝트
python3 scripts/recall.py --read feedback/example.md
```

검색은 활성 노트 요약 최대 8개·8192 bytes. `--project`는 해당 프로젝트와 전역만; 생략하면 모든 프로젝트를 검색한다. 생략 표시가 있거나 관련 기억을 못 찾으면 키워드·범위를 바꾸고 `--limit`/`--max-bytes`를 늘린다. 원문도 기본 예산이 있으므로 잘린 원문을 완독했다고 하지 않는다. `--include-inactive`로 보관/대체된 기억도 검색한다. 실제 파일·버전·현재 사실은 적용 전에 확인한다.

## 저장

먼저 `references/conventions.md`와 필요한 vault 규약을 읽는다. 같은 주제는 안정적인 `--key`로 기존 정본에 갱신한다. 사건마다 새 파일을 만들지 않는다. 유사 후보는 아래와 같이 **쓰기 없이** 조회할 수 있다.

```bash
python3 scripts/save.py --type feedback --name example --key example --desc "한 줄 요약" --tags "a,b" --hook "적용 조건과 규칙" --check
# 후보 원문 검토 후 같은 인자로 --check를 빼고 본문을 stdin에 전달
python3 scripts/lint.py
```

`save.py`는 같은 key를 기존 파일로 라우팅하고, 관련 후보가 있으면 신규 생성을 거부한다. 별개 주제임을 확인한 경우만 `--distinct-reason`을 쓴다. 저장 후 `consolidation_due=True`면 아래 정리를 수행한다. `CONSOLIDATION_REQUIRED`를 우회해 파일을 직접 추가하지 않는다.

## 정리: 별도 요청을 기다리며 계속 누적하지 않는다

명시적 정리 요청, 저장 후 due 상태, hook의 정리 안내가 있으면 `references/consolidation.md`를 읽고 **끝까지 실행**한다.

```bash
python3 scripts/consolidate.py
```

전체 inventory를 scope별로 검토해 keep/update/merge/drop 계획을 만든다. 의미·예외·검증 근거를 판단하는 것은 현재 에이전트의 역할이다. CLI가 의미 중복을 자동 판정했다고 가정하지 않는다. 처음에는 전체 원문을 읽고, 이후에는 변경 원문과 관련 정본을 검토한다.

계획을 dry-run한 뒤 승인된 범위에서 적용한다. **merge/drop은 원문 파일을 제거하고 MEMORY.md를 활성 정본에서 다시 만든다.** `superseded` 표시만 하고 파일/인덱스를 남기는 것으로 정리를 끝내지 않는다. 나이만으로 삭제하지 않으며 서로 다른 예외는 보존한다. 참조가 남거나 원본이 바뀌면 중단·재검토한다.

`lint.py`, 실제 파일/인덱스 개수, 무관한 원문 hash, 복구 dry-run을 확인한 뒤 결과를 보고한다. 백업은 최근 20개 정상 완료 bundle만 유지한다. hook에서 직접 지식 삭제·LLM 호출은 실행하지 않는다.

hook 설치·출력 예산 → `references/maintenance.md`. 정본 통합·퇴역·재생성·복구 정책 → `references/consolidation.md`.
