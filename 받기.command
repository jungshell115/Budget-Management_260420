#!/bin/zsh
"$(cd "$(dirname "$0")" && pwd)/sync-pull.sh"
echo ""
echo "완료: 최신 코드 받기"
read -k 1 "?아무 키나 누르면 종료..."
echo
