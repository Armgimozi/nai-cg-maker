#!/bin/bash
# 반지 칸 그림 (DESIGN.md 9.4, 10.4): 인벤토리 2×2 제작 칸 자리의 반지 칸 둘 (왼쪽 세로 두 칸) 을 실제 클라이언트로 찍는다.
#   ring_shots.sh <포트> <서버폴더> <앞머리>
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면><SUFFIX>.png 로 남는다. W, H, G = 화면 크기·GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게),
# SUFFIX = 이름 끝 (영어 클라이언트면 _en). 시험 줄이 그림에 남지 않게 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서.
# 장면 (차례대로, 끼기는 서버 명령이 아니라 진짜 누르기로 한다):
#   ring_none              반지를 끼지 않았다 (흐린 반지 둘). 가방에 시험 반지 셋
#   ring_hover_ring        대조: 빈 반지 칸 1 에 마우스 (가리킴 테가 그려진다. 찍은 그림에 커서가 없어 이것이 마우스 자리를 보인다)
#   ring_hover_erased      지운 오른쪽 위 칸 (116, 18) 에 같은 길로 마우스: 가리킴 테가 없다 (GUI 셰이더, 10.8)
#   ring_hover_erased_lower 지운 오른쪽 아래 칸 (116, 36): 테가 없다
#   ring_hover_result      지운 결과 칸 (154, 28): 테가 없다
#   ring_recipe_open       투명한 제작법 책 단추 자리 (GUI 104..124, 61..79) 를 눌러 빈 책이 열리고 창이 오른쪽으로 77 밀린 것
#                          (9.4 의 알려진 한계 1). 마우스는 창 밖 오른쪽
#   ring_hover_ring_open   책을 연 채 밀린 반지 칸 1 에 마우스: 테가 그려진다 (대조)
#   ring_hover_erased_open 책을 연 채 밀린 지운 칸 (116, 18): 테가 없다 (셰이더의 책 열린 갈래)
#   ring_hover_result_open 책을 연 채 밀린 결과 칸 (154, 28): 테가 없다. 그다음 책을 닫는다 (클라이언트와 서버가 기억한다)
#   ring_one               가방의 스태미나 반지를 집어 반지 칸 1 (왼쪽 위) 에 누른다
#   ring_two               가방의 강인도 반지를 웅크리고 누른다 (빈 반지 칸 2 에 낀다)
#   ring_tooltip           낀 스태미나 반지의 설명 칸 (이름, 효과 줄 "스태미나 회복 +20%", 설명)
#   ring_tooltip_pending   낀 강인도 반지의 설명 칸 (효과 줄 밑에 "아직 적용되지 않는 효과")
# 찍기 앞의 꾸밈은 ui_shots.sh 의 invplain (시안 dist/screenshots/ring_slots/ring_B_1080.png 의 바탕) 과 같다: 시험 방 저녁,
# 단축 슬롯에 아이템 여럿, 든 칸·소지품 첫 칸에 레딘 경비대 직검, 왼손은 비움. 끝나면 반지를 빼고 인벤토리를 비운다.
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
con gamemode adventure Tester
con effect clear Tester
inw time set 12700
inw gamerule advance_time false 2>/dev/null
inw weather clear
con execute as Tester run soulstest ring equip 1 none
con execute as Tester run soulstest ring equip 2 none
con clear Tester
con item replace entity Tester hotbar.1 with minecraft:bread 48
con item replace entity Tester hotbar.2 with minecraft:bone 6
con item replace entity Tester hotbar.3 with minecraft:coal 10
con item replace entity Tester hotbar.4 with minecraft:torch 16
con item replace entity Tester hotbar.5 with minecraft:flint 6
con item replace entity Tester hotbar.6 with minecraft:rotten_flesh 18
con item replace entity Tester hotbar.7 with minecraft:netherite_ingot 2
con item replace entity Tester hotbar.8 with minecraft:charcoal 5
inw tp Tester 200.5 101 -189.5 180 0
# 든 칸 (단축 1) 과 소지품 첫 칸 (가방 9) 에 직검. 반지 셋은 가방 10·11·12 (시험 반지는 가방부터 들어간다)
do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give redin_guard_sword" \
    "cmd:/soulstest ring give test_stamina" "cmd:/soulstest ring give test_poise" "cmd:/soulstest ring give test_parry" \
    "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5
# 인벤토리 판의 왼쪽 위 (GUI 가운데 - 88, - 83). 칸 (GUI x, y) 의 가운데는 L + (x + 8) G, T + (y + 8) G
L=$((CX - 88*G)); T=$((CY - 83*G))
at() { echo "$((L + ($1 + 8)*G)):$((T + ($2 + 8)*G))"; }
OUT=$(at -48 32)              # 판 밖 왼쪽 (설명 칸 없이)
RING1=$(at 98 18); RING2=$(at 98 36); ERASED=$(at 116 18); ERASED2=$(at 116 36); RESULT=$(at 154 28)
BAG10=$(at 26 84); BAG11=$(at 44 84)
# 제작법 책 단추 (바닐라 InventoryScreen: 판 왼쪽 + 104, 화면 가운데 높이 - 22, 20×18. 그림은 투명). 책을 열면 판이 오른쪽으로 77
RX=$((L + (104 + 10)*G)); RY=$((CY - 13*G)); LO=$((L + 77*G))
ato() { echo "$((LO + ($1 + 8)*G)):$((T + ($2 + 8)*G))"; }
OUT_OPEN=$(ato 196 40)        # 밀린 판 밖 오른쪽
do_ key:e wait:1.2 move:$OUT wait:0.8 shot:${P}ring_none${X}
# 가리킴 테: 같은 move 로 빈 반지 칸 (대조, 테가 있다) 과 지운 세 칸 (테가 없다)
do_ move:$RING1 wait:0.8 shot:${P}ring_hover_ring${X} move:$ERASED wait:0.8 shot:${P}ring_hover_erased${X} \
    move:$ERASED2 wait:0.8 shot:${P}ring_hover_erased_lower${X} move:$RESULT wait:0.8 shot:${P}ring_hover_result${X}
# 제작법 책이 열린 길 (셰이더의 둘째 갈래: 판 왼쪽 = 177 + (화면 너비 - 376) / 2). 끝나면 책을 닫는다
do_ click:$RX:$RY wait:1.2 move:$OUT_OPEN wait:0.8 shot:${P}ring_recipe_open${X} \
    move:$(ato 98 18) wait:0.8 shot:${P}ring_hover_ring_open${X} move:$(ato 116 18) wait:0.8 shot:${P}ring_hover_erased_open${X} \
    move:$(ato 154 28) wait:0.8 shot:${P}ring_hover_result_open${X} click:$((RX + 77*G)):$RY wait:0.8 move:$OUT wait:0.5
do_ click:$BAG10 wait:0.5 click:$RING1 wait:0.8 move:$OUT wait:0.8 shot:${P}ring_one${X}
do_ down:Shift_L click:$BAG11 up:Shift_L wait:0.8 move:$OUT wait:0.8 shot:${P}ring_two${X}
do_ move:$RING1 wait:1.0 shot:${P}ring_tooltip${X}
do_ move:$RING2 wait:1.0 shot:${P}ring_tooltip_pending${X}
do_ key:Escape wait:0.5
con execute as Tester run soulstest ring equip 1 none
con execute as Tester run soulstest ring equip 2 none
con clear Tester
