# 개발 가이드

> **주의**: 이 파일은 Notion `개발 표준 포맷 > 설계 > 개발지침서 > 개발 가이드` 페이지와 동기화됩니다.
> 프로젝트별로 RFP, WBS, Config가 채워진 후 에이전트가 내용을 자동 작성합니다.

---

## 1. 프로젝트 개요

[RFP 가공 데이터 > 목적(Why) 기반 자동 작성 예정]

---

## 2. 기술 스택 및 개발 환경

[RFP 가공 데이터 > 개발 Tool(How) 기반 자동 작성 예정]

---

## 3. 코드 작성 규칙

### 명명법 (.dev-config.yaml 기준)

| 대상 | 규칙 |
|------|------|
| 변수 | `snake_case` |
| 함수 | `snake_case` |
| 클래스 | `PascalCase` |
| 상수 | `UPPER_SNAKE_CASE` |
| 파일 | `snake_case` |

### 파일 헤더 주석

```
# File: {file_name}
# Description: {1~2줄 요약}
# Author: {author}
# Created: YYYY-MM-DD
# Last Modified By: {modifier}
# Last Modified: YYYY-MM-DD
# Change Log: {변경 요약}
```

### 로그 레벨

| 레벨 | 색상 | 형식 |
|------|------|------|
| DEBUG | gray | `[DEBUG][timestamp][module] message` |
| INFO | blue | `[INFO][timestamp][module] message` |
| WARNING | yellow | `[WARN][timestamp][module] message` |
| ERROR | red | `[ERROR][timestamp][module] message` → **Notion 이슈관리 자동 등록** |

---

## 4. 디렉토리 구조

```
(repo root)
├── .github/PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── diagrams/    # Mermaid 코드 구조 다이어그램
│   ├── specs/       # 파일별 기능명세 (*.md)
│   └── dev-guide.md
├── .dev-config.yaml
└── README.md
```

---

## 5. Git 브랜치 전략

- `main` — 서비스 배포
- `develop` — 통합 개발
- `feature/{name}` — 기능 개발
- `hotfix/{name}` — 긴급 수정

---

## 6. Notion 연동 워크플로우

1. Config + 개발 가이드 읽기
2. WBS 확인
3. 코드 작성 (Config 제약사항 반영)
4. commit/push → 이슈관리 DB 자동 기록
5. docs/ 갱신 (다이어그램, 기능명세)
6. WBS 진도율 업데이트

---

## 7. 참고 문서

[RFP 가공 데이터 > 개발 Tool reference_mapping 기반 자동 작성 예정]
