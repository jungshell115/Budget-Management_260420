#!/bin/zsh
cd "$HOME/Projects/Budget-Management_260420" || exit 1
git pull
echo ""
echo "완료: 최신 코드 받기(git pull)"
read -k 1 "?아무 키나 누르면 종료..."
echo
