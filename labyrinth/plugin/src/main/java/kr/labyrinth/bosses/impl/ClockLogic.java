package kr.labyrinth.bosses.impl;

import kr.labyrinth.bosses.BossMath;

/**
 * 지하 9층 시계탑의 간수 테오라의 순수 규칙 (Bukkit 무관 — 단위 테스트 대상, GDD §7.9).
 * <ul>
 *   <li>시간 봉인: 봉인석 수(6명 이상 6개)·시계 방향 배치, 시곗바늘 각속도·회전 방향, 각도 창(열림) 판정, 다음 열림까지 남은 시간</li>
 *   <li>종말 시계: 남은 시간 가감·0 판정, 1분마다 보스 피해 증가 배율, m:ss 표기</li>
 *   <li>진자 베기: 왕복 통과 위치·흔들림 각도, 통과마다 판정 구간</li>
 *   <li>톱니 폭풍: 아레나 원을 가로지르는 현(시작점·길이)</li>
 * </ul>
 * 각도는 아레나 배치 규칙({@link BossMath#ax}) 그대로 — 0° = +X(동), 90° = +Z(남), 270° = −Z(북 = 12시).
 * 시계 방향(위에서 볼 때 12 → 3 → 6 → 9시)은 각도가 커지는 쪽이다.
 */
public final class ClockLogic {

    private ClockLogic() {}

    /** 12시 방향 각도 (북쪽 = −Z). */
    public static final double TWELVE = 270.0;

    // ── 시간 봉인 ────────────────────────────────────────────────────────

    /** 봉인석 수: 기본 base, 파티 6명 이상이면 atSix (GDD: 4개, n≥6 이면 6개). */
    public static int sealCount(int partySize, int base, int atSix) {
        return Math.max(1, partySize >= 6 ? atSix : base);
    }

    /** 봉인석 각도: 12시부터 시계 방향으로 균등 (4개 = 12·3·6·9시, 6개 = 2시간 간격). */
    public static double[] sealAngles(int count) {
        int n = Math.max(1, count);
        double[] out = new double[n];
        for (int i = 0; i < n; i++) out[i] = BossMath.norm(TWELVE + 360.0 * i / n);
        return out;
    }

    /** 바늘이 한 틱에 도는 각도(도). dir = +1 시계 방향, −1 반대. periodSec ≤ 0 이면 멈춤. */
    public static double degPerTick(double periodSec, int dir) {
        if (periodSec <= 0) return 0;
        return Math.signum(dir) * 360.0 / (periodSec * 20.0);
    }

    /** 열림 창(±windowSec)을 각도로: 360 × window ÷ period. */
    public static double windowDeg(double windowSec, double periodSec) {
        if (periodSec <= 0) return 0;
        return Math.min(180, 360.0 * Math.max(0, windowSec) / periodSec);
    }

    /** 바늘이 봉인석 ± windowDeg 안에 있는가 (= 봉인석이 금색으로 열림). */
    public static boolean isOpen(double handDeg, double sealDeg, double windowDeg) {
        return BossMath.angleGap(handDeg, sealDeg) <= windowDeg + 1e-9;
    }

    /**
     * 바늘이 지금 회전 방향으로 sealDeg 에 닿기까지 남은 초 (이미 막 지났으면 거의 한 바퀴).
     * periodSec ≤ 0 이면 무한대.
     */
    public static double secondsUntil(double handDeg, double sealDeg, int dir, double periodSec) {
        if (periodSec <= 0 || dir == 0) return Double.POSITIVE_INFINITY;
        double delta = dir > 0 ? BossMath.norm(sealDeg - handDeg) : BossMath.norm(handDeg - sealDeg);
        return delta / 360.0 * periodSec;
    }

    /** 봉인 서기 진행: 열린 봉인석 위면 +1, 벗어나거나 닫히면 0 으로. @return 새 진행 틱 */
    public static int standProgress(int prev, boolean onSeal, boolean open) {
        return onSeal && open ? prev + 1 : 0;
    }

    // ── 종말 시계 ────────────────────────────────────────────────────────

    /** 시작 시간(틱) = start_seconds × 난이도 제한 시간 배율 (최소 30초). */
    public static int doomStartTicks(double startSeconds, double timerMult) {
        return (int) Math.max(600, Math.round(startSeconds * Math.max(0.1, timerMult) * 20));
    }

    /** 남은 시간 가감 (0 아래로는 0). */
    public static int adjust(int remainingTicks, double deltaSeconds) {
        return (int) Math.max(0, remainingTicks + Math.round(deltaSeconds * 20));
    }

    /** 1분마다 보스 피해 +perMinute: 1 + perMinute × ⌊경과 분⌋. */
    public static double rampMult(long elapsedTicks, double perMinute) {
        if (elapsedTicks <= 0 || perMinute <= 0) return 1.0;
        return 1.0 + perMinute * Math.floor(elapsedTicks / 1200.0);
    }

    /** 남은 틱 → "m:ss" (올림 — 0.1초 남아도 0:01). */
    public static String clock(int remainingTicks) {
        int s = (int) Math.ceil(Math.max(0, remainingTicks) / 20.0);
        return (s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
    }

    // ── 진자 베기 ────────────────────────────────────────────────────────

    /**
     * 진자 추의 차선 위 위치 (차선 중앙 기준, −half ~ +half). 한 번 통과(passTicks) 동안 끝에서 끝으로 가며
     * (끝에서 느리고 가운데서 빠름 — 코사인), 통과마다 방향이 바뀐다. t &gt; 통과 수 × passTicks 이면 마지막 끝.
     */
    public static double pendulumAlong(int t, int passTicks, int passes, double half) {
        int pt = Math.max(1, passTicks);
        int k = Math.min(Math.max(0, t) / pt, Math.max(1, passes) - 1);
        double u = Math.min(1.0, (Math.max(0, t) - k * (double) pt) / pt);
        double s = -Math.cos(Math.PI * u); // −1 → +1
        return (k % 2 == 0 ? s : -s) * half;
    }

    /** 지금 몇 번째 통과인가 (0부터). */
    public static int pendulumPass(int t, int passTicks, int passes) {
        return Math.min(Math.max(0, t) / Math.max(1, passTicks), Math.max(1, passes) - 1);
    }

    /** 흔들림 각도(도): 매단 줄 길이 arm 에서 추가 along 만큼 옆에 있을 때 (±80° 로 자름). */
    public static double pendulumAngle(double along, double arm) {
        if (arm <= 0) return 0;
        double s = Math.max(-0.985, Math.min(0.985, along / arm));
        return Math.toDegrees(Math.asin(s));
    }

    /**
     * 진자 차선 중앙의 현 위 위치: 대상이 현의 st 지점에 있을 때, 길이 2·half 차선이 현(길이 chordLen) 밖으로 나가지 않게 자른 중앙.
     * 현이 차선보다 짧으면 현 가운데.
     */
    public static double laneCenter(double st, double chordLen, double half) {
        double h = Math.min(half, chordLen / 2);
        return Math.max(h, Math.min(chordLen - h, st));
    }

    /** 이번 틱 추가 a → b 로 움직이는 동안 차선 위치 x 를 지났는가 (판정 여유 tol). */
    public static boolean swept(double a, double b, double x, double tol) {
        double lo = Math.min(a, b) - tol, hi = Math.max(a, b) + tol;
        return x >= lo && x <= hi;
    }

    /**
     * 대응 진자 차선 (GDD §8.6): 대상이 벽 wallBand 칸 안(중심에서 r − wallBand 이상)이면 차선이 벽을 따라간다 — 방향 = 접선
     * (중심 → 대상에 수직), 현 반경 r + pad. 아니면 방향 = 보스 → 대상, 현 반경 r − 1 (로테이션과 같음). 현이 없거나 4칸보다 짧으면
     * 보스 → 대상 · r − 1 로 다시, 그래도 없으면 null. 현은 대상을 지난다 (차선 가운데는 {@link #laneCenter} 로 대상 쪽에 잡힌다).
     * @return {방향 x, 방향 z, 현 시작 x, 현 시작 z, 현 길이}
     */
    public static double[] answerLane(double tx, double tz, double bx, double bz, double cx, double cz, double r, double wallBand,
                                      double pad) {
        double ox = tx - cx, oz = tz - cz;
        double d = Math.hypot(ox, oz);
        if (d > 1e-6 && d >= r - wallBand) {
            double dx = -oz / d, dz = ox / d;
            double[] ch = chord(tx, tz, dx, dz, cx, cz, r + pad);
            if (ch != null && ch[2] >= 4) return new double[] {dx, dz, ch[0], ch[1], ch[2]};
        }
        double dx = tx - bx, dz = tz - bz;
        double len = Math.hypot(dx, dz);
        if (len < 1e-6) {
            dx = 1;
            dz = 0;
        } else {
            dx /= len;
            dz /= len;
        }
        double[] ch = chord(tx, tz, dx, dz, cx, cz, r - 1);
        if (ch != null && ch[2] >= 4) return new double[] {dx, dz, ch[0], ch[1], ch[2]};
        return null;
    }

    // ── 톱니 폭풍 ────────────────────────────────────────────────────────

    /**
     * 점 (px, pz) 를 지나고 방향 (dx, dz) 인 직선이 원(중심 cx, cz, 반경 r)에 들어가는 점과 현의 길이.
     * @return {시작 x, 시작 z, 길이} — 직선이 원과 만나지 않으면 null
     */
    public static double[] chord(double px, double pz, double dx, double dz, double cx, double cz, double r) {
        double len = Math.hypot(dx, dz);
        if (len < 1e-9 || r <= 0) return null;
        double ux = dx / len, uz = dz / len;
        double fx = px - cx, fz = pz - cz;
        double b = fx * ux + fz * uz;
        double c = fx * fx + fz * fz - r * r;
        double disc = b * b - c;
        if (disc < 0) return null;
        double sq = Math.sqrt(disc);
        double t0 = -b - sq, t1 = -b + sq;
        return new double[]{px + ux * t0, pz + uz * t0, t1 - t0};
    }

    /** 굴러가는 톱니의 회전 각(라디안): 굴러간 거리 ÷ 반지름 (앞으로 구르게 음수). */
    public static double rollAngle(double distance, double radius) {
        return radius <= 0 ? 0 : -distance / radius;
    }
}
