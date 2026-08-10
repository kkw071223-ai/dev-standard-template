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

현재 **591.66**, Isaac Sim 6.0.1이 요구하는 값은 **595.97**이다. 공식 요구사항
표에서 minimum / good / ideal 세 등급이 **전부 같은 번호**이고, 문서는 이것이
"테스트된 버전"이라고 명시한다. 즉 **목표는 595.97 하나**다.

**갈래를 틀리면 안 된다.** 이 GPU는 프로 계열(RTX PRO)이므로 GeForce Game Ready가
아니라 **NVIDIA RTX / Quadro Enterprise** 드라이버를 받아야 한다. 595.97 자체가
이 계열의 R595 Production Branch 빌드다.

nvidia.com/drivers 에서:

| 항목 | 고를 값 |
|---|---|
| Product Type | **NVIDIA RTX / Quadro** |
| Product Series | **NVIDIA RTX PRO Blackwell Series (Notebooks)** |
| Product | **RTX PRO 5000 Blackwell Laptop GPU** |
| OS | Windows 11 |
| Download Type | **Production Branch / Studio** |

595.97이 목록에 없으면 같은 R595 브랜치의 더 높은 596.x를 고른다. 595.97 이상이면
요구사항은 충족한다.

설치할 때: **AC 연결 상태**에서, 사용자 지정 설치 → **깨끗한 설치 수행** 체크,
끝나면 재부팅.

```powershell
nvidia-smi     # Driver Version 이 595.97 이상이면 통과
```

설치 프로그램이 "호환 하드웨어 없음"으로 거부하면 노트북 제조사가 드라이버를
커스터마이즈한 경우다. 제조사 지원 페이지에서 받는다.

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

### 막히는 곳: `claude` 용어가 인식되지 않습니다

설치는 성공했는데 명령이 안 잡히는 경우. 원인은 거의 항상 **현재 창이 옛날 PATH를
들고 있는 것**이다. 환경 변수는 프로세스가 시작할 때 한 번 읽히고, 설치 프로그램이
바꾼 값은 이미 열려 있는 창에 소급되지 않는다.

**먼저 이것부터.** PowerShell 창을 닫고 **새로 연 다음** `claude --version`.

그래도 안 되면 진단한다:

```powershell
# 1) 실제로 어디에 깔렸나
Get-ChildItem $env:USERPROFILE -Filter claude.exe -Recurse -Depth 4 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty FullName

# 2) 지금 창의 PATH를 저장된 값으로 새로고침 (창을 새로 열지 않고)
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path","User")
claude --version
```

2번으로 잡히면 원인은 PATH 새로고침이었고, 다음부터는 새 창만 열면 된다.

1번이 경로를 찾았는데 2번이 여전히 실패하면, 설치 프로그램이 PATH 등록에 실패한
것이다. **이 PC에서 실제로 이 경우였다** — 2026-08-10, 설치는 성공 보고를 했고
바이너리도 `C:\Users\HP\.local\bin\claude.exe` 에 있었지만 사용자 PATH에는
그 폴더가 없었다. 직접 등록한다:

```powershell
$bin = "$env:USERPROFILE\.local\bin"      # 1번이 알려준 실제 폴더

# 정말 없는지 확인 (아무것도 안 나오면 없는 것)
$user = [Environment]::GetEnvironmentVariable("Path","User")
$user -split ';' | Where-Object { $_ -like "*.local\bin*" }

# 중복 없이 영구 등록
if ($user -notlike "*$bin*") {
  [Environment]::SetEnvironmentVariable("Path", ($user.TrimEnd(';') + ";$bin"), "User")
}

# 지금 창에도 즉시 반영
$env:Path = "$env:Path;$bin"
claude --version
```

등록이 영구적으로 됐는지는 **창을 닫고 새로 열어** 다시 확인한다. 새 창에서
안 나오면 `SetEnvironmentVariable`이 먹지 않은 것이다.

1번이 아무것도 못 찾으면 설치가 실제로는 안 된 것이다. winget으로 다시 깐다:

```powershell
winget install --id Anthropic.ClaudeCode -e --accept-package-agreements --accept-source-agreements
$LASTEXITCODE      # 0 이면 성공. 한국어 출력이라 문자열로 판단하지 말 것
```

> **관리자 PowerShell에서 작업하지 마라.** 프롬프트가 `PS C:\windows\system32>` 라면
> 관리자 창이다. Claude Code는 일반 사용자 권한으로 돌리고, 작업 폴더도
> `system32`가 아니라 clone한 repo 안이어야 한다. Phase 0의 `powercfg`처럼 관리자가
> 필요한 명령만 따로 관리자 창에서 실행한다.

## ④ 인수인계

```powershell
claude
```

그리고 [`PROMPT.md`](PROMPT.md)의 블록 전체를 **한 번에** 붙여넣는다.
나눠서 치면 에이전트가 Phase 중간에 규칙을 잊는다.

이후 진행은 Phase 5a(텔레그램)가 서는 순간부터 폰으로 지켜볼 수 있다.
