$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: 현재 경로가 Git 저장소가 아닙니다."
  Read-Host "엔터 누르면 종료"
  exit 1
}

$branch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
  Write-Host "오류: 현재 브랜치를 확인할 수 없습니다(Detached HEAD 가능)."
  Read-Host "엔터 누르면 종료"
  exit 1
}

git fetch origin
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: 원격 정보를 가져오지 못했습니다."
  Read-Host "엔터 누르면 종료"
  exit 1
}

git pull --rebase --autostash origin $branch
if ($LASTEXITCODE -ne 0) {
  Write-Host "오류: pull/rebase 중 충돌이 발생했습니다. 충돌 해결 후 다시 실행하세요."
  Read-Host "엔터 누르면 종료"
  exit 1
}

Write-Host "완료: 최신 코드 받기 성공 ($branch)"
Read-Host "엔터 누르면 종료"
