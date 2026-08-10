# 부트스트랩 — 사람이 할 일 3단계

에이전트가 넘겨받기 전까지, 사람만 할 수 있는 일이 셋 있다. **20분이면 끝난다.**
전체 설계는 [`../docs/07-agent-pc-design.md`](../docs/07-agent-pc-design.md).

| 파일 | 무엇 |
|---|---|
| `00-preflight.ps1` | 시스템 실측. 아무것도 설치하지 않는다 |
| `preflight-report.txt` | 이 PC의 실측 결과 (2026-08-10). **설계서보다 우선한다** |
| `PROMPT.md` | Claude Code에 붙여넣을 지시문 |

---

## 실측으로 확정된 것

| | 값 |
|---|---|
| CPU | Core Ultra 9 **285HX**, 24코어 |
| RAM | 127 GB |
| GPU | RTX PRO 5000 Blackwell **Laptop**, 24 GB |
| 드라이버 | **591.66 → 595.97 필요. 블로커** |
| 디스크 | C: 1,795 GB 여유. **D: 없음 → `C:\agent`** |
| 절전 | Modern Standby(S0)만. S3·최대절전 없음 |
| 네트워크 | 13개 엔드포인트 전부 도달. 프록시 없음 |

---

## ① GPU 드라이버 갱신 — 유일한 블로커

Isaac Sim 6.0.1은 **595.97 이상**을 요구하는데 현재 591.66이다.

NVIDIA 앱 또는 nvidia.com에서 RTX PRO 5000 Blackwell Laptop GPU용 최신
드라이버를 받아 설치한다. Studio/Production Branch 쪽이 시뮬레이션 워크로드에
더 안정적이다.

```powershell
nvidia-smi     # Driver Version 이 595.97 이상이면 통과
```

> 지금 당장 안 해도 Phase 5a까지는 진행된다. Phase 6(Isaac Sim) 전까지만
> 끝내면 된다. 다만 재부팅이 필요하므로 먼저 해두는 편이 편하다.

## ② 텔레그램 봇 — 5분

1. 텔레그램에서 `@BotFather` → `/newbot` → 이름 입력 → **봇 토큰** 획득
2. 만든 봇과 대화 시작 (아무 말이나)
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates`
   → `"chat":{"id":숫자}` 에서 **chat_id** 확인

두 값은 나중에 `%USERPROFILE%\.agent\secrets.env` 에만 넣는다. 어디에도
커밋하지 않는다.

## ③ Claude Code CLI 설치 + repo clone — 5분

```powershell
irm https://claude.ai/install.ps1 | iex
claude --version
claude                                  # 브라우저 → Claude Max 로그인
```

CLI여야 한다. VS Code 확장이나 Desktop으로는 Conductor가 프로그램으로 호출할
수 없다 ([설계서 §3.2](../docs/07-agent-pc-design.md)). 확장은 나중에 같이
깔면 되고, 둘은 같은 구독을 쓴다.

git이 아직 없으므로 먼저 깐다:

```powershell
winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
# 새 PowerShell 창을 열어 PATH를 다시 읽는다
mkdir C:\agent\repos
cd C:\agent\repos
git clone -b claude/omniverse-agents-skills-analysis-gc40zw `
  https://github.com/kkw071223-ai/dev-standard-template.git
cd dev-standard-template
```

---

## ④ 인수인계

```powershell
claude
```

그리고 [`PROMPT.md`](PROMPT.md)의 블록 전체를 **한 번에** 붙여넣는다.
나눠서 치면 에이전트가 Phase 중간에 규칙을 잊는다.

이후 진행은 Phase 5a(텔레그램)가 서는 순간부터 폰으로 지켜볼 수 있다.
