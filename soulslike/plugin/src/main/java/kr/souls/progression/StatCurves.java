package kr.souls.progression;

import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;

/**
 * 능력치 곡선 (5.2). 표 (능력치 값 → 값) 사이는 직선으로 잇고, 표 밖은 끝값이다 (Stamina.maxFor 와 같은 셈). 기억 칸만 계단이다.
 * Bukkit 을 쓰지 않는 순수 클래스라 JUnit 이 5.2 의 표를 그대로 본다 (13.1). 값은 config.yml 의 stats.* 에서 오고
 * (Config 가 만든다), 없으면 {@link #defaults()} (설계 문서의 표) 다.
 */
public final class StatCurves {
    /** 직선 곡선. */
    public static final class Curve {
        private final TreeMap<Integer, Double> pts;

        public Curve(Map<Integer, Double> points) {
            this.pts = new TreeMap<>(points);
        }

        public static Curve of(double... kv) {
            TreeMap<Integer, Double> m = new TreeMap<>();
            for (int i = 0; i + 1 < kv.length; i += 2) m.put((int) kv[i], kv[i + 1]);
            return new Curve(m);
        }

        public double at(double x) {
            if (pts.isEmpty()) return 0;
            Map.Entry<Integer, Double> lo = pts.floorEntry((int) Math.floor(x)), hi = pts.ceilingEntry((int) Math.ceil(x));
            if (lo == null) return pts.firstEntry().getValue();
            if (hi == null) return pts.lastEntry().getValue();
            if (lo.getKey().equals(hi.getKey())) return lo.getValue();
            double t = (x - lo.getKey()) / (hi.getKey() - lo.getKey());
            return lo.getValue() + (hi.getValue() - lo.getValue()) * t;
        }

        public Map<Integer, Double> points() {
            return Collections.unmodifiableMap(pts);
        }
    }

    /** 계단: 열쇠 이상이면 그 값 (가장 큰 열쇠). 첫 열쇠 밑은 0. */
    public static final class Steps {
        private final TreeMap<Integer, Integer> pts;

        public Steps(Map<Integer, Integer> points) {
            this.pts = new TreeMap<>(points);
        }

        public int at(int x) {
            Map.Entry<Integer, Integer> e = pts.floorEntry(x);
            return e == null ? 0 : e.getValue();
        }
    }

    public final int max;
    /**
     * 근력의 공격력 몫 (stats.strength.attack): AR = 무기의 공격력 × (1 + 이 값). 모든 무기에 같다 (장비에는 보정이 없다,
     * DECISIONS 2026-10-10). 옛 판의 보정 C (0.8 × 옛 곡선) 를 그대로 옮겼다
     */
    public final Curve strAttack;
    /** 지력의 술법 세기 몫 (stats.intelligence.spell-power): 술법 세기 = 촉매의 술법 세기 × (1 + 이 값). 모든 촉매에 같다 */
    public final Curve intSpell;
    public final double defenseBase, defensePerLevel;
    public final Curve maxHealth, vigorDefense;
    public final Curve maxMana, magicDefense;
    public final Steps memorySlots;
    public final Curve maxStamina, regenScale;
    public final Curve equipLoad;
    public final Curve moveSpeed, attackSpeed;
    public final Curve statusResist;

    public StatCurves(int max, Curve strAttack, Curve intSpell, double defenseBase, double defensePerLevel, Curve maxHealth,
                      Curve vigorDefense, Curve maxMana, Curve magicDefense, Steps memorySlots, Curve maxStamina, Curve regenScale,
                      Curve equipLoad, Curve moveSpeed, Curve attackSpeed, Curve statusResist) {
        this.max = max;
        this.strAttack = strAttack;
        this.intSpell = intSpell;
        this.defenseBase = defenseBase;
        this.defensePerLevel = defensePerLevel;
        this.maxHealth = maxHealth;
        this.vigorDefense = vigorDefense;
        this.maxMana = maxMana;
        this.magicDefense = magicDefense;
        this.memorySlots = memorySlots;
        this.maxStamina = maxStamina;
        this.regenScale = regenScale;
        this.equipLoad = equipLoad;
        this.moveSpeed = moveSpeed;
        this.attackSpeed = attackSpeed;
        this.statusResist = statusResist;
    }

    /**
     * 설계 문서 5.2 의 표 (2026-10-10 판: 장비의 보정 등급을 없애고 근력·민첩·지력 곡선 하나씩. 근력·지력은 옛 보정 C 의 몫
     * (0.8 × 옛 곡선), 민첩 공격 속도는 옛 B 기준 표 그대로 (C 로 맞추면 민첩이 가장 약한 능력치가 되어서, 검토 dex-weakest-stat).
     * config.yml 이 비었을 때 쓴다.
     */
    public static StatCurves defaults() {
        Map<Integer, Integer> slots = new TreeMap<>();
        slots.put(8, 1); slots.put(13, 2); slots.put(18, 3); slots.put(24, 4); slots.put(30, 5);
        Curve bonus = Curve.of(1, 0.0, 10, 0.10, 20, 0.28, 30, 0.42, 40, 0.54, 60, 0.64, 99, 0.80);
        return new StatCurves(99, bonus, bonus,
                20, 0.4,
                Curve.of(1, 310, 10, 400, 20, 670, 30, 905, 40, 1105, 60, 1305, 99, 1500),
                Curve.of(1, 10, 10, 16, 20, 26, 30, 33, 40, 38, 60, 42, 99, 46),
                Curve.of(1, 42, 10, 60, 20, 95, 30, 125, 40, 145, 60, 170, 99, 200),
                Curve.of(1, 6, 10, 12, 20, 26, 30, 36, 40, 44, 60, 52, 99, 58),
                new Steps(slots),
                Curve.of(1, 82, 10, 100, 20, 130, 30, 150, 40, 165, 60, 180, 99, 200),
                Curve.of(1, 0.91, 10, 1.0, 20, 1.15, 30, 1.24, 40, 1.30, 60, 1.36, 99, 1.40),
                Curve.of(1, 30, 10, 40, 20, 54, 30, 66, 40, 76, 60, 88, 99, 100),
                Curve.of(10, 0.0, 20, 0.05, 30, 0.08, 40, 0.10, 60, 0.12, 99, 0.13),
                Curve.of(10, 0.0, 20, 0.10, 30, 0.17, 40, 0.22, 60, 0.26, 99, 0.30),
                Curve.of(10, 0.0, 20, 0.10, 30, 0.18, 40, 0.24, 60, 0.30, 99, 0.35));
    }
}
