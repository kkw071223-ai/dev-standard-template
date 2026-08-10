<#
    00-preflight.ps1 — turn the design's assumptions into facts.

    docs/07-agent-pc-design.md §15 lists seven things marked "assumed". Every
    later phase is built on them, so they get checked before anything is
    installed. Nothing here writes to the system: it reads, and it makes a few
    outbound HEAD requests to confirm the endpoints the design depends on are
    actually reachable from this network.

    Run in a normal PowerShell window — administrator is not required.

        powershell -ExecutionPolicy Bypass -File .\00-preflight.ps1

    Writes preflight-report.txt next to itself. Send that file back.
#>

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$out  = [System.Collections.Generic.List[string]]::new()
function Say([string]$s) { Write-Host $s; $out.Add($s) }
function Head([string]$s) { Say ""; Say "== $s $('=' * [Math]::Max(0, 58 - $s.Length))" }

Head "PREFLIGHT  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# ── OS ────────────────────────────────────────────────────────────────────
Head "OS"
$os = Get-CimInstance Win32_OperatingSystem
Say ("edition   : {0}" -f $os.Caption)
Say ("version   : {0} (build {1})" -f $os.Version, $os.BuildNumber)
Say ("uptime    : {0:dd}d {0:hh}h {0:mm}m" -f ((Get-Date) - $os.LastBootUpTime))

# ── CPU / RAM ─────────────────────────────────────────────────────────────
Head "CPU / RAM"
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Say ("cpu       : {0}" -f $cpu.Name.Trim())
Say ("cores     : {0} physical / {1} logical" -f $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
Say ("ram       : {0:N0} GB" -f ($os.TotalVisibleMemorySize / 1MB))

# ── Chassis: laptop or desktop ────────────────────────────────────────────
# The design assumes a mobile workstation (lid, battery, AC/DC power policy).
Head "CHASSIS"
$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($bat) {
    Say "type      : LAPTOP (battery present)"
    Say ("battery   : status {0}, charge {1}%" -f $bat.BatteryStatus, $bat.EstimatedChargeRemaining)
} else {
    Say "type      : DESKTOP (no battery) <- design assumed a laptop; tell me"
}

# ── GPU / driver ──────────────────────────────────────────────────────────
# Isaac Sim 6.0.1 needs Windows driver 595.97 or newer.
Head "GPU"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $q = (nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader) 2>&1
    Say ("nvidia-smi: {0}" -f ($q -join ' | '))
    $drv = ($q -split ',')[-1].Trim()
    if ($drv -as [version] -and [version]$drv -lt [version]'595.97') {
        Say "  !! driver below 595.97 — Isaac Sim 6.0.1 requires 595.97+. Update first."
    } elseif ($drv) {
        Say "  ok: driver meets the Isaac Sim 6.0.1 minimum (595.97)"
    }
} else {
    Say "nvidia-smi: NOT FOUND — NVIDIA driver missing or not on PATH"
}
Get-CimInstance Win32_VideoController | ForEach-Object {
    Say ("adapter   : {0}" -f $_.Name)
}

# ── Disks ─────────────────────────────────────────────────────────────────
# The design wants ~270 GB: Isaac Sim 50 + assets 100 + WSL/Docker 60 +
# models 40 + vault/runs 20.
Head "DISKS"
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    Say ("{0}  {1,7:N0} GB free of {2,7:N0} GB" -f $_.DeviceID, ($_.FreeSpace/1GB), ($_.Size/1GB))
}
$d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction SilentlyContinue
if ($d) {
    Say ("D: exists, {0:N0} GB free — target for D:\agent" -f ($d.FreeSpace/1GB))
    if ($d.FreeSpace/1GB -lt 300) { Say "  !! under 300 GB — skip the Isaac asset pack for now" }
} else {
    Say "D: does not exist — the design falls back to C:\agent"
}

# ── Power policy ──────────────────────────────────────────────────────────
# Normal state is AC, lid open, never sleeping. The lid setting still matters
# because the lid does get closed sometimes, and the machine must keep running.
Head "POWER"
$lidAc = (powercfg /q SCHEME_CURRENT SUB_BUTTONS LIDACTION | Select-String 'Current AC Power Setting Index') -replace '.*:\s*',''
$lidDc = (powercfg /q SCHEME_CURRENT SUB_BUTTONS LIDACTION | Select-String 'Current DC Power Setting Index') -replace '.*:\s*',''
$slpAc = (powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE  | Select-String 'Current AC Power Setting Index') -replace '.*:\s*',''
Say ("lid close (AC) : {0}   [0=do nothing 1=sleep 2=hibernate 3=shutdown]" -f $lidAc)
Say ("lid close (DC) : {0}" -f $lidDc)
Say ("sleep idle (AC): {0}   [0x0 = never]" -f $slpAc)
Say ("active scheme  : {0}" -f ((powercfg /getactivescheme) -replace '.*\(|\)',''))
Say "sleep states available:"
(powercfg /a) -split "`r?`n" | Where-Object { $_.Trim() } | ForEach-Object { Say ("  " + $_.Trim()) }

# ── Already installed ─────────────────────────────────────────────────────
Head "EXISTING TOOLS"
foreach ($t in 'winget','git','python','python3','node','npm','npx','docker','wsl','claude','ollama','code','pwsh','curl') {
    $c = Get-Command $t -ErrorAction SilentlyContinue
    if ($c) {
        $v = try { (& $t --version 2>&1 | Select-Object -First 1) } catch { '?' }
        Say ("{0,-8} : {1}" -f $t, $v)
    } else {
        Say ("{0,-8} : -" -f $t)
    }
}

# ── WSL ───────────────────────────────────────────────────────────────────
Head "WSL"
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    ((wsl -l -v) 2>&1 | Out-String) -replace "`0","" -split "`r?`n" |
        Where-Object { $_.Trim() } | ForEach-Object { Say ("  " + $_.Trim()) }
} else {
    Say "  wsl not present — Phase 0 installs it"
}

# ── winget package ids ────────────────────────────────────────────────────
# §15 marks these as assumed. Resolve them now rather than failing mid-install.
Head "WINGET PACKAGE IDS"
if (Get-Command winget -ErrorAction SilentlyContinue) {
    foreach ($id in 'Git.Git','Python.Python.3.11','OpenJS.NodeJS.LTS','Obsidian.Obsidian',
                    'Docker.DockerDesktop','Microsoft.VisualStudioCode','Microsoft.PowerShell',
                    '7zip.7zip','Ollama.Ollama','Anthropic.ClaudeCode') {
        $r = (winget show --id $id -e --disable-interactivity 2>&1 | Out-String)
        $ok = if ($r -match 'Found ') { 'OK' } else { 'NOT FOUND' }
        Say ("{0,-30} {1}" -f $id, $ok)
    }
} else {
    Say "winget missing — install 'App Installer' from the Microsoft Store first"
}

# ── Network ───────────────────────────────────────────────────────────────
# This is the one most likely to sink the design. A corporate proxy that
# blocks Telegram takes out the whole command-and-report channel (§8).
Head "NETWORK REACHABILITY"
$urls = [ordered]@{
    'downloads.isaacsim.nvidia.com' = 'https://downloads.isaacsim.nvidia.com/'
    'api.telegram.org  (CRITICAL)'  = 'https://api.telegram.org/'
    'workers.dev       (CRITICAL)'  = 'https://workers.cloudflare.com/'
    'mcp.notion.com'                = 'https://mcp.notion.com/'
    'claude.ai'                     = 'https://claude.ai/'
    'api.anthropic.com'             = 'https://api.anthropic.com/'
    'github.com'                    = 'https://github.com/'
    'registry.npmjs.org'            = 'https://registry.npmjs.org/'
    'pypi.org'                      = 'https://pypi.org/'
    'ngc.nvidia.com'                = 'https://ngc.nvidia.com/'
    'integrate.api.nvidia.com'      = 'https://integrate.api.nvidia.com/'
    'ollama.com'                    = 'https://ollama.com/'
    'registry-1.docker.io'          = 'https://registry-1.docker.io/'
}
foreach ($k in $urls.Keys) {
    $code = (curl.exe -s -o NUL -w "%{http_code}" -m 10 -I $urls[$k]) 2>&1
    $verdict = if ($code -match '^[2345]\d\d$' -and $code -ne '000') { "reachable ($code)" } else { "BLOCKED ($code)" }
    Say ("{0,-32} {1}" -f $k, $verdict)
}
Say ""
Say "proxy env: HTTP_PROXY=$env:HTTP_PROXY HTTPS_PROXY=$env:HTTPS_PROXY"

Head "DONE"
$path = Join-Path $PSScriptRoot 'preflight-report.txt'
$out -join "`r`n" | Set-Content -Path $path -Encoding UTF8
Write-Host ""
Write-Host "report written: $path" -ForegroundColor Green
Write-Host "Send that file back before installing anything." -ForegroundColor Green
