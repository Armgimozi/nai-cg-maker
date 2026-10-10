#!/bin/bash
# 실제 바닐라 1.21.11 클라이언트로 접속해 화면을 찍는다 (DESIGN.md 13.4). mcclient.py 의 얇은 껍데기.
#   run_client.sh <포트> <찍을폴더> [동작...]     켜고 → 동작을 차례로 → 끈다
#   run_client.sh --start <포트> <찍을폴더>       켜 두기만 (뒤에서 돈다)
#   run_client.sh --do <포트> [동작...]           켜 둔 클라이언트에 동작
#   run_client.sh --stop <포트>
#   run_client.sh --status <포트>
# 예:
#   run_client.sh 25602 shots join shot:joined sprint:2 hold:Shift_L:0.1 wait:0.3 shot:roll "cmd:/soulstest kill" wait:2 shot:died respawn
# 동작 목록과 환경 변수는 인수 없이 실행하면 나온다 (README.md 에도 있다).
# 처음에는 클라이언트·라이브러리·에셋을 받는다 (약 110MB, ~/.cache/souls-client). Xvfb·xdotool·ImageMagick·mesa 가 없고
# root 에 apt-get 이 있으면 여기서 설치한다 (컨테이너를 새로 받을 때마다 빠져 있다).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)

need=""
command -v Xvfb >/dev/null 2>&1 || need="$need xvfb"
command -v xdotool >/dev/null 2>&1 || need="$need xdotool"
command -v import >/dev/null 2>&1 || need="$need imagemagick"
# 소프트웨어 OpenGL (mesa llvmpipe): GLX 껍데기 + swrast 드라이버
{ ls /usr/lib/*/libGLX_mesa.so.0 && ls /usr/lib/*/dri/swrast_dri.so; } >/dev/null 2>&1 \
  || need="$need libgl1 libglx-mesa0 libgl1-mesa-dri"
if [ -n "$need" ]; then
  if [ "$(id -u)" = 0 ] && command -v apt-get >/dev/null 2>&1; then
    echo "[client] 설치:$need"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q $need >/dev/null 2>&1 \
      || { apt-get update -q >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get install -y -q $need >/dev/null 2>&1; } \
      || { echo "[client] 설치 실패:$need" >&2; exit 1; }
  else
    echo "[client] 필요한 것:$need (apt-get install -y$need)" >&2
    exit 1
  fi
fi

case "${1:-}" in
  --start) shift; exec python3 "$HERE/mcclient.py" start "$@" ;;
  --do) shift; exec python3 "$HERE/mcclient.py" do "$@" ;;
  --stop) shift; exec python3 "$HERE/mcclient.py" stop "$@" ;;
  --status) shift; exec python3 "$HERE/mcclient.py" status "$@" ;;
  ""|-h|--help) exec python3 "$HERE/mcclient.py" ;;
esac
exec python3 "$HERE/mcclient.py" run "$@"
