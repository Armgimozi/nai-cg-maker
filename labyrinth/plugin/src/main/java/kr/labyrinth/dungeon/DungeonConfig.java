package kr.labyrinth.dungeon;

import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.core.Log;
import kr.labyrinth.stats.XpCurve;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * dungeon.yml 래퍼 (불변 스냅샷, reload 시 교체). 없는 키는 코드 기본값(= jar 안 dungeon.yml 값) —
 * 이미 깔린 서버의 dungeon.yml 에 새 키가 없어도 새 동작이 켜진다. 끄려면 키를 명시한다.
 */
public record DungeonConfig(
        int blocksPerTick, int maxInstances, boolean resetWorldOnStartup, int topFloorY, int floorSpacing,
        int emptyTimeout, int startCountdown, int roomLockDelay, double mobCountPerMember, int maxMobsPerRoom,
        double restHeal, double fallbackHpMult, double fallbackDamageMult, int stairsWaitSeconds,
        int finalReturnSeconds, int wipeReturnSeconds, int treasureChests, double mimicChance, int mimicMobs,
        double spectatorLeash, double fallDamage, boolean requireNearEntrance, TrapRules traps,
        Map<Integer, Double> partyMobCount, boolean partyMobReward, double roomClearHeal, double firstClearBonus,
        Special specialTrial) {

    /** 솔로·2인 전투방 몹 수 배율 기본값 (party_mob_count 가 없거나 비어 있을 때). */
    public static final Map<Integer, Double> DEFAULT_PARTY_MOB_COUNT = Map.of(1, 0.7, 2, 0.9);

    /**
     * 전투방 웨이브 하나: 실제로 세울 몹 수 + 그 웨이브 몹 한 마리당 보상 배율(경험치·골드·루팅 확률).
     * rewardMult = 배율 없이 나왔을 수 ÷ 실제 수 → 몹 수를 줄여도 방 하나의 보상은 그대로.
     */
    public record Wave(int count, double rewardMult) {}

    /**
     * 함정·미로 상자 공통 규칙 (dungeon.yml {@code traps.*}·{@code treasure.*}, GDD §5.5·§5.6).
     * disarmSeconds = 함정 옆에서 웅크리고 있어야 하는 초, shadowDisarmSeconds = 그림자 직업, shadowSense = 그림자가 함정 윤곽을 보는 거리,
     * disarmGold = 해제 골드 (× 층), disarmXp = 해제 경험치 (× 층 일반 몹 평균), mimicLockSeconds = 미믹이 달아날 때까지의 초
     * (상자 자리 근처에 살아 있는 파티원이 있을 때만 흐르고, 맞고 있으면 미룸 — 다 되면 달아나고 상자가 돌아옴).
     * 바깥 레코드의 mimicMobs 는 mobs.yml 에 미믹 몹이 없을 때만 쓴다(예전처럼 층 일반 몹 수).
     */
    public record TrapRules(double disarmSeconds, double shadowDisarmSeconds, double shadowSense, int disarmGold, double disarmXp,
                            int mimicLockSeconds) {}

    /**
     * 특별 시련 (dungeon.yml {@code special_trial.*}, GDD §10.1, {@code dungeon.rooms.SpecialTrial}).
     * chance = 층 방문마다 시련방이 특별 시련일 확률, pityVisits = 이만큼 연속 못 보면 다음은 확정(0 = 끔),
     * xpBonus = 조건까지 지키면 시련 경험치 × (1 + 값). 조건 값: 서두름 swift.* · 무상 unscathed.* · 절제 abstain.*.
     */
    public record Special(boolean enabled, double chance, int pityVisits, double xpBonus,
                          double swiftTimeFactor, int swiftMinSeconds, int swiftDefaultSeconds,
                          int unscathedHits, int unscathedPerMember, double unscathedMinDamage,
                          boolean abstainPotions, boolean abstainScrolls) {

        /** 코드 기본값 (= jar dungeon.yml). */
        public static final Special DEFAULT = new Special(true, 0.3, 3, 0.5, 0.7, 40, 75, 2, 1, 0.03, true, true);

        /** 같은 값으로 끈 것 ({@code special_trial: false}). */
        public Special disabled() {
            return new Special(false, chance, pityVisits, xpBonus, swiftTimeFactor, swiftMinSeconds, swiftDefaultSeconds,
                    unscathedHits, unscathedPerMember, unscathedMinDamage, abstainPotions, abstainScrolls);
        }

        static Special of(ConfigurationSection c) {
            if (c == null) return DEFAULT;
            Special d = DEFAULT;
            return new Special(c.getBoolean("enabled", d.enabled()),
                    Math.max(0, Math.min(1, c.getDouble("chance", d.chance()))),
                    Math.max(0, Math.min(50, c.getInt("pity_visits", d.pityVisits()))),
                    Math.max(0, Math.min(5, c.getDouble("xp_bonus", d.xpBonus()))),
                    Math.max(0.1, Math.min(1, c.getDouble("conditions.swift.time_factor", d.swiftTimeFactor()))),
                    Math.max(5, c.getInt("conditions.swift.min_seconds", d.swiftMinSeconds())),
                    Math.max(5, c.getInt("conditions.swift.default_seconds", d.swiftDefaultSeconds())),
                    Math.max(0, c.getInt("conditions.unscathed.hits", d.unscathedHits())),
                    Math.max(0, c.getInt("conditions.unscathed.per_member", d.unscathedPerMember())),
                    Math.max(0, Math.min(1, c.getDouble("conditions.unscathed.min_damage", d.unscathedMinDamage()))),
                    c.getBoolean("conditions.abstain.potions", d.abstainPotions()),
                    c.getBoolean("conditions.abstain.scrolls", d.abstainScrolls()));
        }
    }

    public static DungeonConfig load(JavaPlugin plugin) {
        File f = new File(plugin.getDataFolder(), "dungeon.yml");
        try {
            if (!f.exists()) plugin.saveResource("dungeon.yml", false);
        } catch (Exception e) {
            Log.warn("dungeon.yml 기본 파일 복사 실패: " + e.getMessage());
        }
        YamlConfiguration c = YamlConfiguration.loadConfiguration(f);
        try (var in = plugin.getResource("dungeon.yml")) {
            if (in != null) c.setDefaults(YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8)));
        } catch (Exception ignored) {
            // 기본값 없이 진행
        }
        return of(c);
    }

    public static DungeonConfig of(ConfigurationSection c) {
        return new DungeonConfig(
                Math.max(200, c.getInt("blocks_per_tick", 4000)),
                Math.max(1, Math.min(256, c.getInt("max_instances", 32))),
                c.getBoolean("reset_world_on_startup", true),
                Math.max(250, Math.min(300, c.getInt("top_floor_y", 280))),
                Math.max(30, Math.min(34, c.getInt("floor_spacing", 30))),
                Math.max(5, c.getInt("empty_instance_timeout", 30)),
                Math.max(0, c.getInt("start_countdown", 3)),
                Math.max(0, c.getInt("room_lock_delay", 2)),
                Math.max(0, c.getDouble("mob_count_per_member", 0.15)),
                Math.max(1, c.getInt("max_mobs_per_room", 14)),
                Math.max(0, Math.min(1, c.getDouble("rest_heal", 0.5))),
                Math.max(1, c.getDouble("boss_fallback.hp_mult", 6.0)),
                Math.max(0.1, c.getDouble("boss_fallback.damage_mult", 1.25)),
                Math.max(10, c.getInt("stairs_wait_seconds", 120)),
                Math.max(3, c.getInt("final_floor_return_seconds", 25)),
                Math.max(1, c.getInt("wipe_return_seconds", 5)),
                Math.max(1, Math.min(6, c.getInt("treasure.chests", 3))),
                Math.max(0, Math.min(1, c.getDouble("treasure.mimic_chance", 0.3))),
                Math.max(1, c.getInt("treasure.mimic_mobs", 2)),   // 0.3.6~: mobs.yml 에 미믹 몹이 없을 때만 (MimicEncounter)
                Math.max(8, c.getDouble("spectator_leash", 28)),
                Math.max(0, c.getDouble("fall_damage", 0.10)),
                c.getBoolean("require_near_entrance", true),
                new TrapRules(Math.max(0.5, c.getDouble("traps.disarm_seconds", 3.0)),
                        Math.max(0.2, c.getDouble("traps.shadow_disarm_seconds", 1.0)),
                        Math.max(0, c.getDouble("traps.shadow_sense_radius", 10)),
                        Math.max(0, c.getInt("traps.disarm_gold", 6)),
                        Math.max(0, c.getDouble("traps.disarm_xp", 0.5)),
                        Math.max(5, c.getInt("treasure.mimic_lock_seconds", 30))),
                c.get("party_mob_count", null) instanceof Boolean on && !on ? Map.of()
                        : parsePartyMobCount(c.getConfigurationSection("party_mob_count")),
                c.getBoolean("party_mob_reward", true),
                Math.max(0, Math.min(1, c.getDouble("room_clear_heal", 0.15))),
                Math.max(0, Math.min(2, c.getDouble("first_clear_bonus", 0.4))),
                c.get("special_trial", null) instanceof Boolean on && !on ? Special.DEFAULT.disabled()
                        : Special.of(c.getConfigurationSection("special_trial")));
    }

    /**
     * party_mob_count 파싱: {인원: 배율} (0.1~1.5). 섹션이 없거나 인원 키가 하나도 없으면 코드 기본값,
     * {@code enabled: false} (또는 {@code party_mob_count: false}) 면 끔(빈 맵 = 모든 인원 1.0).
     */
    static Map<Integer, Double> parsePartyMobCount(ConfigurationSection s) {
        if (s == null) return DEFAULT_PARTY_MOB_COUNT;
        if (!s.getBoolean("enabled", true)) return Map.of();
        Map<Integer, Double> out = new TreeMap<>();
        for (String k : s.getKeys(false)) {
            int n;
            try {
                n = Integer.parseInt(k.trim());
            } catch (NumberFormatException e) {
                continue; // enabled 등
            }
            if (n >= 1) out.put(n, Math.max(0.1, Math.min(1.5, s.getDouble(k, 1.0))));
        }
        return out.isEmpty() ? DEFAULT_PARTY_MOB_COUNT : Collections.unmodifiableMap(out);
    }

    public static DungeonConfig defaults() { return of(new YamlConfiguration()); }

    /** 층 n 의 바닥 y (B1 이 가장 높고 B10 이 가장 낮다). */
    public int floorY(int floor) { return topFloorY - (Math.max(1, floor) - 1) * floorSpacing; }

    // ── 솔로·2인 몹 수 (party_mob_count) ─────────────────────────────────

    /** 인원 n 의 전투방 몹 수 배율 (없는 인원은 1.0). */
    public double mobCountMult(int n) { return partyMobCount.getOrDefault(Math.max(1, n), 1.0); }

    /**
     * 일반 전투방 웨이브: round(굴림 × 배율 × (1 + mob_count_per_member × (n−1))), 1 ~ max_mobs_per_room.
     * @param base floors.yml mob_density 굴림
     */
    public Wave battleWave(int base, int n) {
        double party = 1 + mobCountPerMember * (Math.max(1, n) - 1);
        int full = clampCount(Math.round(base * party));
        int count = clampCount(Math.round(base * mobCountMult(n) * party));
        return new Wave(count, rewardMult(full, count));
    }

    /** 정예방 호위: round(굴림 × 배율), 최소 1. @param base 2~3 굴림 */
    public Wave eliteEscort(int base, int n) {
        int count = Math.max(1, (int) Math.round(base * mobCountMult(n)));
        return new Wave(count, rewardMult(base, count));
    }

    private int clampCount(long v) { return (int) Math.max(1, Math.min(maxMobsPerRoom, v)); }

    private double rewardMult(int full, int count) {
        return partyMobReward && count > 0 && full > 0 ? (double) full / count : 1.0;
    }

    // ── 층 첫 돌파 보너스 (first_clear_bonus) ─────────────────────────────

    /** 그 층 level_range 구간 필요 경험치 합 × first_clear_bonus (난이도 배율 없음). 0 이면 끔. */
    public long firstClearXp(XpCurve curve, IntRange levelRange) {
        if (firstClearBonus <= 0 || curve == null || levelRange == null) return 0;
        long span = curve.totalTo(levelRange.max()) - curve.totalTo(levelRange.min());
        return Math.max(0, Math.round(span * firstClearBonus));
    }
}
