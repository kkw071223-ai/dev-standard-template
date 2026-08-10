---
id: FCT-YYYY-MMDD-000
domain:
claim:                      # 한 문장. 측정값이면 숫자와 단위까지
confidence: verified        # verified | reported | assumed
verified_on:
method: cmd                 # cmd | doc | inference
cmd:                        # confidence=verified 이면 필수
exit:                       # confidence=verified 이면 필수
source:                     # confidence=reported 이면 URL + 조회일
evidence:                   # [[RUN-...]]
expires:                    # 버전이 바뀌면 재검증해야 하는 시점
---

## 원문 출력

```
<명령 출력 그대로. 요약하거나 다듬지 않는다.>
```

<!--
신뢰도 3단계 — 에이전트가 말할 수 있는 방식이 여기서 갈린다.

  verified   이 PC에서 명령을 돌려 exit code까지 확인
             -> "...이다"  (단정 가능)

  reported   공식 문서에 그렇게 쓰여 있음. 직접 확인 안 함
             -> "문서에 따르면 ...라고 한다 (URL, 조회 YYYY-MM-DD)"

  assumed    추론·유추
             -> "추정: ..."  (경고 표시 필수)

verified 카드를 만들려면 cmd + exit + 원문 출력이 있어야 한다.
지어낼 방법이 없다는 것, 그게 이 카드의 존재 이유다.
-->
