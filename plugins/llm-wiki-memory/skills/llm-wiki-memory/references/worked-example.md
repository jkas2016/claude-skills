# Worked example

User: "내가 게임플레이 프로그래머야. UE 5.4 위주로 일해."

## 1. 만들기 전 recall

```
python scripts/recall.py user identity unreal
```

인덱스와 관련 노트를 먼저 확인 — 같은 사실이 이미 있는지, 충돌하는지 판단.

## 2. type 판단

정체성·직무 → `user`. (판단 기준은 `references/conventions.md`.)

## 3. 저장 (frontmatter·날짜·인덱스를 스크립트가 처리)

```
python scripts/save.py --type user --name user_role \
  --desc "게임플레이 프로그래머, UE 5.4 중심 작업" \
  --tags "identity,gamedev,unreal" --alias "게임플레이 프로그래머" \
  --hook "UE 5.4 중심, 게임플레이 프로그래밍이 주영역" <<'EOF'
게임플레이 프로그래머. 주 작업 환경은 Unreal Engine 5.4.

**Why:** 사용자가 직무·도구를 명시적으로 공유.

**How to apply:** Unreal/C++/게임플레이 질문에 UE 5.4를 default로 가정.
EOF
```

→ `user/user_role.md` 생성 + `MEMORY.md`의 `## user`에 포인터 자동 추가. `created`/`updated`는 오늘 날짜로 자동 기입.

## 4. 검증

```
python scripts/lint.py
```

7필드·인덱스↔파일·dead link를 검사. 문제 0이면 끝.

## 5. 갱신·삭제

- **갱신**: 같은 `save.py`를 재실행 — `created`는 보존되고 `updated`만 오늘로 바뀐다.
- **삭제**: 파일을 지운 뒤 `lint.py`를 돌려 "인덱스에 포인터 없음 / dead link"로 잡히는 줄을 `MEMORY.md`에서 제거.

## Read-before-act

메모리가 명명한 파일 경로·함수·플래그를 사용자에게 추천하기 전에 실제 존재를 확인(grep/파일 읽기)한다. "현재" 상태는 메모리 스냅샷보다 `git log`/파일이 우선. stale면 그 자리서 `save.py`로 갱신하거나 삭제.
