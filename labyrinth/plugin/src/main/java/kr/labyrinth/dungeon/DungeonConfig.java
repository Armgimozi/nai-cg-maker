package kr.labyrinth.dungeon;

import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import kr.labyrinth.core.Log;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

/** dungeon.yml 래퍼 (불변 스냅샷, reload 시 교체). 없는 키는 jar 안 기본값. */
public record DungeonConfig(
        int blocksPerTick, int maxInstances, boolean resetWorldOnStartup, int topFloorY, int floorSpacing,
        int emptyTimeout, int startCountdown, int roomLockDelay, double mobCountPerMember, int maxMobsPerRoom,
        double restHeal, double fallbackHpMult, double fallbackDamageMult, int stairsWaitSeconds,
        int finalReturnSeconds, int wipeReturnSeconds, int treasureChests, double mimicChance, int mimicMobs,
        double spectatorLeash, double fallDamage, boolean requireNearEntrance) {

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
                Math.max(1, c.getInt("treasure.mimic_mobs", 2)),
                Math.max(8, c.getDouble("spectator_leash", 28)),
                Math.max(0, c.getDouble("fall_damage", 0.10)),
                c.getBoolean("require_near_entrance", true));
    }

    public static DungeonConfig defaults() { return of(new YamlConfiguration()); }

    /** 층 n 의 바닥 y (B1 이 가장 높고 B10 이 가장 낮다). */
    public int floorY(int floor) { return topFloorY - (Math.max(1, floor) - 1) * floorSpacing; }
}
