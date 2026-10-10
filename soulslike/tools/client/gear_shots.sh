#!/bin/bash
# 장비 설명 칸과 레벨 올리기 그림 (2026-10-10 사용자 결정 "장비에는 보정·요구 능력치가 없다", DESIGN 9.7, 5.9, 5.10, 3.5):
#   gear_shots.sh <포트> <서버폴더> <앞머리>
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면>.png 로 남는다. W, H, G = 화면 크기, GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게).
# ui_shots.sh 의 inv 장면과 같은 꾸밈 (시험 방 저녁, 단축 슬롯에 바닐라 아이템 여럿, 든 칸에 레딘 경비대 직검, 왼손에 순례자 버클러)
# 에서 찍는다. 묶음 (ONLY 에 빈칸으로 골라 준다. 없으면 모두):
#   origin   출신 확인 창 (5.10): origin_confirm_warrior (양손 대검 공격력 123), origin_confirm_thief (단도 52, 패링 알림).
#            찍은 뒤 빈털터리로 되돌리고 꾸밈을 다시 한다
#   tips     소지품 첫 칸에 아이템 하나를 두고 마우스를 올려 설명 칸을 찍는다:
#              tooltip_redin_guard_sword  직검: 공격력 · 무게 한 줄 (보정·필요 능력치 줄이 없다)
#              tooltip_gaoler_greatsword  대검: 공격력 · 무게
#              tooltip_redin_guard_shield 중형 방패: 막기 · 무게 (패링 창은 보이지 않는다)
#              tooltip_kiln_pot           촉매: 술법 세기 · 무게
#              tooltip_parrying_dagger    패링 단검 (왼손 무기): 분류 줄 "패링 단검 · 찌르기", 공격력 · 무게
#              tooltip_test_parry         시험 반지: 효과 줄 "패링 창 +0.10초", 실선, 설명 (무게가 없어 무게 줄도 없다)
#   levelup  레벨 올리기 창 (5.9): 근력 +3 (levelup_str: 공격력 a → b) 과 근력 단추의 설명 칸 (levelup_str_tip),
#            민첩 +10 (levelup_dex: 공격 속도 0% → +10%) 과 민첩 단추 (levelup_dex_tip),
#            왼손에 쇠단지를 들고 지력 +10 (levelup_int: 술법 세기 110 → 128) 과 지력 단추 (levelup_int_tip)
#   stats    능력치 창 (5.9): 왼손 쇠단지 (stats_dialog: 공격력 한손 68, 술법 세기 110)
# 시험 줄이 그림에 남지 않게 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서 찍는다. 영어는 MC_LANG=en_us 와 SUFFIX=_en.
# 능력치 "+" 단추 줄의 화면 높이는 TIP_Y (기본: 1080 이면 797, 720 이면 525. 창 본문이 위에서부터 놓여 화면 높이에 따라 단추 줄이
# 옮겨 간다: 실제 화면에서 잰 값). 단추는 한 줄에 여섯 (폭 64 + 사이 2, 5.9): i 째 (0 부터) 단추의 가운데는 가운데 + (i − 2.5) × 66 GUI
set -u
R=$(cd "$(dirname "$0")/../.." && pwd)
PORT=$1; SRV=$2; P=$3; shift 3
W=${W:-1920}; H=${H:-1080}; G=${G:-4}
X=${SUFFIX:-}
CX=$((W/2)); CY=$((H/2))
cd "$R"
do_() { tools/client/run_client.sh --do "$PORT" "$@" 2>&1 | grep -E "SHOT|오류|rror" ; }
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
inw() { con execute in minecraft:souls_world run "$@"; }
tst() { con execute as Tester run soulstest "$@"; }
home() { inw tp Tester 200.5 101 -189.5 180 0; }
con gamemode adventure Tester
con effect clear Tester
inw time set 12700
inw gamerule advance_time false 2>/dev/null
inw weather clear
con clear Tester
con item replace entity Tester hotbar.1 with minecraft:bread 48
con item replace entity Tester hotbar.2 with minecraft:bone 6
con item replace entity Tester hotbar.3 with minecraft:coal 10
con item replace entity Tester hotbar.4 with minecraft:torch 16
con item replace entity Tester hotbar.5 with minecraft:flint 6
con item replace entity Tester hotbar.6 with minecraft:rotten_flesh 18
con item replace entity Tester hotbar.7 with minecraft:netherite_ingot 2
con item replace entity Tester hotbar.8 with minecraft:charcoal 5
home
gear() { do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give pilgrim_buckler off" "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5; }
ONLY=${ONLY:-}
want() { [ -z "$ONLY" ] || [[ " $ONLY " == *" $1 "* ]]; }
# 출신 확인 창: 지우면 출신 창이 뜬다 → 전사 → 돌아가기 → 도적 → 고른다 → 다시 지우고 빈털터리로 (ui_shots.sh origin 과 같은 길)
if want origin; then
  con souls origin reset Tester
  do_ wait:2.5
  tst press origin warrior
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}origin_confirm_warrior${X}
  tst press origin_confirm back
  do_ wait:1.5
  tst press origin thief
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}origin_confirm_thief${X}
  tst press origin_confirm choose
  do_ wait:1
  con souls origin reset Tester
  do_ wait:1.5
  tst origin deprived
  do_ wait:1
fi
gear
# 인벤토리 판의 왼쪽 위 (GUI): 가운데 - 88, - 83. 소지품 첫 칸의 아이템 (8, 84)
L=$((CX - 88*G)); T=$((CY - 83*G))
TIP_Y=${TIP_Y:-$(( H >= 1080 ? 797 : 525 ))}
plus_x() { echo $(( CX + ($1 * 66 - 165) * G )); }   # 능력치 i (vig 0 … int 5) 의 "+" 단추 가운데
tip() {
  local name=$1; shift
  con item replace entity Tester inventory.0 with minecraft:air
  do_ "cmd:$*" wait:1 key:e wait:1 move:$((L + 16*G)):$((T + 92*G)) wait:0.8 shot:${P}tooltip_${name}${X} key:Escape wait:0.5
}
if want tips; then
  tip redin_guard_sword /soulstest give redin_guard_sword
  tip gaoler_greatsword /soulstest give gaoler_greatsword
  tip redin_guard_shield /soulstest give redin_guard_shield
  tip kiln_pot /soulstest give kiln_pot
  tip parrying_dagger /soulstest give parrying_dagger
  tip test_parry /soulstest ring give test_parry
  con item replace entity Tester inventory.0 with minecraft:air
fi
# 레벨 올리기 창: 한 번 열 때마다 하나 (나가기 → 휴식 창 → 다시 레벨 올리기 로 더한 점을 비운다)
lv() {   # lv <능력치> <점> <이름> <단추 x> <단추 y>
  tst press rest levelup
  tst levelup "$1" "$2"
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}levelup_$3${X}
  # 단추 설명 칸은 마우스를 올리고 조금 움직인 뒤 잠시 머물러야 뜬다 (한 번 옮기고 1초면 둘째 단추부터 뜨지 않았다)
  do_ move:$4:$5 wait:0.3 move:$(( $4 + 2 )):$(( $5 - 2 )) wait:2.5 shot:${P}levelup_$3_tip${X}
  tst press levelup exit
  do_ wait:1
}
if want levelup || want stats; then
  tst souls 25000
  tst rest
  do_ wait:2
fi
if want levelup; then
  lv str 3 str $(plus_x 3) $TIP_Y
  lv dex 10 dex $(plus_x 4) $TIP_Y
fi
if want levelup || want stats; then
  # 지력·능력치 창은 왼손에 쇠단지 (촉매는 왼손, 3.12.4): 술법 세기가 보인다
  tst press rest leave 2>/dev/null
  do_ wait:1 key:Escape wait:0.5 "cmd:/soulstest give kiln_pot off" wait:1 clearchat wait:0.5
  tst rest
  do_ wait:2
fi
if want levelup; then
  lv int 10 int $(plus_x 5) $TIP_Y
fi
if want stats; then
  tst press rest stats
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}stats_dialog${X} key:Escape wait:1
fi
if want levelup || want stats; then
  do_ wait:0.5 key:Escape wait:1 "cmd:/soulstest give pilgrim_buckler off" wait:1 clearchat
  tst souls 0
fi
