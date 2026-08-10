---
id: RUN-YYYYMMDD-HHMM-slug
flow:                       # FLOW-XXX-000
domain:
date:
status:                     # PASS | FAIL | BLOCKED
duration:
attempts:
mode:                       # headless | sim | think
verified_by:                # 실행과 다른 프로세스여야 한다
exit_code:
---

> Conductor가 `result.json`에서 생성한다. 사람이 쓰지 않는다.
> **`result.json`에 없는 수치가 여기 있으면 그건 환각이다** — 린터가 잡는다.

## 목표

plan.md에서 그대로 가져온다. 실행 후 고쳐 쓰지 않는다.

## 결과

<!-- 시각 자료 최소 1개. 권장이 아니라 규칙이다.
     숫자만으로는 아무도 판단하지 못한다.
       물리 실험    -> 지표 시계열 플롯 PNG        (CPU, 항상)
       지오메트리   -> 와이어프레임/솔리드 캡처    (소량 GPU)
       스윕         -> 비교 곡선 1장               (CPU)
       동역학·유체  -> MP4 2~10초                  (GPU, SIM 모드만)
       디지털 트윈  -> 트랙 오버레이 프레임        (GPU)
     HEADLESS 모드에서는 플롯만. 렌더는 VRAM 예산을 깨뜨린다. -->

![[RUN-YYYYMMDD-HHMM-slug/metric.png]]

| 지표 | 값 | 임계 | 판정 |
|---|---|---|---|
| | | | |

## 검증

```
<검증 명령과 출력 원문 그대로. 요약 금지.>
exit N
```

## 실패했다면

원문 로그, 진단, 다음 시도에서 바꾼 것.
**플로우 문서 5절에 한 줄 추가했는지 확인한다.** 그게 이 런의 유일한 영구 산출물이다.

## 아티팩트

- `runs/RUN-YYYYMMDD-HHMM-slug/`

<!-- 보존 정책: PNG 영구 / MP4는 90일 후 실패 런만 남기고 삭제.
     성공한 실험 영상은 재현 가능하므로 보관 가치가 낮다. -->
