package kr.souls.combat;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * M1 전투의 맞출 값 (M1_PLAN 0.4): config.yml combat.* 를 한 번 읽어 굳힌 것. 체계마다 레코드 하나 (입력·동작 P1a, 대기열·막기 P2a,
 * 예고 P2b, 패링·치명타 P3, 강인도·자세 P4, 왼손 공격·모은 강공격·낙하 P6, 활 P7, 표적 고정 P8). Config 에는 이 칸 하나
 * ({@code Config.tuning}) 만 있다. 적 (enemies.*) 은 enemy/EnemyTuning (P5a), 도장 (dojo.*) 은 world/Dojo.Cfg (P1b) 가 따로 읽는다.
 * <ul>
 *   <li>값 하나는 한 곳에만 있다 (R21). 수는 모두 여기나 content/*.yml 에서 오고 코드에 박지 않는다 (사용자가 도장에서 맞춘다).</li>
 *   <li>읽는 법: 열쇠가 없거나 틀리면 그 열쇠의 기본값 (jar 의 config.yml 과 같은 값을 코드에도 적는다), 범위를 넘으면 자른다.
 *       예전 판의 config.yml 에 절이 없으면 Bukkit 이 jar 기본값을 보고 빈 절을 돌려준다 (Config 의 guard·parry 와 같다):
 *       {@link #ints} 처럼 표를 읽는 도우미는 빈 절을 "없음" 으로 본다. ConfigDefaultsTest 가 jar 의 config.yml 과 빈 설정 둘 다 본다.</li>
 *   <li>묶음은 아래 표시 줄 밑에 자기 레코드·칸·읽는 줄을 더한다 (다른 묶음의 줄은 고치지 않는다).</li>
 * </ul>
 */
public final class CombatTuning {
    // ── M1 P1a ── (record Input, record Moves: combat.input, combat.moves)
    // ── M1 P2a ── (record Queue, record GuardM1: combat.queue, combat.guard 의 M1 열쇠)
    // ── M1 P2b ── (record Telegraph: combat.telegraph)
    // ── M1 P3 ── (record ParryM1, Riposte, Backstab, Crit, Telemetry)
    // ── M1 P4 ── (record Poise, Posture)
    // ── M1 P6 ── (record Charge, Plunge, Offhand: combat.moves.charge·plunge·offhand, combat.offhand-swap)
    // ── M1 P7 ── (Archery.Cfg 는 combat/Archery 에 있다: 여기서는 combat.bow 를 넘기기만)
    // ── M1 P8 ── (LockOn.Cfg 는 combat/LockOn 에 있다)
    // ── M1 끝 ──

    /** 읽은 절 (combat). 묶음의 Cfg 가 자기 절을 여기서 꺼낸다 (Archery.Cfg, LockOn.Cfg). 없으면 빈 절 */
    private final ConfigurationSection combat;

    public CombatTuning(ConfigurationSection combat) {
        this.combat = combat != null ? combat : new YamlConfiguration();
        // ── M1 P1a ──
        // ── M1 P2a ──
        // ── M1 P2b ──
        // ── M1 P3 ──
        // ── M1 P4 ──
        // ── M1 P6 ──
        // ── M1 P7 ──
        // ── M1 P8 ──
        // ── M1 끝 ──
    }

    /** config.yml 의 combat 절을 읽는다. */
    public static CombatTuning read(FileConfiguration c) {
        return new CombatTuning(c == null ? null : c.getConfigurationSection("combat"));
    }

    /** combat 밑의 절 (path 는 combat 뒤, 예: "bow"). 없으면 빈 절 (null 이 아니다). */
    public ConfigurationSection section(String path) {
        ConfigurationSection s = combat.getConfigurationSection(path);
        return s != null ? s : new YamlConfiguration();
    }

    // ── 읽는 도우미 (묶음이 함께 쓴다) ──

    /** 정수: 없거나 정수가 아니면 def, [min, max] 로 자른다. */
    public static int i(ConfigurationSection s, String path, int def, int min, int max) {
        int v = def;
        if (s != null) {
            if (s.isInt(path)) v = s.getInt(path);
            else if (s.isDouble(path) || s.isLong(path)) v = (int) Math.max(Integer.MIN_VALUE, Math.min(Integer.MAX_VALUE, Math.round(s.getDouble(path))));
        }
        return Math.max(min, Math.min(max, v));
    }

    /** 실수: 없거나 수가 아니면 def, [min, max] 로 자른다. */
    public static double d(ConfigurationSection s, String path, double def, double min, double max) {
        double v = def;
        if (s != null && (s.isDouble(path) || s.isInt(path) || s.isLong(path))) v = s.getDouble(path);
        if (Double.isNaN(v) || Double.isInfinite(v)) v = def;
        return Math.max(min, Math.min(max, v));
    }

    /** 참거짓: 없거나 참거짓이 아니면 def. */
    public static boolean b(ConfigurationSection s, String path, boolean def) {
        return s != null && s.isBoolean(path) ? s.getBoolean(path) : def;
    }

    /**
     * 이름 → 정수 표 (분류마다 값 같은 것). 절이 없거나 비었으면 def 그대로 (예전 config.yml 의 빈 절, Config.guard 와 같은 규칙),
     * 있으면 그 절의 값만 (def 에 없는 이름도), 각 값은 [min, max] 로 자른다. 바꿀 수 없는 표.
     */
    public static Map<String, Integer> ints(ConfigurationSection s, String path, Map<String, Integer> def, int min, int max) {
        ConfigurationSection t = s == null ? null : s.getConfigurationSection(path);
        if (t == null || t.getKeys(false).isEmpty()) return Collections.unmodifiableMap(new LinkedHashMap<>(def));
        Map<String, Integer> out = new LinkedHashMap<>();
        for (String k : t.getKeys(false)) {
            if (t.isInt(k) || t.isDouble(k)) out.put(k, Math.max(min, Math.min(max, (int) Math.round(t.getDouble(k)))));
        }
        return Collections.unmodifiableMap(out.isEmpty() ? new LinkedHashMap<>(def) : out);
    }

    /** 이름 → 실수 표 ({@link #ints} 와 같은 규칙). */
    public static Map<String, Double> doubles(ConfigurationSection s, String path, Map<String, Double> def, double min, double max) {
        ConfigurationSection t = s == null ? null : s.getConfigurationSection(path);
        if (t == null || t.getKeys(false).isEmpty()) return Collections.unmodifiableMap(new LinkedHashMap<>(def));
        Map<String, Double> out = new LinkedHashMap<>();
        for (String k : t.getKeys(false)) {
            if (t.isInt(k) || t.isDouble(k)) {
                double v = t.getDouble(k);
                if (!Double.isNaN(v) && !Double.isInfinite(v)) out.put(k, Math.max(min, Math.min(max, v)));
            }
        }
        return Collections.unmodifiableMap(out.isEmpty() ? new LinkedHashMap<>(def) : out);
    }

    /** 실수 목록 (동작 배율 [100, 105, 115] 같은 것): 없거나 수가 아닌 것이 섞였으면 def. */
    public static List<Double> list(ConfigurationSection s, String path, List<Double> def) {
        List<?> raw = s == null ? null : s.getList(path);
        if (raw == null || raw.isEmpty()) return List.copyOf(def);
        Double[] out = new Double[raw.size()];
        for (int k = 0; k < out.length; k++) {
            if (!(raw.get(k) instanceof Number n)) return List.copyOf(def);
            out[k] = n.doubleValue();
        }
        return List.of(out);
    }
}
