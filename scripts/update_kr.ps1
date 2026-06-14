# OldnRich - KR(국장) recommendation daily updater (run by Task Scheduler)
# Runs the engine for KR only (KIS works from Korean IP), then commits & pushes.
$ErrorActionPreference = "Continue"

$repo = "C:\Users\LEE\OldbutRich"
$py   = "C:\Users\LEE\anaconda3\python.exe"
$log  = Join-Path $repo "scripts\update_kr.log"

function Log($m) {
    "$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))  $m" |
        Out-File -FilePath $log -Append -Encoding utf8
}

Set-Location $repo
$env:PYTHONIOENCODING   = "utf-8"
$env:ALLOW_MOCK_FALLBACK = "0"   # never publish fake data
$env:ENABLE_MARKETS      = "KR"  # KR only; US is handled by GitHub Actions

Log "=== KR update start ==="

# 1) run engine (KR only) -> updates recommendations.json (KR), preserves US
& $py -m files.main 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Log "engine failed (exit $LASTEXITCODE) - skip push"
    exit 1
}

# 2) commit KR change + cache, then sync with remote (US updated by CI) and push
git add recommendations.json cache
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {            # staged changes exist
    $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm')
    git commit -m "data(KR): local scheduler update $stamp UTC" 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    # --autostash: 무관한 unstaged 변경(.claude 등)이 있어도 rebase 진행
    git pull --rebase --autostash origin main 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    git push origin main 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
    if ($LASTEXITCODE -eq 0) { Log "pushed KR update" }
    else { Log "push failed (see git output above)" }
} else {
    Log "no change - skip commit"
}
Log "=== done ==="
