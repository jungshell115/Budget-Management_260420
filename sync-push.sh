#!/bin/zsh
MSG="${1:-auto sync $(date '+%Y-%m-%d %H:%M')}"
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

python3 "$SCRIPT_DIR/scripts/prune_sync_data.py" --root "$SCRIPT_DIR" --keep 1 || exit 1

git add -A
if [[ -z "$(git status --porcelain)" ]]; then
  echo "커밋할 변경 없음: 최신 반영 후 push 시도"
else
  git commit -m "$MSG" || exit 1
fi

git fetch origin || exit 1
git pull --rebase --autostash origin "$BRANCH" || exit 1
git push origin "$BRANCH" || exit 1
echo "완료: 변경사항 올리기 성공 ($BRANCH)"
