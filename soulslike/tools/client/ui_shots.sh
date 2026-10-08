#!/bin/bash
# UI 점검 그림 (DESIGN.md 10.2, 10.4, 10.5): HUD·창·설정·사망 화면·채팅·휴식 창을 실제 클라이언트로 찍는다.
#   ui_shots.sh <포트> <서버폴더> <앞머리> [장면...]
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면>.png 로 남는다. W, H, G = 화면 크기, GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게).
# 장면 (기본: chat 을 뺀 전부):
#   hud damage low boss inv chest craft pause options dialog death      (처음부터 있던 것)
#   invplain   설명 칸 없는 인벤토리, 왼손 칸이 빈 것 (빈 방패 칸 그림)
#   recipe     인벤토리의 제작법 책 (판, 탭, 검색 글 칸, 제작법 칸, 거르개 단추). 찍은 뒤 다시 닫는다 (클라이언트가 기억한다)
#   chests     큰 상자 (작은 설명 칸 "뼈다귀" 를 띄운다), 통, 엔더 상자
#   effects    효과 표시 (HUD 오른쪽 위, 인벤토리 옆)
#   water      물속의 숨 거품 (단축 슬롯 위)
#   toasts     발전 과제 알림과 제작법 알림 (오른쪽 위)
#   stats adv  일시 정지 → 통계 / 발전 과제 창
#   widgets    고름 칸·글 칸 (게임 안에서는 바닐라 /dialog 의 boolean·text 입력으로만 보인다)
#   settings   세계를 정한다 창 (5.7: 난이도 넷 + PvP 체크 칸)
#   origin     출신 창과 도적 확인 창 (5.10). 찍은 뒤 빈털터리로 되돌린다 (souls 아이템이 거둬진다)
#   levelup    휴식 창 → 레벨 올리기 창 (체력 +3, 민첩 +2 를 더한 미리보기) → 능력치 창 (5.9)
#   그리고 chat
# 시험 줄 ([T] …) 이 그림에 남지 않게: chat 밖의 장면은 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서 (채팅 글이 그려지지
# 않는다), chat 은 보통 클라이언트에서 채팅을 비운 뒤 서버 콘솔의 tellraw 줄만, 채팅 창을 열지 않고 찍는다 (들어온 사람 자신에게는
# 플러그인이 "게임에 참여했습니다" 를 보내지 않는다, WorldService.onJoin). 영어 그림은 MC_LANG=en_us 로 켠 클라이언트에서.
# 시험 방 저녁 (시간 12700), 단축 슬롯에 아이템 여럿, 든 칸·소지품 첫 칸에 레딘 경비대 직검, 왼손에 순례자 버클러.
set -u
R=$(cd "$(dirname "$0")/../.." && pwd)
PORT=$1; SRV=$2; P=$3; shift 3
SCENES=${*:-"hud damage low boss inv invplain recipe chest chests craft effects water toasts pause stats adv options widgets dialog settings origin levelup death"}
W=${W:-1920}; H=${H:-1080}; G=${G:-4}
X=${SUFFIX:-}     # 그림 이름 끝 (영어 클라이언트면 _en)
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
  con execute as Tester run soulstest hit 140 type=none
  do_ wait:0.25 shot:${P}hud_damage${X} wait:1.5
  con execute as Tester run soulstest heal
  do_ wait:0.5
fi
if has low; then
  con execute as Tester run soulstest stamina set 6
  con execute as Tester run soulstest hit 300 type=none
  do_ wait:0.4 shot:${P}hud_low_stamina${X} wait:0.5
  # 잃은 몫이 다 빠진 뒤 (Hud.TRAIL_HOLD 0.8 초 + 줄어듦): 체력 채움 → 빈 몫의 끝
  do_ wait:1.6 shot:${P}hud_low_drained${X}
  con execute as Tester run soulstest heal
  do_ wait:0.5
fi
if has boss; then
  # 한 번 맞혀 잃은 몫이 다 빠지게 기다린 뒤 (빈 길) 다시 맞힌다 (짧은 잃은 몫): 채움·잃은 몫·빈 길·자세 줄이 다 보인다
  con execute as Tester run soulstest boss 100 100
  con execute as Tester run soulstest boss 75 20
  do_ wait:2.5
  con execute as Tester run soulstest boss 61 34
  do_ wait:0.5 shot:${P}hud_boss${X}
  con execute as Tester run soulstest boss off
  do_ wait:0.5
fi
# 인벤토리 판의 왼쪽 위 (GUI): 가운데 - 88, - 83. 소지품 첫 칸의 아이템 (8, 84)
L=$((CX - 88*G)); T=$((CY - 83*G))
if has inv; then
  do_ key:e wait:1 move:$((L + 16*G)):$((T + 92*G)) wait:0.8 shot:${P}inventory_tooltip${X} key:Escape wait:0.5
fi
if has invplain; then
  # 왼손을 비우고 (빈 방패 칸 그림), 마우스는 창 밖 (설명 칸 없이 27 칸 전부)
  con item replace entity Tester weapon.offhand with minecraft:air
  do_ wait:0.5 key:e wait:1 move:$((L - 40*G)):$((T + 40*G)) wait:0.8 shot:${P}inventory${X} key:Escape wait:0.5
  do_ "cmd:/soulstest give pilgrim_buckler off" wait:1
fi
if has recipe; then
  # 제작법 책 단추 (바닐라 InventoryScreen: 판 왼쪽 + 104, 화면 가운데 높이 - 22, 20×18). 열면 판이 오른쪽으로 77 비킨다
  RX=$((L + (104 + 10)*G)); RY=$((CY - 13*G))
  do_ key:e wait:1 click:$RX:$RY wait:1.2 move:$((CX - 120*G)):$((CY - 40*G)) wait:0.8 shot:${P}inventory_recipe${X} \
      click:$((RX + 77*G)):$RY wait:0.8 key:Escape wait:0.5
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
if has chests; then
  # 큰 상자 (오른쪽 반 x 200 + 왼쪽 반 x 201, 남쪽을 본다), 통, 엔더 상자. 큰 상자는 뼈다귀 위를 가리켜 작은 설명 칸을 띄운다
  con gamemode creative Tester
  inw setblock 200 102 -191 "minecraft:chest[facing=south,type=right]"
  inw setblock 201 102 -191 "minecraft:chest[facing=south,type=left]"
  inw item replace block 200 102 -191 container.3 with minecraft:rotten_flesh 7
  inw item replace block 200 102 -191 container.13 with minecraft:bone 2
  inw item replace block 201 102 -191 container.5 with minecraft:coal 12
  home
  T6=$((CY - 111*G))
  do_ mouse:right wait:1.5 move:$((L + (8+18*4+8)*G)):$((T6 + (18+18*1+8)*G)) wait:0.6 shot:${P}chest_double${X} key:Escape wait:0.5
  inw setblock 201 102 -191 minecraft:air
  inw setblock 200 102 -191 "minecraft:barrel[facing=south]"
  inw item replace block 200 102 -191 container.4 with minecraft:flint 3
  home
  do_ mouse:right wait:1.5 move:$((L - 40*G)):$((CY)) wait:0.6 shot:${P}barrel${X} key:Escape wait:0.5
  inw setblock 200 102 -191 "minecraft:ender_chest[facing=south]"
  home
  do_ mouse:right wait:1.5 move:$((L - 40*G)):$((CY)) wait:0.6 shot:${P}ender_chest${X} key:Escape wait:0.5
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
if has effects; then
  con effect give Tester minecraft:resistance 120 0
  con effect give Tester minecraft:slowness 120 0
  do_ wait:1 shot:${P}hud_effects${X} key:e wait:1 move:$((L - 40*G)):$((T + 40*G)) wait:0.6 shot:${P}inventory_effects${X} key:Escape wait:0.5
  con effect clear Tester
fi
if has water; then
  inw setblock 200 101 -190 minecraft:water
  inw setblock 200 102 -190 minecraft:water
  home
  do_ wait:6 shot:${P}hud_underwater${X}
  inw setblock 200 102 -190 minecraft:air
  inw setblock 200 101 -190 minecraft:air
  home
  do_ wait:1
fi
if has toasts; then
  con advancement revoke Tester only minecraft:story/mine_stone
  con recipe take Tester minecraft:torch
  con advancement grant Tester only minecraft:story/mine_stone
  con recipe give Tester minecraft:torch
  do_ wait:1.6 shot:${P}toasts${X} wait:6
fi
if has pause; then
  do_ key:Escape wait:2.5 move:$((CX + 40)):$((CY - 40*G)) wait:0.5 move:$((CX)):$((CY - 49*G)) wait:0.5 \
      move:$((CX + 3)):$((CY - 48*G)) wait:0.8 shot:${P}pause${X} key:Escape wait:0.5
fi
if has stats; then
  # 일시 정지 화면 둘째 줄 (가운데 높이/4 + 8 + 24 줄의 가운데): 왼쪽 발전 과제, 오른쪽 통계
  do_ key:Escape wait:2.5 click:$((CX + 53*G)):$(( (GH/4 + 42) * G )) wait:2 move:$((CX)):$((H - 20)) wait:0.5 shot:${P}stats${X} \
      key:Escape wait:1 key:Escape wait:0.8
fi
if has adv; then
  do_ key:Escape wait:2.5 click:$((CX - 53*G)):$(( (GH/4 + 42) * G )) wait:2 move:$((CX)):$((H - 20)) wait:0.5 shot:${P}advancements${X} \
      key:Escape wait:1 key:Escape wait:0.8
fi
if has options; then
  # 일시 정지 → 설정 → 비디오 설정 (밀대 여럿, 두루마리, 나눔줄). 찍을 때 마우스는 위젯 밖 (오른쪽 위 귀: 제목 줄 옆) 에
  # 둔다: 가리킨 손잡이·밀대는 금빛이라 초안 그림 (가리키지 않은 쇠빛) 과 견줄 수 없다
  # 설정 화면의 줄은 화면 높이와 상관없이 위에서 GUI 39 (시야 범위), 121 (비디오 설정) 에 놓인다
  PX=$((W - 8)); PY=8
  do_ key:Escape wait:2.5 move:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:0.5 click:$((CX - 53*G)):$(( (GH/4 + 90) * G )) wait:2.5 \
      move:$((CX - 40*G)):$((60*G)) wait:0.5 move:$PX:$PY wait:1 shot:${P}options${X}
  do_ click:$((CX - 80*G)):$((121*G)) wait:2.5 move:$PX:$PY wait:1 shot:${P}video${X} \
      key:Escape wait:1 key:Escape wait:1 key:Escape wait:0.8
fi
if has widgets; then
  # 고름 칸 (checkbox) 과 글 칸 (text_field): 게임 안에서 바닐라가 그리는 곳이 없어 (설정의 원격 측정 창은 꺼져 있다) 바닐라
  # /dialog 의 boolean·text 입력으로 띄운다. 글은 바닐라 언어 열쇠
  con 'dialog show Tester {type:"minecraft:notice",title:{translate:"options.title"},inputs:[{type:"minecraft:boolean",key:"a",label:{translate:"options.autoJump"},initial:1b},{type:"minecraft:boolean",key:"b",label:{translate:"options.hideMatchedNames"}},{type:"minecraft:text",key:"c",label:{translate:"gui.recipebook.search_hint"},width:200}]}'
  do_ wait:2 move:$((CX + 40)):$((CY - 30*G)) wait:0.5 move:$((CX)):$((H - 40)) wait:0.8 shot:${P}widgets${X} key:Escape wait:0.8
fi
if has dialog; then
  do_ "cmd:/soulstest dialog" wait:3 move:$((CX + 40)):$((CY)) wait:0.5 move:$((CX)):$((99*G)) wait:0.5 move:$((CX + 3)):$((100*G)) \
      wait:0.8 shot:${P}rest_dialog${X} key:Escape wait:0.6
fi
# 시작 설정·출신·레벨 (5.7~5.10): 서버가 띄우는 Dialog 창. 단추는 시험 명령 (soulstest press) 으로 누른다 (봇과 같은 단추 이름)
tst() { con execute as Tester run soulstest "$@"; }
if has settings; then
  con execute as Tester run souls settings
  do_ wait:2.5 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}settings_dialog${X} key:Escape wait:0.8
fi
if has origin; then
  con souls origin reset Tester
  do_ wait:2.5 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}origin_dialog${X}
  tst press origin thief
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}origin_confirm${X}
  tst press origin_confirm choose
  do_ wait:1 key:e wait:1 move:$((L - 40*G)):$((T + 40*G)) wait:0.8 shot:${P}origin_thief_inventory${X} key:Escape wait:0.5
  con souls origin reset Tester
  do_ wait:1.5
  tst origin deprived
  do_ wait:1 slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give pilgrim_buckler off" wait:1 clearchat
fi
if has levelup; then
  tst souls 25000
  tst rest
  do_ wait:2.5 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}rest_menu${X}
  tst press rest levelup
  tst levelup vig 3
  tst levelup dex 2
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}levelup${X}
  tst press levelup exit
  tst press rest stats
  # 능력치 창의 나가기는 휴식 창으로 돌아가고, 휴식 창의 나가기 (일어선다) 가 닫는다
  do_ wait:2 move:$((CX)):$((H - 20)) wait:0.8 shot:${P}stats_dialog${X} key:Escape wait:1 key:Escape wait:0.8
  tst souls 0
fi
if has chat; then
  do_ clearchat wait:0.5
  con tellraw Tester '{"translate":"souls.bonfire.lit","color":"#9e7c44"}'
  con tellraw Tester '{"translate":"souls.bonfire.enemies-back","color":"#858079"}'
  con tellraw Tester '{"translate":"souls.souls.recovered","color":"#b3a37f"}'
  do_ wait:1.2 shot:${P}chat${X}
fi
if has death; then
  do_ "cmd:/soulstest kill" wait:2.5 move:$((CX)):$((CY + 30*G)) wait:0.6 shot:${P}death${X} respawn wait:3
  home
fi
