# Conventions (skill-local)

스크립트가 강제하지 못하는 **판단**과 최소 스펙만. vault의 `$LLM_WIKI_PATH/CONVENTIONS.md`도 확인한다. 사용자 지시를 우선하며, 기존 규약이 즉시 삭제를 요구하면 이번 유지관리의 보관·복구 정책과 충돌함을 알리고 승인 범위에서 처리한다.

## 무엇을 저장하나 (type 판단)

- `user` 정체성·직무·선호 / `feedback` 작업 방식 교정·확정 / `project` 진행 작업·결정·일정 / `reference` 외부 포인터(URL·MCP·문서). **새 type 금지** — 프로젝트 한정이면 `--project <name>`으로 `projects/<name>/` 하위에.
- **저장 안 함**: 코드·구조·파일 경로·git history·디버깅 레시피·CLAUDE.md 중복. 일반 작업에서는 이런 내용을 자동 메모리로 축적하지 않는다. 사용자가 명시적으로 Obsidian 분석 문서 저장을 요청했다면 그 범위를 따른다.
- `feedback`/`project` 본문 = 한 문장 결론 + `**Why:**` + `**How to apply:**`. `user`/`reference`는 자유 형식이되 **Why** 한 단락 권장.

## 분석 문서 (명시적 저장 의도일 때만)

분석 문서 저장은 LLM-Wiki/Obsidian 목적지가 명시되거나 기존 대화에서 확정된 경우다. 일반적인 "분석해서 저장"이나 "`<doc>.md`로 만들어줘"는 지정된 작업 폴더에 저장하며 메모리 저장으로 확대하지 않는다.

- 경로 `projects/<project>/reference/<doc>.md` (`save.py --type reference --project <project>`).
- 본문에 반드시: 정량 수치·표·핵심 코드 경로(`file:line`)·**Surprising 발견** 단락·권장 탐색 순서.
- **근거 인용**: 외부 지식·라이브러리·플랫폼 동작 추론은 작성 *전* 공식 문서를 찾아 URL 첨부, 없으면 근거 코드 경로 명시. 추측 서술 금지. (vault `feedback/cite_official_docs.md`.)

## HTML 산출물 형태

산출물이 HTML이면 저장 위치가 repo든 vault든 무관하게 형태는 vault 피드백을 **그대로** 따른다 — 여기 재진술하지 않는다. recall로 읽어 적용:

- `feedback/info_first_html_doc.md` — 화이트·단일 컬럼 880px·표/mermaid 중심. hero·다크·그라데이션·펄스·디스플레이 serif·수작업 SVG **금지**.
- `feedback/mermaid_chartjs_quirks.md` — mermaid 11.x / chart.js 4.x 함정.
- `reference/chrome_devtools_mcp.md` — 전달 전 시각 검증(console error 0 + 스크린샷).

## 명명·인덱스

`name`은 영문 snake_case 1-3 단어(파일명과 일치). 인덱스 한 줄은 ~150자 이내, type/프로젝트 섹션별로 의미 클러스터 정렬. 포인터 작성은 `save.py`, 정합성은 `lint.py`가 처리한다. 의미 클러스터링은 에이전트가 판단한다. 인덱스 전체를 hook으로 주입하지 않는다. 0.3부터 인덱스는 정본에서 생성하는 핵심 목록·scope 탐색 지도이며, 모든 파일의 포인터를 누적하지 않는다.

## 수명주기

기존 7필드는 그대로 유지한다. 선택적 status/pinned/superseded_by와 상태 편집은 `maintenance.md`, 실제 통합·파일 제거·인덱스 재구성은 `consolidation.md`를 따른다. 저장 전에 기존 정본을 검색하고, 단순 사건 기록을 독립 규칙으로 계속 추가하지 않는다.
