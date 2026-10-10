#!/bin/bash
# 능력치 표와 시작 창 그림 (DECISIONS 2026-10-10 "AI 티 나는 UI 글·화면을 고친다", DESIGN 5.7, 5.9, 5.10):
#   sheet_shots.sh <포트> <서버폴더> <앞머리>
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 그림은 그 찍을폴더에
# <앞머리><장면>.png 로 남는다. W, H, G = 화면 크기, GUI 배율 (클라이언트를 켤 때의 MC_SIZE, MC_GUI_SCALE 과 같게). 영어는
# MC_LANG=en_us 클라이언트와 SUFFIX=_en. 시험 줄이 그림에 남지 않게 MC_OPTIONS="chatScale:0.0" 로 켠 클라이언트에서 찍는다.
# 장면 (ONLY 에 빈칸으로 골라 준다. 없으면 모두):
#   settings  세계 설정 창 (5.7): settings
#   origin    출신 창 (origin_list) 과 도적 확인 창 (origin_confirm_thief: 시작 아이템 셋, 능력치 표, 조작 줄). 찍은 뒤 빈털터리로
#   levelup   레벨 업 창 (5.9, 소울 25,000, 왼손 순례자 버클러): 더한 점 없이 (levelup_idle), 근력 +3 (levelup_str: 레벨 1 → 4,
#             보유 소울 25,000 → 23,980, 근력 10 → 13, 공격력·장비 중량·방어력 미리보기) 과 근력 "+" 단추의 설명 칸 (levelup_str_tip)
#   stats     능력치 창 (5.9): 출신·레벨·보유 소울과 능력치 여섯 | 나온 값, 장비 중량 밑의 무게 단계 (stats)
#   rest      휴식 창 (4.1): 본문의 레벨·보유 소울·필요 소울 세 줄 (rest_menu)
# 근력 "+" 단추는 능력치 단추 줄 (여섯, 폭 64 + 사이 2) 의 넷째 칸: 가운데 + 33 GUI. 줄의 화면 높이는 PLUS_Y (기본: 1080 이면 797,
# 720 이면 525: 실제 화면에서 잰 값. 창 본문이 위에서부터 놓여 화면 높이에 따라 단추 줄이 옮겨 간다)
set -u
R=$(cd "$(dirname "$0")/../.." && pwd)
PORT=$1; SRV=$2; P=$3; shift 3
W=${W:-1920}; H=${H:-1080}; G=${G:-4}
X=${SUFFIX:-}
CX=$((W/2))
PLUS_Y=${PLUS_Y:-$(( H >= 1080 ? 797 : 525 ))}
cd "$R"
do_() { tools/client/run_client.sh --do "$PORT" "$@" 2>&1 | grep -E "SHOT|오류|rror" ; }
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
inw() { con execute in minecraft:souls_world run "$@"; }
tst() { con execute as Tester run soulstest "$@"; }
ONLY=${ONLY:-}
want() { [ -z "$ONLY" ] || [[ " $ONLY " == *" $1 "* ]]; }
# 마우스는 왼쪽 가장자리 가운데 (단추·바닥 줄 밖: 가리킨 단추의 장식과 설명 칸이 그림에 남지 않게)
away() { do_ move:10:$((H / 2)) wait:0.8 "shot:${P}$1${X}"; }

con gamemode adventure Tester
con effect clear Tester
inw time set 12700
inw gamerule advance_time false 2>/dev/null
inw weather clear
con clear Tester
inw tp Tester 200.5 101 -189.5 180 0
gear() { do_ slot:1 "cmd:/soulstest give redin_guard_sword main" "cmd:/soulstest give pilgrim_buckler off" "cmd:/soulstest heal" wait:1.5 clearchat wait:0.5; }

if want settings; then
  con execute as Tester run souls settings
  do_ wait:2.5
  away settings
  do_ key:Escape wait:0.8
fi
if want origin; then
  con souls origin reset Tester
  do_ wait:2.5
  away origin_list
  tst press origin thief
  do_ wait:2
  away origin_confirm_thief
  tst press origin_confirm choose
  do_ wait:1
  con souls origin reset Tester
  do_ wait:1.5
  tst origin deprived
  do_ wait:1
fi
gear
if want levelup || want stats || want rest; then
  tst souls 25000
  tst rest
  do_ wait:2
fi
if want rest; then
  away rest_menu
fi
if want levelup; then
  tst press rest levelup
  do_ wait:2
  away levelup_idle
  tst levelup str 3
  do_ wait:2
  away levelup_str
  # 단추 설명 칸은 마우스를 올리고 조금 움직인 뒤 잠시 머물러야 뜬다
  do_ move:$((CX + 33*G)):$PLUS_Y wait:0.3 move:$((CX + 33*G + 2)):$((PLUS_Y - 2)) wait:2.5 "shot:${P}levelup_str_tip${X}"
  tst press levelup exit
  do_ wait:1
fi
if want stats; then
  tst press rest stats
  do_ wait:2
  away stats
  do_ key:Escape wait:1
fi
if want levelup || want stats || want rest; then
  do_ wait:0.5 key:Escape wait:1
  tst souls 0
fi
