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
echo "끝: $OUT"
