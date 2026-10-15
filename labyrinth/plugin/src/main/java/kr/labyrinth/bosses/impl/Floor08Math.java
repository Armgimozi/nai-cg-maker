package kr.labyrinth.bosses.impl;

import java.util.Random;
import kr.labyrinth.bosses.BossMath;

/**
 * 8층 잉크 사서 오르벨의 순수 계산 (Bukkit 무관 — 단위 테스트 대상): 깃펜 부채 각도, 룬 책장 배치·방향,
 * 먹물 분신 자리 섞기, 분신 소멸 판정, 룬마다 다른 음 높이. 각도는 아레나 배치 규칙(수학 각도: 0 = +X, 90 = +Z 남쪽).
 */
public final class Floor08Math {

    private Floor08Math() {}

    /** 북쪽 입구(270°)·남쪽 계단(90°) 사이로 책장을 놓을 때 비켜 둘 각도. */
    public static final double SHELF_MARGIN_DEG = 15;

    /**
     * 부채꼴 투사체의 방향 오프셋(도). count 개를 spread 각도 안에 균등 배치, 가운데가 0.
     * 예: 5갈래 40° → −20, −10, 0, 10, 20.
     */
    public static double[] fanOffsets(int count, double spreadDeg) {
        int n = Math.max(1, count);
        double[] out = new double[n];
        if (n == 1) return out;
        double step = spreadDeg / (n - 1);
        for (int i = 0; i < n; i++) out[i] = -spreadDeg / 2 + step * i;
        return out;
    }

    /** 오프셋(도)만큼 돌린 수평 방향 (x, z). */
    public static double[] rotate(double dx, double dz, double offsetDeg) {
        double a = Math.toRadians(offsetDeg);
        double c = Math.cos(a), s = Math.sin(a);
        return new double[]{dx * c - dz * s, dx * s + dz * c};
    }

    /** 룬 책장 각도 — 입구·계단 방향을 비켜 고르게. */
    public static double[] shelfAngles(int count) {
        return BossMath.ringAngles(Math.max(1, count), 90, SHELF_MARGIN_DEG);
    }

    /**
     * 책장이 중심을 바라보는 축 정렬 방향 (블록이 깔끔하게 놓이도록 4방위로 반올림).
     * @return {dx, dz} — 중심 쪽 단위 방향 (−1/0/1)
     */
    public static int[] inwardCardinal(double angleDeg) {
        double ix = -BossMath.ax(angleDeg), iz = -BossMath.az(angleDeg);
        if (Math.abs(ix) >= Math.abs(iz)) return new int[]{(int) Math.signum(ix), 0};
        return new int[]{0, (int) Math.signum(iz)};
    }

    /** 먹물 분신 자리 (진짜 1 + 분신 doubles): start 부터 균등 간격 각도(도). */
    public static double[] splitAngles(int doubles, double startDeg) {
        int n = Math.max(1, doubles + 1);
        double[] out = new double[n];
        for (int i = 0; i < n; i++) out[i] = BossMath.norm(startDeg + 360.0 * i / n);
        return out;
    }

    /** 진짜가 설 자리 번호 (0 ~ slots−1, 균등 무작위). */
    public static int realSlot(int slots, Random rng) {
        return rng.nextInt(Math.max(1, slots));
    }

    /** 분신 소멸: 갈라진 뒤 진짜가 받은 피해 ≥ 최대 HP × ratio. */
    public static boolean dispelled(double damageSinceSplit, double maxHp, double ratio) {
        return damageSinceSplit >= Math.max(1e-6, maxHp * ratio);
    }

    /** 룬 번호(0~7)마다 다른 음 — 5음 음계(도·레·미·솔·라)로 올라가 소리로도 순서를 외울 수 있게. */
    public static float runePitch(int rune) {
        int[] semis = {0, 2, 4, 7, 9, 12, 14, 16};
        int s = semis[Math.floorMod(rune, semis.length)];
        return (float) (0.6 * Math.pow(2, s / 12.0));
    }

    /** 먹물 방울 개수: 플레이어마다 1 + 난이도 추가, [1, cap]. */
    public static int inkDrops(int players, int extra, int cap) {
        int n = Math.max(1, players) + Math.max(0, extra);
        return cap > 0 ? Math.min(cap, n) : n;
    }

    /** 진행 표시 (글 대신 점): done 개는 on 색 ◆, 나머지는 off 색 ◇. 예: {@code pips(2, 4, "<gold>", "<dark_gray>")}. */
    public static String pips(int done, int total, String on, String off) {
        int t = Math.max(0, total), d = Math.max(0, Math.min(t, done));
        StringBuilder b = new StringBuilder();
        if (d > 0) b.append(on).append("◆".repeat(d));
        if (t - d > 0) b.append(off).append("◇".repeat(t - d));
        return b.toString();
    }
}
