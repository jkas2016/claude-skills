---
name: llm-wiki-memory
description: Use whenever auto-memory should be saved/updated/removed/recalled, OR when the user explicitly asks to persist a code/architecture analysis to the shared Obsidian vault. Routes everything to $LLM_WIKI_PATH so every machine sees the same notes. Trigger on "기억해", "저장해", "잊어버려", "메모리에 추가", or analysis-save phrases like "분석해서 저장해", "정리해서 저장", "문서로 만들어줘", "<프로젝트>/reference에 추가해줘" — even if the user does not say "memory".
---

# LLM Wiki Memory

모든 메모리는 `$LLM_WIKI_PATH`(Obsidian vault)에 둔다. 시스템 프롬프트 기본 경로는 안 쓴다. 미설정/없음이면 멈추고 알린다. (스크립트 경로는 이 스킬 디렉터리 기준.)

## 만들기 전에: recall ← 이 스킬이 제일 자주 깨지는 곳

저장·생산·추천을 **하기 직전** 인덱스를 펴고 걸리는 메모리를 적용한다. 발동 조건은 "사용자가 과거를 언급할 때"가 아니라 **"내가 산출물을 만들 때"** — 산출물의 *형태*(HTML·PR·다이어그램…)에 걸린 피드백은 사용자가 말 안 해도 찾아 적용한다. SessionStart hook은 없을 수 있으니 의존하지 않는다.

```
python scripts/recall.py [키워드...]   # 인덱스 + 매칭 노트 본문. 무엇이든 만들기 전 먼저 실행.
```

쓰기 전 verify: 메모리가 명명한 파일·함수는 실제 존재 확인, stale면 그 자리서 고친다.

## 저장

무엇을 저장/안 저장하나, type 판단, 본문 구조, 분석 문서 규약 → `references/conventions.md`. frontmatter 7필드·날짜·인덱스 포인터는 손으로 쓰지 말고 스크립트가 만든다(LLM은 오늘 날짜를 모른다 — 스크립트가 시스템 시계로 채운다):

```
python scripts/save.py --type feedback --name x --desc "..." \
  --tags "a,b" --alias "별명" --hook "인덱스 한 줄" [--project name] < body.md
python scripts/lint.py     # 7필드·인덱스↔파일·dead link 검사. 편집/삭제 후 실행.
```

삭제: 파일 지우고 `lint.py`가 가리키는 끊긴 인덱스 줄을 제거. 흐름 예시 → `references/worked-example.md`.
