# ONBOARDING.md — 협력사 / 동료 온보딩 가이드

> 이 프로젝트에 처음 투입되는 모든 개발자(및 AI 에이전트)를 위한 시작 가이드입니다.

---

## 1. 시작 전 받아야 할 것 (관리자에게 요청)

| 항목 | 내용 |
|---|---|
| GitHub 저장소 URL | 프로젝트 전용 저장소 (템플릿 복제본) |
| Notion 페이지 접근 권한 | 프로젝트 Notion 워크스페이스 초대 |
| Notion 프로젝트 페이지 URL | WBS, 이슈관리 DB 직접 링크 |
| 담당 WBS 항목명 | 내가 맡은 작업 범위 |

> 위 4가지가 없으면 작업을 시작할 수 없습니다. 반드시 관리자에게 먼저 요청하세요.

---

## 2. 환경 설정 (1회만 수행)

### 2-1. Claude Code 설치 및 MCP 설정

```bash
# Claude Code CLI 설치 (이미 설치된 경우 생략)
npm install -g @anthropic/claude-code

# 프로젝트 저장소 클론
git clone {관리자에게 받은 GitHub 저장소 URL}
cd {저장소명}
```

### 2-2. MCP 서버 설정 (Notion 연동)

Claude Code 설정 파일(`~/.claude/settings.json` 또는 프로젝트 `.claude/settings.json`)에 추가:

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": {
        "OPENAPI_MCP_HEADERS": "{\"Authorization\": \"Bearer {Notion Integration Token}\", \"Notion-Version\": \"2022-06-01\"}"
      }
    }
  }
}
```

> Notion Integration Token은 관리자에게 요청하거나, 본인 Notion 계정에서 발급합니다.
> Notion 설정 → 연결 → 새 API 통합 만들기 → 토큰 복사

---

## 3. 작업 시작 방법

### 3-1. 사람이 직접 작업하는 경우

```
1. GitHub 저장소 clone (2-1 완료 후)
2. docs/dev-guide.md 읽기
3. Notion WBS에서 담당 항목 확인, 상태를 '진행중'으로 변경
4. 브랜치 생성: git checkout -b feature/{작업항목명}
5. 코드 작성 (.dev-config.yaml 기준 준수)
6. PR 생성 → .github/PULL_REQUEST_TEMPLATE.md 체크리스트 완료
7. Notion WBS 진도율 업데이트
```

### 3-2. AI 에이전트(Claude Code)가 작업하는 경우

저장소 루트에서 Claude Code를 실행하면 `CLAUDE.md`를 자동으로 읽습니다.

추가 지시가 필요한 경우 아래 명령어 패턴을 사용하세요:

```
"docs/dev-guide.md를 읽고, Notion WBS에서 [담당 항목명] 항목을 확인한 뒤 작업을 시작해줘.
작업 완료 후 WBS 진도율을 업데이트하고 PR을 생성해줘."
```

---

## 4. 코드 작성 핵심 규칙 (상세는 .dev-config.yaml 참조)

### 파일 헤더 주석 (모든 코드 파일 상단 필수)

```python
# -----------------------------------------------------------------------------
# File      : {파일명.py}
# Desc      : {이 파일의 역할을 1~2줄로 설명}
# Author    : {최초 작성자}
# Created   : {YYYY-MM-DD}
# Modified  : {YYYY-MM-DD} by {수정자} — {변경 내용 한줄 요약}
# -----------------------------------------------------------------------------
```

### 브랜치 전략

| 브랜치 | 용도 |
|---|---|
| `main` | 최종 배포 브랜치 (직접 push 금지) |
| `develop` | 통합 개발 브랜치 |
| `feature/{항목명}` | 기능 개발 |
| `hotfix/{이슈명}` | 긴급 버그 수정 |

### 로그 레벨

| 레벨 | 사용 시점 |
|---|---|
| DEBUG | 개발/디버깅 시 상세 정보 |
| INFO | 정상 처리 흐름 기록 |
| WARNING | 처리는 됐지만 주의 필요 |
| ERROR | 처리 실패, 이슈관리 DB 등록 필수 |

---

## 5. Notion 업데이트 규칙

| 시점 | 업데이트 항목 | 위치 |
|---|---|---|
| 작업 시작 | 상태 → `진행중` | WBS DB |
| 작업 완료 | 진도율 업데이트, 상태 → `완료` | WBS DB |
| 이슈 발생 | 이슈 등록 | 이슈관리 DB |
| 주차 마감 | 금주 실적, 차주 계획 작성 | 주차별 진척관리 DB |

---

## 6. 자주 묻는 질문

**Q. Notion에 직접 접근이 안 돼요**
→ 관리자에게 Notion 워크스페이스 초대를 요청하세요.

**Q. 어떤 WBS 항목을 맡아야 하나요?**
→ 관리자에게 담당 항목명을 확인하세요. WBS DB에서 담당자가 본인으로 배정됩니다.

**Q. PR은 어디에 올리나요?**
→ `develop` 브랜치로 PR을 올리세요. `main`으로 직접 PR 금지.

**Q. 에이전트가 Notion을 못 읽어요**
→ MCP 설정(2-2)이 올바른지 확인하고, Notion Integration이 해당 페이지에 연결되었는지 확인하세요.
