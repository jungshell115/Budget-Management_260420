#!/bin/zsh
MSG="${1:-auto sync $(date '+%Y-%m-%d %H:%M')}"
cd "$HOME/Projects/Budget-Management_260420" || exit 1
git add .
if [[ -z "$(git status --porcelain)" ]]; then
  echo "커밋할 변경 없음"
else
  git commit -m "$MSG"
  git push
fi
