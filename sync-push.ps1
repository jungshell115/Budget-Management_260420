param([string]$msg)

Set-Location -LiteralPath $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($msg)) {
  $msg = "auto sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git add -A
$status = git status --porcelain

if ([string]::IsNullOrWhiteSpace($status)) {
  Write-Host "커밋할 변경 없음"
  exit 0
}

git commit -m $msg
git push
