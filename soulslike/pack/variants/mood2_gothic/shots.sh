#!/bin/bash
# mood2_gothic 시안을 실제 클라이언트로 찍는다.
#   shots.sh <포트> <서버폴더> <찍을폴더> <앞머리> [장면...]
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start, --do join). W, H, G = 화면 크기, GUI 배율.
# 장면: hud damage low boss inv pause options dialog chat death (기본 전부). 영어 설명 칸은 MC_LANG=en_us 로 켠 클라이언트에서 inv 만.
# 시험 방 저녁 (시간 12700), 단축 슬롯에 아이템 여럿, 든 칸과 소지품 첫 칸에 레딘 경비대 직검.
set -u
R=$(cd "$(dirname "$0")/../../.." && pwd)
PORT=$1; SRV=$2; OUT=$3; P=$4; shift 4
SCENES=${*:-"hud damage low boss inv pause options dialog chat death"}
W=${W:-1920}; H=${H:-1080}; G=${G:-4}
CX=$((W/2)); CY=$((H/2))
cd "$R"
mkdir -p "$OUT"
do_() { tools/client/run_client.sh --do "$PORT" "$@" 2>&1 | grep -E "SHOT|오류|rror" ; }
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
inw() { con execute in minecraft:souls_world run "$@"; }
home() { inw tp Tester 200.5 101 -189.5 180 0; }
has() { case " $SCENES " in *" $1 "*) return 0 ;; esac; return 1; }
con gamemode adventure Tester
con effect clear Tester
inw time set 12700
inw gamerule advance_time false 2>/dev/null
inw gamerule doDaylightCycle false 2>/dev/null
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
do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give redin_guard_sword" "cmd:/soulstest give pilgrim_buckler off" "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5
if has hud; then
  do_ wait:1 shot:${P}hud_idle
fi
if has damage; then
  con execute as Tester run soulstest hit 7 type=none
  do_ wait:0.25 shot:${P}hud_damage wait:1.5
  con execute as Tester run soulstest heal
  do_ wait:0.5 clearchat
fi
if has low; then
  con execute as Tester run soulstest stamina set 6
  con execute as Tester run soulstest hit 15 type=none
  do_ wait:0.4 shot:${P}hud_low wait:0.5
  con execute as Tester run soulstest heal
  do_ wait:0.5 clearchat
fi
if has boss; then
  con execute as Tester run soulstest boss 100 100
  con execute as Tester run soulstest boss 61 34
  do_ wait:0.5 clearchat wait:0.3 shot:${P}hud_boss
  con execute as Tester run soulstest boss off
  do_ wait:0.5 clearchat
fi
L=$((CX - 88*G)); T=$((CY - 83*G))
if has inv; then
  do_ key:e wait:1 move:$((L + 16*G)):$((T + 92*G)) wait:0.8 shot:${P}inventory_tooltip key:Escape wait:0.5
fi
if has pause; then
  do_ key:Escape wait:2.5 move:$((CX + 40)):$((CY - 40*G)) wait:0.5 move:$((CX)):$((CY - 49*G)) wait:0.5 move:$((CX + 3)):$((CY - 48*G)) wait:0.8 shot:${P}pause key:Escape wait:0.5
fi
if has options; then
  # 일시 정지 → 설정 (밀대·단추): 설정 단추는 왼쪽 열 셋째 줄 (GUI y = 높이/4 + 90)
  GH=$((H/G))
  do_ key:Escape wait:2.5 move:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:0.5 click:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:2.5 \
      move:$((CX - 80*G)):$((60*G)) wait:0.4 move:$((CX - 78*G)):$((62*G)) wait:0.8 shot:${P}options key:Escape wait:1 key:Escape wait:0.8
fi
if has dialog; then
  do_ clearchat wait:0.3 "cmd:/soulstest dialog" wait:3 move:$((CX + 40)):$((CY)) wait:0.5 move:$((CX)):$((99*G)) wait:0.5 move:$((CX + 3)):$((100*G)) wait:0.8 shot:${P}rest_dialog key:Escape wait:0.6 clearchat
fi
if has chat; then
  con tellraw Tester '{"translate":"souls.bonfire.lit","color":"#9e7c44"}'
  con tellraw Tester '{"translate":"souls.bonfire.enemies-back","color":"#858079"}'
  con tellraw Tester '{"translate":"multiplayer.player.joined","with":["Tester"],"color":"yellow"}'
  con tellraw Tester '{"translate":"souls.souls.recovered","color":"#b3a37f"}'
  do_ "cmd:/time query daytime" wait:0.8 key:t wait:0.8 shot:${P}chat key:Escape wait:0.5 clearchat
fi
if has death; then
  do_ "cmd:/soulstest kill" wait:2.5 clearchat move:$((CX)):$((CY + 30*G)) wait:0.6 shot:${P}death respawn wait:3 clearchat
  home
fi
