#!/bin/zsh
cd "$HOME/Projects/Budget-Management_260420" || exit 1

echo -n "커밋 메시지 입력(비우면 자동): "
read MSG
if [[ -z "$MSG" ]]; then
  MSG="auto sync $(date '+%Y-%m-%d %H:%M')"
fi

git add -A
if [[ -z "$(git status --porcelain)" ]]; then
  echo "커밋할 변경 없음"
else
  git commit -m "$MSG" && git push
fi

echo ""
echo "완료: 변경사항 올리기"
read -k 1 "?아무 키나 누르면 종료..."
echo
