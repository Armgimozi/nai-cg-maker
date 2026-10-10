#!/bin/bash
# 바닐라 쥐는 법 점검 그림 (M1 P0, DECISIONS 2026-10-11 "무기 쥐는 각도는 바닐라 마인크래프트와 똑같이", pack/weapons/SPEC.md 1.3):
#   grip_shots.sh <포트> <서버폴더> [묶음...]       묶음: fp mq tp walk look (기본 모두). 끝에 겹침 그림과 차이 수치를 만든다
#   grip_shots.sh --diff <찍은폴더>                 찍은 그림으로 겹침 그림·수치만 다시 만든다
# 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>, --do <포트> join). 찍은 원본은 그 찍을폴더에 남고,
# 겹침 그림은 OUT (기본 dist/screenshots/grip/) 에 <장면>.png (바닐라 | 시험 모형 | 겹침 (빨강 바닐라만, 초록 시험 모형만, 노랑 둘 다)
# | 차이 ×4), 수치는 OUT/overlay.json 과 표준 출력의 표. 어긋남 (px) 은 시험 모형 그림을 ±4 화소 옮겨 바닐라와 가장 잘 맞는 자리의
# 거리다 (0 이면 그대로 겹친다). 그 자리에서도 남는 차이 (rest) 는 옆면의 가는 줄·빛 셈이 다른 곳, 0~3 화소 안에서 어떻게 옮겨도
# 남는 차이 (left) 도 적는다.
# 아이템 자리는 빈 모형 장 (E) 과 다른 화소에서 작은 덩이 (날리는 재, 등불 불꽃) 를 지운 것. MC_GUI_SCALE=2 (1280×720) 로 켠 클라이언트에서 찍는다 (1인칭은 단축 슬롯·이름
# 자리를 가리고 견준다). 시험 줄과 흐르는 구름이 그림에 남지 않게 MC_OPTIONS='chatScale:0.0;bobView:false;renderClouds:"false";particles:2' 로 켠다.
#
# 시험 모형 (팩 pack/weapons/gripcheck.py): 바닐라 그림을 P⁻¹ 로 우리 모형 공간에 놓고 우리 display 를 붙인 모형이다. 바닐라 아이템과
# 0 픽셀로 겹치면 우리 display 가 바닐라 자세를 그대로 옮긴 것이다. 짝 (바닐라 V / 시험 P / 빈 모형 E: 팔 자세는 같고 아이템만 없다):
#   sword   iron_sword / flint[item_model=souls:test_grip_sword]            (handheld: 검·도끼·단검·촉매)
#   mace    mace / flint[item_model=souls:test_grip_mace]                   (철퇴: 망치 셋)
#   spear   iron_spear / stone_spear[item_model=souls:test_grip_spear]      (창: 창·미늘창. 둘 다 #minecraft:spears 라 창 팔 자세)
#   bow     bow / bow[item_model=souls:test_grip_bow]                       (활, 당김 셋)
#   shield  shield / shield[item_model=souls:test_grip_shield]              (방패, 막기)
# 묶음
#   fp    플레이어 1인칭: 주손·왼손 평소, 막기 (칼·철퇴·창은 blocks_attacks 를 붙여 바닐라 칼 막기 몸짓, 방패는 왼손), 활 당김
#         0.75초·1.3초 (/tick rate 2 로 느리게: 당김 몸짓이 시간에 따라 움직인다)
#   mq    마네킹 (minecraft:mannequin, 플레이어 모형과 같은 손 사슬) 의 3인칭 손: 앞·뒤·오른쪽·왼쪽에서 주손·왼손, 방패 막기 모형과
#         활 당김 모형 (쓰지 않아도 보이는 정의 souls:test_grip_vanilla_* 와 souls:test_grip_shield_block, _bow_pulling_*). /tick freeze
#         한 세계에 아이템마다 새 마네킹을 소환한다 (장비는 소환 NBT: 언 몸은 장비 바뀜을 보내지 않는다). 클라이언트에서 새 몸은
#         틱 0 에 언 채라 팔 흔들림 (bobArms) 이 장마다 같다: 3인칭 display 의 정확한 검사
#   tp    플레이어 F5 등 뒤·앞: 평소, 막기, 활 당김. 플레이어는 얼지 않아 팔 흔들림이 장마다 조금 다르다 (/tick rate 1 로 줄인다)
#   walk  플레이어 F5 걷기 (잇달아 찍고 몸 자세가 가장 비슷한 장끼리 견준다)
#   look  실제 아이템 (/soulstest give): 1인칭, F5 등 뒤·앞, 막기·당김 (look_<id>.png)
# 환경 변수: OUT, ONLY_PROBES (기본 "sword mace spear bow shield"), LOOK (look 의 "id:main|off" 목록)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
R=$(cd "$HERE/../.." && pwd)
OUT=${OUT:-$R/dist/screenshots/grip}
mkdir -p "$OUT"

diff_only=0
if [ "${1:-}" = "--diff" ]; then
  diff_only=1; RAW=$2
else
  [ $# -ge 2 ] || { sed -n '2,32p' "$0"; exit 2; }
  PORT=$1; SRV=$2; shift 2
  WHAT=${*:-fp mq tp walk look}
  RC="$HERE/run_client.sh"; DEV="$HERE/devserver.sh"
  RAW=$("$RC" --status "$PORT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('outdir',''))")
  [ -d "$RAW" ] || { echo "grip_shots: 클라이언트가 켜져 있지 않다 (run_client.sh --start, --do join)" >&2; exit 2; }
fi

if [ "$diff_only" = 0 ]; then
PROBES=${ONLY_PROBES:-sword mace spear bow shield}
want() { [[ " $WHAT " == *" $1 "* ]]; }
do_() { "$RC" --do "$PORT" "$@" > /dev/null 2>&1 || { echo "grip_shots: 동작 실패: $*" >&2; exit 1; }; }
con() { "$DEV" --cmd "$SRV" "$1"; sleep "${2:-0.5}"; }
W=souls_world
# 플레이어 자리 (시험 방 가운데 조금 남쪽, 북쪽을 본다: 앞 11칸·뒤 4칸이 비어 F5 카메라가 막히지 않는다) 와 마네킹 자리 (2.5 블록 앞).
# 방 가운데 (200, 100, -200) 는 devserver 의 시험 세계 기본값
PX=${PX:-200.5}; PY=${PY:-101}; PZ=${PZ:--201.5}
MX=$PX; MZ=$(python3 -c "print($PZ - 2.5)")
home() { con "execute in minecraft:$W run tp Tester $PX $PY $PZ 180 ${1:-12}"; }
mq_at() { con "execute in minecraft:$W run tp @e[type=minecraft:mannequin,tag=grip] $1 $PY $2 ${3:-0} 0"; }
CAM=0
cam() {   # 0 1인칭, 1 F5 등 뒤, 2 F5 앞
  local n=$(( ($1 - CAM + 3) % 3 )) a=()
  for _ in $(seq $n); do a+=(key:F5 wait:0.4); done
  [ $n -gt 0 ] && do_ "${a[@]}"
  CAM=$1
}
HIDE=0
hud() { [ "$1" != "$HIDE" ] && { do_ key:F1 wait:0.3; HIDE=$1; }; }   # 1 = F1 로 HUD 와 1인칭 손을 감춘다
item() {   # item <probe> <v|p|e> [block]
  local base v blk=""
  case $1 in
    sword) base=minecraft:flint; v=minecraft:iron_sword ;;
    mace) base=minecraft:flint; v=minecraft:mace ;;
    spear) base=minecraft:stone_spear; v=minecraft:iron_spear ;;
    bow) base=minecraft:bow; v=minecraft:bow ;;
    shield) base=minecraft:shield; v=minecraft:shield ;;
  esac
  [ "${3:-}" = block ] && blk="blocks_attacks={}"
  [ "${3:-}" = block ] && [ "$1" = spear ] && blk="blocks_attacks={},!kinetic_weapon"
  case $2 in
    v) [ -n "$blk" ] && echo "$v[$blk]" || echo "$v" ;;
    p) echo "$base[item_model=\"souls:test_grip_$1\"${blk:+,$blk}]" ;;
    e) echo "$base[item_model=\"souls:test_grip_empty\"${blk:+,$blk}]" ;;
  esac
}
put() { con "item replace entity $1 $2 with $3" "${4:-0.5}"; }
# 언 세계에서는 서버가 마네킹의 장비 바뀜을 그 몸의 틱에서 보낸다: 바꾼 뒤 한 틱만 돌린다 (팔 흔들림도 한 틱만큼만 움직인다)
mput() { put "$MQ" "$1" "$2" 0.2; con "tick step 1" "${3:-0.7}"; }
PL=Tester
MQ='@e[type=minecraft:mannequin,tag=grip,limit=1]'
clear_hands() { put $PL weapon.mainhand minecraft:air 0.2; put $PL weapon.offhand minecraft:air 0.2; }

con "execute in minecraft:$W run time set 6000"
con "gamerule advance_time false"
con "weather clear"
con "gamemode adventure Tester"
con "effect clear Tester"
con "clear Tester"
con "tick unfreeze"
con "tick rate 20"
con "kill @e[type=minecraft:mannequin,tag=grip]"
con "execute in minecraft:$W run summon minecraft:mannequin $MX $PY $MZ {Rotation:[0f,0f],Tags:[\"grip\"],hide_description:1b,immovable:1b}"
con "give Tester minecraft:arrow 64"
home
do_ wait:1.5

# ── 1인칭 (플레이어) ──
if want fp; then
  cam 0; hud 0
  mq_at $((210)) $MZ 0          # 마네킹을 시야 밖으로
  for pr in $PROBES; do
    for hand in main off; do
      clear_hands
      for k in v p e; do
        put $PL weapon.${hand}hand "$(item $pr $k)" 0.3
        do_ wait:2.6 "shot:fp_${pr}_${hand}_$k"
      done
    done
    # 막기: 칼·철퇴·창은 주손 (바닐라 칼 막기 몸짓), 방패는 왼손. 활은 막지 않는다
    [ "$pr" = bow ] && continue
    clear_hands
    hand=main; [ "$pr" = shield ] && hand=off
    for k in v p e; do
      put $PL weapon.${hand}hand "$(item $pr $k block)" 0.3
      do_ wait:2.6 mdown:right wait:1.0 "shot:fp_${pr}_block_$k" mup:right wait:0.5
    done
  done
  if [[ " $PROBES " == *" bow "* ]]; then
    clear_hands
    con "tick rate 2"
    for k in v p e; do
      put $PL weapon.mainhand "$(item bow $k)" 0.3
      do_ wait:5 mdown:right wait:7.5 "shot:fp_bow_draw075_$k" wait:5.3 "shot:fp_bow_draw130_$k" mup:right wait:2
    done
    con "tick rate 20"
  fi
  clear_hands
fi

# ── 마네킹 3인칭 (언 세계에 장마다 새 마네킹: 팔 흔들림이 틱 0 자세로 같다) ──
nbt() {   # nbt <probe> <v|p|e> → 아이템 NBT ({id, count, components})
  local base v
  case $1 in
    sword) base=minecraft:flint; v=minecraft:iron_sword ;;
    mace) base=minecraft:flint; v=minecraft:mace ;;
    spear) base=minecraft:stone_spear; v=minecraft:iron_spear ;;
    bow) base=minecraft:bow; v=minecraft:bow ;;
    shield) base=minecraft:shield; v=minecraft:shield ;;
  esac
  case $2 in
    v) echo "{id:\"$v\",count:1}" ;;
    p) echo "{id:\"$base\",count:1,components:{\"minecraft:item_model\":\"${3:-souls:test_grip_$1}\"}}" ;;
    e) echo "{id:\"$base\",count:1,components:{\"minecraft:item_model\":\"souls:test_grip_empty\"}}" ;;
    m) echo "{id:\"$base\",count:1,components:{\"minecraft:item_model\":\"$3\"}}" ;;
  esac
}
mspawn() {   # mspawn <yaw> <mainhand|offhand> <아이템 NBT>
  # 언 세계에서 죽인 몸은 쓰러지는 몸짓 (20틱) 에 멈춰 남는다: 21틱을 돌려 치운 뒤 새 몸을 소환한다 (새 몸은 틱 0)
  con "kill @e[type=minecraft:mannequin,tag=grip]" 0.2
  con "tick step 21" 1.6
  con "execute in minecraft:$W run summon minecraft:mannequin $MX $PY $MZ {Rotation:[${1}f,0f],Tags:[\"grip\"],hide_description:1b,immovable:1b,equipment:{$2:$3}}" 1.0
}
if want mq; then
  clear_hands
  cam 0; hud 1
  home 10
  con "kill @e[type=minecraft:mannequin,tag=grip]"
  con "tick freeze" 0.8
  for o in front back right left; do
    case $o in front) yaw=0 ;; back) yaw=180 ;; right) yaw=-90 ;; left) yaw=90 ;; esac
    for pr in $PROBES; do
      for hand in main off; do
        for k in v p e; do
          mspawn $yaw ${hand}hand "$(nbt $pr $k)"
          do_ "shot:mq_${o}_${pr}_${hand}_$k"
        done
      done
    done
    # 방패 막기 모형 (왼손), 활 당김 셋 (주손): 쓰지 않아도 보이는 정의
    if [[ " $PROBES " == *" shield "* ]]; then
      for k in v p e; do
        case $k in v) it=$(nbt shield m souls:test_grip_vanilla_shield_block) ;; p) it=$(nbt shield m souls:test_grip_shield_block) ;;
                   e) it=$(nbt shield e) ;; esac
        mspawn $yaw offhand "$it"
        do_ "shot:mq_${o}_shieldblock_off_$k"
      done
    fi
    if [[ " $PROBES " == *" bow "* ]]; then
      for i in 0 1 2; do
        for k in v p e; do
          case $k in v) it=$(nbt bow m souls:test_grip_vanilla_bow_pulling_$i) ;; p) it=$(nbt bow m souls:test_grip_bow_pulling_$i) ;;
                     e) it=$(nbt bow e) ;; esac
          mspawn $yaw mainhand "$it"
          do_ "shot:mq_${o}_bowpull${i}_main_$k"
        done
      done
    fi
  done
  con "kill @e[type=minecraft:mannequin,tag=grip]"
  con "tick unfreeze"
  con "execute in minecraft:$W run summon minecraft:mannequin $MX $PY $MZ {Rotation:[0f,0f],Tags:[\"grip\"],hide_description:1b,immovable:1b}"
  hud 0
fi

# ── 플레이어 F5 (팔 흔들림은 /tick rate 1 로 줄인다) ──
if want tp; then
  clear_hands
  mq_at 210 $MZ 0
  home 12
  hud 1
  con "tick rate 1"
  for view in 1 2; do
    cam $view
    vn=back; [ $view = 2 ] && vn=front
    for pr in $PROBES; do
      hand=main; [ "$pr" = shield ] && hand=off
      for k in v p e; do
        put $PL weapon.${hand}hand "$(item $pr $k)" 0.2
        do_ wait:1.6 "shot:tp_${vn}_${pr}_$k"
      done
      put $PL weapon.${hand}hand minecraft:air 0.2
      if [ "$pr" != bow ] && [ "$pr" != mace ]; then
        for k in v p e; do
          put $PL weapon.${hand}hand "$(item $pr $k block)" 0.2
          do_ wait:1.2 mdown:right wait:2.6 "shot:tp_${vn}_${pr}_block_$k" mup:right wait:1.2
        done
        put $PL weapon.${hand}hand minecraft:air 0.2
      fi
    done
  done
  con "tick rate 20"
  if [[ " $PROBES " == *" bow "* ]]; then
    cam 2
    con "tick rate 2"
    for k in v p e; do
      put $PL weapon.mainhand "$(item bow $k)" 0.3
      do_ wait:2 mdown:right wait:7.5 "shot:tp_front_bow_draw075_$k" wait:5.3 "shot:tp_front_bow_draw130_$k" mup:right wait:2
    done
    con "tick rate 20"
    put $PL weapon.mainhand minecraft:air 0.2
  fi
  cam 0; hud 0
fi

# ── 걷기 (F5 앞, 잇달아 찍는다) ──
if want walk; then
  clear_hands
  mq_at 210 $MZ 0
  hud 1
  cam 2
  for pr in sword spear shield; do
    [[ " $PROBES " == *" $pr "* ]] || continue
    hand=main; [ "$pr" = shield ] && hand=off
    for k in v p e; do
      put $PL weapon.${hand}hand "$(item $pr $k)" 0.2
      home 12
      do_ wait:1.5 down:w wait:0.5 "burst:walk_${pr}_$k:14:::0.06" up:w wait:0.8
    done
    put $PL weapon.${hand}hand minecraft:air 0.2
  done
  home 12
  cam 0; hud 0
fi

# ── 실제 아이템 ──
if want look; then
  LOOK=${LOOK:-redin_guard_sword:main gaoler_greatsword:main redin_spear:main hrolf_halberd:main gaoler_club:main levy_hatchet:off kiln_pot:off redin_guard_shield:off volk_greatshield:off wall_shortbow:main}
  mq_at 210 $MZ 0
  for spec in $LOOK; do
    id=${spec%%:*}; hand=${spec##*:}
    clear_hands
    con "execute as Tester run soulstest give $id $hand" 0.8
    home 12
    cam 0; hud 0
    do_ wait:2.6 "shot:look_${id}_fp"
    act=""
    case $id in
      redin_guard_sword|redin_spear|redin_guard_shield|volk_greatshield) act=block ;;
      wall_shortbow) act=draw ;;
    esac
    if [ "$act" = block ]; then do_ mdown:right wait:1.0 "shot:look_${id}_fp_use" mup:right wait:0.6; fi
    if [ "$act" = draw ]; then do_ mdown:right wait:1.4 "shot:look_${id}_fp_use" mup:right wait:0.6; fi
    hud 1
    cam 1; do_ wait:1.0 "shot:look_${id}_back"
    cam 2; do_ wait:1.0 "shot:look_${id}_front"
    if [ -n "$act" ]; then do_ mdown:right wait:1.4 "shot:look_${id}_front_use" mup:right wait:0.6; fi
    cam 0; hud 0
  done
  clear_hands
  con "clear Tester"
fi
con "kill @e[type=minecraft:mannequin,tag=grip]"
fi

# ── 겹침 그림과 수치 ──
python3 - "$RAW" "$OUT" <<'PY'
import glob, json, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
raw, out = sys.argv[1:]
T = 14          # 아이템 화소: 빈 모형 장과 채널 차이가 이보다 크다
TC = 6          # 색 차이 (같은 장면이라 아이템 밖은 똑같다: 낮게)
def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)
def hud_mask(name, shape):
    m = np.ones(shape[:2], bool)
    if name.startswith("fp_"):          # 1인칭은 HUD 가 보인다: 단축 슬롯·왼손 칸·든 것 이름 자리
        m[580:720, 380:840] = False
    return m
def dilate(m):
    o = m.copy()
    o[1:] |= m[:-1]; o[:-1] |= m[1:]
    o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    o[1:, 1:] |= m[:-1, :-1]; o[:-1, :-1] |= m[1:, 1:]; o[1:, :-1] |= m[:-1, 1:]; o[:-1, 1:] |= m[1:, :-1]
    return o
def directed(a, b, cap=40):
    """a 의 모든 화소가 b 에서 몇 화소 (체비쇼프) 안에 있는가."""
    if not a.any():
        return 0
    if not b.any():
        return cap
    cur = b.copy()
    for k in range(cap + 1):
        if not (a & ~cur).any():
            return k
        cur = dilate(cur)
    return cap
def clean(m, least=30):
    """작은 이어진 덩이 (날리는 재 입자, 등불 불꽃의 깜박임) 를 지운다 (8 이웃)."""
    from collections import deque
    seen = np.zeros(m.shape, bool)
    out = m.copy()
    comps = []
    H, Wd = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        comp, q = [], deque([(y0, x0)])
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            comp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < Wd and m[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        q.append((yy, xx))
        comps.append(comp)
    big = max((len(c) for c in comps), default=0)
    for comp in comps:
        # 아이템 덩이만 남긴다: 가장 큰 덩이의 5 % 보다 작은 덩이는 (흩날리는 재, 등불 불꽃의 깜박임) 지운다
        if len(comp) < max(least, 0.05 * big):
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = False
    return out
def crop_box(m, shape, pad=14):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return (0, 0, shape[1], shape[0])
    return (max(0, xs.min() - pad), max(0, ys.min() - pad), min(shape[1], xs.max() + pad + 1), min(shape[0], ys.max() + pad + 1))
def sheet(name, V, P, mV, mP, label):
    x0, y0, x1, y1 = crop_box(mV | mP, V.shape)
    s = max(1, min(3, 260 // max(1, y1 - y0)))
    ov = np.zeros(V.shape, np.uint8) + 24
    ov[mV & ~mP] = (230, 40, 40); ov[mP & ~mV] = (40, 220, 60); ov[mV & mP] = (220, 200, 60)
    df = np.clip(np.abs(V - P).max(axis=2) * 4, 0, 255).astype(np.uint8)
    tiles = [Image.fromarray(V.astype(np.uint8)), Image.fromarray(P.astype(np.uint8)), Image.fromarray(ov), Image.fromarray(df).convert("RGB")]
    tiles = [t.crop((x0, y0, x1, y1)).resize(((x1 - x0) * s, (y1 - y0) * s), Image.NEAREST) for t in tiles]
    w, h = tiles[0].size
    img = Image.new("RGB", (4 * w + 5 * 6, h + 40), (16, 15, 14))
    d = ImageDraw.Draw(img)
    for i, (t, cap) in enumerate(zip(tiles, ["vanilla", "probe (ours)", "overlay: red vanilla only, green probe only", "abs diff x4"])):
        img.paste(t, (6 + i * (w + 6), 22))
        d.text((6 + i * (w + 6), 4), cap, fill=(225, 220, 205))
    d.text((6, h + 25), label, fill=(225, 220, 205))
    img.save(os.path.join(out, name + ".png"))
def shifted(A, dy, dx):
    return np.roll(np.roll(A, dy, axis=0), dx, axis=1)
def explain(V, P, U):
    """어긋남 셈 (아이템 자리 U 안): 시험 모형 그림을 ±4 화소 옮겨 바닐라와 가장 잘 맞는 자리 (차이의 합이 가장 작은 곳).
    돌려주는 값 (그 자리 (dy, dx), 그 자리에서도 남는 차이 화소 수 (작은 점 지움), 0~3 화소 안에서 옮겨 보아도 남는 차이 [k=0..3])."""
    best, cost = (0, 0), None
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            c = float((np.abs(V - shifted(P, dy, dx)).max(axis=2) * U).sum())
            if cost is None or c < cost - 1e-6 or (abs(c - cost) <= 1e-6 and abs(dy) + abs(dx) < abs(best[0]) + abs(best[1])):
                best, cost = (dy, dx), c
    rest = int(clean((np.abs(V - shifted(P, *best)).max(axis=2) > TC) & U, least=6).sum())
    left = []
    for k in range(4):
        cur = None
        for dy in range(-k, k + 1):
            for dx in range(-k, k + 1):
                d = np.abs(V - shifted(P, dy, dx)).max(axis=2)
                cur = d if cur is None else np.minimum(cur, d)
        left.append(int(clean((cur > TC) & U, least=6).sum()))
    return best, rest, left
def item_masks(V, P, E, keep):
    mV = clean((np.abs(V - E).max(axis=2) > T) & keep)
    mP = clean((np.abs(P - E).max(axis=2) > T) & keep)
    return mV, mP
results = []
for vp in sorted(glob.glob(os.path.join(raw, "*_v.png"))):
    base = os.path.basename(vp)[:-6]
    pp, ep = os.path.join(raw, base + "_p.png"), os.path.join(raw, base + "_e.png")
    if not (os.path.exists(pp) and os.path.exists(ep)):
        continue
    V, P, E = load(vp), load(pp), load(ep)
    keep = hud_mask(base, V.shape)
    mV, mP = item_masks(V, P, E, keep)
    U = dilate(dilate(mV | mP)) & keep
    sh, col, left = explain(V, P, U)
    r = {"scene": base, "px": max(abs(sh[0]), abs(sh[1])), "shift": list(sh), "colour": col, "unexplained": left,
         "item_px": int(mV.sum()), "shape_xor": int((mV ^ mP).sum())}
    results.append(r)
    sheet(base, V, P, mV, mP, f"{base}: best overlay shift {sh} px; {col} px still differ there (thin side-face lines, shading); "
                              f"left after any 0/1/2/3 px shift: {left}; vanilla item {r['item_px']} px")
# 걷기: 잇달아 찍은 장에서 몸 자세가 가장 비슷한 짝 (바닐라 i, 시험 j, 빈 k)
for vp0 in sorted(glob.glob(os.path.join(raw, "walk_*_v_00.png"))):
    base = os.path.basename(vp0)[:-9]
    Vs = [load(p) for p in sorted(glob.glob(os.path.join(raw, base + "_v_[0-9][0-9].png")))]
    Ps = [load(p) for p in sorted(glob.glob(os.path.join(raw, base + "_p_[0-9][0-9].png")))]
    Es = [load(p) for p in sorted(glob.glob(os.path.join(raw, base + "_e_[0-9][0-9].png")))]
    if not (Vs and Ps and Es):
        continue
    small = lambda a: a[::4, ::4]
    i, j = min(((i, j) for i in range(len(Vs)) for j in range(len(Ps))), key=lambda ij: np.abs(small(Vs[ij[0]]) - small(Ps[ij[1]])).mean())
    k = min(range(len(Es)), key=lambda k: np.abs(small(Vs[i]) - small(Es[k])).mean())
    V, P, E = Vs[i], Ps[j], Es[k]
    keep = np.ones(V.shape[:2], bool)
    mV, mP = item_masks(V, P, E, keep)
    U = dilate(dilate(mV | mP))
    sh, col, left = explain(V, P, U)
    h = max(abs(sh[0]), abs(sh[1]))
    xor = int((mV ^ mP).sum())
    r = {"scene": base, "px": h, "shift": list(sh), "colour": col, "unexplained": left, "item_px": int(mV.sum()), "shape_xor": xor,
         "frames": [i, j, k], "note": "burst, closest body pose; includes walk-phase mismatch"}
    results.append(r)
    sheet(base, V, P, mV, mP, f"{base}: frames v{i} p{j} e{k} (closest pose), offset {h} px (left {left}), {col} px colour")
# 실제 아이템 한 줄
looks = {}
for p in sorted(glob.glob(os.path.join(raw, "look_*.png"))):
    m = re.match(r"look_(.+?)_(fp|fp_use|back|front|front_use)\.png$", os.path.basename(p))
    if m:
        looks.setdefault(m.group(1), {})[m.group(2)] = p
for wid, views in looks.items():
    order = [v for v in ("fp", "fp_use", "back", "front", "front_use") if v in views]
    ims = [Image.open(views[v]).convert("RGB").resize((640, 360)) for v in order]
    img = Image.new("RGB", (len(ims) * 646 + 6, 390), (16, 15, 14))
    d = ImageDraw.Draw(img)
    for n, (im, v) in enumerate(zip(ims, order)):
        img.paste(im, (6 + n * 646, 24))
        d.text((8 + n * 646, 5), {"fp": "first person", "fp_use": "first person, use (block / draw)", "back": "F5 back",
                                  "front": "F5 front", "front_use": "F5 front, use"}[v], fill=(225, 220, 205))
    img.save(os.path.join(out, f"look_{wid}.png"))
if results:
    with open(os.path.join(out, "overlay.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("%-34s %4s %9s %7s %7s  %s" % ("scene", "px", "shift", "rest", "item", "left after 0/1/2/3 px"))
    for r in results:
        print("%-34s %4d %9s %7d %7d  %s" % (r["scene"], r["px"], tuple(r["shift"]), r["colour"], r["item_px"], r["unexplained"]))
print("겹침 그림:", out)
PY
