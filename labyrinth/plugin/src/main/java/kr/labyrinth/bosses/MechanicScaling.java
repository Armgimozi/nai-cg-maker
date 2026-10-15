package kr.labyrinth.bosses;

import kr.labyrinth.content.Params;

/**
 * 기믹 배율 (HP·피해 말고 "패턴 자체"를 키우는 규칙). Bukkit 무관 — 단위 테스트 대상.
 * <ul>
 *   <li>파티 인원: GDD §8.4 의 {@code *_base/_per_member/_per_members/solo_*} 를 {@link Params#scaled} 로 (패턴마다 YAML).</li>
 *   <li>난이도: 경고 시간은 {@code Difficulty.windup}(telegraph 배율, 최소 0.5초). 여기서는 그 밖의 것 —
 *       패턴 쿨다운 배율, 다중 대상 패턴의 추가 개수, 투사체·돌진 속도, 오브젝트 HP 배율.</li>
 *   <li>난이도마다 값 한 벌 — 1층부터 같은 쿨다운·추가 개수·속도·오브젝트 HP·제한 시간 (0.3.3, 층 램프 기본값 없음 → ramp 1).</li>
 *   <li>층 램프(관리자가 config 에 직접 적었을 때만): ramp = 난이도 층 램프 진행도(0~1, {@code InstanceContext.rampProgress}).
 *       난이도 배율 v 는 1 + (v − 1) × ramp 로 보간하고, 추가 개수는 ramp 0.5 이상부터 붙는다.</li>
 *   <li>페이즈: 3페이즈부터 쿨다운 −10%, 광폭화(엔레이지) 후 쿨다운 × {@link #ENRAGE_COOLDOWN}.</li>
 * </ul>
 * 난이도 id 는 config 프리셋 키(easy/normal/hard/nightmare). 모르는 id 는 보통.
 */
public record MechanicScaling(int partySize, String difficulty, int phase, boolean enraged, double ramp) {

    public static final double ENRAGE_COOLDOWN = 0.6;
    public static final double MIN_COOLDOWN_MULT = 0.45;
    /** (직접 적은 층 램프) 이 진행도부터 다중 대상 패턴의 난이도 추가 개수가 붙는다. */
    public static final double EXTRA_COUNT_RAMP = 0.5;

    public MechanicScaling {
        partySize = Math.max(1, partySize);
        difficulty = difficulty == null ? "normal" : difficulty;
        phase = Math.max(1, phase);
        ramp = Double.isNaN(ramp) ? 1.0 : Math.max(0.0, Math.min(1.0, ramp));
    }

    /** 램프 없음 = 난이도 값 그대로 (기본). */
    public MechanicScaling(int partySize, String difficulty, int phase, boolean enraged) {
        this(partySize, difficulty, phase, enraged, 1.0);
    }

    /** 난이도 배율 v 를 램프 진행도로 보간: 1 + (v − 1) × ramp. */
    private double ramped(double v) { return 1.0 + (v - 1.0) * ramp; }

    public boolean solo() { return partySize == 1; }

    /** 패턴 쿨다운 배율 (작을수록 자주). */
    public double cooldownMult() {
        double d = ramped(switch (difficulty) {
            case "easy" -> 1.15;
            case "hard" -> 0.9;
            case "nightmare" -> 0.8;
            default -> 1.0;
        });
        if (phase >= 3) d *= 0.9;
        if (enraged) d *= ENRAGE_COOLDOWN;
        return Math.max(MIN_COOLDOWN_MULT, d);
    }

    /**
     * 다중 대상 패턴(표식·장판·쫄 수)의 추가 개수: 어려움 = 인원 6명 이상일 때 +1, 악몽 = +1 (6명 이상이면 +2).
     * 직접 적은 층 램프의 진행도가 {@link #EXTRA_COUNT_RAMP} 미만이면 0 (기본은 램프가 없어 1층부터 붙는다).
     */
    public int extraCount() {
        if (ramp < EXTRA_COUNT_RAMP) return 0;
        return switch (difficulty) {
            case "hard" -> partySize >= 6 ? 1 : 0;
            case "nightmare" -> partySize >= 6 ? 2 : 1;
            default -> 0;
        };
    }

    /** 투사체·돌진·밀어내기 속도 배율. */
    public double speedMult() {
        return ramped(switch (difficulty) {
            case "easy" -> 0.9;
            case "hard" -> 1.1;
            case "nightmare" -> 1.2;
            default -> 1.0;
        });
    }

    /** 부술 수 있는 오브젝트(알·고치·인장) HP 배율 — 난이도 HP 와 같은 방향이지만 완만하게. */
    public double objectHpMult() {
        return ramped(switch (difficulty) {
            case "easy" -> 0.8;
            case "hard" -> 1.25;
            case "nightmare" -> 1.6;
            default -> 1.0;
        });
    }

    /** 기믹 제한 시간(밸브 창·고치 시간 등) 배율 — 쉬움은 여유, 악몽은 빡빡하게. */
    public double timerMult() {
        return ramped(switch (difficulty) {
            case "easy" -> 1.25;
            case "hard" -> 0.9;
            case "nightmare" -> 0.8;
            default -> 1.0;
        });
    }

    /**
     * 패턴의 개수 키(GDD §8.4) + 난이도 추가 개수, [1, cap] 으로 자름. cap ≤ 0 이면 상한 없음.
     * 예: {@code count(p, "count", 1, 5)} → count_base + floor((n−1)×count_per_member) + extra.
     */
    public int count(Params p, String key, int def, int cap) {
        int c = p.scaledInt(key, partySize, def) + extraCount();
        int max = cap > 0 ? cap : p.integer("max", Integer.MAX_VALUE);
        return Math.max(1, Math.min(max, c));
    }

    /** 쿨다운(초) → 틱 (배율 적용, 최소 1초). */
    public int cooldownTicks(double seconds) {
        return (int) Math.max(20, Math.round(seconds * 20 * cooldownMult()));
    }

    /** 오브젝트 HP: hp × (1 + hp_per_member × (n−1)) × 난이도 배율. */
    public double objectHp(Params p, double defHp) {
        return BossMath.objectHp(p.dbl("hp", defHp), p.dbl("hp_per_member", 0), partySize) * objectHpMult();
    }

    public MechanicScaling withPhase(int newPhase) { return new MechanicScaling(partySize, difficulty, newPhase, enraged, ramp); }

    public MechanicScaling withEnraged(boolean e) { return new MechanicScaling(partySize, difficulty, phase, e, ramp); }
}
