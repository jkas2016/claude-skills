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

먼저 `references/conventions.md`와 필요한 vault 규약을 읽는다. 같은 주제의 기존 정본을 우선 갱신한다. 유사 후보는 아래와 같이 **쓰기 없이** 조회할 수 있다.

```bash
python3 scripts/save.py --type feedback --name example --desc "한 줄 요약" --tags "a,b" --hook "적용 조건과 규칙" --check
# 후보 원문 검토 후 같은 인자로 --check를 빼고 본문을 stdin에 전달
python3 scripts/lint.py
```

`save.py`는 기존 날짜·선택 메타데이터·비활성 상태를 보존하며 노트와 인덱스를 백업한다. 비활성 기억의 재활성화는 유지관리 계획으로 명시한다.

## 정리

사용자가 정리를 요청하거나 저장 전 검색에서 중복·모순을 발견하면 `references/maintenance.md`를 읽는다. `audit.py`는 읽기 전용 후보 보고서다. 오래됨·유사도만으로 삭제하지 않는다. 정본에 **범위·예외·출처·미해결 모순**을 보존한 뒤 축약/통합/보관안을 만들고 `maintain.py`로 검증·적용한다. 기존 승인 범위 안에서 진행하되 사실이나 중요한 선택이 불명확하면 확인한다. hook에서 지식 정리·LLM 호출·자동 삭제를 실행하지 않는다.

세션 경량화 설정과 hook 교체, 변경 계획·복구 형식 → `references/maintenance.md`.
