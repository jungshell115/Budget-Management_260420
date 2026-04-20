#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "오류: 현재 경로가 Git 저장소가 아닙니다."
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  echo "오류: 현재 브랜치를 확인할 수 없습니다(Detached HEAD 가능)."
  exit 1
fi

git fetch origin || exit 1
git pull --rebase --autostash origin "$BRANCH" || exit 1
echo "완료: 최신 코드 받기 성공 ($BRANCH)"
