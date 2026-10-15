package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.bosses.BossMath;

/**
 * 지하 7층 다이아드의 극성 규칙 (GDD §7.7) 중 순수 계산 — Bukkit 무관, 단위 테스트 대상.
 * 극성 배정·피해 배율·반사·파동·분광 광선 흡수 순서·기둥 배치·솔로 대체 규칙.
 */
public final class Floor07Logic {

    private Floor07Logic() {}

    /** 빛 / 어둠 극성. */
    public enum Polarity {
        LIGHT, DARK;

        public Polarity opposite() { return this == LIGHT ? DARK : LIGHT; }

        /** 한국어 이름 (빛 / 어둠). */
        public String label() { return this == LIGHT ? "빛" : "어둠"; }

        /** 기호 (☀ / ☾). */
        public String icon() { return this == LIGHT ? "☀" : "☾"; }

        /** MiniMessage 색 태그 이름 (#ffd27a 금빛 / #b47cff 보라). */
        public String hex() { return this == LIGHT ? "#ffd27a" : "#b47cff"; }

        /** "<#ffd27a>☀ 빛</#ffd27a>" 꼴. */
        public String tag() { return "<" + hex() + ">" + icon() + " " + label() + "</" + hex() + ">"; }

        /** 굵은 색 문구: "☀ 빛" + suffix (예: "의 파동!"). */
        public String phrase(String suffix) {
            return "<b><" + hex() + ">" + icon() + " " + label() + suffix + "</" + hex() + "></b>";
        }

        /** YAML 값 "light"/"빛" = 빛, 그 밖 = 어둠. */
        public static Polarity byName(String s) {
            if (s == null) return DARK;
            String t = s.trim().toLowerCase(java.util.Locale.ROOT);
            return t.equals("light") || t.equals("빛") ? LIGHT : DARK;
        }
    }

    /** 시작 배정 (mode alternate): 0번 = 빛, 1번 = 어둠 … 번갈아. 솔로는 빛. */
    public static List<Polarity> assignAlternate(int count) {
        List<Polarity> out = new ArrayList<>();
        for (int i = 0; i < Math.max(0, count); i++) out.add(i % 2 == 0 ? Polarity.LIGHT : Polarity.DARK);
        return out;
    }

    /** 나중에 들어온 사람: 적은 쪽 (같으면 빛). */
    public static Polarity forLateJoiner(int light, int dark) {
        return dark < light ? Polarity.DARK : Polarity.LIGHT;
    }

    /**
     * 플레이어가 보스에게 주는 피해 배율: 보스 얼굴과 반대면 1 + oppositeBonus(+25%), 같으면 1 − samePenalty(−50%).
     * 극성이 없으면(null) 1.
     */
    public static double damageMult(Polarity attacker, Polarity face, double oppositeBonus, double samePenalty) {
        if (attacker == null || face == null) return 1.0;
        return attacker == face ? Math.max(0, 1 - samePenalty) : 1 + oppositeBonus;
    }

    /**
     * 굴절 반사 피해: 굴절 중이고 공격자 극성 = 보스 얼굴이면 damage × ratio (cap > 0 이면 cap 이하), 아니면 0.
     * damage = 극성 배율을 곱하기 전 최종 피해 ("피해의 50%가 반사").
     */
    public static double reflected(Polarity attacker, Polarity face, boolean refracting, double damage, double ratio, double cap) {
        if (!refracting || attacker == null || attacker != face || damage <= 0 || ratio <= 0) return 0;
        double r = damage * ratio;
        return cap > 0 ? Math.min(cap, r) : r;
    }

    /** 극성 파동 배율: 같은 극성 = 0(무피해), 다른 극성(또는 극성 없음) = mult. */
    public static double waveMult(Polarity player, Polarity wave, double mult) {
        return player != null && player == wave ? 0 : mult;
    }

    /** 3페이즈 2연속 파동 색 순서: [첫 색, 반대 색], 아니면 [첫 색]. */
    public static List<Polarity> waveSequence(Polarity first, boolean doubleWave) {
        return doubleWave ? List.of(first, first.opposite()) : List.of(first);
    }

    /**
     * 분광 광선 흡수 (GDD §7.7 split_beam): 보스에서 멀어지는 순(along 오름차순)으로 선 위의 플레이어를 본다.
     * 광선과 같은 극성인 첫 사람이 soak 배율로 흡수하고 광선이 멈춘다(뒤 사람 무사). 그 앞의 다른 극성은 full 배율.
     * 아무도 흡수하지 않으면 선 위의 모두가 full (대상 포함).
     * @param along 각자 보스로부터의 선 방향 거리 (정렬 안 돼도 됨)
     * @param pols  각자 극성 (null = 극성 없음 = 흡수 못 함)
     * @return 각자 받는 배율 (입력 순서 그대로)
     */
    public static double[] resolveBeam(double[] along, Polarity[] pols, Polarity beam, double soak, double full) {
        int n = along.length;
        double[] out = new double[n];
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        java.util.Arrays.sort(order, (a, b) -> Double.compare(along[a], along[b]));
        for (Integer i : order) {
            if (pols[i] != null && pols[i] == beam) {
                out[i] = soak;
                break;
            }
            out[i] = full;
        }
        return out;
    }

    /** 흡수한 사람이 있는가 (resolveBeam 결과에서 soak 칸). */
    public static int absorberIndex(double[] along, Polarity[] pols, Polarity beam) {
        int best = -1;
        for (int i = 0; i < along.length; i++) {
            if (pols[i] == null || pols[i] != beam) continue;
            if (best < 0 || along[i] < along[best]) best = i;
        }
        return best;
    }

    /**
     * 솔로 분광 광선 색: 기둥을 쓸 수 있으면 반대 색(기둥으로 바꿔 0.6배를 받게), 재사용 대기 중이면 지금 색(그대로 흡수).
     */
    public static Polarity soloBeamColor(Polarity player, boolean canSwapInTime) {
        Polarity p = player == null ? Polarity.LIGHT : player;
        return canSwapInTime ? p.opposite() : p;
    }

    /** 기둥 하나의 자리 (수학 각도, 0 = 동쪽 +X, 90 = 남쪽 +Z) 와 색. */
    public record PylonSpot(double angle, Polarity polarity) {}

    /**
     * 기둥 배치: 아레나 양쪽(동·서)에 빛·어둠 기둥 한 쌍씩, 쌍 안 간격 spread 도 (GDD §7.7 "반경 12 링의 양쪽").
     * 쌍마다 북쪽(입구 270° 에 가까운 쪽)이 빛. 3쌍 이상이면 동쪽·서쪽 호(남쪽 계단 90°·북쪽 입구 270° 에서 30° + 반 간격 비킴)에
     * 번갈아 나눠 고르게 놓는다. 최대 4쌍.
     * @param total 기둥 총 수 (홀수면 올림해 쌍으로)
     */
    public static List<PylonSpot> pylonLayout(int total, double spreadDeg) {
        int pairs = Math.max(1, Math.min(4, (Math.max(2, total) + 1) / 2));
        double half = Math.max(4, Math.min(40, spreadDeg)) / 2;
        List<Double> centers = new ArrayList<>();
        if (pairs == 1) {
            centers.add(0.0);
        } else {
            double arc = Math.max(0, 180 - 2 * (30 + half));
            int east = (pairs + 1) / 2, west = pairs / 2;
            for (int j = 0; j < east; j++) centers.add((j - (east - 1) / 2.0) * arc / east);
            for (int j = 0; j < west; j++) centers.add(180 + (j - (west - 1) / 2.0) * arc / west);
        }
        List<PylonSpot> out = new ArrayList<>();
        for (double c : centers) {
            double a1 = BossMath.norm(c - half), a2 = BossMath.norm(c + half);
            boolean firstNorth = BossMath.angleGap(a1, 270) <= BossMath.angleGap(a2, 270);
            out.add(new PylonSpot(firstNorth ? a1 : a2, Polarity.LIGHT));
            out.add(new PylonSpot(firstNorth ? a2 : a1, Polarity.DARK));
        }
        return out;
    }

    /** 기둥 재사용 남은 틱 (0 = 지금 가능). */
    public static long swapRemaining(long now, long readyAt) { return Math.max(0, readyAt - now); }

    /** 얼굴 전환 간격(초): 3페이즈부터 p3 값. */
    public static double faceInterval(int phase, double interval, double p3Interval) {
        return phase >= 3 && p3Interval > 0 ? p3Interval : interval;
    }
}
