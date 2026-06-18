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

# 0) sync with remote FIRST so the engine regenerates on top of the latest US
#    data (CI updates US). This avoids a recommendations.json rebase conflict
#    between the KR commit and the US CI commit (both edit the same file).
#    --autostash: 무관한 unstaged 변경(.claude 등)이 있어도 진행.
git pull --rebase --autostash origin main 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    # pull 실패(충돌 등) 시 rebase 잔재를 정리해 다음 실행이 깨지지 않게 함
    git rebase --abort 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
    Log "git pull failed - abort run (repo left clean)"
    exit 1
}

# 1) run engine (KR only) -> regenerates recommendations.json KR, preserves US
& $py -m files.main 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Log "engine failed (exit $LASTEXITCODE) - skip push"
    exit 1
}

# 2) commit KR change + cache, then push (fast-forward — no conflict)
git add recommendations.json cache
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {            # staged changes exist
    $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm')
    git commit -m "data(KR): local scheduler update $stamp UTC" 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    git push origin main 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
    if ($LASTEXITCODE -eq 0) {
        Log "pushed KR update"
    } else {
        # 푸시 사이에 CI가 또 푸시한 경우(드묾): 한 번만 재동기화 후 재시도.
        # 우리 변경은 로컬에 커밋돼 있으니, rebase로 CI 커밋 위에 얹고 다시 푸시.
        Log "push rejected - resync once and retry"
        git pull --rebase --autostash origin main 2>&1 |
            Out-File -FilePath $log -Append -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            git rebase --abort 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
            Log "retry resync failed - giving up (repo left clean)"
            exit 1
        }
        git push origin main 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
        if ($LASTEXITCODE -eq 0) { Log "pushed KR update (after retry)" }
        else { Log "push failed after retry (see git output above)" }
    }
} else {
    Log "no change - skip commit"
}
Log "=== done ==="
