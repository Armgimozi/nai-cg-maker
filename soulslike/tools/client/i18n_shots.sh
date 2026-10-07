#!/bin/bash
# 영어판 점검 그림 (DESIGN.md 10.3, 10.9, 13.4). 같은 장면을 한국어 클라이언트와 영어 클라이언트로 찍어 글이 제 언어로
# 나오고 자리 (단추·창·설명 칸) 에 들어가는지 본다. 서버는 debug.test-mode 여야 한다 (devserver.sh).
#   i18n_shots.sh <포트> <찍을폴더> [언어...]      언어 기본 "ko_kr en_us"
# 그림 (언어마다 <언어>_ 를 앞에 붙인다):
#   01_join_hud        들어온 화면. 행동 막대 "소울 0" / "Souls 0" (번역 열쇠 souls.hud.souls)
#   02_rest_dialog     휴식 창 꼴 (/soulstest dialog): 제목 (화톳불 이름), 본문 "소울 0 · 레벨 1", 단추 셋 (폭 160)
#   03_item_tooltip    인벤토리에서 시험 막기 도구 위에 마우스: 이름과 설명 두 줄 (번역 열쇠라 클라이언트 언어로)
#   04_death_screen    사망 화면: YOU DIED (두 언어 공통 그림 글자), 회색 단추 둘 (일어선다/그만둔다, Rise/Depart)
#   05_quit_confirm    사망 화면의 둘째 단추를 누른 확인 창 (deathScreen.quit.confirm). 둘째 단추 (일어선다/Rise) 로 돌아온다
#   06_title_subtitle  큰 글씨와 부제목의 폭 (10.3): 바닐라 /title 로 번역 열쇠를 띄운다. 가장 긴 큰 글씨 taster.end
#                      (4배로 그려진다) 와 가장 긴 부제목 door.one-way (2배)
# SRVDIR=<서버폴더> (devserver.sh 로 켠 그 폴더) 를 주면 설정 단계 (pack.send-at: configure) 점검도 한다. 팩을 싣기 전이라
# 서버가 클라이언트가 알려 준 언어로 채우는 글이 제 언어인지 본다 (10.9, 13.4 의 13). 서버를 설정을 바꿔 다시 켜고, 끝나면
# 원래 설정으로 다시 켠다:
#   07_configure_prompt      팩을 묻는 창 (MC_PACK=prompt) 의 서버 안내 pack.prompt
#   08_configure_pack_failed 팩 주소를 일부러 죽여 받지 못하게 했을 때 서버가 쫓아낸 글 pack.failed
# 채팅은 숨긴다 (chatScale:0). 화면 좌표는 1280x720, GUI 배율 3 (자동) 기준이다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 2 ] || { echo "쓰는 법: i18n_shots.sh <포트> <찍을폴더> [언어...]" >&2; exit 2; }
PORT=$1
OUT=$2
shift 2
LANGS=${*:-ko_kr en_us}
export MC_OPTIONS="${MC_OPTIONS:-chatScale:0.0}"
RC="$HERE/run_client.sh"
mkdir -p "$OUT"

# GUI 배율 3 의 화면 좌표 (1280x720 → GUI 426x240)
INV_HOTBAR1="423:561"      # 인벤토리 (176x166, 가운데) 의 단축 칸 1: GUI (125+16, 37+150)
DEATH_SECOND="639:498"     # 사망 화면 둘째 단추: GUI (213, 240/4 + 96 + 10)
CONFIRM_NO="879:438"       # 확인 창 오른쪽 단추: GUI (293, 240/6 + 96 + 10)

for L in $LANGS; do
  echo "== $L"
  MC_LANG=$L "$RC" --start "$PORT" "$OUT" || exit 1
  "$RC" --do "$PORT" \
    join "cmd:/clear" slot:1 "cmd:/soulstest heal" "cmd:/souls tp room" wait:8 shot:${L}_01_join_hud \
    "cmd:/soulstest dialog" wait:1.5 shot:${L}_02_rest_dialog close wait:0.5 \
    "cmd:/soulstest guard empty" wait:1 key:e wait:1 move:$INV_HOTBAR1 wait:0.8 shot:${L}_03_item_tooltip close wait:0.5 \
    "cmd:/soulstest kill" wait:2 shot:${L}_04_death_screen \
    click:$DEATH_SECOND wait:1 shot:${L}_05_quit_confirm click:$CONFIRM_NO wait:2 "cmd:/soulstest heal" \
    "cmd:/title @s times 10 200 10" "cmd:/title @s subtitle {translate:\"souls.door.one-way\",color:\"#858079\"}" \
    "cmd:/title @s title {translate:\"souls.taster.end\",color:\"#b3a37f\"}" wait:1.5 shot:${L}_06_title_subtitle \
    || { "$RC" --stop "$PORT" >/dev/null 2>&1; exit 1; }
  "$RC" --stop "$PORT" >/dev/null 2>&1
done

if [ -n "${SRVDIR:-}" ]; then
  DEV="$HERE/devserver.sh"
  restart() {   # restart [SET 값]: 서버를 그 설정으로 다시 켠다
    "$DEV" --stop "$SRVDIR" >/dev/null 2>&1
    SET="${1:-}" "$DEV" "$PORT" "$SRVDIR" >/dev/null || { echo "서버를 다시 켜지 못했다 ($SRVDIR/console.log)" >&2; exit 1; }
  }
  trap 'restart' EXIT
  # 07: 묻는 창. 답을 오래 기다리게 해 창이 남아 있는 동안 찍는다
  restart "pack.send-at=configure pack.configure-timeout=60"
  for L in $LANGS; do
    MC_LANG=$L MC_PACK=prompt "$RC" --start "$PORT" "$OUT" || exit 1
    "$RC" --do "$PORT" "log:Connecting to:120" wait:8 shot:${L}_07_configure_prompt || { "$RC" --stop "$PORT" >/dev/null 2>&1; exit 1; }
    "$RC" --stop "$PORT" >/dev/null 2>&1
    sleep 2
  done
  grep -a -E 'PACK configure' "$SRVDIR/console.log" | sed 's/^/  서버: /'
  # 08: 받지 못함. 자체 확인을 끄면 팩이 필수로 남는다 (10.10). 클라이언트는 같은 SHA-1 의 팩을 받아 둔 것이 있으면 주소에
  # 가지 않으므로 (downloads/) 받아 둔 서버 팩을 지운다 (이 포트의 실행 폴더만)
  restart "pack.send-at=configure pack.self-check=false pack.url=\"http://127.0.0.1:1/{sha1}.zip\""
  for L in $LANGS; do
    rm -rf "${SOULS_CLIENT_HOME:-$HOME/.cache/souls-client}/run/$PORT/game/downloads"
    MC_LANG=$L "$RC" --start "$PORT" "$OUT" || exit 1
    "$RC" --do "$PORT" "log:Client disconnected with reason:120" wait:1.5 shot:${L}_08_configure_pack_failed \
      || { "$RC" --stop "$PORT" >/dev/null 2>&1; exit 1; }
    "$RC" --stop "$PORT" >/dev/null 2>&1
    sleep 2
  done
  grep -a -E 'PACK configure|리소스팩 답을' "$SRVDIR/console.log" | sed 's/^/  서버: /'
fi
echo "끝: $OUT"
