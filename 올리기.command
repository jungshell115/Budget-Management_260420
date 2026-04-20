#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo -n "커밋 메시지 입력(비우면 자동): "
read MSG
"$SCRIPT_DIR/sync-push.sh" "$MSG"

echo ""
echo "완료: 변경사항 올리기"
read -k 1 "?아무 키나 누르면 종료..."
echo
