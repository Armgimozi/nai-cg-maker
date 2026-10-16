package kr.labyrinth.pvp;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.bukkit.configuration.ConfigurationSection;

/**
 * config.yml {@code pvp:} 블록 (GDD §18, pvp_spec §12). 규칙 판정은 {@link PvpRules}, 숫자 계산은 {@link PvpMath}·{@link PvpCc}.
 * <p>
 * 0.3.5: 한 방 상한 없음(1.0), 피해 = 원피해 × 기준 배율 m(L) × 직업 보정 × 스킬 pvp_mult × (1 − 강인함) × HP ÷ (HP + 완충),
 * 방어 대신 강인함, 치명 추가 피해 × 0.6, PvP 전투 중 회복·보호막 감소, 플레이어가 건 상태이상은 짧게 + 줄어듦 + 면역.
 *
 * @param enabled          플레이어끼리 싸울 수 있는가 (false = 같은 파티가 아니어도 서로 피해 없음)
 * @param damageMultiplier 기본 대비 배율 (1.0 = 명세의 균형). 0.3.4 의 0.7(안 고친 값)은 1.0, 고친 값은 ÷ 0.7 로 옮겨 읽는다
 * @param levelCurve       기준 배율 m(L) = base × min(1, (ref ÷ L)^exponent), L = 두 사람 중 높은 레벨
 * @param bufferHp         PvP 완충 체력 B(L) — 모두에게 같은 양
 * @param defenseWeight    피해 공식의 방어를 PvP 에서 얼마나 셀지 (0 = 방어 대신 강인함)
 * @param resilience       강인함 R = cap × S ÷ (S + perLevel × L), S = VIT + 방어
 * @param critDamageScale  치명 '추가' 피해 배율 (0.6 → 치명 피해 2.5 가 1.9)
 * @param maxHitRatio      한 번의 피해 상한 = 맞는 사람 최대 HP × 이 값 (1 = 상한 없음, 관리자용)
 * @param classDamage      직업 보정 (플레이어에게 주는 피해, 레벨대별 값도 됨)
 * @param combatSeconds    'PvP 전투 중' = 다른 파티 플레이어와 피해를 주고받은 지 이 시간 안
 * @param healing          PvP 전투 중 받는 모든 회복 배율
 * @param potion           물약은 한 번 더 (healing × potion)
 * @param lifesteal        플레이어를 때려 얻는 흡혈 배율 (healing 대신)
 * @param shield           PvP 전투 중 새로 얻는 보호막 배율
 * @param flatHealByPool   고정량 회복(치유력·흡혈·재생)은 × HP ÷ (HP + B)
 * @param longFight        긴 싸움: start 초 뒤부터 회복·보호막이 초마다 perSecond 씩 줄어 floor 까지
 * @param cc               상태이상 규칙 (플레이어가 다른 파티 플레이어에게 건 것만)
 * @param safeZoneVillage  마을(labyrinth-village.yml) 안은 PvP 금지
 * @param safeZoneMargin   마을 반경에 더하는 여유 칸
 * @param partyNameColor   파티원 이름표를 초록색으로 (보는 사람 기준)
 */
public record PvpConfig(boolean enabled, double damageMultiplier, LevelCurve levelCurve, BufferHp bufferHp,
                        double defenseWeight, Resilience resilience, double critDamageScale, double maxHitRatio,
                        ClassDamage classDamage, double combatSeconds, double healing, double potion, double lifesteal,
                        double shield, boolean flatHealByPool, LongFight longFight, CcConfig cc,
                        boolean safeZoneVillage, int safeZoneMargin, boolean partyNameColor) {

    /** 0.3.4 기본값 (안 고친 값이면 새 기본값으로 옮긴다). */
    public static final double LEGACY_DAMAGE_MULTIPLIER = 0.7;
    public static final double LEGACY_MAX_HIT_RATIO = 0.35;

    /** 0.3.5 에 새로 생긴 키 — 하나라도 있으면 이미 새 판 설정(옮기지 않음). */
    static final Set<String> NEW_KEYS = Set.of("level_curve", "buffer_hp", "defense_weight", "resilience", "crit_damage_scale",
            "class_damage", "class_damage_levels", "combat_seconds", "healing", "potion", "lifesteal", "shield",
            "flat_heal_by_pool", "long_fight", "cc");

    /** m(L) = base × min(1, (refLevel ÷ L)^exponent). */
    public record LevelCurve(double base, int refLevel, double exponent) {}

    /** B(L) = perLevelLow × min(L, knee) + perLevelHigh × max(0, L − knee). */
    public record BufferHp(double perLevelLow, int kneeLevel, double perLevelHigh) {}

    /** R = cap × S ÷ (S + perLevel × L). */
    public record Resilience(double cap, double perLevel) {}

    /** max(floor, 1 − perSecond × max(0, t − start)). */
    public record LongFight(double start, double perSecond, double floor) {}

    /** 레벨대 하나의 직업 보정 (low: L &lt; midFrom · mid: midFrom ≤ L &lt; highFrom · high: L ≥ highFrom). */
    public record Band(double low, double mid, double high) {
        public static Band of(double v) { return new Band(v, v, v); }
    }

    /**
     * 직업 보정. config {@code class_damage: {hunter: 0.9, arcanist: {low: 1.2, mid: 1.1, high: 1.2}}} — 숫자 하나 또는 레벨대 셋.
     * 레벨대 경계는 {@code class_damage_levels: {mid: 28, high: 43}} (Lv20·35·50 의 가운데). 적지 않은 직업 = 1.0.
     */
    public record ClassDamage(Map<String, Band> byClass, int midFrom, int highFrom) {
        public ClassDamage {
            byClass = Map.copyOf(byClass);
        }

        /** level = 두 사람 중 높은 레벨. */
        public double of(String classId, int level) {
            Band b = classId == null ? null : byClass.get(classId);
            if (b == null) return 1.0;
            return level >= highFrom ? b.high() : level >= midFrom ? b.mid() : b.low();
        }
    }

    /**
     * 상태이상 규칙.
     * @param duration        종류별 PvP 시간 배율 (없는 종류 = 1)
     * @param maxSeconds      종류별 한 번 최대 시간 (없는 종류 = 상한 없음)
     * @param slowMaxPotency  플레이어에게 거는 둔화 세기 상한
     * @param window          같은 분류를 이 시간(초) 안에 다시 맞으면 줄어듦 단계가 오른다
     * @param steps           줄어듦 단계 (첫 번째 1.0 → … → 0 = 면역). 마지막 값이 계속 쓰인다
     * @param groups          효과 id → 분류 (control·root·silence·blind). 없는 효과는 줄어듦 없음
     * @param controlImmunity 행동 불가(control 분류)가 끝난 뒤 이 시간 동안 control 면역
     * @param minSeconds      줄여서 이보다 짧으면 걸지 않는다 (횟수는 센다)
     */
    public record CcConfig(Map<String, Double> duration, Map<String, Double> maxSeconds, double slowMaxPotency,
                           double window, List<Double> steps, Map<String, String> groups, double controlImmunity,
                           double minSeconds) {
        public static final String CONTROL = "control";

        public CcConfig {
            duration = Map.copyOf(duration);
            maxSeconds = Map.copyOf(maxSeconds);
            steps = List.copyOf(steps.isEmpty() ? List.of(1.0) : steps);
            groups = Map.copyOf(groups);
        }

        public String groupOf(String effectId) { return effectId == null ? null : groups.get(effectId); }

        public boolean isControl(String effectId) { return CONTROL.equals(groupOf(effectId)); }

        static CcConfig defaults() {
            Map<String, String> g = new LinkedHashMap<>();
            g.put("stun", CONTROL);
            g.put("frozen", CONTROL);
            g.put("root", "root");
            g.put("silence", "silence");
            g.put("blind", "blind");
            return new CcConfig(
                    Map.of("stun", 0.8, "frozen", 1.0, "root", 0.8, "silence", 0.8, "blind", 0.7, "slow", 1.0, "cooldown_slow", 0.5),
                    Map.of("stun", 1.0, "frozen", 1.5, "root", 1.5, "silence", 1.5, "blind", 1.5, "slow", 3.0, "cooldown_slow", 2.0),
                    0.5, 8, List.of(1.0, 0.5, 0.25, 0.0), g, 2.0, 0.2);
        }
    }

    /** 기본값 (config.yml 에 키가 없을 때 = jar 의 config.yml). 근거는 pvp_spec §1~§9. */
    public static final PvpConfig DEFAULT;

    /** pvp 모듈이 켜지기 전 / 설정이 없을 때: 플레이어끼리 싸우지 않는다 (나머지 값은 기본값). */
    public static final PvpConfig OFF;

    static {
        Map<String, Band> cd = new LinkedHashMap<>();
        cd.put("hunter", Band.of(0.9));
        cd.put("arcanist", Band.of(1.2));
        cd.put("shadow", Band.of(1.2));
        DEFAULT = new PvpConfig(true, 1.0, new LevelCurve(2.0, 20, 2.35), new BufferHp(42, 20, 12), 0.0,
                new Resilience(0.40, 8), 0.6, 1.0, new ClassDamage(cd, 28, 43), 8, 0.6, 0.6, 0.5, 0.8, true,
                new LongFight(20, 0.025, 0.10), CcConfig.defaults(), true, 8, true);
        OFF = DEFAULT.withEnabled(false).withSafeZone(false, 0, false);
    }

    public PvpConfig withEnabled(boolean on) {
        return new PvpConfig(on, damageMultiplier, levelCurve, bufferHp, defenseWeight, resilience, critDamageScale, maxHitRatio,
                classDamage, combatSeconds, healing, potion, lifesteal, shield, flatHealByPool, longFight, cc, safeZoneVillage,
                safeZoneMargin, partyNameColor);
    }

    public PvpConfig withSafeZone(boolean village, int margin, boolean nameColor) {
        return new PvpConfig(enabled, damageMultiplier, levelCurve, bufferHp, defenseWeight, resilience, critDamageScale, maxHitRatio,
                classDamage, combatSeconds, healing, potion, lifesteal, shield, flatHealByPool, longFight, cc, village, margin,
                nameColor);
    }

    /** 배율·한 방 상한만 바꾼 사본 (시험용). */
    public PvpConfig withDamage(double multiplier, double maxHit) {
        return new PvpConfig(enabled, multiplier, levelCurve, bufferHp, defenseWeight, resilience, critDamageScale, maxHit,
                classDamage, combatSeconds, healing, potion, lifesteal, shield, flatHealByPool, longFight, cc, safeZoneVillage,
                safeZoneMargin, partyNameColor);
    }

    public static PvpConfig from(ConfigurationSection s) { return from(s, null); }

    /**
     * config 읽기 + 0.3.4 값 옮기기 (pvp_spec §13). 새 판 키가 하나도 없는 블록(= 0.3.4 config.yml 그대로)만 옮긴다:
     * damage_multiplier 0.7 → 1.0 · 고친 값 v → v ÷ 0.7, max_hit_ratio 0.35 → 1.0 (고친 값은 그대로 — 일부러 상한을 원하는 서버).
     * 파일은 고쳐 쓰지 않으므로 다시 읽어도 결과가 같다.
     * @param notes 옮긴 내용 한 줄씩 (켤 때 로그, null 가능)
     */
    public static PvpConfig from(ConfigurationSection s, List<String> notes) {
        if (s == null) return DEFAULT;
        PvpConfig d = DEFAULT;
        boolean legacy = isLegacy(s);

        double mult = d.damageMultiplier;
        if (s.contains("damage_multiplier", true)) {
            double v = s.getDouble("damage_multiplier", d.damageMultiplier);
            if (legacy) {
                double moved = Math.abs(v - LEGACY_DAMAGE_MULTIPLIER) < 1e-9 ? d.damageMultiplier : v / LEGACY_DAMAGE_MULTIPLIER;
                note(notes, "PvP 피해 배율을 새 기준으로 옮겼습니다 (" + fmt(v) + " → " + fmt(moved) + ")");
                v = moved;
            }
            mult = v;
        }
        double maxHit = d.maxHitRatio;
        if (s.contains("max_hit_ratio", true)) {
            double v = s.getDouble("max_hit_ratio", d.maxHitRatio);
            if (legacy && Math.abs(v - LEGACY_MAX_HIT_RATIO) < 1e-9) {
                note(notes, "PvP 한 방 상한을 없앴습니다 (max_hit_ratio " + fmt(v) + " → 1)");
                v = 1.0;
            }
            maxHit = v;
        }

        LevelCurve lc = new LevelCurve(
                clamp(s.getDouble("level_curve.base", d.levelCurve.base()), 0.05, 10),
                (int) clamp(s.getInt("level_curve.ref_level", d.levelCurve.refLevel()), 1, 100),
                clamp(s.getDouble("level_curve.exponent", d.levelCurve.exponent()), 0, 6));
        BufferHp bh = new BufferHp(
                clamp(s.getDouble("buffer_hp.per_level_low", d.bufferHp.perLevelLow()), 0, 1000),
                (int) clamp(s.getInt("buffer_hp.knee_level", d.bufferHp.kneeLevel()), 1, 100),
                clamp(s.getDouble("buffer_hp.per_level_high", d.bufferHp.perLevelHigh()), 0, 1000));
        Resilience rs = new Resilience(
                clamp(s.getDouble("resilience.cap", d.resilience.cap()), 0, 0.9),
                clamp(s.getDouble("resilience.per_level", d.resilience.perLevel()), 0.1, 1000));
        LongFight lf = new LongFight(
                clamp(s.getDouble("long_fight.start", d.longFight.start()), 0, 3600),
                clamp(s.getDouble("long_fight.per_second", d.longFight.perSecond()), 0, 1),
                clamp(s.getDouble("long_fight.floor", d.longFight.floor()), 0, 1));

        return new PvpConfig(
                s.getBoolean("enabled", d.enabled),
                clamp(mult, 0.0, 5.0), lc, bh,
                clamp(s.getDouble("defense_weight", d.defenseWeight), 0, 1), rs,
                clamp(s.getDouble("crit_damage_scale", d.critDamageScale), 0, 1),
                clamp(maxHit, 0.05, 1.0),
                classDamage(s, d.classDamage),
                clamp(s.getDouble("combat_seconds", d.combatSeconds), 1, 120),
                clamp(s.getDouble("healing", d.healing), 0, 2),
                clamp(s.getDouble("potion", d.potion), 0, 2),
                clamp(s.getDouble("lifesteal", d.lifesteal), 0, 2),
                clamp(s.getDouble("shield", d.shield), 0, 2),
                s.getBoolean("flat_heal_by_pool", d.flatHealByPool), lf,
                cc(sub(s, "cc"), d.cc),
                s.getBoolean("safe_zone_village", d.safeZoneVillage),
                (int) clamp(s.getInt("safe_zone_margin", d.safeZoneMargin), 0, 256),
                s.getBoolean("party_name_color", d.partyNameColor));
    }

    /** 0.3.5 키가 하나도 없는 블록 = 0.3.4 config.yml (jar 기본값은 보지 않음). */
    static boolean isLegacy(ConfigurationSection s) {
        for (String k : NEW_KEYS) if (s.contains(k, true)) return false;
        return true;
    }

    private static ClassDamage classDamage(ConfigurationSection s, ClassDamage def) {
        int mid = (int) clamp(s.getInt("class_damage_levels.mid", def.midFrom()), 1, 200);
        int high = (int) clamp(s.getInt("class_damage_levels.high", def.highFrom()), mid, 200);
        ConfigurationSection c = sub(s, "class_damage");
        if (c == null) return new ClassDamage(def.byClass(), mid, high);
        Map<String, Band> out = new LinkedHashMap<>();
        for (String k : c.getKeys(false)) {
            String id = k.toLowerCase(Locale.ROOT);
            ConfigurationSection b = sub(c, k);
            if (b != null) {
                double all = clamp(b.getDouble("all", 1.0), 0.1, 3);
                out.put(id, new Band(clamp(b.getDouble("low", all), 0.1, 3), clamp(b.getDouble("mid", all), 0.1, 3),
                        clamp(b.getDouble("high", all), 0.1, 3)));
            } else {
                out.put(id, Band.of(clamp(c.getDouble(k, 1.0), 0.1, 3)));
            }
        }
        return new ClassDamage(out, mid, high);
    }

    private static CcConfig cc(ConfigurationSection s, CcConfig def) {
        if (s == null) return def;
        Map<String, Double> dur = new LinkedHashMap<>(def.duration());
        ConfigurationSection ds = sub(s, "duration");
        if (ds != null) for (String k : ds.getKeys(false)) dur.put(k.toLowerCase(Locale.ROOT), clamp(ds.getDouble(k, 1.0), 0, 2));
        Map<String, Double> max = new LinkedHashMap<>(def.maxSeconds());
        ConfigurationSection ms = sub(s, "max_seconds");
        if (ms != null) for (String k : ms.getKeys(false)) max.put(k.toLowerCase(Locale.ROOT), clamp(ms.getDouble(k, 1.0), 0.05, 60));
        double window = def.window();
        List<Double> steps = def.steps();
        Map<String, String> groups = def.groups();
        ConfigurationSection dim = sub(s, "diminishing");
        if (dim != null) {
            window = clamp(dim.getDouble("window", def.window()), 0, 120);
            if (dim.contains("steps", true)) {
                List<Double> st = new ArrayList<>();
                List<?> raw = dim.getList("steps");
                if (raw != null) for (Object o : raw) if (o instanceof Number n) st.add(clamp(n.doubleValue(), 0, 1));
                if (!st.isEmpty()) steps = st;
            }
            ConfigurationSection gs = sub(dim, "groups");
            if (gs != null) {
                Map<String, String> g = new LinkedHashMap<>();
                for (String group : gs.getKeys(false)) {
                    for (String id : gs.getStringList(group)) g.put(id.toLowerCase(Locale.ROOT), group.toLowerCase(Locale.ROOT));
                }
                groups = g;
            }
        }
        return new CcConfig(dur, max, clamp(s.getDouble("slow_max_potency", def.slowMaxPotency()), 0, 0.95), window, steps,
                groups, clamp(s.getDouble("control_immunity", def.controlImmunity()), 0, 60),
                clamp(s.getDouble("min_seconds", def.minSeconds()), 0, 5));
    }

    /** 이 config 에 실제로 적힌 하위 블록만 (jar 기본값의 빈 블록을 만들지 않게). */
    private static ConfigurationSection sub(ConfigurationSection s, String key) {
        return s.contains(key, true) && s.isConfigurationSection(key) ? s.getConfigurationSection(key) : null;
    }

    private static void note(List<String> notes, String line) {
        if (notes != null) notes.add(line);
    }

    /** 0.70 → "0.7", 1.0 → "1". */
    static String fmt(double v) {
        return java.math.BigDecimal.valueOf(Math.round(v * 100) / 100.0).stripTrailingZeros().toPlainString();
    }

    private static double clamp(double v, double min, double max) {
        return Double.isNaN(v) ? min : Math.max(min, Math.min(max, v));
    }
}
