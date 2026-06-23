# Conventions (skill-local)

스크립트가 강제하지 못하는 **판단**과 최소 스펙만. 전체 규약은 `$LLM_WIKI_PATH/CONVENTIONS.md`, 모순 시 그쪽 우선.

## 무엇을 저장하나 (type 판단)

- `user` 정체성·직무·선호 / `feedback` 작업 방식 교정·확정 / `project` 진행 작업·결정·일정 / `reference` 외부 포인터(URL·MCP·문서). **새 type 금지** — 프로젝트 한정이면 `--project <name>`으로 `projects/<name>/` 하위에.
- **저장 안 함**: 코드·구조·파일 경로·git history·디버깅 레시피·CLAUDE.md 중복. 사용자가 "저장"이라 해도 그런 항목은 "뭐가 surprising했나"를 되물어 그 부분만 저장한다 — 단, 명시적 *분석 문서* 요청은 예외.
- `feedback`/`project` 본문 = 한 문장 결론 + `**Why:**` + `**How to apply:**`. `user`/`reference`는 자유 형식이되 **Why** 한 단락 권장.

## 분석 문서 (명시적 저장 의도일 때만)

트리거는 "분석해줘"가 아니라 "분석해서 저장 / reference에 추가 / `<doc>.md`로 만들어줘". 모호하면 묻는다.

- 경로 `projects/<project>/reference/<doc>.md` (`save.py --type reference --project <project>`).
- 본문에 반드시: 정량 수치·표·핵심 코드 경로(`file:line`)·**Surprising 발견** 단락·권장 탐색 순서.
- **근거 인용**: 외부 지식·라이브러리·플랫폼 동작 추론은 작성 *전* 공식 문서를 찾아 URL 첨부, 없으면 근거 코드 경로 명시. 추측 서술 금지. (vault `feedback/cite_official_docs.md`.)

## HTML 산출물 형태

산출물이 HTML이면 저장 위치가 repo든 vault든 무관하게 형태는 vault 피드백을 **그대로** 따른다 — 여기 재진술하지 않는다. recall로 읽어 적용:

- `feedback/info_first_html_doc.md` — 화이트·단일 컬럼 880px·표/mermaid 중심. hero·다크·그라데이션·펄스·디스플레이 serif·수작업 SVG **금지**.
- `feedback/mermaid_chartjs_quirks.md` — mermaid 11.x / chart.js 4.x 함정.
- `reference/chrome_devtools_mcp.md` — 전달 전 시각 검증(console error 0 + 스크린샷).

## 명명·인덱스

`name`은 영문 snake_case 1-3 단어(파일명과 일치). 인덱스 한 줄은 ~150자 이내, type/프로젝트 섹션별로 의미 클러스터 정렬. 이 모든 건 `save.py`/`lint.py`가 처리하니 손으로 만지지 않는다.
