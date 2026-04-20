param([string]$msg)

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: 현재 경로가 Git 저장소가 아닙니다."
  exit 1
}

$branch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
  Write-Host "오류: 현재 브랜치를 확인할 수 없습니다(Detached HEAD 가능)."
  exit 1
}

python "$PSScriptRoot/scripts/prune_sync_data.py" --root "$PSScriptRoot" --keep 1
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: 동기화 데이터 정리에 실패했습니다."
  exit 1
}

if ([string]::IsNullOrWhiteSpace($msg)) {
  $msg = "auto sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git add -A
$status = git status --porcelain

if (-not [string]::IsNullOrWhiteSpace($status)) {
  git commit -m $msg
  if ($LASTEXITCODE -ne 0) {
    Write-Host "오류: 커밋에 실패했습니다."
    exit 1
  }
} else {
  Write-Host "커밋할 변경 없음: 최신 반영 후 push 시도"
}

git fetch origin
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: 원격 정보를 가져오지 못했습니다."
  exit 1
}

git pull --rebase --autostash origin $branch
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: pull/rebase 중 충돌이 발생했습니다. 충돌 해결 후 다시 실행하세요."
  exit 1
}

git push origin $branch
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: push에 실패했습니다."
  exit 1
}

Write-Host "완료: 변경사항 올리기 성공 ($branch)"
