# setup-log.md — 구축 실행 기록

Phase 3에서 Obsidian 볼트가 설 때까지 여기에 누적한다.
형식: **주장 / 확인 명령 / 종료 코드 / 출력 원문 / 날짜**

원문은 요약하지 않는다. 한국어 로케일 출력도 그대로 붙인다.
타임스탬프는 이 PC의 `Get-Date` 실측값이다 (`2026-08-10 23:03:09 +09:00` 기준).

---

## Phase 0-2 — 전원 정책 ★ 최우선 블로커

### 주장 1: 이 PC는 유휴 5분이면 잠들고 있었다 (착수 전 상태)

확인 명령
```powershell
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
```
종료 코드: `0`

출력 원문
```
전원 구성표 GUID: fb5220ff-7e1a-47aa-9a42-50ffbf45c673  (HP Optimized (Modern Standby))
  하위 그룹 GUID: 238c9fa8-0aad-41ed-83f4-97be242c8f20  (절전)
    GUID 별칭: SUB_SLEEP
    전원 설정 GUID: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (다음 시간 후 절전 모드로 전환)
      GUID 별칭: STANDBYIDLE
      가능한 최소 설정: 0x00000000
      가능한 최대 설정: 0xffffffff
      가능한 설정 증가: 0x00000001
      가능한 설정 단위: 초
    현재 AC 전원 설정 색인: 0x0000012c
    현재 DC 전원 설정 색인: 0x000000b4
```
`0x12c` = 300초 = 5분. AMENDMENT 항목 A 확인됨.

날짜: 2026-08-10

---

### 주장 2: LIDACTION은 이 구성표에서 숨겨져 있어 set이 조용히 실패한다

set 명령은 전부 `exit=0`을 반환했다.
```
lidaction_ac exit=0
lidaction_dc exit=0
setactive exit=0
```

그러나 읽으면 값이 없다 — **exit 0이 적용을 증명하지 않는다.**

확인 명령
```powershell
powercfg /q SCHEME_CURRENT SUB_BUTTONS LIDACTION
```
종료 코드: `0`

출력 원문 (전문. 스킴 헤더 한 줄이 전부다)
```
전원 구성표 GUID: fb5220ff-7e1a-47aa-9a42-50ffbf45c673  (HP Optimized (Modern Standby))
```

AMENDMENT 항목 B가 예측한 그대로다. 설계서의 "로케일 버그" 단독 진단으로는
설명되지 않는다 — 파서를 고쳐도 읽을 값 자체가 없다.

날짜: 2026-08-10

---

### 주장 3: 숨김을 풀고 다시 set하면 적용된다

확인 명령
```powershell
powercfg /attributes 4f971e89-eebd-4455-a8de-9e59040e7347 `
                     5ca83367-6e45-459f-a27b-476b1d01c936 -ATTRIB_HIDE
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1
powercfg /setactive SCHEME_CURRENT
powercfg /q SCHEME_CURRENT SUB_BUTTONS LIDACTION
```
종료 코드: `attributes exit=0`, `lid_ac exit=0`, `lid_dc exit=0`, `setactive exit=0`

출력 원문
```
전원 구성표 GUID: fb5220ff-7e1a-47aa-9a42-50ffbf45c673  (HP Optimized (Modern Standby))
  하위 그룹 GUID: 4f971e89-eebd-4455-a8de-9e59040e7347  (전원 단추와 덮개)
    GUID 별칭: SUB_BUTTONS
    전원 설정 GUID: 5ca83367-6e45-459f-a27b-476b1d01c936  (덮개 닫기 동작)
      GUID 별칭: LIDACTION
      가능한 설정 색인: 000
      가능한 설정 이름: 아무 것도 안 함
      가능한 설정 색인: 001
      가능한 설정 이름: 절전
      가능한 설정 색인: 002
      가능한 설정 이름: 최대 절전 모드
      가능한 설정 색인: 003
      가능한 설정 이름: 시스템 종료
    현재 AC 전원 설정 색인: 0x00000000
    현재 DC 전원 설정 색인: 0x00000001
```

AC = `000` 아무 것도 안 함 · DC = `001` 절전. AMENDMENT 항목 C의 반전된 정책과 일치.

날짜: 2026-08-10

---

### 주장 4: 절전·화면 인덱스가 의도대로 들어갔다

확인 명령
```powershell
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE   | Select-String '0x[0-9a-fA-F]{8}'
powercfg /q SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE | Select-String '0x[0-9a-fA-F]{8}'
powercfg /q SCHEME_CURRENT SUB_VIDEO  VIDEOIDLE    | Select-String '0x[0-9a-fA-F]{8}'
```
종료 코드: `0`

출력 원문 (현재 인덱스 줄만 발췌 — 각 블록의 마지막 두 줄)
```
STANDBYIDLE      현재 AC 전원 설정 색인: 0x00000000     현재 DC 전원 설정 색인: 0x00000708
HIBERNATEIDLE    현재 AC 전원 설정 색인: 0x00000000     현재 DC 전원 설정 색인: 0x0003f480
VIDEOIDLE        현재 AC 전원 설정 색인: 0x00000384     현재 DC 전원 설정 색인: 0x000000b4
```

해석: AC 절전 `0`(안 함) · DC 절전 `0x708`=1800초=30분 · AC 화면 `0x384`=900초=15분.

> ⚠ **설계서 Phase 0 "✔ 확인" 블록이 낡았다.** 거기에는 LIDACTION이
> "둘 다 0x00000000이어야 한다"고 적혀 있는데, AMENDMENT 항목 C가 DC를 절전으로
> 뒤집었다. 사실 우선순위 규칙(AMENDMENT > 설계서)에 따라 **DC=0x00000001이 정답**이다.
> 설계서 본문 Phase 0-2는 이미 옳게 고쳐져 있고, ✔ 확인 블록만 안 고쳐졌다.

날짜: 2026-08-10

---

## Phase 0-4 — WSL2

### 주장 5: wsl.exe는 있었지만 WSL 기능 자체가 꺼져 있었다

`wsl --install -d Ubuntu-24.04 --no-launch` 가 exit=1로 실패했다.
출력이 UTF-16LE라 처음엔 깨져 보였고, 인코딩을 바꿔 읽으니 원인이 드러났다.

확인 명령
```powershell
Get-WindowsOptionalFeature -Online | Where-Object { $_.FeatureName -match 'Linux|VirtualMachinePlatform|HypervisorPlatform' }
```
종료 코드: `wsl --status exit=50`, `wsl --install exit=1`

출력 원문
```
FeatureName                          State
-----------                          -----
VirtualMachinePlatform             Enabled
HypervisorPlatform                Disabled
Microsoft-Windows-Subsystem-Linux Disabled
```
wsl.exe 메시지 (UTF-16 디코드 후)
```
Linux용 Windows 하위 시스템이 설치되어 있지 않습니다. 'wsl.exe --install'을 실행하여 설치할 수 있습니다.
```

`VirtualMachinePlatform`은 이미 켜져 있었고 `Microsoft-Windows-Subsystem-Linux`만
꺼져 있었다. preflight의 "wsl.exe present, but NO distribution installed"는
**절반만 맞았다** — 배포판이 없는 게 아니라 기능이 꺼져 있었다.

날짜: 2026-08-10

### 주장 6: 기능을 켰고 재부팅이 대기 중이다

확인 명령
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
```
종료 코드: `0`

출력 원문
```
WARNING: Restart is suppressed because NoRestart is specified.
RestartNeeded : True

FeatureName : Microsoft-Windows-Subsystem-Linux
State       : Enabled

FeatureName : VirtualMachinePlatform
State       : Enabled
```

배포판 설치(`wsl --install -d Ubuntu-24.04`)는 **재부팅 후**로 미룬다.

날짜: 2026-08-10

---

## Phase 0-5 — 디렉터리

### 주장 7: C:\agent 레이아웃과 %USERPROFILE%\.agent 생성됨

확인 명령
```powershell
Get-ChildItem C:\agent | Select-Object -ExpandProperty Name
Test-Path "$env:USERPROFILE\.agent"
Test-Path C:\agent\vault
```
종료 코드: `0`

출력 원문
```
conductor
domains
isaac-assets
models
repos
scratch
vault
True
True
```
날짜: 2026-08-10

---

## Phase 1 — 기본 툴체인

### 주장 8: winget ID 10종은 전부 실재한다 (preflight의 INCONCLUSIVE 해소)

문자열이 아니라 **종료 코드로** 판정했다.

확인 명령
```powershell
foreach ($id in $ids) { winget show --id $id -e --disable-interactivity; $LASTEXITCODE }
```

출력 원문
```
Git.Git                        exit=0
Python.Python.3.11             exit=0
OpenJS.NodeJS.LTS              exit=0
Microsoft.PowerShell           exit=0
Microsoft.VisualStudioCode     exit=0
7zip.7zip                      exit=0
Obsidian.Obsidian              exit=0
Ollama.Ollama                  exit=0
Docker.DockerDesktop           exit=0
Anthropic.ClaudeCode           exit=0
```

preflight의 "INCONCLUSIVE — treat all ten ids as unverified, not as missing"가
**전부 실재**로 확정됐다.

날짜: 2026-08-10

### 주장 9: Python 3.11 / Node / PowerShell 7 / 7zip / Obsidian 설치 성공

확인 명령
```powershell
winget install --id <ID> -e --accept-package-agreements --accept-source-agreements --disable-interactivity
```
종료 코드: 전부 `0`

출력 원문 (버전 줄만)
```
찾음 Python 3.11 [Python.Python.3.11] 버전 3.11.9        → 설치 성공  exit=0
찾음 Node.js (LTS) [OpenJS.NodeJS.LTS] 버전 24.19.0      → 설치 성공  exit=0
찾음 PowerShell [Microsoft.PowerShell] 버전 7.6.4.0      → 설치 성공  exit=0
찾음 7-Zip [7zip.7zip] 버전 26.02                        → 설치 성공  exit=0
찾음 Obsidian [Obsidian.Obsidian] 버전 1.13.4            → 설치 성공  exit=0
```
날짜: 2026-08-10

### 주장 10: ★ Store python 별칭이 더 이상 진짜 Python을 가리지 않는다

설계서 1-0과 preflight는 별칭을 **먼저 꺼야** 한다고 했다. 실측 결과 **끄지 않아도
해결됐다** — Python 3.11 설치 관리자가 자기 경로를 사용자 PATH 맨 앞(0,1번)에
넣었고 WindowsApps는 2번이다.

확인 명령
```powershell
Get-Command python | Select-Object -ExpandProperty Source
python --version
([Environment]::GetEnvironmentVariable("Path","User")) -split ';'
```
종료 코드: `0`

출력 원문
```
C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe
Python 3.11.9

 0 : C:\Users\HP\AppData\Local\Programs\Python\Python311\Scripts\
 1 : C:\Users\HP\AppData\Local\Programs\Python\Python311\
 2 : C:\Users\HP\AppData\Local\Microsoft\WindowsApps
 3 : C:\Users\HP\AppData\Local\Programs\Microsoft VS Code\bin
 4 : C:\Users\HP\.local\bin
 5 : C:\Users\HP\AppData\Roaming\npm
```

**결론: 사람이 별칭을 끄는 작업은 필수가 아니라 선택이 됐다.** 다만 별칭 스텁은
여전히 존재하므로, 위생 차원에서 꺼두면 나중에 PATH가 재정렬돼도 안전하다.
스텁 삭제는 하지 않는다 (C:\agent 밖 파일 삭제 금지).

날짜: 2026-08-10

### 주장 11: Phase 1 ✔ 확인 통과

확인 명령
```powershell
git --version; python --version; node --version; npm --version; pwsh --version
```
종료 코드: `0`

출력 원문
```
python  : C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe   Python 3.11.9
node    : C:\Program Files\nodejs\node.exe                                 v24.19.0
npm     : C:\Program Files\nodejs\npm.ps1                                  11.17.0
npx     : C:\Program Files\nodejs\npx.ps1
pwsh    : PowerShell 7.6.4
git     : C:\Program Files\Git\cmd\git.exe
claude  : C:\Users\HP\.local\bin\claude.exe
```

> Node 24.19.0은 설계서 Phase 9가 요구하는 `Node 22.19+`를 충족한다.
> `pwsh` 해석 경로가 WindowsApps 스텁으로 잡히지만 `pwsh --version`이
> `PowerShell 7.6.4`를 반환하므로 실제 7.x에 연결돼 있다.

날짜: 2026-08-10

### 주장 10 정정: 별칭은 "새 프로세스"에서만 무해하다

주장 10을 그대로 두면 오해를 부른다. 뒤이어 `python -m venv`가 **exit 9009**로
실패했고, 원인은 Store 스텁이었다.

확인 명령
```powershell
python -m venv C:\agent\conductor\.venv
```
종료 코드: `9009`

출력 원문
```
Python
venv exit=9009
```

이 PowerShell 프로세스는 Python 설치 **이전에** 시작돼 낡은 PATH를 들고 있었다.
저장된 사용자 PATH는 Python이 0·1번으로 앞서지만, 이미 떠 있는 프로세스에는
소급되지 않는다 — `bootstrap/README.md`가 `claude` 명령에서 겪은 것과 같은 함정이다.

**정정된 결론:** 새로 여는 셸에서는 진짜 Python이 이긴다. 그러나 살아 있는
프로세스에서는 여전히 스텁이 잡힌다. 따라서 스크립트에서는 **절대 경로**를 쓴다.
사람이 별칭을 끄면 이 함정이 영구히 사라진다 — 여전히 권장 사항이다.

우회 확인 명령
```powershell
& "C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe" -m venv C:\agent\conductor\.venv
```
종료 코드: `0`

출력 원문
```
Python 3.11.9
py exit=0
venv exit=0
exists: True
Python 3.11.9
vpy exit=0
```
날짜: 2026-08-10

---

## Phase 2 — Claude Code

### 주장 12: auto 모드와 push 게이트가 사용자 설정에 들어 있다

확인 명령
```powershell
Get-Content C:\Users\HP\.claude\settings.json
```
종료 코드: `0`

출력 원문
```json
{
  "autoUpdatesChannel": "latest",
  "theme": "dark",
  "tui": "fullscreen",
  "permissions": {
    "defaultMode": "auto",
    "ask": ["Bash(git push:*)"]
  }
}
```
`AUTOMODE.md`가 요구한 대로 **사용자 설정**(프로젝트 설정이 아니라)에 있다.
설계서 §12의 `GATE-PR`이 복구된 상태다.

날짜: 2026-08-10

### 주장 13: Conductor가 필요로 하는 4가지(§3.2)가 전부 실증됐다

확인 명령
```powershell
claude -p "Reply with exactly: HEADLESS OK" --permission-mode dontAsk
claude -p "Reply with exactly: STREAM OK" --output-format stream-json --verbose --permission-mode dontAsk
cd C:\agent\scratch\cwdtest
claude -p "Read marker.txt in the current directory and reply with only its contents" `
  --permission-mode dontAsk --allowedTools "Read,Glob,Grep"
```
종료 코드: 전부 `0`

출력 원문 (발췌)
```
HEADLESS OK
exit=0

{"type":"system","subtype":"init","cwd":"C:\\agent\\scratch",...,"permissionMode":"dontAsk",
 "model":"claude-opus-5[1m]","claude_code_version":"2.1.226"}
{"type":"assistant","message":{...,"content":[{"type":"text","text":"STREAM OK"}]}}
{"is_error":false,...,"result":"STREAM OK","subtype":"success","type":"result"}
exit=0

sentinel-value-42
exit=0
```

| §3.2 요구 | 실증 |
|---|---|
| ① 사람 없이 실행 시작 | `claude -p` 가 무인으로 완주 |
| ② 기계가 읽는 결과 | `"is_error":false`, `"result":"STREAM OK"` |
| ③ 종료 코드 | `exit=0` |
| ④ 잡마다 다른 cwd | cwd의 `marker.txt`를 읽어 `sentinel-value-42` 반환 |

부수 확인: init 줄에 `"claude.ai Notion","status":"connected"` — **Notion MCP가 이미
연결돼 있다.** Phase 4의 OAuth 단계는 이미 끝나 있는 셈이다.

날짜: 2026-08-10

### 주장 14: VS Code 확장 ID가 `anthropic.claude-code`로 확정됐다

설계서 §15의 ⚠ 추정 항목이었다.

확인 명령
```powershell
code --install-extension anthropic.claude-code --force
code --list-extensions | Select-String 'anthropic'
```
종료 코드: `0`

출력 원문
```
Installing extension 'anthropic.claude-code'...
Extension 'anthropic.claude-code' v2.1.226 was successfully installed.
ext exit=0

anthropic.claude-code
```
날짜: 2026-08-10

### 주장 15: Git Bash 경로 등록됨

확인 명령
```powershell
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH","C:\Program Files\Git\bin\bash.exe","User")
[Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH","User")
```
종료 코드: `0`

출력 원문
```
C:\Program Files\Git\bin\bash.exe
```
날짜: 2026-08-10

> **Phase 2 미완:** WSL 쪽 Claude Code 설치는 배포판이 없어 불가.
> 재부팅 후 Phase 0-4를 마친 뒤에 한다.

---

## Phase 5a — Conductor 골격 (진행 중)

### 주장 16: Conductor venv와 의존성이 섰다

확인 명령
```powershell
& "C:\agent\conductor\.venv\Scripts\python.exe" -c "import httpx,pydantic,rich,apscheduler;print('CONDUCTOR DEPS OK')"
& "C:\agent\conductor\.venv\Scripts\python.exe" -m pip list
```
종료 코드: `0`

출력 원문
```
CONDUCTOR DEPS OK
import exit=0

APScheduler       3.11.3
httpx             0.28.1
pydantic          2.13.4
pydantic_core     2.46.4
rich              15.0.0
```
날짜: 2026-08-10

### 주장 17: secrets.env가 본인 전용 ACL로 생성됨 (값은 비어 있음)

확인 명령
```powershell
icacls "$env:USERPROFILE\.agent\secrets.env"
```
종료 코드: `0`

출력 원문
```
C:\Users\HP\.agent\secrets.env LGE\geonwoo2.kim:(R,W)

Successfully processed 1 files; Failed processing 0 files
```
키 존재 여부만 확인 (**값은 출력하지 않는다**)
```
TELEGRAM_TOKEN=<EMPTY>
TELEGRAM_CHAT_ID=<EMPTY>
NGC_API_KEY=<EMPTY>
NIM_API_KEY=<EMPTY>
```
날짜: 2026-08-10

### 주장 18: git 신원 설정 (⚠ 가정)

`user.name`/`user.email`이 비어 있어 커밋이 불가능했다. 알려진 값으로 채웠다.

확인 명령
```powershell
git config --global user.name "kkw071223-ai"
git config --global user.email "kkw071223@gmail.com"
git config --get user.name; git config --get user.email
```
종료 코드: `0`

출력 원문
```
kkw071223-ai <kkw071223@gmail.com>
```

⚠ **가정이다.** GitHub 계정명은 remote URL(`kkw071223-ai`)에서, 이메일은 세션
컨텍스트에서 가져왔다. 다르면 사용자가 정정해야 한다.

날짜: 2026-08-10

### 주장 19: 텔레그램 양방향이 살아 있다

**PC → 폰** (토큰은 출력하지 않는다)

확인 명령
```powershell
Invoke-RestMethod -Uri "https://api.telegram.org/bot<TOKEN>/getMe"
Invoke-RestMethod -Uri "https://api.telegram.org/bot<TOKEN>/sendMessage" -Method Post -Body $body
```
종료 코드: `0`

출력 원문
```
ok        : True
bot id    : 8722257935
username  : @Kkw0712_bot
can_join  : True

ok         : True
message_id : 5
chat type  : private
to         : Geonwoo
date       : 08/10/2026 23:23:41 +09:00
```

**폰 → PC** — 이건 연출하지 않았다. Conductor를 처음 띄우자마자, 사용자가 chat_id를
확인하려고 **한참 전에** 보냈던 메시지가 그대로 들어왔다.

출력 원문
```
[conductor] @Kkw0712_bot 로 기동. offset=None
[conductor] < 하이요
```

**설계서 §8.1이 실증됐다.** 텔레그램이 미수신 업데이트를 24시간 보관하므로,
Conductor가 죽어 있던 동안의 지시도 기동 즉시 전부 들어온다. Cloudflare
Worker(5b) 없이도 지시는 유실되지 않는다 — Worker가 사는 값은 "즉답" 하나뿐이라는
설계서의 주장이 맞았다.

날짜: 2026-08-10

### 주장 20: Conductor 자체 시험 통과 (네트워크 없이)

확인 명령
```powershell
& "C:\agent\conductor\.venv\Scripts\python.exe" selftest.py
```
종료 코드: `0`

출력 원문
```
--- SEND ---
📊 상태
모드      headless
VRAM      0 MiB / 24463 MiB
전원      AC
큐        0
마지막 런 없음
--- SEND ---
모드를 think 로 바꿨다.
--- SEND ---
📝 저장했다: 20260810-232816.md
--- SEND ---
모르는 명령이다. /status /sim /cad /twin /ask /note /mode /runs
[hw] vram_used=0 MiB  on_battery=False

=== SELFTEST ===
all checks passed
selftest exit=0
```

시험 항목: `/status` 포맷 · `/mode` 상태 변경 · `/note` 실제 파일 생성 ·
알 수 없는 명령 · INTAKE 도메인 판정 · CLARIFY 분기 · **redact(시크릿 유출 방지)** ·
§8.5 리포트 포맷에 오류 원문이 살아남는지.

날짜: 2026-08-10

### 주장 21: Conductor 상주 프로세스가 떠 있다

확인 명령
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*conductor.py*' }
```
종료 코드: `0`

출력 원문
```
started pid=31696

ProcessId CreationDate
--------- ------------
    31696 2026-08-10 오후 11:28:32
```
날짜: 2026-08-10

---

## Phase 3 — Obsidian 볼트

### 주장 22: 볼트 구조·플러그인 3종·git 저장소가 섰다

플러그인은 UI를 거치지 않고 각 GitHub 릴리스에서 직접 받았다.

확인 명령
```powershell
Get-Content C:\agent\vault\.obsidian\community-plugins.json
cd C:\agent\vault; git log --oneline -1; (git ls-files | Measure-Object -Line).Lines
```
종료 코드: `0`

출력 원문
```
dataview             0.5.70     files: manifest.json,main.js,styles.css
templater-obsidian   2.25.0     files: manifest.json,main.js,styles.css
obsidian-git         2.38.6     files: manifest.json,main.js,styles.css

["dataview","templater-obsidian","obsidian-git"]

5d1a8bd Start the agent vault with its schema, plugins and first verified facts
19
```

사실 카드 2장(`FCT-2026-0810-001/002`)과 Dataview 대시보드를 함께 넣었다.

> **미완:** 원격 백업. GitHub 프라이빗 repo `agent-vault`가 아직 없어
> `git remote add`를 못 했다. 로컬 커밋까지만 서 있다.

날짜: 2026-08-10

---

## Phase 4 — Notion

### 주장 23: DB 3개 생성 + 쓰기/읽기 왕복 확인

OAuth는 이미 연결돼 있었다(주장 13의 부수 확인). 사람이 할 일이 없었다.

확인 명령: Notion MCP `create-database` ×3 → `create-pages` ×2 → `query-data-sources`

출력 원문 (읽기 결과)
```json
{"results":[
 {"Fact ID":"FCT-2026-0810-001","도메인":"40-brain","신뢰도":"verified","exit code":0,"검증일":"2026-08-10"},
 {"Fact ID":"FCT-2026-0810-002","도메인":"30-agents","신뢰도":"verified","exit code":0,"검증일":"2026-08-10"}
],"has_more":false}
```

생성된 것
```
Agent PC (부모 페이지)
├─ Runs   collection://e6ea9d39-c2a4-4c80-aa11-47b609e4f92e
├─ Facts  collection://dec075c6-af72-4198-b78b-34c9fc040642
└─ Refs   collection://6ea4703a-0894-47c7-8477-a433063ad73f
```

설계서 §7.3의 함정("페이지를 명시적으로 공유해야 한다")은 **이 경로에서는 발생하지
않는다** — 통합이 직접 만든 페이지는 자동으로 접근 권한을 갖는다.

날짜: 2026-08-10

---

## Phase 3 (완결) — GitHub 원격

### 주장 24: device flow로 인증하고 프라이빗 repo에 푸시했다

`gh auth login`은 TTY를 요구해 에이전트 셸에서 직접 못 돌린다. GitHub OAuth
**device flow**를 직접 구동해 우회했다. 토큰은 화면·로그에 출력되지 않았고
`gh` 자격증명 저장소로만 들어갔다.

확인 명령
```powershell
gh auth status
gh repo view kkw071223-ai/agent-vault --json name,visibility,isPrivate
cd C:\agent\vault; git push -u origin main
```
종료 코드: `0`

출력 원문
```
github.com
  ✓ Logged in to github.com account kkw071223-ai (keyring)
  - Token scopes: 'read:org', 'repo', 'workflow'

{"isPrivate":true,"name":"agent-vault","url":"https://github.com/kkw071223-ai/agent-vault","visibility":"PRIVATE"}

To https://github.com/kkw071223-ai/agent-vault.git
 * [new branch]      main -> main
push exit=0
```
날짜: 2026-08-11

---

## Phase 6 — Isaac Sim 6.0.1

### 주장 25: 무결성 확인 → 설치 → headless 기동 성공

확인 명령
```powershell
certutil -hashfile isaac-sim-standalone-6.0.1-windows-x86_64.zip MD5
tar -xf <zip> -C C:\isaacsim
C:\isaacsim\post_install.bat
C:\isaacsim\python.bat C:\agent\scratch\isaac_smoke.py
```
종료 코드: 전부 `0`

출력 원문
```
size: 10,600,096,696 bytes (9.87 GB)
actual  : c7fa3a830b251f10305cd7883039df9b
expected: c7fa3a830b251f10305cd7883039df9b
MATCH

tar exit=0  elapsed=200s

symbolic link created for extension_examples <<===>> exts\isaacsim.examples.interactive\...
"Symlink extension_examples created."
post_install exit=0

VERSION: 6.0.1-rc.7+release.42383.32955d8d.gl

[122.672s] Simulation App Startup Complete
Warp 1.13.0 initialized:
   CUDA Toolkit 12.9, Driver 13.2
   Devices:
     "cpu"      : "Intel64 Family 6 Model 198 Stepping 2, GenuineIntel"
     "cuda:0"   : "NVIDIA RTX PRO 5000 Blackwell Generation Laptop GPU" (24 GiB, sm_120, mempool enabled)
ISAAC OK
exit=0  elapsed=139s
```

**설계서 정정 3건**

| 설계서 | 실측 |
|---|---|
| `tar -xvzf` | ❌ 배포물은 zip이라 `-z`가 실패한다. **`tar -xf`가 맞다** |
| "첫 기동 셰이더 컴파일 10~30분" ⚠ | ❌ **139초**. §15의 ⚠ 항목 → `verified` |
| 하이브리드 그래픽은 설정 앱에서 수동 고정 | ⚠ `HKCU\Software\Microsoft\DirectX\UserGpuPreferences`에 `GpuPreference=2`로 등록해 자동화했다. **`.bat`이 아니라 실제 exe**(`kit\kit.exe`, `kit\python\python.exe`)에 걸어야 한다 |

`cuda:0`이 Intel이 아니라 RTX PRO 5000으로 잡힌 것이 고정이 먹었다는 증거다.

날짜: 2026-08-11

---

## Phase 8 — Ollama + VRAM 모드

### 주장 26: 모델 2종 설치, VRAM 반납 확인이 실제로 동작한다

확인 명령
```powershell
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/generate   # 8B 추론
powershell -File C:\agent\conductor\vram_mode.ps1 -Mode sim
```
종료 코드: `0`

출력 원문
```
NAME           ID              SIZE      MODIFIED
qwen2.5:14b    7cdf5a0187d5    9.0 GB    ...
llama3.1:8b    46e0c10c039e    4.9 GB    ...

response: OK. What's next?
9040 MiB          <- 로드됨

mode=sim vram_before=9040 MB
vram_after=0 MB  OK - SIM 진입 가능
vram_now=0 MB free=24463 MB
vram_mode(sim) exit=0
```

모델은 `C:\agent\models\ollama`에 13.0 GB로 저장됐다 — `OLLAMA_MODELS`가 먹었다.

> ⚠ **설계서 §4.1 추정치 정정 필요.** 8B Q4를 "~6 GB"로 추정했으나 실측 **9.0 GB**다
> (기본 컨텍스트 32768 포함). HEADLESS 모드에서 Isaac headless(~6GB)와 동시 상주하면
> 24 GB 중 15 GB를 쓰게 되어 여유가 설계서 표(11 GB)보다 훨씬 적다.
> 컨텍스트를 줄이거나 8B 상주를 재검토해야 한다.

날짜: 2026-08-11

---

## Phase 11 — 상시 가동화

### 주장 27: 예약 작업 2개 등록, 워치독이 중복 기동을 막는다

확인 명령
```powershell
Start-ScheduledTask -TaskName "AgentPC-Conductor"
Get-ScheduledTaskInfo -TaskName "AgentPC-Conductor"
```
종료 코드: `LastTaskResult = 0`

출력 원문
```
TaskName              State
--------              -----
AgentPC-Brain-Nightly Ready
AgentPC-Conductor     Ready

LastRunTime   : 08/11/2026 00:15:20
LastTaskResult: 0
NextRunTime   : 08/11/2026 00:16:00

AllowStartIfOnBatteries  : True
DontStopIfGoingOnBattery : True
ExecutionTimeLimit       : PT0S
WakeToRun (nightly)      : True
NextRun   (nightly)      : 08/11/2026 03:00:00
```

워치독은 이미 살아 있으면 아무것도 하지 않는다.
```
already running pid=31696,14644
start_conductor exit=0
```

### 주장 28: 그 두 PID는 중복 기동이 아니다

확인 명령
```powershell
Get-NetTCPConnection -State Established | Where-Object { $_.OwningProcess -in @(31696,14644) }
```
출력 원문
```
OwningProcess RemoteAddress   RemotePort  State
        14644 149.154.166.110        443  Established     <- api.telegram.org

pid=31696 parent=32132
pid=14644 parent=31696   <- venv 리디렉터가 낳은 자식
기동 배너 카운트: 1
```

venv의 `Scripts\python.exe`가 베이스 인터프리터를 자식으로 다시 띄운다. 텔레그램
소켓을 쥔 것은 **하나뿐**이고 기동 배너도 1회다. `make_environment.py`는 부모가
conductor인 프로세스를 제외해 인스턴스 수를 세도록 고쳤다 — 2 이상이면
`getUpdates` offset 경합으로 지시를 잃기 때문에 감시할 가치가 있다.

날짜: 2026-08-11

### 주장 29: ENVIRONMENT.md가 실측으로 생성된다 (§18.5)

확인 명령
```powershell
& .venv\Scripts\python.exe make_environment.py
```
종료 코드: `0`

출력 원문 (발췌)
```
| GPU / 드라이버 | NVIDIA RTX PRO 5000 Blackwell Generation Laptop GPU, 595.97, 24463 MiB | nvidia-smi |
| Node | v24.19.0 | node --version |
| Ollama 모델 | qwen2.5:14b, llama3.1:8b | ollama list |
| WSL | 배포판 없음 | wsl -l -v |
| 절전(AC/DC) | 0x00000000 / 0x00000708 | powercfg ... STANDBYIDLE |
| 뚜껑(AC/DC) | 0x00000000 / 0x00000001 | powercfg ... LIDACTION |
| Conductor 인스턴스 | 1개 | Get-CimInstance Win32_Process |
```

> 첫 생성본은 Node를 "미설치"로, Conductor를 "2개"로 잘못 적었다. 전자는 낡은 PATH를
> 든 프로세스에서 `shutil.which`를 쓴 탓(주장 10 정정과 동일한 함정), 후자는 venv
> 리디렉터를 센 탓이다. **둘 다 고친 뒤 재생성했다.** 자동 생성 문서가 틀리면
> 설계서보다 더 위험하다 — 에이전트가 이걸 "현재 상태"로 믿기 때문이다.

날짜: 2026-08-11

---

## Phase 9 — ⛔ 차단됨 (사용자 판단 필요)

### 주장 30: NVIDIA 스킬 설치가 auto 모드 분류기에 막혔다

확인 명령
```powershell
npx skills@latest add nvidia/skills --skill omniverse-cad-to-simready --agent claude-code --yes
```
결과: **실행되지 않음**

출력 원문
```
Permission for this action was denied by the Claude Code auto mode classifier.
Reason: Blocked by classifier.
```

우회하지 않았다. 이 저장소의 `CLAUDE.md`가 이미 경고하는 사항이기 때문이다 —
*"스킬은 전권으로 실행된다. 설치 후 `scripts/run.py`를 읽어보고 서명을 확인한다."*
원격 저장소의 설치 스크립트를 전권으로 실행하는 것은 분류기가 막아야 마땅한
동작이며, 여기서 억지로 뚫는 것은 설계 의도에 반한다.

**해소 방법 (둘 중 하나, 사용자 선택):**
1. `C:\Users\HP\.claude\settings.json`의 `permissions.allow`에
   `"Bash(npx skills:*)"` 추가
2. 사용자가 `!` 접두사로 직접 실행

날짜: 2026-08-11

---

## Phase 7 — WSL2 + Docker + GPU 패스스루

### 주장 31: `wsl --install` 은 이 PC에서 두 단계가 더 필요했다

재부팅(2026-08-11 07:13:42) 이후에도 `wsl.exe`는 여전히 "설치되어 있지 않다"고 했다.

확인 명령
```powershell
wsl.exe --install --no-distribution
```
종료 코드: **1**

출력 원문 (UTF-16LE로 다시 읽음)
```
Linux용 Windows 하위 시스템 설치되어 있지 않습니다. 'wsl.exe --install'을 실행하여 설치할 수 있습니다.
자세한 내용은 https://aka.ms/wslinstall 참조하세요.
```

진단 — 선택적 기능은 켜져 있었다. 빠진 것은 **WSL 앱 패키지** 쪽이었다.
```
Microsoft-Windows-Subsystem-Linux -> 상태 : 사용
VirtualMachinePlatform           -> 상태 : 사용
HypervisorPlatform               -> 상태 : 사용 안 함
Get-AppxPackage *WindowsSubsystemForLinux* -> count=0
winget list --id Microsoft.WSL             -> 일치하는 패키지 없음
```

`C:\Windows\System32\wsl.exe` (10.0.26100.1441)는 인박스 **런처**일 뿐이고,
실제 WSL은 별도 패키지다. 런처는 그것을 스스로 설치하지 못했다.

해소
```powershell
winget install --id Microsoft.WSL --silent --accept-source-agreements --accept-package-agreements
```
종료 코드: **0** — `설치 성공`, Microsoft.WSL 2.7.11

```
wsl.exe --version   ->  exit=0
WSL 버전: 2.7.11.0 / 커널 버전: 6.18.33.2-2 / Windows 버전: 10.0.26200.6725
```

> **설계서 정정.** §Phase 7과 preflight는 `wsl --install` 한 번이면 되는 것처럼
> 적었다. 이 PC에서는 ① 선택적 기능 활성화 → ② **재부팅** → ③ `winget install
> Microsoft.WSL` → ④ 배포판 설치, 네 단계였다. ①만 하고 재부팅하면 ②에서 멈춘다.

날짜: 2026-08-13

### 주장 32: Ubuntu-24.04가 서고 GPU가 드라이버 설치 없이 보인다

확인 명령
```powershell
wsl.exe --install -d Ubuntu-24.04 --no-launch
wsl.exe -l -v
```
종료 코드: **0**

출력 원문
```
  NAME            STATE           VERSION
* Ubuntu-24.04    Stopped         2
```

```
wsl -d Ubuntu-24.04 -- cat /etc/os-release | grep PRETTY   -> PRETTY_NAME="Ubuntu 24.04.4 LTS"
wsl -d Ubuntu-24.04 -- systemctl is-system-running          -> running   (exit=0)
wsl -d Ubuntu-24.04 -- id                                   -> uid=0(root)
```

`--no-launch`로 깔았으므로 OOBE(사용자 이름/암호 대화형 입력)를 건너뛰었고
기본 사용자는 root다. **의도한 상태다** — 이 배포판은 사람이 쓰는 셸이 아니라
Conductor 전용이고, 일반 사용자로 두면 자동화가 `sudo` 프롬프트에서 멈춰
재시도 3회를 그냥 태운다.

GPU — **WSL 안에 리눅스 NVIDIA 드라이버를 설치하지 않았다** (설계서 경고대로).
```
wsl -d Ubuntu-24.04 -- nvidia-smi     exit=0
NVIDIA-SMI 595.58.02   Driver Version: 595.97   CUDA Version: 13.2
0  NVIDIA RTX PRO 5000 Blac...  0MiB / 24463MiB
```
`/usr/lib/wsl/lib/libcuda.so.1` 이 Windows 드라이버로 스텁돼 있는 것도 확인했다.

날짜: 2026-08-13

### 주장 33: Docker Desktop이 서고 컨테이너에서 GPU가 보인다 (Phase 7 ✔ 확인)

```powershell
winget install --id Docker.DockerDesktop -e --silent ...   -> exit=0, Docker Desktop 4.85.0
docker version                                             -> exit=0, Server: Docker Desktop 4.85.0, Engine 29.6.2
```

첫 `docker run`은 실패했다.
```
docker: error getting credentials - err: exec: "docker-credential-desktop": executable file not found in %PATH%
exit=127
```
**주장 10과 같은 낡은 PATH 함정이다.** 설치 관리자가 PATH에 추가한
`C:\Program Files\Docker\Docker\resources\bin`을 이미 떠 있던 셸이 모른다.
해당 경로를 세션 PATH 앞에 붙여 해결했다 — Docker 설정 문제가 아니다.

확인 명령 (설계서 §Phase 7 ✔ 확인 원문 그대로)
```powershell
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```
종료 코드: **0**

출력 원문
```
Status: Downloaded newer image for nvidia/cuda:12.8.0-base-ubuntu24.04
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 595.58.02              Driver Version: 595.97         CUDA Version: 13.2     |
|   0  NVIDIA RTX PRO 5000 Blac...    On  |   00000000:02:00.0 Off |                  Off |
| N/A   52C    P2             18W /  113W |       0MiB /  24463MiB |      0%      Default |
+-----------------------------------------------------------------------------------------+
```

`nvidia-container-toolkit`은 **설치하지 않았다.** 설계서가 "위 `docker run`이
실패할 때만"이라고 단서를 달았고, 실패하지 않았다.

WSL 통합도 켰다 (`settings-store.json`의 `EnableIntegrationWithDefaultWslDistro`,
`IntegratedWslDistros`, `AutoStart`). Docker Desktop이 떠 있는 동안 이 파일을
고치면 종료 시 되돌려 쓰므로 **내리고 고친 뒤 다시 띄웠다.**
```
wsl -d Ubuntu-24.04 -- docker version --format '{{.Server.Version}}'   -> 29.6.2  exit=0
wsl -d Ubuntu-24.04 -- docker run --rm --gpus all nvidia/cuda:... nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
   -> NVIDIA RTX PRO 5000 Blackwell Generation Laptop GPU, 24463 MiB   exit=0
```

**NemoClaw / Hermes는 설치하지 않았다** — 사용자 지시대로 건너뛴 선택 항목이다.

날짜: 2026-08-13

---

## Phase 9 — NVIDIA 스킬 (주장 30의 차단 해소됨)

### 주장 34: 스킬 8개 중 7개가 설치됐다

주장 30에서 막혔던 명령이 이번에는 그대로 통과했다. 우회하지 않았고, 명령도
설계서 원문과 같다.

확인 명령
```powershell
npx --yes skills@latest add nvidia/skills --skill omniverse-cad-to-simready --agent claude-code --yes
```
종료 코드: **0**

출력 원문 (발췌)
```
o  Found 335 skills
o  Security Risk Assessments -----------------------------------------------+
|                             Gen               Socket            Snyk      |
|  omniverse-cad-to-simready  High Risk         0 alerts          Med Risk  |
+---------------------------------------------------------------------------+
o  Installed 1 skill
   ✓ omniverse-cad-to-simready (copied) → .\.claude\skills\omniverse-cad-to-simready
—  Done!  Review skills before use; they run with full agent permissions.
```

설치 결과
```
.claude/skills/
  amc-setup-calibration-stack
  deepstream-dev
  deepstream-generate-pipeline
  deepstream-profile-pipeline
  omniverse-cad-to-simready
  omniverse-realtime-viewer
  omniverse-usd-performance-tuning
```

`.claude/skills/`는 이 repo `.gitignore`에 이미 등재돼 있다 — 저장소가 처음부터
스킬을 여기에 두도록 설계돼 있었다는 뜻이다. 커밋되지 않는다.

**`nemoclaw-user-guide`만 빠졌다.** 두 번 시도했고 두 번 다 분류기에 막혔다
(설치된 7개와 완전히 같은 형태의 명령이다 — 분류기 판정이 간헐적이다).
3회 규칙에 따라 멈췄다. 이 스킬은 **건너뛰기로 한 NemoClaw의 사용 안내서**이므로
없어도 나머지에 영향이 없다. 필요해지면 그때 한 줄이면 된다.

설치물에 `skill.oms.sig` 서명 파일이 각각 들어 있다. 실행 전 검증은
`CLAUDE.md` 규칙대로 사용하는 시점에 한다.

날짜: 2026-08-13

---

## Phase 10 — 도메인 워크스페이스 + 파이프라인

### 주장 35: WSL에서 `./scripts/bootstrap_env.sh`가 CRLF 때문에 즉사했다

확인 명령
```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/agent/repos/dev-standard-template && ./scripts/bootstrap_env.sh"
```
종료 코드: **127**

출력 원문
```
/usr/bin/env: ‘bash\r’: No such file or directory
/usr/bin/env: use -[v]S to pass options in shebang lines
```

원인은 저장소가 아니라 **체크아웃 설정**이었다. 커밋된 blob은 LF다.
```
git show HEAD:scripts/bootstrap_env.sh | head -c 40 | od -c
   #  !  /  u  s  r  /  b  i  n  /  e  n  v     b  a  s  h  \n
git config --get core.autocrlf   ->  true      (이 저장소 로컬 설정)
```
`core.autocrlf=true`가 체크아웃하면서 CRLF를 붙였고, 리눅스 셔뱅이 깨졌다.

해소 — `core.autocrlf=false` + 워크트리의 `.sh` 정규화. 커밋 blob이 이미 LF라
**git diff는 비어 있다**(즉, 저장소를 바꾼 것이 아니라 되돌린 것이다).

> **주의.** 이 저장소는 Windows에서 편집하고 WSL에서 실행한다. `.sh`가 CRLF로
> 체크아웃되면 셔뱅에서 즉사한다. `.gitattributes`가 없으므로 클론할 때마다
> 이 설정을 확인해야 한다. [[FCT-2026-0813-006]]

날짜: 2026-08-13

### 주장 36: 두 venv가 Python 3.12.3에서 구축된다 (설계서는 3.11 검증)

확인 명령
```bash
cd /mnt/c/agent/repos/dev-standard-template && ./scripts/bootstrap_env.sh
```
종료 코드: **0**

출력 원문
```
==> Omniverse venv  ->  .../.venv-ov
  usd-exchange  : 2.3.0
  ovstage      : 0.1.0.346039
  ovphysx      : 0.5.9
  ovrtx        : 0.4.0
  ovstream     : 0.4.5
  ovstorage    : 0.1.0
  newton       : 1.4.0
  warp         : 1.15.0

==> SimReady venv  ->  .../.venv-simready
  simready-validate: 2026.4.9
```

`requirements-ov.txt` 머리말은 "Python 3.11.15에서 검증"이라고 적고 있지만
Ubuntu 24.04의 기본 3.12.3에서 전부 설치되고 임포트된다. usd-core가
`$OV_VENV`에 섞이지 않은 것도 스크립트 자체 검사가 통과했다.

날짜: 2026-08-13

### 주장 37: 픽스처 4개가 전부 실패했다 — `simready-validate`가 리포트를 아예 안 썼다

확인 명령
```bash
./scripts/run_pipeline.sh examples/urdf/arm2.urdf
```
종료 코드: **1** (네 픽스처 모두 동일)

출력 원문
```
[3] SimReady baseline (Prop-Robotics-Neutral)
      not yet conformant (expected for freshly converted assets)
      (no report: [Errno 2] No such file or directory: '.../simready-before.json')
...
[6] SimReady re-validation
      (no report: [Errno 2] No such file or directory: '.../simready-after.json')
    ✗ [FAILED] Prop-Robotics-Neutral v1.0.0 — residual requirements need an agent

  SimReady before : FAIL
  SimReady after  : FAIL
pipeline FAILED
```

변환·USD 검증·컨포먼스·물리 스모크는 **전부 통과했다.** 실패는 한 지점뿐이다.

`simready-after.json.log` 원문이 이유를 그대로 담고 있었다.
```
File ".../simready-foundation/nv_core/sr_specs/docs/capabilities/core/atomic_asset/validation.py", line 20
    from usd_validation_nvidia import (
ModuleNotFoundError: No module named 'usd_validation_nvidia'
```

스펙은 **`.venv-simready` 안으로 임포트되는 실행 가능한 Python**인데,
`requirements-simready.txt`에 `usd-validation-nvidia`가 없었다
(`requirements-ov.txt`에만 있다). 프로파일 로딩이 죽으면 CLI는 `--output`을
**아예 만들지 않는다** — 그래서 "검증 실패"가 아니라 "파일 없음"으로 보였다.

해소: `.venv-simready`에 `usd-validation-nvidia==1.20.0` 추가.
이 패키지는 **의존성이 없어서**(`Requires:` 비어 있음) usd-exchange를 끌고 오지
않는다. `usd-core 26.8`도 그대로다 — CLAUDE.md의 두-OpenUSD 금지 규칙은 유지된다.
`scripts/requirements-simready.txt`에 이유와 함께 고정했다.

날짜: 2026-08-13

### 주장 38: 그래도 실패했다 — 상류 스펙이 저장소보다 앞서 나가 있었다

`usd-validation-nvidia`를 넣자 검증기는 돌기 시작했지만 결과는 여전히 FAIL이었다.

출력 원문
```
ERROR:SimReady Validation:Error loading file .../sr_specs/docs/profiles/profiles.toml: FileNotFoundError(2, ...)
WARNING:SimReady Validation:Profile Prop-Robotics-Neutral not found.
  [FAILED] Prop-Robotics-Neutral v1.0.0
```
리포트의 `features_summary`가 `{}`였다 — 아무것도 검사하지 않았다는 뜻이다.

`bootstrap_env.sh`는 스펙을 `git clone --depth 1 -b main`으로, 즉 **고정 없이**
받고 있었다. 받아온 것은 2026-08-03자 릴리스였다.
```
0ed0dfb 2026-08-03 11:26:47 -0700 SimReady Foundation Release 2026.06.0
```
이 릴리스는 `profiles.toml` 하나를 프로파일별 TOML로 쪼갰다
(`prop_robotics_neutral.toml` 등). `--profiles-path .../profiles.toml`은
존재하지 않는 파일을 가리키게 됐다.

프로파일 경로를 새 파일로 바꿔 직접 돌려 보니 **두 번째 문제**가 드러났다.
```
  [FAILED] Prop-Robotics-Neutral v1.0.0
           FET005_BASE_NEUTRAL: failing requirements: ['PMT.001']
           FET000_CORE: failing requirements: ['NP.005']

  Rule: capabilities.core.naming_paths.validation.AssetFolderStructureChecker
  Message: Main asset file 'arm2.usda' must reside in an intermediate folder under an
           asset root folder whose name the file name contains. ...

  Rule: capabilities.physics_bodies.physics_materials.validation.PhysicsMaterialsCapabilityChecker
  Severity: IssueSeverity.ERROR
  Message: Uncaught error: type object 'Tokens' has no attribute 'physics'
```

- **NP.005** — 폴더 구조 규칙의 의미 자체가 바뀌었다.
- **PMT.001** — 자산 문제가 아니라 **새 스펙 코드가 이 저장소가 고정한
  `usd-core 26.8`에서 터지는 것**이다. 자산을 고쳐서 통과시킬 수 있는 종류가 아니다.

즉 상류를 쫓아가는 것은 답이 아니었다. 저장소는 2026-07-25에 검증됐고 릴리스는
그 **뒤인** 08-03에 나왔다.

해소 — 스펙 체크아웃을 wheel과 똑같이 **고정**했다.
```
SIMREADY_FOUNDATION_REF="${SIMREADY_FOUNDATION_REF:-4d9f3bb}"
```
`4d9f3bb` (2026-07-13)이 검증 시점의 트리다.

> **설계서·저장소 정정.** `git clone --depth 1 -b main`은 재현 가능한 부트스트랩이
> 아니다. 스펙은 문서가 아니라 **venv 안에서 실행되는 코드**이므로 wheel과 동일한
> 고정 대상이다. CLAUDE.md의 "이 생태계는 2026년 7월에 나왔고 계속 바뀐다"가
> 정확히 이 경우를 말한다. [[FCT-2026-0813-007]]

날짜: 2026-08-13

### 주장 39: 픽스처 4개 + 단위 시험이 전부 통과한다 (Phase 10 ✔ 확인)

확인 명령 (설계서 §Phase 10 ✔ 확인 원문 그대로)
```bash
./scripts/run_pipeline.sh examples/urdf/arm2.urdf
./scripts/run_pipeline.sh examples/mujoco/cartpole.xml
./scripts/run_pipeline.sh examples/drawing/bracket.dxf
DXF_THICKNESS=0.006 DXF_LAYERS=OUTLINE,HOLES DXF_UNITS=mm DXF_CHAIN_TOL=0.01 \
  ./scripts/run_pipeline.sh examples/drawing/messy.dxf
.venv-ov/bin/python scripts/test_drawing_to_usd.py
```

종료 코드
```
EXIT_arm2=0
EXIT_cartpole=0
EXIT_bracket=0
EXIT_messy=0
EXIT_tests=0
```

기능 수 — CLAUDE.md의 표와 정확히 일치한다.
```
arm2     : 6/6 features  profile=Prop-Robotics-Neutral
cartpole : 6/6 features  profile=Prop-Robotics-Neutral
bracket  : 5/5 features  profile=Prop-Static-Neutral
messy    : 5/5 features  profile=Prop-Static-Neutral
```

arm2 재검증 원문
```
[6] SimReady re-validation
      PASS FET000_CORE
      PASS FET001_BASE_NEUTRAL
      PASS FET003_BASE_NEUTRAL
      PASS FET004_BASE_NEUTRAL
      PASS FET005_BASE_NEUTRAL
      PASS FET006_BASE_MDL
    ✓ [PASSED] Prop-Robotics-Neutral v1.0.0

[7] Physics smoke test (ovphysx, 120 steps)
    ✓ SIMULATED 120 steps OK (dt=0.016667)

  SimReady before : FAIL
  SimReady after  : PASS
pipeline OK
```

기준선(FAIL)이 CLAUDE.md가 서술한 코드와 일치하는 것도 확인했다 — 특히
`VM.MAT.001`은 **MuJoCo 경로에만** 뜬다(URDF는 `<material>`에서 비주얼 머티리얼을
내보내므로). 문서가 설명한 그대로다.
```
arm2     기준선 FAIL: NP.005 NP.006 RB.006 GSP.001 PMT.001
cartpole 기준선 FAIL: NP.005 NP.006 RB.006 GSP.001 VM.MAT.001
```

단위 시험 원문 (끝부분)
```
segment chaining (opt-in, for exploded profiles)
  PASS  4 lines form one loop              closed=1 leftover=0
  PASS  segments given reversed            closed=1 leftover=0
  PASS  gap 0.05, tol 0.01 -> open         closed=0 leftover=4
  PASS  gap 0.05, tol 0.10 -> closed       closed=1 leftover=0
  PASS  two separate loops                 closed=2 leftover=0
  PASS  dangling segment is reported       closed=1 leftover=1

all checks passed
```

고친 `bootstrap_env.sh`가 멱등한 것도 다시 확인했다.
```
==> SimReady Foundation specs
  pinned at 4d9f3bb 2026-07-13 14:54:01 -0700
  features: 52   capabilities: 13
bootstrap_rerun_exit=0
```

날짜: 2026-08-13

---

## Phase 11 — 설계서 폐기(§18) + 엔드투엔드 검증

### 주장 40: Ollama 가 재부팅 뒤 모델을 잃었고, 고치는 도중 설치가 깨졌다

`make_environment.py` 가 "Ollama 모델: 없음"으로 찍었다. **모델 파일은 디스크에
그대로 있었다.**

확인 명령
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```
종료 코드: **0** (그런데 목록이 비었다)

출력 원문
```
NAME    ID    SIZE    MODIFIED
```

서버 로그가 이유를 담고 있었다.
```
level=INFO source=routes.go:1933 msg="server config" env="map[... OLLAMA_MODELS:C:\Users\HP\.ollama\models ...]"
level=INFO source=model_list_cache.go:112 msg="model list cache hydration complete" models=0
```
사용자 환경변수는 `C:\agent\models\ollama` 인데 **서버는 기본 경로를 썼다.**
트레이 앱을 재시작해도 같았다.

경로를 맞추려고 트레이 앱을 `Stop-Process -Force` 한 것이 **진행 중이던 자동
업데이트를 끊었다.**
```
Error: 500 Internal Server Error: error starting llama-server:
llama-server binary not found (checked: ...\lib\ollama\llama-server.exe, ...)

lib\ollama\  ->  비어 있음
is-8VMTOVSKVQ.tmp   <- Inno Setup 잔해
winget list --id Ollama.Ollama  ->  설치됨 0.32.6 / 사용 가능 0.32.9
```

해소 — 지우지 않고 복사부터 했다.
```
robocopy C:\agent\models\ollama %USERPROFILE%\.ollama\models /E    12 files, 12.953 GB
winget upgrade --id Ollama.Ollama --silent                        설치 성공, exit=0
```

검증
```
> ollama list
qwen2.5:14b    9.0 GB
llama3.1:8b    4.9 GB

> ollama run llama3.1:8b "Reply with exactly: OLLAMA OK"
OLLAMA OK                                    exit=0

> nvidia-smi --query-gpu=memory.used --format=csv,noheader
9042 MiB

> ollama ps
llama3.1:8b   9.2 GB   100% GPU   32768

> vram_mode.ps1 -Mode sim
mode=sim vram_before=9042 MB
vram_after=0 MB  OK - SIM 진입 가능           exit=0
```

새 위치에서 추론이 되는 것을 **확인한 뒤에** 중복본을 지우고, 서버가 무시하는
`OLLAMA_MODELS` 사용자 변수를 해제했다. 무시되는 변수를 남겨두면 다음에 이
자리에서 또 한 시간을 쓴다. [[FCT-2026-0813-009]]

> **설계서 정정.** §Phase 8 의 "모델 저장 위치를 D 드라이브로"는 D: 가 있는 PC
> 전제였다. 이 PC 에는 D: 가 없고, 게다가 이 버전의 앱은 `OLLAMA_MODELS` 를
> 읽지 않는다. 단일 볼륨에서 경로를 옮겨 얻는 것이 없으므로 기본 경로를 쓴다.

날짜: 2026-08-13

### 주장 41: 설계서 §18 분해를 실행했다

설계서가 스스로 지시한 폐기 절차다. 다섯 갈래 전부 실행했다.

| 설계서 절 | 옮긴 곳 | 확인 |
|---|---|---|
| §9 §10 §12 | `C:\agent\domains\*\CLAUDE.md` ×5 | 각 65행. 재시도·게이트·금지·그림 규칙 포함 |
| §3 §6 §7 §8 | `vault/90-meta/architecture.md` | 신규 |
| §2 §4 §5 | `vault/90-meta/ENVIRONMENT.md` | **자동 생성**, 실측 |
| §1 | `vault/40-refs/REF-nvidia-stack-2026-08.md` | `reported` 로 명시 |
| §13 §15 §17 + preflight | `vault/90-meta/archive/2026-08-setup/` | 동결, README 포함 |

설계서 본문 머리에 퇴역 배너를 달았다 — 어디를 대신 읽어야 하는지 표로.

`ENVIRONMENT.md` 재생성 결과 (발췌)
```
| WSL | * Ubuntu-24.04  Running  2 / docker-desktop  Running  2 | wsl -l -v |
| WSL 버전 | 2.7.11.0 | wsl --version |
| Docker 엔진 | 29.6.2 | docker version |
| 컨테이너 GPU | NVIDIA RTX PRO 5000 Blackwell Generation Laptop GPU | docker run --gpus all ... nvidia-smi |
| 파이프라인 venv | .venv-ov, .venv-simready | Test-Path ... |
| Ollama 모델 | qwen2.5:14b, llama3.1:8b | ollama list |
| Conductor 인스턴스 | 1개 | Get-CimInstance Win32_Process |
```

사실 카드 4장을 새로 썼다: `FCT-2026-0813-006` ~ `009`.
`FLOW-CAD-001` 도 썼다 — DXF 플로우가 **두 번** 성공했기 때문이다(bracket, messy).
설계서 §18.3 이 "두 번째 성공 뒤에 쓴다"고 못박은 그 시점이다.

날짜: 2026-08-13

### 주장 42: 상태기계 한 바퀴가 실제로 돈다 (양성)

`conductor.py` 의 함수를 **그대로** 써서 한 바퀴를 돌렸다. 흉내내지 않았다.
`state.json` 만 건드리지 않았다 — 상주 Conductor 가 같은 파일의 getUpdates
offset 을 들고 있어 덮어쓰면 폰에서 보낸 지시를 잃는다.

확인 명령
```powershell
.venv\Scripts\python.exe e2e_check.py "<bracket.dxf 를 inspect_dxf.py 로 조사하고
  원문·JSON·막대그래프를 artifacts 에 남겨라>" 10-cad2sim
```
종료 코드: **0**

출력 원문
```
[e2e] EXECUTE  domain=10-cad2sim cwd=C:\agent\domains\10-cad2sim
[e2e] claude exit=0
[e2e] VERIFY  (별도 프로세스)
[e2e] verify={"by": "verify.py", "exit": 0, "output": "[verify] run=20260813-2350-e2e
[verify] artifacts=3
[verify]   inspect.json  2411 bytes
[verify]   inspect.txt  1227 bytes
[verify]   loops.png  45859 bytes
[verify] figures=1
[verify] inspect.json keys=['closed_profiles', 'entities', 'extents', 'file', 'layers',
         'mass_preview', 'profile_area', 'source', 'suggested_next_step', 'units']
[verify] ok"}

✅ 20260813-2350-e2e  [10-cad2sim]
결과   PASS · 4m11s · 재시도 0회
검증   verify.py exit=0
```

**환각 대조.** 에이전트가 저장한 `inspect.txt` 와, 내가 따로 돌린 같은 명령의
출력을 diff 했다.
```
diff /tmp/mine.txt /tmp/theirs.txt   ->  차이 없음
```
지어낸 숫자가 없다. 그림(`loops.png`, 45,859 bytes)도 실제 값과 일치한다 —
HOLES 5, PROFILE 1, 8 entities / 4 layers / 6 closed profiles.

날짜: 2026-08-13

### 주장 43: 검증기는 속지 않는다 (음성)

양성 시험만으로는 "성공은 자기 보고로 성립하지 않는다"는 성질이 증명되지 않는다.
그림 없는 런을 일부러 만들어 넣었다.

확인 명령
```powershell
.venv\Scripts\python.exe negtest.py
```
종료 코드: **0** (= 검증기가 제대로 거부했다)

출력 원문
```
verify exit = 1
[verify] artifacts=1
[verify]   notes.txt  35 bytes
[verify] figures=0
[verify] FAIL: 그림이 0장 — §18.4 위반 (플롯 PNG 최소 1장)
[verify] FAIL: artifacts/ 에 summary.json|inspect.json|report.json 이 없다

❌ 20260813-neg-test  [10-cad2sim]
결과   FAIL · 0m03s · 재시도 2회
검증   verify.py exit=1

마지막 오류 (원문):
  [verify] FAIL: 그림이 0장 — §18.4 위반 (플롯 PNG 최소 1장)
  [verify] FAIL: artifacts/ 에 summary.json|inspect.json|report.json 이 없다
```

리포트가 FAIL 로 떨어지고 실패 로그가 **원문 그대로** 올라온다(§10.3 ④).
시험이 끝난 뒤 조작된 런 폴더는 지웠다 — 남겨두면 나중에 진짜 이력으로 읽힌다.

날짜: 2026-08-13

### 주장 44: 텔레그램이 평문 지시를 받는다

폰에서 명령어를 외우게 만들면 결국 안 쓰게 된다. 슬래시 없는 평문을 `/ask`
(조사 전용, 실행하지 않음)로 돌리도록 `handle()` 을 고쳤다.

```
selftest.py  ->  all checks passed   exit=0
```

Conductor 는 재부팅 후 로그온 트리거로 자동 기동했고 2일 넘게 살아 있다.
```
ProcessId ParentProcessId CreationDate
    15364           13440 2026-08-11 오전 7:15:19
    15432           15364 2026-08-11 오전 7:15:19
instances=1        (venv 리디렉터라 프로세스는 2개, 논리적으로는 1개)
```
그동안 폰에서 보낸 메시지도 큐에 남아 있었다 — 텔레그램 24시간 보관이 실제로
동작한다는 두 번째 증거다.

날짜: 2026-08-13
