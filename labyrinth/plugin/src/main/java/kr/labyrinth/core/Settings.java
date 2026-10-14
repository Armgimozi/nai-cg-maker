package kr.labyrinth.core;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.MemoryConfiguration;

/**
 * config.yml 의 타입 래퍼 (불변 스냅샷). reload 시 새 인스턴스로 교체된다.
 * 값을 바꾸는 쓰기는 {@code Services#updateConfig} 로 한다(파일 저장 + 재생성).
 */
public final class Settings {

    private final Map<String, Difficulty> difficulties;
    private final String difficultyId;
    private final PartyScaling party;
    private final int partyInviteTimeout;
    private final String worldName;
    private final Entrance entrance;
    private final Pack pack;
    private final int autosaveMinutes;
    private final Combat combat;
    private final Level level;
    private final Map<String, Double> weaponAttackSpeed;

    public record Entrance(String mode, String world, double x, double y, double z, float yaw, float pitch, double radius) {
        public boolean isSet() { return world != null && !world.isBlank(); }

        /** 월드가 로드돼 있지 않으면 null. */
        public Location toLocation() {
            if (!isSet()) return null;
            World w = Bukkit.getWorld(world);
            return w == null ? null : new Location(w, x, y, z, yaw, pitch);
        }
    }

    public record Pack(boolean enabled, int port, String bind, String publicHost, String url, String sha1,
                       boolean required, boolean kickOnDecline, boolean updateFromJar, String prompt) {}

    public record Combat(boolean damageNumbers, int damageNumberTicks, double baseCritChance, double baseCritDamage,
                         boolean scaleVanillaDamage) {}

    public record Level(int max, int pointsPerLevel, double xpA, double xpExp, double xpB) {
        public static final Level DEFAULT = new Level(50, 5, 40, 1.6, 60);
    }

    public Settings(ConfigurationSection c) {
        if (c == null) c = new MemoryConfiguration();
        Map<String, Difficulty> diffs = new LinkedHashMap<>();
        diffs.put("easy", Difficulty.EASY);
        diffs.put("normal", Difficulty.NORMAL);
        diffs.put("hard", Difficulty.HARD);
        diffs.put("nightmare", Difficulty.NIGHTMARE);
        ConfigurationSection ds = c.getConfigurationSection("difficulties");
        if (ds != null) {
            for (String id : ds.getKeys(false)) {
                ConfigurationSection d = ds.getConfigurationSection(id);
                if (d == null) continue;
                Difficulty def = diffs.getOrDefault(id, Difficulty.NORMAL);
                diffs.put(id, new Difficulty(id, d.getString("name", def.name()), d.getDouble("hp", def.hp()),
                        d.getDouble("damage", def.damage()), d.getDouble("drop", def.drop()),
                        d.getDouble("xp", def.xp()), d.getDouble("telegraph", def.telegraph())));
            }
        }
        this.difficulties = Collections.unmodifiableMap(diffs);
        String did = c.getString("difficulty", "");
        did = did == null ? "" : did.trim().toLowerCase(Locale.ROOT);
        this.difficultyId = diffs.containsKey(did) ? did : "";

        this.party = new PartyScaling(Math.max(1, c.getInt("party.max_size", 10)),
                c.getDouble("party.hp_per_member", 0.6), c.getDouble("party.dmg_per_member", 0.08),
                c.getDouble("party.reward_per_member", 0.05));
        this.partyInviteTimeout = c.getInt("party.invite_timeout", 60);
        this.worldName = c.getString("world.name", "labyrinth_world");
        this.entrance = new Entrance(c.getString("entrance.mode", ""), c.getString("entrance.world", ""),
                c.getDouble("entrance.x"), c.getDouble("entrance.y"), c.getDouble("entrance.z"),
                (float) c.getDouble("entrance.yaw"), (float) c.getDouble("entrance.pitch"),
                c.getDouble("entrance.radius", 8));
        this.pack = new Pack(c.getBoolean("pack.enabled", true), c.getInt("pack.port", 8163),
                c.getString("pack.bind", "0.0.0.0"), c.getString("pack.public_host", ""), c.getString("pack.url", ""),
                c.getString("pack.sha1", ""), c.getBoolean("pack.required", true),
                c.getBoolean("pack.kick_on_decline", false), c.getBoolean("pack.update_from_jar", true),
                c.getString("pack.prompt", "<gray>미궁 라비린스 전용 리소스팩입니다.</gray>"));
        this.autosaveMinutes = Math.max(1, c.getInt("data.autosave_minutes", 5));
        this.combat = new Combat(c.getBoolean("combat.damage_numbers", true),
                Math.max(4, c.getInt("combat.damage_number_ticks", 16)), c.getDouble("combat.base_crit_chance", 0.05),
                c.getDouble("combat.base_crit_damage", 1.5), c.getBoolean("combat.scale_vanilla_damage", true));
        this.level = new Level(Math.max(1, c.getInt("level.max", 50)), c.getInt("level.points_per_level", 5),
                c.getDouble("level.xp_a", 40), c.getDouble("level.xp_exp", 1.6), c.getDouble("level.xp_b", 60));
        Map<String, Double> was = new LinkedHashMap<>();
        ConfigurationSection ws = c.getConfigurationSection("weapon_attack_speed");
        if (ws != null) for (String k : ws.getKeys(false)) was.put(k, ws.getDouble(k));
        was.putIfAbsent("none", 1.6);
        this.weaponAttackSpeed = Collections.unmodifiableMap(was);
    }

    public Map<String, Difficulty> difficulties() { return difficulties; }

    /** 서버 난이도가 정해졌는가 (초기 설정 완료 여부). false 면 미궁 입장을 막는다. */
    public boolean isDifficultySet() { return !difficultyId.isEmpty(); }

    /** 현재 서버 난이도. 아직 안 정했으면 보통(계산용 기본값). */
    public Difficulty difficulty() {
        return difficultyId.isEmpty() ? difficulties.getOrDefault("normal", Difficulty.NORMAL) : difficulties.get(difficultyId);
    }

    public Difficulty difficulty(String id) { return id == null ? null : difficulties.get(id.toLowerCase(Locale.ROOT)); }

    public PartyScaling party() { return party; }
    public int partyInviteTimeout() { return partyInviteTimeout; }
    public String worldName() { return worldName; }
    public Entrance entrance() { return entrance; }
    public Pack pack() { return pack; }
    public int autosaveMinutes() { return autosaveMinutes; }
    public Combat combat() { return combat; }
    public Level level() { return level; }

    public double weaponAttackSpeed(String weaponType) {
        if (weaponType == null) return weaponAttackSpeed.get("none");
        return weaponAttackSpeed.getOrDefault(weaponType, weaponAttackSpeed.get("none"));
    }
}
