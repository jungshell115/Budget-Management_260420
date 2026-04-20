param([string]$msg = "auto sync $(Get-Date -Format ''yyyy-MM-dd HH:mm'')")
cd "C:\Users\user\Desktop\2026 예산\budget_tool"
git add .
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
  Write-Host "커밋할 변경 없음"
} else {
  git commit -m $msg
  git push
}
Read-Host "완료(올리기). 엔터 누르면 종료"
