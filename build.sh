#!/bin/bash
# Terranion 엔진 빌드 → bin/terranion  (이 서버 CPU에 맞춰 -march=native 로 컴파일하므로 '배포할 서버에서' 실행하세요)
set -e
cd "$(dirname "$0")"
mkdir -p bin
g++ -O3 -march=${MARCH:-native} -std=c++17 -pthread -static-libstdc++ -static-libgcc engine/terranion.cpp -o bin/terranion
echo "OK: bin/terranion"
