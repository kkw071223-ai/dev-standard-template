# Claude Code에 붙여넣을 지시문

`bootstrap/README.md`의 3단계까지 끝낸 뒤, `C:\agent\repos\dev-standard-template`
에서 아래 순서로 진행한다.

## 시작 전 3가지

**① MCP 서버 4개를 묻거든 Esc — 전부 거부한다.**
`omni-ui-mcp` / `kit-mcp` / `usd-code-mcp` / `isaacsim-mcp` 는 `localhost:9901~9904`
의 도커 컨테이너를 가리킨다. 아직 Docker도 없고 그 포트에 아무것도 없다. 켜면 매
세션 연결 실패만 뜨고, 에이전트가 USD 도구가 있다고 착각한다. **Phase 7 이후**에
켠다. (Phase 4의 Notion MCP는 원격 서버라 이것들과 무관하다.)

**② auto 모드를 켠다.** [`AUTOMODE.md`](AUTOMODE.md) 참조. 요약하면
`C:\Users\<you>\.claude\settings.json` 에:

```json
{
  "permissions": {
    "defaultMode": "auto",
    "ask": ["Bash(git push:*)"]
  }
}
```

`ask` 규칙이 있어야 하는 이유: auto 모드는 기본적으로 push와 PR 생성을 허용한다.
설계서 §12가 그 둘을 게이트로 두기로 했으므로 규칙으로 되돌린다.

**③ PATH 새로고침 함수를 만들어 둔다.** Phase 1에서 Python·Node·VS Code를 줄줄이
깔게 되는데, 설치 프로그램이 PATH를 바꿔도 열려 있는 창은 모른다.

```powershell
function refreshpath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path","User")
}
```

---

## 붙여넣을 블록

**전체를 한 번에** 넣는다. 문단마다 나눠서 치지 말 것 — 규칙과 게이트가 한 덩어리로
들어가야 에이전트가 Phase 중간에 규칙을 잊지 않는다.

---

```
이 PC를 상시 가동 자율 에이전트 워크스테이션으로 구축한다.

## 먼저 읽을 것 (순서대로)
1. docs/07-agent-pc-design.md  - 설계서 전문
2. bootstrap/preflight-report.txt - 이 PC의 실측값

## 사실의 우선순위
preflight-report.txt가 설계서보다 우선한다. 설계서 §15에 "assumed(⚠)"로
표시된 항목은 전부 실측값으로 대체하라. 특히 이미 확정된 것:

- 경로: D: 드라이브는 없다. 설계서의 모든 D:\agent 는 C:\agent 로 읽어라.
  C:는 1,795 GB 비어 있으니 용량 걱정은 하지 마라.
- GPU 드라이버 591.66 은 Isaac Sim 6.0.1 최소값 595.97 미만이다. 이건
  블로커다. Phase 6 전에 반드시 올려야 한다.
- 하이브리드 그래픽(Intel + NVIDIA)이다. Isaac Sim이 내장 GPU로 붙으면
  실패한다. NVIDIA 어댑터로 고정하라.
- python 은 Microsoft Store App Execution Alias 스텁이다. 진짜 인터프리터가
  아니다. 실제 Python 3.11 설치 전에 별칭을 꺼라.
- Modern Standby(S0)만 지원한다. S3도 최대절전도 없다. 뚜껑 동작은 AC/DC
  양쪽 다 "아무것도 안 함"으로 설정하라.
- 네트워크는 전부 뚫려 있고 프록시도 없다. api.telegram.org, workers.dev
  포함 13개 엔드포인트 전부 도달 가능하다.
- winget 패키지 ID 10개는 "미확인"이지 "없음"이 아니다. 1차 점검 스크립트의
  로케일 버그였다. `winget show --id <ID> -e` 의 종료 코드로 직접 확인하라.

## 진행 방식
Phase 0부터 순서대로. 각 Phase 끝의 "✔ 확인"을 통과해야 다음으로 간다.

- 통과 판정은 반드시 **명령 출력 원문과 종료 코드**로 한다. 네 판단으로
  "됐다"고 하지 마라.
- 통과하지 못하면 멈추고, 실패한 명령과 출력 원문 그대로 보고하라.
  요약하거나 의역하지 마라.
- 같은 실패를 3번 시도했으면 더 시도하지 말고 보고하라.
- 각 Phase가 끝나면 무엇을 설치했고 무엇으로 확인했는지 3줄 이내로 보고하라.

## Phase 5a가 최우선 목표다
텔레그램 왕복이 서는 순간부터 내가 폰으로 지켜볼 수 있다. Isaac Sim은
다운로드만 몇 시간이므로 5a보다 먼저 시작하지 마라.

권장 순서: Phase 0 → 1 → 2 → 5a → 3 → 4 → 6 → 7 → 8 → 9 → 10 → 11
(설계서의 번호 순서와 다르다. 5a를 앞으로 당긴 것이다.)

## 승인이 필요한 것 (그 외에는 전부 자율)
1. 과금이 발생하는 API 호출
2. GitHub PR 생성 또는 기본 브랜치 푸시
이 둘은 실행 전에 나에게 물어라. 나머지는 묻지 말고 진행하라.

## 하지 말 것
- C:\Windows, 드라이버, 레지스트리 시스템 영역 변경
- C:\agent 밖의 파일 삭제
- secrets.env 의 값을 로그/리포트/커밋/화면에 출력
- Hermes / NemoClaw 설치 (설계서 §1.4대로 선택 항목이다. 지금은 건너뛴다)
- Cloudflare Worker 구축 (Phase 5b, 선택. 지금은 건너뛴다)

## 기록
설치하면서 확인한 사실은 나중에 Obsidian 볼트의 20-facts/ 에 사실 카드로
남길 것이다 (설계서 §9.3). Phase 3에서 볼트가 서기 전까지는
bootstrap/setup-log.md 에 누적하라. 형식은 사실 카드와 동일하게:
주장 / 확인 명령 / 종료 코드 / 출력 원문 / 날짜.

Phase 3에서 볼트를 만들 때는 vault-template/ 를 복사해서 쓴다. 템플릿 3종
(FLOW / RUN / FACT)이 들어 있다.

## Phase 11의 마지막 작업 - 설계서 폐기
설계서 §18을 읽고 그대로 실행하라. 이 설계서는 구축용 소모품이며 세팅이
끝나면 분해되어 폐기된다. 계속 들고 있으면 에이전트가 지난 계획을 현재
상태로 착각한다.

1. §9/§10/§12 를 도메인 CLAUDE.md 5개로 이주 (여기가 실제 강제되는 자리)
2. §3/§6/§7/§8 을 90-meta/architecture.md 로
3. §2/§4/§5 를 대체할 90-meta/ENVIRONMENT.md 를 실측으로 생성
   (nvidia-smi, 설치된 버전, 디스크, venv 상태. 주 1회 자동 재생성)
4. §1 을 사실 카드 + 40-refs/ 로 분해
5. §13/§15/§17 과 사전 점검 리포트를 90-meta/archive/2026-08-setup/ 로 동결
6. 완료 후 이 설계서는 일상 작업에서 열지 않는다

## 리포트에는 그림이 있어야 한다
설계서 §18.4 규칙이다. 권장이 아니다. "0.31% 드리프트"라는 숫자만으로는
아무도 판단하지 못한다. 런 리포트에 시각 자료를 최소 1개 첨부하라.
HEADLESS 모드에서는 플롯만 만든다 - 렌더는 VRAM 예산을 깨뜨린다.

Phase 0부터 시작하라.
```

---

## 중간에 막혔을 때 쓸 후속 지시문

| 상황 | 붙여넣을 말 |
|---|---|
| 특정 Phase만 다시 | `Phase 6을 처음부터 다시 하라. bootstrap/setup-log.md에 이전 시도의 실패 원인이 있으니 먼저 읽어라.` |
| 확인만 | `지금까지 완료했다고 기록한 Phase를 전부 재검증하라. 설계서의 "✔ 확인" 명령을 실제로 다시 돌리고, 출력 원문으로 판정하라. 기억에 의존하지 마라.` |
| 드라이버 갱신 후 | `GPU 드라이버를 갱신했다. nvidia-smi로 595.97 이상인지 확인하고, 통과하면 Phase 6을 진행하라.` |
| 진행 상황 | `현재 Phase 진행 상황을 표로 정리하라. 각 행은 Phase / 상태 / 무슨 명령으로 확인했는지 / 종료 코드.` |
