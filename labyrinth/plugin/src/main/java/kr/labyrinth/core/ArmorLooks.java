package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.ArmorLook;
import org.bukkit.configuration.ConfigurationSection;

/**
 * config.yml {@code armor_looks} — 방어구 겉모습 장단점 (look_spec §7, 불변). 키가 없으면 코드 기본값 {@link #DEFAULT}
 * (= jar 의 config.yml). {@code enabled: false} 면 숨은 효과·4부위 효과가 모두 꺼진다 (요구 능력치는 items.yml 그대로).
 * <ul>
 *   <li>{@code piece}: 부위 하나의 숨은 효과 (머리·몸·다리·발·방패 어느 칸이든 같은 값, 굴리지 않음). 키는 장비 스탯 키(더하기)
 *       또는 {@link #MULT_KEYS}(곱하기). 모르는 키는 경고 한 줄 뒤 무시, 값은 ±0.5 안으로 자른다.</li>
 *   <li>4부위 효과: 판금 {@link Steadfast 버팀} · 가죽 {@link Tumble 구르기} · 천 {@link ManaShield 마나 보호막}.</li>
 * </ul>
 * 주인 결정 D1: 구르기 재사용 대기 5초 (look_spec 의 8초 대신).
 */
public record ArmorLooks(boolean enabled, int fullPieces, ArmorLook shieldCountsAs, Map<ArmorLook, Look> looks,
                         Steadfast steadfast, Tumble tumble, ManaShield manaShield, List<String> warnings) {

    /** 곱하는 키: 최종 방어 · 최대 HP · 초당 MP 재생 · 직업·무기 스킬 재사용 대기 시간 × (1 + 합). */
    public static final Set<String> MULT_KEYS = Set.of("defense_pct", "hp_pct", "mana_regen_pct", "cooldown_pct");
    /** 숨은 효과 한 값의 범위. */
    public static final double MAX_PIECE = 0.5;

    /** 겉모습 하나: 이름 · 색 · 부위 하나의 숨은 효과. */
    public record Look(String name, String color, Map<String, Double> piece) {
        public Look {
            piece = piece == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(piece));
        }

        public double get(String key) { return piece.getOrDefault(key, 0.0); }
    }

    /** 판금 4부위 — 버팀: 밀려나는 세기 −knockbackResist (힘과 더함, 상한 85%) · 기절·속박·빙결 시간 −ccResist. 보스가 한 것은 그대로. */
    public record Steadfast(String name, double knockbackResist, double ccResist) {
        public static final Steadfast DEFAULT = new Steadfast("버팀", 0.60, 0.40);

        public Steadfast {
            knockbackResist = clamp(knockbackResist, 0, 0.85, 0.60);
            ccResist = clamp(ccResist, 0, 0.9, 0.40);
        }
    }

    /**
     * 가죽 4부위 — 구르기: 땅 위에서 웅크리기 키를 doubleTap 초 안에 두 번 → 움직이던 방향으로 distance 칸 (방향 키가 없으면 뒤로
     * backDistance 칸), iframe 초 동안 피할 수 있는 공격은 모두 회피, cooldown 초에 한 번. 웅크리기 조합 스킬을 쓴 뒤 comboGuard 초 안이면 안 구름.
     */
    public record Tumble(String name, double doubleTap, double distance, double backDistance, double iframe, double cooldown,
                         double comboGuard, boolean readySound) {
        public static final Tumble DEFAULT = new Tumble("구르기", 0.30, 3.5, 2.0, 0.40, 5.0, 0.40, true);

        public Tumble {
            doubleTap = clamp(doubleTap, 0.1, 1.0, 0.30);
            distance = clamp(distance, 0, 8, 3.5);
            backDistance = clamp(backDistance, 0, 8, 2.0);
            iframe = clamp(iframe, 0, 1.5, 0.40);
            cooldown = clamp(cooldown, 0.5, 120, 5.0);
            comboGuard = clamp(comboGuard, 0, 2, 0.40);
        }
    }

    /** 천 4부위 — 마나 보호막: 받는 최종 피해의 absorb 를 MP 가 대신 (MP 1 = 피해 damagePerMp), MP 가 최대의 offBelow 아래면 쉼. */
    public record ManaShield(String name, double absorb, double damagePerMp, double offBelow) {
        public static final ManaShield DEFAULT = new ManaShield("마나 보호막", 0.20, 2.0, 0.20);

        public ManaShield {
            absorb = clamp(absorb, 0, 0.9, 0.20);
            damagePerMp = clamp(damagePerMp, 0.1, 100, 2.0);
            offBelow = clamp(offBelow, 0, 1, 0.20);
        }
    }

    public static final Look DEFAULT_HEAVY = new Look("판금", "#b8c4d6", ordered(
            "defense_pct", 0.04, "damage_reduction", 0.005, "move_speed", -0.02, "evasion", -0.01, "cooldown_pct", 0.02));
    public static final Look DEFAULT_LIGHT = new Look("가죽", "#c9a46a", ordered(
            "evasion", 0.015, "crit_chance", 0.01, "attack_speed", 0.015, "move_speed", 0.01, "defense_pct", -0.06));
    public static final Look DEFAULT_CLOTH = new Look("천", "#b99cff", ordered(
            "skill_damage", 0.02, "cooldown_pct", -0.015, "mana_regen_pct", 0.06, "hp_pct", -0.02));

    /** 코드 기본값 (= jar 의 config.yml, 구르기 5초). */
    public static final ArmorLooks DEFAULT = new ArmorLooks(true, 4, ArmorLook.HEAVY,
            Map.of(ArmorLook.HEAVY, DEFAULT_HEAVY, ArmorLook.LIGHT, DEFAULT_LIGHT, ArmorLook.CLOTH, DEFAULT_CLOTH),
            Steadfast.DEFAULT, Tumble.DEFAULT, ManaShield.DEFAULT, List.of());

    /** 모두 끔 (시험·옛 시그니처용). */
    public static final ArmorLooks OFF = DEFAULT.withEnabled(false);

    public ArmorLooks {
        fullPieces = Math.max(1, Math.min(4, fullPieces));
        if (shieldCountsAs == null || !shieldCountsAs.real()) shieldCountsAs = ArmorLook.HEAVY;
        EnumMap<ArmorLook, Look> m = new EnumMap<>(ArmorLook.class);
        if (looks != null) m.putAll(looks);
        m.putIfAbsent(ArmorLook.HEAVY, DEFAULT_HEAVY);
        m.putIfAbsent(ArmorLook.LIGHT, DEFAULT_LIGHT);
        m.putIfAbsent(ArmorLook.CLOTH, DEFAULT_CLOTH);
        looks = Collections.unmodifiableMap(m);
        if (steadfast == null) steadfast = Steadfast.DEFAULT;
        if (tumble == null) tumble = Tumble.DEFAULT;
        if (manaShield == null) manaShield = ManaShield.DEFAULT;
        warnings = warnings == null ? List.of() : List.copyOf(warnings);
    }

    public ArmorLooks withEnabled(boolean on) {
        return new ArmorLooks(on, fullPieces, shieldCountsAs, looks, steadfast, tumble, manaShield, warnings);
    }

    public ArmorLooks withTumble(Tumble t) {
        return new ArmorLooks(enabled, fullPieces, shieldCountsAs, looks, steadfast, t, manaShield, warnings);
    }

    /** 판금·가죽·천의 설정 (평상복·any 면 null). */
    public Look look(ArmorLook l) { return l == null ? null : looks.get(l); }

    /** 겉모습 이름 (판금 · 가죽 · 천 · 평상복 · 어느 겉모습이든). */
    public String name(ArmorLook l) {
        if (l == null) return "";
        Look k = looks.get(l);
        if (k != null) return k.name();
        return l == ArmorLook.PLAIN ? "평상복" : "어느 겉모습이든";
    }

    /** 겉모습 색 (#rrggbb, 평상복·any 는 회색). */
    public String color(ArmorLook l) {
        Look k = l == null ? null : looks.get(l);
        return k != null ? k.color() : "#a0a0a0";
    }

    /** 4부위 효과 이름 (버팀 · 구르기 · 마나 보호막, 없으면 빈 문자열). */
    public String fullName(ArmorLook l) {
        if (l == null) return "";
        return switch (l) {
            case HEAVY -> steadfast.name();
            case LIGHT -> tumble.name();
            case CLOTH -> manaShield.name();
            default -> "";
        };
    }

    // ── 읽기 ──────────────────────────────────────────────────────────────

    /** {@code armor_looks} 섹션 (없으면 기본값). */
    public static ArmorLooks read(ConfigurationSection c) {
        if (c == null) return DEFAULT;
        List<String> warn = new ArrayList<>();
        EnumMap<ArmorLook, Look> looks = new EnumMap<>(ArmorLook.class);
        Steadfast sf = Steadfast.DEFAULT;
        Tumble tb = Tumble.DEFAULT;
        ManaShield ms = ManaShield.DEFAULT;
        for (ArmorLook l : ArmorLook.REAL) {
            Look def = DEFAULT.looks.get(l);
            ConfigurationSection s = c.getConfigurationSection(l.id());
            if (s == null) {
                looks.put(l, def);
                continue;
            }
            Map<String, Double> piece;
            ConfigurationSection ps = s.getConfigurationSection("piece");
            if (ps == null) {
                piece = def.piece();
            } else {
                piece = new LinkedHashMap<>();
                for (String k : ps.getKeys(false)) {
                    if (!knownKey(k)) {
                        warn.add("armor_looks." + l.id() + ".piece." + k + " — 모르는 키라 무시");
                        continue;
                    }
                    double v = ps.getDouble(k, 0);
                    if (Double.isNaN(v) || Math.abs(v) > MAX_PIECE) {
                        warn.add("armor_looks." + l.id() + ".piece." + k + " = " + v + " — ±" + MAX_PIECE + " 안으로 자름");
                        v = Double.isNaN(v) ? 0 : Math.max(-MAX_PIECE, Math.min(MAX_PIECE, v));
                    }
                    if (v != 0) piece.put(k, v);
                }
            }
            looks.put(l, new Look(s.getString("name", def.name()), s.getString("color", def.color()), piece));
            ConfigurationSection f = s.getConfigurationSection("full");
            if (f == null) continue;
            switch (l) {
                case HEAVY -> sf = new Steadfast(f.getString("name", sf.name()), f.getDouble("knockback_resist", sf.knockbackResist()),
                        f.getDouble("cc_resist", sf.ccResist()));
                case LIGHT -> tb = new Tumble(f.getString("name", tb.name()), f.getDouble("double_tap", tb.doubleTap()),
                        f.getDouble("distance", tb.distance()), f.getDouble("back_distance", tb.backDistance()),
                        f.getDouble("iframe", tb.iframe()), f.getDouble("cooldown", tb.cooldown()),
                        f.getDouble("combo_guard", tb.comboGuard()), f.getBoolean("ready_sound", tb.readySound()));
                case CLOTH -> ms = new ManaShield(f.getString("name", ms.name()), f.getDouble("absorb", ms.absorb()),
                        f.getDouble("damage_per_mp", ms.damagePerMp()), f.getDouble("off_below", ms.offBelow()));
                default -> { }
            }
        }
        ArmorLook shield = ArmorLook.byId(c.getString("shield_counts_as", "heavy"));
        if (shield == null || !shield.real()) {
            warn.add("armor_looks.shield_counts_as 는 heavy | light | cloth — heavy 로 둠");
            shield = ArmorLook.HEAVY;
        }
        return new ArmorLooks(c.getBoolean("enabled", true), c.getInt("full_pieces", 4), shield, looks, sf, tb, ms, warn);
    }

    /** piece 아래에 쓸 수 있는 키: 장비 스탯 키(무기 피해 제외, 더하기) 또는 곱하는 키. */
    public static boolean knownKey(String k) {
        return MULT_KEYS.contains(k) || (ContentValidator.ITEM_STAT_KEYS.contains(k) && !"damage".equals(k));
    }

    private static Map<String, Double> ordered(Object... kv) {
        Map<String, Double> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put((String) kv[i], ((Number) kv[i + 1]).doubleValue());
        return m;
    }

    private static double clamp(double v, double lo, double hi, double def) {
        if (Double.isNaN(v)) return def;
        return Math.max(lo, Math.min(hi, v));
    }
}
