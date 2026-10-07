#!/bin/bash
# 구르기 모습 한 줄 그림 (DESIGN.md 3.3 "보이는 모습"). 실제 클라이언트로 앞구르기를 찍어 장면 몇 장을 가로로 잇는다.
#   roll_strip.sh <포트> <서버폴더> [모습...]        모습: tumble spin crawl (기본 셋 다)
# 서버는 devserver.sh 로 켠 시험 서버여야 한다 (Tester 에게 op). 모습마다 서버 설정 combat.roll.visual 을 바꾸고
# /souls reload 한 뒤, 구르기 길 (/souls tp lane) 에서 W 를 누른 채 F 로 앞으로 구른다. 끝나면 설정을 처음 값으로 되돌린다.
# 보는 쪽 (VIEWS): back = F5 한 번 (3인칭 등 뒤), front = F5 두 번 (3인칭 앞), first = 1인칭 (CROP 은 화면 전체가 알맞다).
# 찍기: mcclient 의 burst (BMP 로 잇달아 찍기, 한 장 약 0.04초) 가 F 를 누르기 직전부터 찍고, 찍은 때를 _times.json 에 남긴다.
# 그 가운데 F 를 누른 때부터 SPAN 틱 동안을 FRAMES 장으로 고르게 골라 (가장 가까운 장) 몸 둘레를 잘라 가로로 잇는다.
# 장마다 밑에 F 뒤 게임 시간 (틱, 밀리초) 과 실제로 찍은 때를 적는다.
#
# 환경 변수
#   OUT         결과 폴더 (기본 dist/screenshots/roll). <모습>_<보는 쪽>.png
#   RAW         찍은 원본 (장마다 1280x720 PNG 와 _times.json, 기록) 폴더 (기본 ${TMPDIR:-/tmp}/roll_strip_raw: 저장소 밖)
#   VIEWS       "back front" (기본)
#   TICK_RATE   찍는 동안 /tick rate (기본 5 = 4배 느리게). 이 가상 화면 클라이언트는 llvmpipe 로 초당 10장 안팎이라
#               제 속도 (20) 로는 구르기 0.6초에 다른 장면이 5~6장뿐이다. 클라이언트도 서버 틱 속도를 따라 몸·대역 보간·움직임이
#               모두 같이 느려진다 (마인크래프트 /tick). 그림의 시간은 게임 시간이다. 20 으로 주면 제 속도로 찍는다
#   FRAMES      고를 장수 (기본 8)
#   SPAN        F 뒤 몇 틱까지 고를지 (기본 14: 가벼운 구르기 끝 12틱 + 클라이언트가 늦게 보는 몫)
#   CROP        잘라낼 상자 x0,y0,x1,y1 (기본 440,320,840,700: 1280x720 화면에서 구르는 몸 둘레)
#   HUD=1       HUD 를 숨기지 않는다 (기본은 F1 로 숨긴다: 행동 막대 글자가 대역 위에 겹친다)
#   ITEMS=1     구르기 전에 손·몸에 장비를 준다: 주손 시험 막기 도구 (souls 아이템), 왼손 바닐라 방패, 쇠 투구·흉갑.
#               tumble 이 3인칭에서 든 것·입은 것을 감추고 끝나면 되돌리는지, 단축 슬롯 그림이 그대로인지 본다 (HUD=1, 넓은 CROP 과 함께)
#   SUFFIX      그림 이름 꼬리 (예 _rt: TICK_RATE=20 으로 제 속도로 찍은 판을 tumble_back_rt.png 로 따로 남긴다)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
[ $# -ge 2 ] || { sed -n '2,24p' "$0"; exit 2; }
PORT=$1
SRVDIR=$2
shift 2
VISUALS=${*:-tumble spin crawl}
OUT=${OUT:-$ROOT/dist/screenshots/roll}
VIEWS=${VIEWS:-back front}
TICK_RATE=${TICK_RATE:-5}
FRAMES=${FRAMES:-8}
SPAN=${SPAN:-14}
CROP=${CROP:-440,320,840,700}
RC="$HERE/run_client.sh"
DEV="$HERE/devserver.sh"
CFG="$SRVDIR/plugins/Soulslike/config.yml"
[ -f "$CFG" ] || { echo "roll_strip: 서버 설정이 없다: $CFG" >&2; exit 2; }
RAW=${RAW:-${TMPDIR:-/tmp}/roll_strip_raw}
mkdir -p "$OUT" "$RAW"
export MC_OPTIONS="${MC_OPTIONS:-chatScale:0.0}"

orig=$(grep -E '^ +visual:' "$CFG" | head -n 1 | sed 's/^ *visual: *//')
set_visual() {
  sed -i "s|^\( *\)visual:.*|\1visual: $1|" "$CFG"
  "$DEV" --cmd "$SRVDIR" souls reload
  sleep 1
}

started=0
if ! "$RC" --status "$PORT" 2>/dev/null | grep -q '"running": true'; then
  "$RC" --start "$PORT" "$RAW" || exit 1
  started=1
  "$RC" --do "$PORT" join || exit 1
fi
# burst 는 클라이언트를 켤 때 준 찍을폴더에 쓴다 (이미 켜져 있었으면 그 폴더). 끝나면 RAW 로 옮긴다
SHOTDIR=$("$RC" --status "$PORT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('outdir',''))")
[ -d "$SHOTDIR" ] || { echo "roll_strip: 클라이언트 찍을폴더를 모른다" >&2; exit 1; }
cleanup() {
  [ -n "$orig" ] && set_visual "$orig"
  "$RC" --do "$PORT" "cmd:/tick rate 20" >/dev/null 2>&1
  [ "$started" = 1 ] && "$RC" --stop "$PORT" >/dev/null 2>&1
}
trap cleanup EXIT

# 느리게 찍으면 장 사이를 조금 띄운다 (같은 장면을 여러 번 찍지 않게). 장수는 SPAN 틱 + 앞뒤 여유를 덮게
slow=$(python3 -c "print(20.0 / $TICK_RATE)")
gap=$(python3 -c "print(0.0 if $slow <= 1 else min(0.12, 0.03 * $slow))")
count=$(python3 -c "import math; s=$slow; g=max($gap, 0.04); print(int(math.ceil(((($SPAN + 4) * 0.05 * s) + 0.15) / g)) + 3)")

"$RC" --do "$PORT" "cmd:/clear" "cmd:/effect clear @s" wait:0.5 || exit 1
for v in $VISUALS; do
  set_visual "$v"
  for view in $VIEWS; do
    case "$view" in
      back) f5="key:F5" ;;
      front) f5="key:F5 key:F5" ;;
      first) f5="wait:0" ;;
      *) echo "roll_strip: 모르는 보는 쪽: $view" >&2; exit 2 ;;
    esac
    hud="key:F1"; [ "${HUD:-0}" = 1 ] && hud="wait:0"
    gear="wait:0"
    [ "${ITEMS:-0}" = 1 ] && gear="cmd:/soulstest guard empty|cmd:/item replace entity @s weapon.offhand with minecraft:shield|cmd:/item replace entity @s armor.head with minecraft:iron_helmet|cmd:/item replace entity @s armor.chest with minecraft:iron_chestplate"
    name="${v}_${view}${SUFFIX:-}"
    rm -f "$RAW/${name}"_*.png "$RAW/${name}_times.json" "$SHOTDIR/${name}"_*.png "$SHOTDIR/${name}_times.json"
    # shellcheck disable=SC2086
    IFS='|' read -r -a gearv <<< "$gear"
    "$RC" --do "$PORT" "cmd:/clear" "${gearv[@]}" "cmd:/soulstest heal" "cmd:/souls tp lane" wait:1.2 "cmd:/tick rate $TICK_RATE" wait:0.6 \
      $f5 $hud wait:0.8 down:w wait:$(python3 -c "print(0.25 * $slow)") \
      "burst:$name:$count:f:2:$gap" up:w wait:$(python3 -c "print(0.6 * $slow)") \
      "cmd:/tick rate 20" $hud $(case "$view" in back) echo key:F5 key:F5 ;; front) echo key:F5 ;; *) echo wait:0 ;; esac) wait:0.5 \
      > "$RAW/${name}.log" 2>&1 \
      || { tail -20 "$RAW/${name}.log"; exit 1; }
    grep -a "간격" "$RAW/${name}.log"
    if [ "$SHOTDIR" != "$RAW" ]; then mv "$SHOTDIR/${name}"_*.png "$SHOTDIR/${name}_times.json" "$RAW/"; fi
    python3 - "$OUT" "$RAW" "$name" "$TICK_RATE" "$FRAMES" "$SPAN" "$CROP" "$v" "$view" <<'PY' || exit 1
import json, os, sys
from PIL import Image, ImageDraw
out, raw, name, rate, frames, span, crop, visual, view = sys.argv[1:]
rate, frames, span = float(rate), int(frames), float(span)
box = tuple(int(x) for x in crop.split(","))
tm = json.load(open(os.path.join(raw, name + "_times.json")))
shots, key = tm["shots"], tm["key_at"]
slow = 20.0 / rate
# F 를 누른 때부터 span 틱 (게임 시간) 을 frames 장으로: 실제 시간 = 게임 틱 × 0.05 × slow
want = [key + (span * k / (frames - 1)) * 0.05 * slow for k in range(frames)]
pick = [min(range(len(shots)), key=lambda i: abs(shots[i] - w)) for w in want]
ims = [Image.open(os.path.join(raw, "%s_%02d.png" % (name, i))).convert("RGB").crop(box) for i in pick]
w, h = ims[0].size
head, foot = 22, 30
sheet = Image.new("RGB", (w * len(ims), h + head + foot), (18, 17, 16))
d = ImageDraw.Draw(sheet)
gaps = [b - a for a, b in zip(shots, shots[1:])]
d.text((6, 5), "roll visual=%s view=%s  tick rate %g (x%g slow)  shots %d, spacing %.0f-%.0f ms real, frames picked by game time after F"
       % (visual, view, rate, slow, len(shots), min(gaps) * 1000, max(gaps) * 1000), fill=(225, 220, 205))
for n, (im, i) in enumerate(zip(ims, pick)):
    x = n * w
    sheet.paste(im, (x, head))
    g = (shots[i] - key) / slow          # 게임 시간 (초)
    d.text((x + 6, head + h + 3), "t=%+.1f tick  %+d ms" % (g / 0.05, round(g * 1000)), fill=(225, 220, 205))
    d.text((x + 6, head + h + 16), "shot %d @ %+d ms real" % (i, round((shots[i] - key) * 1000)), fill=(150, 145, 135))
    if n:
        d.line((x, head, x, head + h), fill=(60, 56, 52))
path = os.path.join(out, name + ".png")
sheet.save(path)
print("STRIP", path, "picked", pick)
PY
  done
done
echo "끝: $OUT"
