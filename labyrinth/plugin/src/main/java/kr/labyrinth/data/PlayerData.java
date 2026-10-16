package kr.labyrinth.data;

import java.util.Base64;
import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.Stat;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 플레이어 진행 데이터 (plugins/Labyrinth/players/&lt;uuid&gt;.yml). 메인 스레드에서만 수정한다.
 * 값을 바꾸면 {@link #markDirty()} (setter 들은 자동).
 * <p>
 * 다른 모듈의 추가 데이터(쿨다운 저장 등)는 {@link #ext()} 맵에 String/Number/Boolean/List/Map 으로 넣는다
 * (키 접두어로 모듈 이름 권장: "items.cooldowns").
 */
public final class PlayerData {

    public static final int ACCESSORY_SLOTS = 2;

    private final UUID uuid;
    private String name;
    private int level = 1;
    private long xp;
    private int statPoints;
    private final EnumMap<Stat, Integer> allocated = new EnumMap<>(Stat.class);
    private String classId;
    private long gold;
    private int unlockedFloor = 1;
    private final Map<String, Long> achievements = new LinkedHashMap<>();
    private String equippedTitle;
    private final byte[][] accessories = new byte[ACCESSORY_SLOTS][];
    private final Map<String, Long> counters = new LinkedHashMap<>();
    private final Map<String, Object> ext = new LinkedHashMap<>();
    private long firstJoin;
    private long lastSeen;
    private boolean dirty;

    public PlayerData(UUID uuid, String name) {
        this.uuid = uuid;
        this.name = name;
        this.firstJoin = System.currentTimeMillis();
    }

    // ── 기본 ──────────────────────────────────────────────────────────────
    public UUID uuid() { return uuid; }
    public String name() { return name; }
    public void name(String n) { if (n != null && !n.equals(name)) { name = n; dirty = true; } }

    public int level() { return level; }
    public void level(int l) { level = Math.max(1, l); dirty = true; }
    public long xp() { return xp; }
    public void xp(long x) { xp = Math.max(0, x); dirty = true; }

    public int statPoints() { return statPoints; }
    public void statPoints(int p) { statPoints = Math.max(0, p); dirty = true; }

    /** 분배한 스탯 (읽기 전용 뷰). */
    public Map<Stat, Integer> allocated() { return Collections.unmodifiableMap(allocated); }
    public int allocated(Stat s) { return allocated.getOrDefault(s, 0); }

    /** 미분배 포인트에서 amount 만큼 s 에 투자. 포인트가 부족하면 false. */
    public boolean allocate(Stat s, int amount) {
        if (amount <= 0 || statPoints < amount) return false;
        allocated.merge(s, amount, Integer::sum);
        statPoints -= amount;
        dirty = true;
        return true;
    }

    /** 분배 초기화 → 포인트 반환. 반환한 포인트 수. */
    public int resetAllocation() {
        int sum = 0;
        for (int v : allocated.values()) sum += v;
        allocated.clear();
        statPoints += sum;
        dirty = true;
        return sum;
    }

    public String classId() { return classId; }
    public void classId(String id) { classId = id; dirty = true; }

    public long gold() { return gold; }
    public void gold(long g) { gold = Math.max(0, g); dirty = true; }
    public void addGold(long g) { gold(gold + g); }
    /** 골드가 충분하면 차감하고 true. */
    public boolean takeGold(long g) {
        if (g < 0 || gold < g) return false;
        gold -= g;
        dirty = true;
        return true;
    }

    /** 입장 가능한 최대 층 (처음 1). */
    public int unlockedFloor() { return unlockedFloor; }
    public void unlockedFloor(int f) { unlockedFloor = Math.max(1, f); dirty = true; }
    /** 층 f 를 깼을 때: 다음 층 해금. */
    public void unlockUpTo(int f) { if (f > unlockedFloor) unlockedFloor(f); }

    // ── 칭호/업적 ─────────────────────────────────────────────────────────
    /** 달성한 업적 id → 달성 시각(epoch ms). */
    public Map<String, Long> achievements() { return Collections.unmodifiableMap(achievements); }
    public boolean hasAchievement(String id) { return achievements.containsKey(id); }
    /** 새로 달성했으면 true. */
    public boolean grantAchievement(String id) {
        if (achievements.containsKey(id)) return false;
        achievements.put(id, System.currentTimeMillis());
        dirty = true;
        return true;
    }
    public void revokeAchievement(String id) { if (achievements.remove(id) != null) dirty = true; }
    public String equippedTitle() { return equippedTitle; }
    public void equippedTitle(String id) { equippedTitle = id; dirty = true; }

    // ── 장신구 2칸 (ItemStack#serializeAsBytes) ────────────────────────────
    public byte[] accessory(int slot) { return accessories[slot] == null ? null : accessories[slot].clone(); }
    public void accessory(int slot, byte[] bytes) { accessories[slot] = bytes == null ? null : bytes.clone(); dirty = true; }

    // ── 통계 카운터 ───────────────────────────────────────────────────────
    /** 통계 (kills, boss_kills, deaths, crafts, clears.floor_3, …). */
    public Map<String, Long> counters() { return Collections.unmodifiableMap(counters); }
    public long counter(String key) { return counters.getOrDefault(key, 0L); }
    public long increment(String key, long by) {
        long v = counters.merge(key, by, Long::sum);
        dirty = true;
        return v;
    }
    public void counter(String key, long v) { counters.put(key, v); dirty = true; }

    /** 모듈 확장 데이터. 수정 후 markDirty() 호출. */
    public Map<String, Object> ext() { return ext; }

    /** ext 키: 가죽 4부위 구르기를 끔 (/스탯 단추, 사람마다 — 기본 false = 켜짐). */
    public static final String TUMBLE_OFF_KEY = "look.tumble_off";

    /** 구르기를 껐는가. */
    public boolean tumbleOff() { return Boolean.TRUE.equals(ext.get(TUMBLE_OFF_KEY)); }

    public void tumbleOff(boolean off) {
        if (off) ext.put(TUMBLE_OFF_KEY, true);
        else ext.remove(TUMBLE_OFF_KEY);
        dirty = true;
    }

    // ── 특별 시련 확정 카운터 (층별, ext special_miss.f<층>) ───────────────
    /** 이 층을 연속으로 특별 시련 없이 돈 횟수 (dungeon.yml special_trial.pity_visits). */
    public int specialMiss(int floor) {
        Object v = ext.get(specialMissKey(floor));
        if (v instanceof Number num) return Math.max(0, num.intValue());
        if (v instanceof String str) {
            try {
                return Math.max(0, Integer.parseInt(str.trim()));
            } catch (NumberFormatException ignored) {
                return 0;
            }
        }
        return 0;
    }

    /** 특별 시련을 보면 0, 못 보면 +1. */
    public void specialMiss(int floor, int v) {
        ext.put(specialMissKey(floor), Math.max(0, v));
        dirty = true;
    }

    public static String specialMissKey(int floor) { return "special_miss.f" + floor; }

    public long firstJoin() { return firstJoin; }
    public long lastSeen() { return lastSeen; }
    public void touch() { lastSeen = System.currentTimeMillis(); dirty = true; }

    public boolean isDirty() { return dirty; }
    public void markDirty() { dirty = true; }
    public void clearDirty() { dirty = false; }

    // ── 직렬화 ────────────────────────────────────────────────────────────
    public String toYaml() {
        YamlConfiguration y = new YamlConfiguration();
        y.set("version", 1);
        y.set("uuid", uuid.toString());
        y.set("name", name);
        y.set("level", level);
        y.set("xp", xp);
        y.set("stat_points", statPoints);
        for (Map.Entry<Stat, Integer> e : allocated.entrySet()) y.set("stats." + e.getKey().key(), e.getValue());
        y.set("class", classId);
        y.set("gold", gold);
        y.set("unlocked_floor", unlockedFloor);
        for (Map.Entry<String, Long> e : achievements.entrySet()) y.set("achievements." + e.getKey(), e.getValue());
        y.set("title", equippedTitle);
        for (int i = 0; i < ACCESSORY_SLOTS; i++) {
            if (accessories[i] != null) y.set("accessories." + i, Base64.getEncoder().encodeToString(accessories[i]));
        }
        for (Map.Entry<String, Long> e : counters.entrySet()) y.set("counters." + e.getKey().replace('.', '/'), e.getValue());
        for (Map.Entry<String, Object> e : ext.entrySet()) y.set("ext." + e.getKey().replace('.', '/'), e.getValue());
        y.set("first_join", firstJoin);
        y.set("last_seen", lastSeen);
        return y.saveToString();
    }

    public static PlayerData fromYaml(UUID uuid, String fallbackName, String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        PlayerData d = new PlayerData(uuid, y.getString("name", fallbackName));
        d.level = Math.max(1, y.getInt("level", 1));
        d.xp = Math.max(0, y.getLong("xp", 0));
        d.statPoints = Math.max(0, y.getInt("stat_points", 0));
        ConfigurationSection st = y.getConfigurationSection("stats");
        if (st != null) {
            for (String k : st.getKeys(false)) {
                Stat s = Stat.byKey(k);
                if (s != null) d.allocated.put(s, Math.max(0, st.getInt(k)));
            }
        }
        d.classId = y.getString("class");
        d.gold = Math.max(0, y.getLong("gold", 0));
        d.unlockedFloor = Math.max(1, y.getInt("unlocked_floor", 1));
        ConfigurationSection ach = y.getConfigurationSection("achievements");
        if (ach != null) for (String k : ach.getKeys(false)) d.achievements.put(k, ach.getLong(k));
        d.equippedTitle = y.getString("title");
        for (int i = 0; i < ACCESSORY_SLOTS; i++) {
            String b64 = y.getString("accessories." + i);
            if (b64 != null && !b64.isEmpty()) d.accessories[i] = Base64.getDecoder().decode(b64);
        }
        ConfigurationSection cnt = y.getConfigurationSection("counters");
        if (cnt != null) for (String k : cnt.getKeys(false)) d.counters.put(k.replace('/', '.'), cnt.getLong(k));
        ConfigurationSection ex = y.getConfigurationSection("ext");
        if (ex != null) ContentLoader.toPlain(ex).forEach((k, v) -> d.ext.put(k.replace('/', '.'), v));
        d.firstJoin = y.getLong("first_join", System.currentTimeMillis());
        d.lastSeen = y.getLong("last_seen", 0);
        d.dirty = false;
        return d;
    }
}
