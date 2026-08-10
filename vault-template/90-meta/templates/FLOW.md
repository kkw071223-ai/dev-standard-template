---
id: FLOW-XXX-000
domain:                     # 10-cad2sim | 20-digitaltwin | 30-agents | 40-brain | 50-physics
title:
status: draft               # draft | production | deprecated
graph:                      # conductor/graphs/<name>.yaml
runs_total: 0
runs_passed: 0
last_verified:
last_run:
---

> 이 문서는 **플로우가 두 번째로 성공했을 때** 만든다.
> 한 번 성공은 우연일 수 있고, 미리 쓰면 실행되지 않는 계획서가 하나 더 늘 뿐이다.

## 1. 목적

이 플로우가 없으면 무엇을 손으로 해야 하는가. 한 문단.

## 2. 입출력 계약

| | |
|---|---|
| 입력 | |
| 필수 옵션 | |
| 출력 | |
| 실패 시 | 런 폴더 동결 + 원문 로그. 부분 산출물은 신뢰하지 않는다 |

## 3. 그래프

단계를 화살표로. 게이트가 있으면 어디인지 표시한다.

## 4. 검증 기준

**측정 가능한 것만 적는다.** "잘 동작한다"는 기준이 아니다.
각 항목은 명령 하나와 기대 종료 코드로 환원되어야 한다.

- [ ]
- [ ]

## 5. 알려진 실패 모드

**이 절이 시간이 갈수록 값이 커지는 유일한 부분이다.**
진단한 실패는 예외 없이 여기 한 줄이 된다. 그래야 다음에 재발명하지 않는다.

| 증상 | 원인 | 조치 | 최초 관측 |
|---|---|---|---|
| | | | |

## 6. 최근 실행

```dataview
TABLE status, duration, file.link
FROM "30-runs"
WHERE flow = this.id
SORT date DESC
LIMIT 10
```

## 7. 변경 이력

- YYYY-MM-DD
