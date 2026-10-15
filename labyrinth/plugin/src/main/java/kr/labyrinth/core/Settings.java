package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
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
    private final List<KitItem> starterKit;
    private final int starterGold;
    private final Death death;
    private final ClassChange classChange;

    public record Entrance(String mode, String world, double x, double y, double z, float yaw, float pitch, double radius) {
        public boolean isSet() { return world != null && !world.isBlank(); }

        /** 월드가 로드돼 있지 않으면 null. */
        public Location toLocation() {
            if (!isSet()) return null;
            World w = Bukkit.getWorld(world);
            return w == null ? null : new Location(w, x, y, z, yaw, pitch);
        }
    }

    public record Pack(boolean enabled, int port, String bind, String publicHost, int publicPort, String url, String sha1,
                       boolean required, boolean kickOnDecline, boolean updateFromJar, String prompt) {}

    public record Combat(boolean damageNumbers, int damageNumberTicks, double baseCritChance, double baseCritDamage,
                         boolean scaleVanillaDamage) {}

    /** startPoints = Lv.1 에서 받는 스탯 포인트(레벨업 전에도 분배할 수 있게), pointsPerLevel = 레벨이 오를 때마다. */
    public record Level(int max, int startPoints, int pointsPerLevel, double xpA, double xpExp, double xpB) {
        public static final Level DEFAULT = new Level(50, 5, 5, 40, 1.6, 60);

        /** 레벨 lv 에서 받아야 할 총 포인트 (분배 + 미분배). */
        public int totalPointsAt(int lv) { return startPoints + (Math.max(1, lv) - 1) * pointsPerLevel; }

        /** 시작 포인트를 이미 granted 만큼 받은 사람에게 더 줄 몫 (설정을 낮춰도 이미 준 것은 거두지 않음). */
        public int startPointsOwed(int granted) { return Math.max(0, startPoints - Math.max(0, granted)); }
    }

    /** 시작 꾸러미 한 줄 (config.yml starter_kit.items). */
    public record KitItem(String item, int amount) {}

    /**
     * 죽을 때 (config.yml death) — 인벤세이브. keepInventory = 소지품을 그대로 지니고 아무것도 떨구지 않음,
     * keepLevel = 바닐라 경험치 레벨 유지(경험치 구슬도 안 떨굼). 미궁 월드 안의 죽음은 이 값과 상관없이 언제나 보존한다
     * (dungeon 담당 — 공략 중이면 쓰러짐·관전). false 면 그 부분만 바닐라(게임 규칙 keepInventory)대로.
     */
    public record Death(boolean keepInventory, boolean keepLevel) {
        /** 코드 기본값 (= jar 의 config.yml). 기존 서버 config.yml 에 death 키가 없어도 켜진다. */
        public static final Death DEFAULT = new Death(true, true);
    }

    /**
     * 직업 변경 제한 (config.yml class_change, 최상위 키) — 첫 직업 선택은 무료. 그 뒤로 바꿀 때는
     * requireItem 이면 item 1장이 사라지고, 직업을 정한 뒤 cooldownHours 시간 동안은 다시 바꿀 수 없다 (0 = 대기 없음).
     * 판정은 {@code classes.ClassChangeRule}. 관리자 {@code /labadmin setclass} 는 이 제한을 받지 않는다.
     */
    public record ClassChange(boolean requireItem, String item, double cooldownHours) {
        public static final String DEFAULT_ITEM = "class_change_scroll";
        /** 코드 기본값 (= jar 의 config.yml): 전직의 두루마리 1장 + 24시간. */
        public static final ClassChange DEFAULT = new ClassChange(true, DEFAULT_ITEM, 24);
        /** {@code class_change: false} — 제한 없음 (예전처럼 언제든 무료로). */
        public static final ClassChange NONE = new ClassChange(false, DEFAULT_ITEM, 0);

        public ClassChange {
            item = item == null || item.isBlank() ? DEFAULT_ITEM : item.trim();
            cooldownHours = Double.isNaN(cooldownHours) ? 0 : Math.max(0, cooldownHours);
        }

        /** 대기 시간(ms). */
        public long cooldownMs() { return Math.round(cooldownHours * 3_600_000d); }
    }

    /**
     * 시작 꾸러미 코드 기본값 (= jar 의 config.yml) — 수련생 방어구 4종 + 하급 치유 물약 10 · 하급 마나 물약 5 · 귀환 주문서 2 ·
     * 빵 16 (minecraft: = 바닐라 아이템). 골드는 {@link #DEFAULT_STARTER_GOLD}.
     */
    public static final List<KitItem> DEFAULT_STARTER_KIT = List.of(new KitItem("novice_cap", 1),
            new KitItem("novice_tunic", 1), new KitItem("novice_trousers", 1), new KitItem("novice_boots", 1),
            new KitItem("minor_healing_potion", 10), new KitItem("minor_mana_potion", 5), new KitItem("return_scroll", 2),
            new KitItem("minecraft:bread", 16));
    /** 예전 판(0.3.2)이 config.yml 에 그대로 적어 둔 목록 — 손대지 않은 것이므로 새 기본값으로 올린다. */
    public static final List<KitItem> LEGACY_STARTER_KIT_032 = List.of(new KitItem("novice_cap", 1),
            new KitItem("novice_tunic", 1), new KitItem("novice_trousers", 1), new KitItem("novice_boots", 1),
            new KitItem("minor_healing_potion", 5));
    /** 시작 골드 기본값 (starter_kit.gold). 하급 물약 15병 · 귀환 주문서 3장 정도. */
    public static final int DEFAULT_STARTER_GOLD = 300;

    public Settings(ConfigurationSection c) {
        if (c == null) c = new MemoryConfiguration();
        Map<String, Difficulty> diffs = new LinkedHashMap<>();
        diffs.put("easy", Difficulty.EASY);
        diffs.put("normal", Difficulty.NORMAL);
        diffs.put("hard", Difficulty.HARD.withRamp(Difficulty.Ramp.HARD));
        diffs.put("nightmare", Difficulty.NIGHTMARE.withRamp(Difficulty.Ramp.NIGHTMARE));
        ConfigurationSection ds = c.getConfigurationSection("difficulties");
        if (ds != null) {
            for (String id : ds.getKeys(false)) {
                ConfigurationSection d = ds.getConfigurationSection(id);
                if (d == null) continue;
                Difficulty def = diffs.getOrDefault(id, Difficulty.NORMAL);
                Difficulty read = new Difficulty(id, d.getString("name", def.name()), d.getDouble("hp", def.hp()),
                        d.getDouble("damage", def.damage()), d.getDouble("drop", def.drop()),
                        d.getDouble("xp", def.xp()), d.getDouble("telegraph", def.telegraph()));
                diffs.put(id, read.withRamp(Boolean.FALSE.equals(d.get("ramp")) ? null
                        : ramp(d.getConfigurationSection("ramp"), read)));
            }
        }
        this.difficulties = Collections.unmodifiableMap(diffs);
        String did = c.getString("difficulty", "");
        did = did == null ? "" : did.trim().toLowerCase(Locale.ROOT);
        this.difficultyId = diffs.containsKey(did) ? did : "";

        this.party = new PartyScaling(Math.max(1, c.getInt("party.max_size", 10)),
                c.getDouble("party.hp_per_member", 0.6), c.getDouble("party.dmg_per_member", 0.08),
                c.getDouble("party.reward_per_member", 0.05),
                clamp(c.getDouble("party.solo_hp", PartyScaling.DEFAULT_SOLO), 0.1, 1.5),
                clamp(c.getDouble("party.solo_damage", PartyScaling.DEFAULT_SOLO), 0.1, 1.5));
        this.partyInviteTimeout = c.getInt("party.invite_timeout", 60);
        this.worldName = c.getString("world.name", "labyrinth_world");
        this.entrance = new Entrance(c.getString("entrance.mode", ""), c.getString("entrance.world", ""),
                c.getDouble("entrance.x"), c.getDouble("entrance.y"), c.getDouble("entrance.z"),
                (float) c.getDouble("entrance.yaw"), (float) c.getDouble("entrance.pitch"),
                c.getDouble("entrance.radius", 8));
        this.pack = new Pack(c.getBoolean("pack.enabled", true), c.getInt("pack.port", 8163),
                c.getString("pack.bind", "0.0.0.0"), c.getString("pack.public_host", ""),
                c.getInt("pack.public_port", 0), c.getString("pack.url", ""),
                c.getString("pack.sha1", ""), c.getBoolean("pack.required", true),
                c.getBoolean("pack.kick_on_decline", false), c.getBoolean("pack.update_from_jar", true),
                c.getString("pack.prompt", "<gray>미궁 라비린스 전용 리소스팩입니다.</gray>"));
        this.autosaveMinutes = Math.max(1, c.getInt("data.autosave_minutes", 5));
        this.combat = new Combat(c.getBoolean("combat.damage_numbers", true),
                Math.max(4, c.getInt("combat.damage_number_ticks", 16)), c.getDouble("combat.base_crit_chance", 0.05),
                c.getDouble("combat.base_crit_damage", 1.5), c.getBoolean("combat.scale_vanilla_damage", true));
        this.level = new Level(Math.max(1, c.getInt("level.max", 50)), Math.max(0, c.getInt("level.start_points", 5)),
                c.getInt("level.points_per_level", 5),
                c.getDouble("level.xp_a", 40), c.getDouble("level.xp_exp", 1.6), c.getDouble("level.xp_b", 60));
        Map<String, Double> was = new LinkedHashMap<>();
        ConfigurationSection ws = c.getConfigurationSection("weapon_attack_speed");
        if (ws != null) for (String k : ws.getKeys(false)) was.put(k, ws.getDouble(k));
        was.putIfAbsent("none", 1.6);
        this.weaponAttackSpeed = Collections.unmodifiableMap(was);
        this.starterKit = Boolean.FALSE.equals(c.get("starter_kit")) ? List.of()
                : starterKit(c.getConfigurationSection("starter_kit"));
        this.starterGold = starterKit.isEmpty() ? 0 : Math.max(0, c.getInt("starter_kit.gold", DEFAULT_STARTER_GOLD));
        this.death = new Death(c.getBoolean("death.keep_inventory", Death.DEFAULT.keepInventory()),
                c.getBoolean("death.keep_level", Death.DEFAULT.keepLevel()));
        this.classChange = Boolean.FALSE.equals(c.get("class_change")) ? ClassChange.NONE
                : classChange(c.getConfigurationSection("class_change"));
    }

    /**
     * class_change — 섹션이 없으면 코드 기본값({@link ClassChange#DEFAULT}). 빠진 키도 기본값.
     * 끄기 = {@code class_change: false} (또는 require_item: false + cooldown_hours: 0).
     */
    static ClassChange classChange(ConfigurationSection k) {
        ClassChange d = ClassChange.DEFAULT;
        if (k == null) return d;
        return new ClassChange(k.getBoolean("require_item", d.requireItem()), k.getString("item", d.item()),
                k.getDouble("cooldown_hours", d.cooldownHours()));
    }

    /**
     * difficulties.&lt;id&gt;.ramp — 키가 없거나 비어 있으면 코드 기본값({@link Difficulty.Ramp#defaultFor}, 어려움·악몽만).
     * 끄기 = {@code ramp: {enabled: false}} (또는 {@code ramp: false}). from_floor(기본 1)·full_floor(from 이하면 램프 없음)·
     * start.hp/damage/telegraph 중 빠진 값은 기본 램프 값, 기본 램프가 없는 난이도면 그 난이도 원래 값.
     */
    static Difficulty.Ramp ramp(ConfigurationSection r, Difficulty d) {
        Difficulty.Ramp def = Difficulty.Ramp.defaultFor(d.id());
        if (def != null) { // hp·damage 를 기본보다 낮춰 쓰는 서버: 기본 시작 값이 원래 값보다 세지 않게
            def = new Difficulty.Ramp(def.fromFloor(), def.fullFloor(), Math.min(def.startHp(), d.hp()),
                    Math.min(def.startDamage(), d.damage()), Math.max(def.startTelegraph(), d.telegraph()));
        }
        if (r == null || r.getKeys(false).isEmpty()) return def;
        if (!r.getBoolean("enabled", true)) return null;
        int from = r.getInt("from_floor", def == null ? 1 : def.fromFloor());
        int full = r.getInt("full_floor", def == null ? from : def.fullFloor());
        if (full <= from) return null;
        return new Difficulty.Ramp(from, full, r.getDouble("start.hp", def == null ? d.hp() : def.startHp()),
                r.getDouble("start.damage", def == null ? d.damage() : def.startDamage()),
                r.getDouble("start.telegraph", def == null ? d.telegraph() : def.startTelegraph()));
    }

    /**
     * starter_kit — 섹션이 없거나 비어 있거나 items 가 비면 코드 기본값.
     * 끄기 = {@code enabled: false} (또는 {@code starter_kit: false}) → 빈 목록.
     */
    static List<KitItem> starterKit(ConfigurationSection k) {
        if (k == null || k.getKeys(false).isEmpty()) return DEFAULT_STARTER_KIT;
        if (!k.getBoolean("enabled", true)) return List.of();
        List<KitItem> out = new ArrayList<>();
        for (Map<?, ?> m : k.getMapList("items")) {
            Object item = m.get("item");
            if (item == null || String.valueOf(item).isBlank()) continue;
            int amount = m.get("amount") instanceof Number n ? n.intValue() : 1;
            if (amount > 0) out.add(new KitItem(String.valueOf(item).trim(), Math.min(64, amount)));
        }
        // 예전 판 기본 목록을 그대로 둔 서버는 새 기본값 (직접 고친 목록은 그대로 따른다)
        return out.isEmpty() || out.equals(LEGACY_STARTER_KIT_032) ? DEFAULT_STARTER_KIT : List.copyOf(out);
    }

    private static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }

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

    /** 시작 꾸러미 (직업을 처음 고를 때 한 번). 빈 목록 = 꺼짐. */
    public List<KitItem> starterKit() { return starterKit; }
    /** 시작 꾸러미 골드 (꾸러미를 끄면 0). */
    public int starterGold() { return starterGold; }

    /** 죽을 때 소지품·레벨 보존 (인벤세이브). */
    public Death death() { return death; }

    /** 직업 변경 제한 (전직의 두루마리·대기 시간). */
    public ClassChange classChange() { return classChange; }

    public double weaponAttackSpeed(String weaponType) {
        if (weaponType == null) return weaponAttackSpeed.get("none");
        return weaponAttackSpeed.getOrDefault(weaponType, weaponAttackSpeed.get("none"));
    }
}
