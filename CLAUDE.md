# CLAUDE.md — AI Agent 세션 시작 지시문

> 이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 파일입니다.
> 에이전트는 아래 지시를 **작업 시작 전 반드시** 따라야 합니다.

---

## 1. 세션 시작 시 필수 읽기 순서

```
1. docs/dev-guide.md        ← 프로젝트 전체 개요, 기술스택, 코드 규칙, Notion URL (필수)
2. .dev-config.yaml         ← 코딩 표준 설정값 파싱 (필수)
3. Notion WBS               ← 현재 담당 작업 항목 확인 (필수, URL은 dev-guide.md 내 명시)
4. Notion RFP > 가공 데이터  ← 개발 배경 및 요구사항 이해 (참고)
```

워크플로우 전체 흐름이 필요하면 → `docs/WORKFLOW.md` 참조
협력사/동료 온보딩이 필요하면 → `docs/ONBOARDING.md` 참조

---

## 2. 저장소 파일 구조 및 역할

```
(repo root)
├── CLAUDE.md                          ← 지금 읽고 있는 파일 (에이전트 세션 자동 진입점)
├── .dev-config.yaml                   ← 코딩 표준 설정 (Config ①~⑤, 에이전트 파싱용)
├── README.md                          ← 프로젝트 개요 + Mermaid 워크플로우 다이어그램
└── docs/
    ├── dev-guide.md                   ← 통합 개발 가이드 (에이전트 필수 참조, Notion URL 포함)
    ├── WORKFLOW.md                    ← 관리자/협력사 전체 워크플로우 정의
    ├── ONBOARDING.md                  ← 협력사/동료 환경설정 및 시작 절차
    ├── diagrams/                      ← 코드 구조 다이어그램 (mermaid, TD 방향)
    └── specs/                         ← 파일별 기능명세 md
```

| 파일 | 주요 독자 | 핵심 내용 |
|---|---|---|
| `CLAUDE.md` | 에이전트 (자동 로드) | 읽기 순서 지시, 작업 체크리스트 |
| `docs/dev-guide.md` | 에이전트 + 사람 | 프로젝트 개요, 기술스택, 코드 규칙, Notion URL |
| `.dev-config.yaml` | 에이전트 (파싱) | 코딩 표준 설정값, 자동화 트리거 |
| `docs/WORKFLOW.md` | 관리자 + 협력사 | 전체 워크플로우, 환경설정 체크리스트 |
| `docs/ONBOARDING.md` | 협력사/동료 | 환경설정 방법, 시작 절차, FAQ |
| `README.md` | 외부인 | 프로젝트 개요, 다이어그램 |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR 작성자 | PR 체크리스트 |

---

## 3. 이 저장소의 역할

이 저장소(`dev-standard-template`)는 **프로젝트 원본 템플릿**입니다.

- **직접 수정 금지** — 실제 프로젝트는 이 템플릿을 "Use this template"으로 복제하여 별도 저장소에서 작업합니다
- 이 저장소를 수정해야 할 경우, 반드시 관리자(저장소 소유자)에게 확인 후 진행합니다

---

## 4. 작업 전 체크리스트

- [ ] `docs/dev-guide.md` 읽기 완료
- [ ] `.dev-config.yaml` 설정값 파악 완료
- [ ] Notion WBS에서 담당 항목 확인 완료 (URL은 dev-guide.md 참조)
- [ ] 브랜치 생성: `feature/{작업항목명}` 또는 `hotfix/{이슈명}`

---

## 5. 코딩 표준 핵심 요약 (상세는 .dev-config.yaml 참조)

| 항목 | 규칙 |
|---|---|
| 변수/함수명 | snake_case |
| 클래스명 | PascalCase |
| 상수명 | UPPER_SNAKE_CASE |
| 파일명 | snake_case |
| 로그 | DEBUG / INFO / WARNING / ERROR 4단계 |
| 예외처리 | try-catch-log 필수, ERROR 레벨 로그 필수 |
| 파일 헤더 | 파일명, 설명, 작성자, 작성일, 수정자, 수정일, 변경사항 주석 필수 |

---

## 6. 작업 완료 후 체크리스트

- [ ] 코드 파일 헤더 주석 갱신 (수정자, 수정일, 변경사항)
- [ ] `docs/specs/` 에 해당 파일의 기능명세 md 생성 또는 갱신
- [ ] `docs/diagrams/` 에 코드 구조 다이어그램 갱신 (mermaid, TD 방향)
- [ ] Notion WBS 진도율 업데이트
- [ ] PR 생성 시 `.github/PULL_REQUEST_TEMPLATE.md` 체크리스트 준수
- [ ] 이슈 발생 시 Notion 이슈관리 DB에 등록

---

## 7. Notion 연동 규칙

- Notion 페이지 URL은 `docs/dev-guide.md` 내 **"참고 문서"** 섹션에 명시합니다
- 작업 시작 전 WBS 상태를 `진행중`으로 변경하고, 완료 후 진도율과 상태를 업데이트합니다
- ERROR 레벨 로그 발생 시 이슈관리 DB에 등록합니다
- 주차 마감 시 주차별 진척관리 DB에 금주 실적 및 차주 계획을 작성합니다
