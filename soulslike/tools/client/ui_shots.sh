#!/bin/bash
# UI 점검 그림 (DESIGN.md 10.2, 10.4, 10.5): HUD·창·설정·사망 화면·채팅·휴식 창을 실제 클라이언트로 찍는다.
#   ui_shots.sh <포트> <서버폴더> <앞머리> [장면...]
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면>.png 로 남는다. W, H, G = 화면 크기, GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게).
# 장면 (기본: chat 을 뺀 전부):
#   hud damage low boss inv chest craft pause options dialog death   그리고 chat
# 시험 줄 ([T] …) 이 그림에 남지 않게: chat 밖의 장면은 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서 (채팅 글이 그려지지
# 않는다), chat 은 보통 클라이언트에서 채팅을 비운 뒤 서버 콘솔의 tellraw 줄만 찍는다. 영어 설명 칸은 MC_LANG=en_us 로 켠
# 클라이언트에서 inv 만.
# 시험 방 저녁 (시간 12700), 단축 슬롯에 아이템 여럿, 든 칸·소지품 첫 칸에 레딘 경비대 직검, 왼손에 순례자 버클러.
set -u
R=$(cd "$(dirname "$0")/../.." && pwd)
PORT=$1; SRV=$2; P=$3; shift 3
SCENES=${*:-"hud damage low boss inv chest craft pause options dialog death"}
W=${W:-1920}; H=${H:-1080}; G=${G:-4}
X=${SUFFIX:-}     # 그림 이름 끝 (영어 클라이언트면 _en)
VY=${VY:-85}      # 비디오 설정에서 가리킬 밀대 줄 (GUI y, 왼쪽 열: 최대 프레임률)
CX=$((W/2)); CY=$((H/2)); GH=$((H/G))
cd "$R"
do_() { tools/client/run_client.sh --do "$PORT" "$@" 2>&1 | grep -E "SHOT|오류|rror" ; }
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
inw() { con execute in minecraft:souls_world run "$@"; }
home() { inw tp Tester 200.5 101 -189.5 180 0; }
has() { case " $SCENES " in *" $1 "*) return 0 ;; esac; return 1; }
con gamemode adventure Tester
con effect clear Tester
inw time set 12700
inw gamerule advance_time false 2>/dev/null
inw weather clear
inw setblock 200 102 -191 minecraft:air
inw setblock 201 102 -191 minecraft:air
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
do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give redin_guard_sword" "cmd:/soulstest give pilgrim_buckler off" \
    "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5
if has hud; then
  do_ wait:1 shot:${P}hud_idle${X}
fi
if has damage; then
  con execute as Tester run soulstest hit 7 type=none
  do_ wait:0.25 shot:${P}hud_damage${X} wait:1.5
  con execute as Tester run soulstest heal
  do_ wait:0.5
fi
if has low; then
  con execute as Tester run soulstest stamina set 6
  con execute as Tester run soulstest hit 15 type=none
  do_ wait:0.4 shot:${P}hud_low_stamina${X} wait:0.5
  con execute as Tester run soulstest heal
  do_ wait:0.5
fi
if has boss; then
  con execute as Tester run soulstest boss 100 100
  con execute as Tester run soulstest boss 61 34
  do_ wait:0.8 shot:${P}hud_boss${X}
  con execute as Tester run soulstest boss off
  do_ wait:0.5
fi
# 인벤토리 판의 왼쪽 위 (GUI): 가운데 - 88, - 83. 소지품 첫 칸의 아이템 (8, 84)
L=$((CX - 88*G)); T=$((CY - 83*G))
if has inv; then
  do_ key:e wait:1 move:$((L + 16*G)):$((T + 92*G)) wait:0.8 shot:${P}inventory_tooltip${X} key:Escape wait:0.5
fi
if has chest; then
  # 시험 방은 블록 상호작용을 막는다 (짓는 사람 = 창작 모드만): 상자를 열 동안만 창작 모드
  con gamemode creative Tester
  inw setblock 200 102 -191 "minecraft:chest[facing=south,type=single]"
  inw item replace block 200 102 -191 container.3 with minecraft:rotten_flesh 7
  inw item replace block 200 102 -191 container.13 with minecraft:bone 2
  inw item replace block 200 102 -191 container.20 with minecraft:coal 12
  inw item replace block 200 102 -191 container.21 with minecraft:flint 4
  home
  T3=$((CY - 84*G))
  do_ mouse:right wait:1.5 move:$((L + (8+18*4+8)*G)):$((T3 + (18+18*1+8)*G)) wait:0.6 shot:${P}chest${X} key:Escape wait:0.5
  inw setblock 200 102 -191 minecraft:air
  con gamemode adventure Tester
fi
if has craft; then
  con gamemode creative Tester
  inw setblock 200 102 -191 minecraft:crafting_table
  home
  do_ mouse:right wait:1.5 move:$((L + (30+18*1+8)*G)):$((T + (17+18*1+8)*G)) wait:0.6 shot:${P}crafting${X} key:Escape wait:0.5
  inw setblock 200 102 -191 minecraft:air
  con gamemode adventure Tester
fi
if has pause; then
  do_ key:Escape wait:2.5 move:$((CX + 40)):$((CY - 40*G)) wait:0.5 move:$((CX)):$((CY - 49*G)) wait:0.5 \
      move:$((CX + 3)):$((CY - 48*G)) wait:0.8 shot:${P}pause${X} key:Escape wait:0.5
fi
if has options; then
  # 일시 정지 → 설정 (시야 범위 밀대를 가리킨다) → 비디오 설정 (밀대 여럿, 두루마리, 나눔줄)
  # 설정 화면의 줄은 화면 높이와 상관없이 위에서 GUI 39 (시야 범위), 121 (비디오 설정) 에 놓인다
  do_ key:Escape wait:2.5 move:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:0.5 click:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:2.5 \
      move:$((CX - 40*G)):$((60*G)) wait:0.5 move:$((CX - 80*G)):$((37*G)) wait:0.5 move:$((CX - 78*G)):$((39*G)) wait:1 shot:${P}options${X}
  do_ click:$((CX - 80*G)):$((121*G)) wait:2.5 move:$((CX - 40*G)):$((VY*G - 12*G)) wait:0.5 move:$((CX - 82*G)):$((VY*G - 2*G)) wait:0.5 \
      move:$((CX - 80*G)):$((VY*G)) wait:1 shot:${P}video${X} key:Escape wait:1 key:Escape wait:1 key:Escape wait:0.8
fi
if has dialog; then
  do_ "cmd:/soulstest dialog" wait:3 move:$((CX + 40)):$((CY)) wait:0.5 move:$((CX)):$((99*G)) wait:0.5 move:$((CX + 3)):$((100*G)) \
      wait:0.8 shot:${P}rest_dialog${X} key:Escape wait:0.6
fi
if has chat; then
  do_ clearchat wait:0.5
  con tellraw Tester '{"translate":"souls.bonfire.lit","color":"#9e7c44"}'
  con tellraw Tester '{"translate":"souls.bonfire.enemies-back","color":"#858079"}'
  con tellraw Tester '{"translate":"multiplayer.player.joined","with":["Tester"],"color":"yellow"}'
  con tellraw Tester '{"translate":"souls.souls.recovered","color":"#b3a37f"}'
  do_ wait:0.8 key:t wait:0.8 shot:${P}chat${X} key:Escape wait:0.5
fi
if has death; then
  do_ "cmd:/soulstest kill" wait:2.5 move:$((CX)):$((CY + 30*G)) wait:0.6 shot:${P}death${X} respawn wait:3
  home
fi
