#!/bin/bash
# 장비 설명 칸과 레벨 올리기 그림 (2026-10-10 사용자 결정 "장비에는 보정·요구 능력치가 없다", DESIGN 9.7, 5.9, 3.5):
#   gear_shots.sh <포트> <서버폴더> <앞머리>
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면>.png 로 남는다. W, H, G = 화면 크기, GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게).
# ui_shots.sh 의 inv 장면과 같은 꾸밈 (시험 방 저녁, 단축 슬롯에 바닐라 아이템 여럿, 든 칸에 레딘 경비대 직검, 왼손에 순례자 버클러)
# 에서 소지품 첫 칸에 아이템 하나를 두고 마우스를 올려 설명 칸을 찍는다:
#   tooltip_redin_guard_sword  직검: 공격력 · 무게 한 줄 (보정·필요 능력치 줄이 없다)
#   tooltip_gaoler_greatsword  대검: 공격력 · 무게
#   tooltip_redin_guard_shield 중형 방패: 막기 · 무게 (패링 창은 보이지 않는다)
#   tooltip_kiln_pot           촉매: 술법 세기 · 무게
#   tooltip_parrying_dagger    패링 단검 (왼손 무기): 공격력 · 무게
#   tooltip_test_parry         시험 반지: 효과 줄 "패링 창 +0.10초" 와 설명뿐 (무게가 없어 무게 줄도 없다)
# 그리고 레벨 올리기 창: 근력 +3 을 더한 미리보기 (levelup_str: 공격력 a → b) 와 근력 단추의 설명 칸 (levelup_str_tip: 한 점의 공격력 변화).
# 시험 줄이 그림에 남지 않게 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서 찍는다. 영어는 MC_LANG=en_us 와 SUFFIX=_en.
# ONLY=levelup 이면 레벨 올리기 창만. 근력 단추의 화면 높이는 TIP_Y (기본: 1080 이면 704, 720 이면 459. 창 본문이 위에서부터 놓여
# 화면 높이에 따라 단추 줄이 옮겨 간다: 실제 화면에서 잰 값)
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
do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give pilgrim_buckler off" "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5
# 인벤토리 판의 왼쪽 위 (GUI): 가운데 - 88, - 83. 소지품 첫 칸의 아이템 (8, 84)
L=$((CX - 88*G)); T=$((CY - 83*G))
ONLY=${ONLY:-}
TIP_Y=${TIP_Y:-$(( H >= 1080 ? 704 : 459 ))}
tip() {
  [ "$ONLY" = levelup ] && return 0
  local name=$1; shift
  con item replace entity Tester inventory.0 with minecraft:air
  do_ "cmd:$*" wait:1 key:e wait:1 move:$((L + 16*G)):$((T + 92*G)) wait:0.8 shot:${P}tooltip_${name}${X} key:Escape wait:0.5
}
tip redin_guard_sword /soulstest give redin_guard_sword
tip gaoler_greatsword /soulstest give gaoler_greatsword
tip redin_guard_shield /soulstest give redin_guard_shield
tip kiln_pot /soulstest give kiln_pot
tip parrying_dagger /soulstest give parrying_dagger
tip test_parry /soulstest ring give test_parry
con item replace entity Tester inventory.0 with minecraft:air
# 레벨 올리기 창: 근력 +3 (공격력의 미리보기), 그다음 근력 단추의 설명 칸 (단추 자리: 가로는 가운데 + 75 GUI, 세로는 TIP_Y)
tst souls 25000
tst rest
tst press rest levelup
tst levelup str 3
do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}levelup_str${X}
do_ move:$((CX + 75*G)):$TIP_Y wait:1.2 shot:${P}levelup_str_tip${X}
tst press levelup exit
do_ wait:1 key:Escape wait:1
tst souls 0
