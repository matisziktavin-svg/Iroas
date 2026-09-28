# Iroas setup - run via setup.bat (double-click). Safe to run again any time:
# it keeps what already works and only asks about what's missing or broken.
#
#   setup.bat                 normal install / repair
#   setup.bat -RefreshClaude  get a new Claude login token (when Iroas says the login expired)

param([switch]$RefreshClaude)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-Location -Path $PSScriptRoot
$Root = $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"

function Say($msg, $color = "Gray") { Write-Host $msg -ForegroundColor $color }
function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $msg" -ForegroundColor Red
    exit 1
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Have-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }

function Winget-Install($id, $name) {
    if (-not (Have-Winget)) {
        Fail "$name is missing and 'winget' isn't available to install it. Install '$name' manually (see the README), then run setup.bat again."
    }
    Say "Installing $name (a window may ask for permission - click Yes)..." Yellow
    winget install -e --id $id --accept-source-agreements --accept-package-agreements --silent
    Refresh-Path
}

# Returns the path of a working Python >= 3.10, or $null.
function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.13", "3.12", "3.11", "3.10")) {
            try {
                $p = (& py "-$v" -c "import sys; print(sys.executable)" 2>$null)
                if ($LASTEXITCODE -eq 0 -and $p) { $candidates += $p.Trim() }
            } catch {}
        }
    }
    $candidates += (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
                    Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    foreach ($c in $candidates) {
        try {
            & $c -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch {}
    }
    return $null
}

function Read-EnvFile {
    $vals = @{}
    if (Test-Path $EnvFile) {
        foreach ($line in Get-Content $EnvFile) {
            if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $vals[$Matches[1]] = $Matches[2].Trim() }
        }
    }
    return $vals
}

function Write-EnvFile($vals) {
    $lines = @(
        "# Written by setup.bat. Keep this file private - it holds your keys.",
        "CLAUDE_CODE_OAUTH_TOKEN=$($vals['CLAUDE_CODE_OAUTH_TOKEN'])",
        "TELEGRAM_BOT_TOKEN=$($vals['TELEGRAM_BOT_TOKEN'])",
        "HEVY_API_KEY=$($vals['HEVY_API_KEY'])",
        "PAIRING_CODE=$($vals['PAIRING_CODE'])",
        "IROAS_MODEL=$($vals['IROAS_MODEL'])"
    )
    # UTF-8 without BOM so Python reads the first key correctly.
    [IO.File]::WriteAllText($EnvFile, ($lines -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
}

function Test-Telegram($token) {
    try {
        $r = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getMe" -TimeoutSec 20
        if ($r.ok) { return $r.result.username }
    } catch {}
    return $null
}

function Test-Hevy($key) {
    try {
        $r = Invoke-RestMethod -Uri "https://api.hevyapp.com/v1/user/info" -Headers @{ "api-key" = $key } -TimeoutSec 20
        if ($r.data.name) { return $r.data.name }
        if ($r.name) { return $r.name }
        return "your account"
    } catch {}
    return $null
}

Say ""
Say "  ================================" White
Say "   Iroas - personal trainer setup" White
Say "  ================================" White
Say "  This takes about 10 minutes. You'll need your phone (Telegram)"
Say "  and a web browser. Answer the questions as they come up."

# --- 1. Programs --------------------------------------------------------------
Step "1/5  Checking programs"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Python = Find-Python
if (-not $Python) {
    Winget-Install "Python.Python.3.13" "Python 3.13"
    $Python = Find-Python
    if (-not $Python) {
        Fail "Python was installed but can't be found yet. Close this window, then double-click setup.bat again."
    }
}
Say "Python: $Python" Green

if (-not (Get-Command git -ErrorAction SilentlyContinue) -and -not (Test-Path "$env:ProgramFiles\Git\bin\bash.exe")) {
    # Claude's tools on Windows run commands through Git Bash.
    Winget-Install "Git.Git" "Git for Windows"
}
if ((Get-Command git -ErrorAction SilentlyContinue) -or (Test-Path "$env:ProgramFiles\Git\bin\bash.exe")) {
    Say "Git for Windows: installed" Green
} else {
    Fail "Git for Windows didn't install. Install it from https://git-scm.com/download/win, then run setup.bat again."
}

# --- 2. Python environment ----------------------------------------------------
Step "2/5  Installing Iroas's Python packages (a few minutes the first time)"
if (-not (Test-Path $VenvPy)) {
    & $Python -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the Python environment (.venv)." }
}
& $VenvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
& $VenvPy -m pip install -r (Join-Path $Root "requirements.txt") --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Fail "Package install failed. Check your internet connection and run setup.bat again." }
Say "Packages installed." Green

$vals = Read-EnvFile
foreach ($k in @("CLAUDE_CODE_OAUTH_TOKEN", "TELEGRAM_BOT_TOKEN", "HEVY_API_KEY", "PAIRING_CODE", "IROAS_MODEL")) {
    if (-not $vals.ContainsKey($k)) { $vals[$k] = "" }
}

# --- 3. Claude login ----------------------------------------------------------
Step "3/5  Claude login (uses your Claude Pro/Max subscription)"
$ClaudeExe = Join-Path $Root ".venv\Lib\site-packages\claude_agent_sdk\_bundled\claude.exe"
if (-not (Test-Path $ClaudeExe)) {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { $ClaudeExe = $cmd.Source } else { Fail "Couldn't find the Claude program that ships with the packages. Run setup.bat again." }
}
if ($vals["CLAUDE_CODE_OAUTH_TOKEN"] -and -not $RefreshClaude) {
    Say "Already have a Claude token. (If Iroas ever says its login expired, double-click refresh_claude_login.bat.)" Green
} else {
    Say "A browser window will open. Sign in to Claude with the account that has your"
    Say "subscription and click Authorize. Then come back to this window: it will show a"
    Say "long token starting with  sk-ant-oat  - copy it (select it, then right-click or Ctrl+C)."
    Read-Host "Press Enter to open the browser"
    & $ClaudeExe setup-token
    while ($true) {
        $tok = (Read-Host "Paste the token here and press Enter").Trim()
        if ($tok -like "sk-ant-oat*") { $vals["CLAUDE_CODE_OAUTH_TOKEN"] = $tok; break }
        if ($tok -like "sk-ant-api*") {
            Say "That's an API key, not a subscription token. Iroas only uses your subscription - paste the sk-ant-oat token." Red
        } else {
            Say "That doesn't look right - it should start with sk-ant-oat. Try again." Red
        }
    }
    Write-EnvFile $vals
    Say "Claude token saved." Green
}

# --- 4. Telegram --------------------------------------------------------------
Step "4/5  Telegram bot"
$botName = $null
if ($vals["TELEGRAM_BOT_TOKEN"]) { $botName = Test-Telegram $vals["TELEGRAM_BOT_TOKEN"] }
if ($botName) {
    Say "Telegram bot already set up: @$botName" Green
} else {
    Say "On your phone, in Telegram:"
    Say "  1. Search for  @BotFather  (blue check mark) and open it, tap Start."
    Say "  2. Send  /newbot"
    Say "  3. Give it a name (e.g. Iroas) and then a username ending in 'bot' (e.g. dave_iroas_bot)."
    Say "  4. BotFather replies with a token like  123456789:AAH...  - send it to yourself"
    Say "     (e.g. email it) so you can copy it here, or type it carefully."
    while (-not $botName) {
        $tok = (Read-Host "Paste the bot token here").Trim()
        $botName = Test-Telegram $tok
        if ($botName) { $vals["TELEGRAM_BOT_TOKEN"] = $tok } else { Say "Telegram didn't accept that token. Check it and try again." Red }
    }
    Write-EnvFile $vals
    Say "Connected to @$botName" Green
}

# --- 5. Hevy ------------------------------------------------------------------
Step "5/5  Hevy"
$hevyName = $null
if ($vals["HEVY_API_KEY"]) { $hevyName = Test-Hevy $vals["HEVY_API_KEY"] }
if ($hevyName) {
    Say "Hevy already connected: $hevyName" Green
} else {
    Say "Hevy's API needs Hevy Pro. Then:"
    Say "  1. On a computer, go to  https://hevy.com/settings?developer  and log in."
    Say "  2. Click to generate an API key and copy it."
    Start-Process "https://hevy.com/settings?developer"
    while (-not $hevyName) {
        $key = (Read-Host "Paste the Hevy API key here").Trim()
        $hevyName = Test-Hevy $key
        if ($hevyName) { $vals["HEVY_API_KEY"] = $key } else { Say "Hevy didn't accept that key (is Hevy Pro active?). Try again." Red }
    }
    Write-EnvFile $vals
    Say "Connected to Hevy: $hevyName" Green
}

if (-not $vals["PAIRING_CODE"]) {
    $vals["PAIRING_CODE"] = "{0:D6}" -f (Get-Random -Minimum 100000 -Maximum 999999)
}
Write-EnvFile $vals

# --- Final check --------------------------------------------------------------
Step "Final check (tests Claude too - takes ~30 seconds)"
& $VenvPy (Join-Path $Root "doctor.py")
$ok = ($LASTEXITCODE -eq 0)

Say ""
if ($ok) {
    Say "  Setup complete!" Green
} else {
    Say "  Setup finished, but the check above found a problem. Fix it, then run setup.bat again." Yellow
}
Say ""
Say "  Next:"
Say "   1. Double-click  start_iroas.bat  and leave that window open (minimize is fine)."
Say "   2. In Telegram, open your bot @$botName and send:"
Say ""
Say "        /start $($vals['PAIRING_CODE'])" White
Say ""
Say "   Iroas will introduce itself and start getting to know you."
