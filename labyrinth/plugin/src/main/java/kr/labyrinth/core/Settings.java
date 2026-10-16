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
    private final double unarmedAttackSpeed;
    private final List<String> ignoredWeaponSpeedKeys;
    /** 맨손 초당 공격 횟수 기본값 (간격 0.625초). */
    public static final double DEFAULT_UNARMED_SPEED = 1.6;
    private final List<KitItem> starterKit;
    private final int starterGold;
    private final Death death;
    private final ClassChange classChange;
    private final ArmorLooks armorLooks;
    private final Wild wild;
    private final List<String> wildWarnings;

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
                       boolean required, boolean kickOnDecline, boolean updateFromJar, String prompt, boolean samePort) {}

    /**
     * combat — 0.3.5 게이지 없는 공격 키가 없으면 코드 기본값({@link #DEFAULT}, jar 의 config.yml 과 같음).
     * @param attackIntervalMin 민첩·공속을 다 쌓아도 이보다 빠르지 않다 (초)
     * @param earlyClickBuffer  간격이 끝나기 이 시간(초) 안의 클릭은 기억했다가 끝나는 순간 넣는다 (0 = 끔)
     * @param earlyClickSound   너무 이른 클릭에 작은 '휙' 소리 (본인만)
     * @param clickToleranceMs  이만큼 이른 클릭은 그냥 통과 (지연 보정)
     * @param jumpCrit          떨어지며 친 근접 공격 배율
     * @param bowFullDrawCue    활을 끝까지 당기면 작은 '탁' 소리 (본인만)
     */
    public record Combat(boolean damageNumbers, int damageNumberTicks, double baseCritChance, double baseCritDamage,
                         boolean scaleVanillaDamage, double attackIntervalMin, double earlyClickBuffer,
                         boolean earlyClickSound, int clickToleranceMs, double jumpCrit, boolean bowFullDrawCue) {
        public static final Combat DEFAULT = new Combat(true, 16, 0.05, 1.5, true, 0.25, 0.35, true, 50, 1.2, true);

        /** 0.3.4 판 생성자 (새 키는 기본값). */
        public Combat(boolean damageNumbers, int damageNumberTicks, double baseCritChance, double baseCritDamage,
                      boolean scaleVanillaDamage) {
            this(damageNumbers, damageNumberTicks, baseCritChance, baseCritDamage, scaleVanillaDamage, 0.25, 0.35, true, 50,
                    1.2, true);
        }

        public Combat {
            attackIntervalMin = Double.isNaN(attackIntervalMin) ? 0.25 : Math.max(0.05, Math.min(2.0, attackIntervalMin));
            earlyClickBuffer = Double.isNaN(earlyClickBuffer) ? 0 : Math.max(0, Math.min(1.0, earlyClickBuffer));
            clickToleranceMs = Math.max(0, Math.min(250, clickToleranceMs));
            jumpCrit = Double.isNaN(jumpCrit) ? 1.2 : Math.max(1.0, Math.min(3.0, jumpCrit));
        }
    }

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
     * 야생 막기 (config.yml wild, 최상위 키, 0.3.5.1) — 주 월드에 마을 메타데이터가 있을 때만 쓰인다 (village.WildService).
     * @param border       마을 둘레에 바닐라 월드 경계 (마을 상자 + 보호 상자 ∪ → + borderMargin, 정사각형)
     * @param borderMargin 마을 가장자리에서 몇 칸 더 (0 ~ 1000)
     * @param spawns       마을 월드 자연 스폰 막기: ALL(적대+동물) · MONSTERS(적대만) · NONE
     * 네더·엔드는 막지 않는다 (바닐라 그대로) — 돌아올 때 경계 밖이면 광장으로 옮기는 것은 경계가 맡는다.
     */
    public record Wild(boolean border, int borderMargin, Spawns spawns) {
        /** 마을 월드 자연 스폰을 어디까지 막나. */
        public enum Spawns {
            /** 적대 몹 + 동물·물고기·박쥐·떠돌이 상인 등 모든 몹. */
            ALL,
            /** 적대 몹(Enemy)만. */
            MONSTERS,
            /** 막지 않음 (village.block_mob_spawns 의 마을 둘레 적대 막기만 남음). */
            NONE;

            /** "all" · "monsters" · "none" (대소문자 무시, 몇 가지 다른 표기도). 모르는 값 = null. */
            public static Spawns parse(String s) {
                if (s == null) return null;
                return switch (s.trim().toLowerCase(Locale.ROOT)) {
                    case "all", "모두", "전부" -> ALL;
                    case "monsters", "monster", "hostile", "hostiles", "적대" -> MONSTERS;
                    case "none", "off", "false", "없음", "끔" -> NONE;
                    default -> null;
                };
            }

            public String id() { return name().toLowerCase(Locale.ROOT); }
        }

        /** 코드 기본값 (= jar 의 config.yml): 경계 켬 · 30칸 · 모두 막기. 기존 서버 config 에 wild 가 없어도 켜진다. */
        public static final Wild DEFAULT = new Wild(true, 30, Spawns.ALL);
        /** {@code wild: false} — 바닐라 그대로 (경계 없음 · 스폰 그대로). */
        public static final Wild OFF = new Wild(false, 30, Spawns.NONE);
        public static final int MAX_MARGIN = 1000;

        public Wild {
            borderMargin = Math.max(0, Math.min(MAX_MARGIN, borderMargin));
            spawns = spawns == null ? Spawns.ALL : spawns;
        }
    }

    /**
     * 시작 꾸러미 코드 기본값 (= jar 의 config.yml) — 수련생 방어구 4종 + 하급 치유 물약 10 · 하급 마나 물약 5 · 귀환 주문서 2.
     * 골드는 {@link #DEFAULT_STARTER_GOLD}. (빵은 0.3.5.1 에서 뺌 — 허기가 늘 가득이라 먹을 수 없었다)
     */
    public static final List<KitItem> DEFAULT_STARTER_KIT = List.of(new KitItem("novice_cap", 1),
            new KitItem("novice_tunic", 1), new KitItem("novice_trousers", 1), new KitItem("novice_boots", 1),
            new KitItem("minor_healing_potion", 10), new KitItem("minor_mana_potion", 5), new KitItem("return_scroll", 2));
    /** 예전 판(0.3.2)이 config.yml 에 그대로 적어 둔 목록 — 손대지 않은 것이므로 새 기본값으로 올린다. */
    public static final List<KitItem> LEGACY_STARTER_KIT_032 = List.of(new KitItem("novice_cap", 1),
            new KitItem("novice_tunic", 1), new KitItem("novice_trousers", 1), new KitItem("novice_boots", 1),
            new KitItem("minor_healing_potion", 5));
    /** 0.3.3 ~ 0.3.5 가 config.yml 에 적어 둔 목록 (빵 16 포함) — 손대지 않은 것이므로 새 기본값으로 올린다. */
    public static final List<KitItem> LEGACY_STARTER_KIT_033 = List.of(new KitItem("novice_cap", 1),
            new KitItem("novice_tunic", 1), new KitItem("novice_trousers", 1), new KitItem("novice_boots", 1),
            new KitItem("minor_healing_potion", 10), new KitItem("minor_mana_potion", 5), new KitItem("return_scroll", 2),
            new KitItem("minecraft:bread", 16));
    /** 파티 최대 인원 기본값 (0.3.5.1 부터 5명 — 5 대 5 파티 대전에 맞춤). */
    public static final int DEFAULT_PARTY_MAX = 5;
    /** 0.3.5 까지의 기본값. config.yml 에 그대로 남아 있으면 손대지 않은 것으로 보고 새 기본값으로 읽는다. */
    public static final int LEGACY_PARTY_MAX = 10;

    /** party.max_size 읽기 — 예전 기본값 10 은 새 기본값 5 로, 그 밖에 직접 고친 값은 그대로 (최소 1). */
    static int partyMaxSize(int v) {
        if (v == LEGACY_PARTY_MAX) return DEFAULT_PARTY_MAX;
        return Math.max(1, v);
    }

    /** 시작 골드 기본값 (starter_kit.gold). 하급 물약 15병 · 귀환 주문서 3장 정도. */
    public static final int DEFAULT_STARTER_GOLD = 300;

    public Settings(ConfigurationSection c) {
        if (c == null) c = new MemoryConfiguration();
        Map<String, Difficulty> diffs = new LinkedHashMap<>();
        for (String id : List.of("easy", "normal", "hard", "nightmare")) diffs.put(id, Difficulty.defaultFor(id));
        ConfigurationSection ds = c.getConfigurationSection("difficulties");
        if (ds != null) {
            for (String id : ds.getKeys(false)) {
                ConfigurationSection d = ds.getConfigurationSection(id);
                if (d != null) diffs.put(id, difficulty(id, d, diffs.getOrDefault(id, Difficulty.NORMAL)));
            }
        }
        this.difficulties = Collections.unmodifiableMap(diffs);
        String did = c.getString("difficulty", "");
        did = did == null ? "" : did.trim().toLowerCase(Locale.ROOT);
        this.difficultyId = diffs.containsKey(did) ? did : "";

        this.party = new PartyScaling(partyMaxSize(c.getInt("party.max_size", DEFAULT_PARTY_MAX)),
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
                c.getString("pack.prompt", "<gray>미궁 라비린스 전용 리소스팩입니다.</gray>"),
                c.getBoolean("pack.same_port", true));
        this.autosaveMinutes = Math.max(1, c.getInt("data.autosave_minutes", 5));
        Combat cd = Combat.DEFAULT;
        this.combat = new Combat(c.getBoolean("combat.damage_numbers", true),
                Math.max(4, c.getInt("combat.damage_number_ticks", 16)), c.getDouble("combat.base_crit_chance", 0.05),
                c.getDouble("combat.base_crit_damage", 1.5), c.getBoolean("combat.scale_vanilla_damage", true),
                c.getDouble("combat.attack_interval_min", cd.attackIntervalMin()),
                c.getDouble("combat.early_click_buffer", cd.earlyClickBuffer()),
                c.getBoolean("combat.early_click_sound", cd.earlyClickSound()),
                c.getInt("combat.click_tolerance_ms", cd.clickToleranceMs()),
                c.getDouble("combat.jump_crit", cd.jumpCrit()),
                c.getBoolean("combat.bow_full_draw_cue", cd.bowFullDrawCue()));
        this.level = new Level(Math.max(1, c.getInt("level.max", 50)), Math.max(0, c.getInt("level.start_points", 5)),
                c.getInt("level.points_per_level", 5),
                c.getDouble("level.xp_a", 40), c.getDouble("level.xp_exp", 1.6), c.getDouble("level.xp_b", 60));
        // 0.3.5: 무기마다 items.yml attack.interval — 이 표는 none(맨손)만 읽는다. 예전 종류 키(sword_shield …)는 무시.
        ConfigurationSection ws = c.getConfigurationSection("weapon_attack_speed");
        double none = ws == null ? DEFAULT_UNARMED_SPEED : ws.getDouble("none", DEFAULT_UNARMED_SPEED);
        this.unarmedAttackSpeed = none > 0 ? Math.min(20, none) : DEFAULT_UNARMED_SPEED;
        List<String> ignored = new ArrayList<>();
        if (ws != null) for (String k : ws.getKeys(false)) if (!"none".equals(k)) ignored.add(k);
        this.ignoredWeaponSpeedKeys = List.copyOf(ignored);
        this.starterKit = Boolean.FALSE.equals(c.get("starter_kit")) ? List.of()
                : starterKit(c.getConfigurationSection("starter_kit"));
        this.starterGold = starterKit.isEmpty() ? 0 : Math.max(0, c.getInt("starter_kit.gold", DEFAULT_STARTER_GOLD));
        this.death = new Death(c.getBoolean("death.keep_inventory", Death.DEFAULT.keepInventory()),
                c.getBoolean("death.keep_level", Death.DEFAULT.keepLevel()));
        this.classChange = Boolean.FALSE.equals(c.get("class_change")) ? ClassChange.NONE
                : classChange(c.getConfigurationSection("class_change"));
        // 0.3.5 방어구 겉모습 장단점 (look_spec §7) — 키가 없으면 코드 기본값 (예전 서버 config 도 그대로 켜진다)
        this.armorLooks = Boolean.FALSE.equals(c.get("armor_looks")) ? ArmorLooks.OFF
                : ArmorLooks.read(c.getConfigurationSection("armor_looks"));
        List<String> ww = new ArrayList<>();
        // getConfigurationSection 은 기본값(jar config)에만 있는 섹션을 서버 config 에 빈 'wild: {}' 로 만들어 저장되게 한다 — get 으로 읽음
        Object wv = c.get("wild");
        this.wild = Boolean.FALSE.equals(wv) ? Wild.OFF : wild(wv instanceof ConfigurationSection wsec ? wsec : null, ww);
        this.wildWarnings = List.copyOf(ww);
    }

    /**
     * wild — 섹션이 없으면 코드 기본값({@link Wild#DEFAULT}), 빠진 키도 기본값. 끄기 = {@code wild: false}.
     * spawns 에 모르는 값이 있으면 기본값(all) + warnings 한 줄. spawns: false 는 none 과 같다.
     */
    static Wild wild(ConfigurationSection w, List<String> warnings) {
        Wild d = Wild.DEFAULT;
        if (w == null) return d;
        Wild.Spawns spawns = d.spawns();
        Object raw = w.get("spawns");
        if (Boolean.FALSE.equals(raw)) spawns = Wild.Spawns.NONE;
        else if (Boolean.TRUE.equals(raw)) spawns = Wild.Spawns.ALL;
        else if (raw != null) {
            Wild.Spawns p = Wild.Spawns.parse(String.valueOf(raw));
            if (p != null) spawns = p;
            else if (warnings != null) warnings.add("wild.spawns '" + raw + "' 를 모릅니다 (all · monsters · none) — all 로 읽습니다");
        }
        int margin = w.getInt("border_margin", d.borderMargin());
        if (warnings != null && (margin < 0 || margin > Wild.MAX_MARGIN)) {
            warnings.add("wild.border_margin " + margin + " 은(는) 0 ~ " + Wild.MAX_MARGIN + " 로 자릅니다");
        }
        return new Wild(w.getBoolean("border", d.border()), margin, spawns);
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
     * difficulties.&lt;id&gt; 한 줄 — 난이도마다 배율 한 벌 (층 램프 없음이 기본, 0.3.3).
     * <ul>
     *   <li>빠진 키 = 코드 기본값({@link Difficulty#defaultFor}, 모르는 id 면 보통).</li>
     *   <li>예전 판(0.3.2·0.3.4)이 적어 둔 어려움·악몽 값({@link Difficulty#legacy032}·{@link Difficulty#legacy034})과 같은 키는
     *       '안 고친 값'으로 보고 새 기본값을 쓴다 (시작 꾸러미와 같은 방식). 다른 값은 직접 고친 값이므로 그대로.
     *       0.3.5: 어려움 HP 1.4(0.3.4)·1.5(0.3.2) → 1.45.</li>
     *   <li>ramp: 0.3.2 의 jar 기본 램프({@link Difficulty.Ramp#legacy032}) 그대로거나 비어 있으면 지운다(= 통합).
     *       직접 고친 램프는 계속 따르고, 그 난이도는 숫자를 적힌 그대로 쓴다(램프가 그 숫자에 맞춰졌으므로 예전 값 승격 없음).
     *       {@code ramp: false}·{@code ramp: {enabled: false}} 도 직접 고친 것 — "예전 값을 1층부터" 그대로 쓴다.</li>
     * </ul>
     */
    static Difficulty difficulty(String id, ConfigurationSection d, Difficulty def) {
        return upgradeRewards(id, difficultyRaw(id, d, def), def);
    }

    /** 0.3.5.2: 예전 jar 기본 보상 배율(쉬움 0.8 · 어려움 1.3 · 악몽 1.8/1.7) 그대로면 새 기본값(1.0). 직접 고친 값은 그대로. */
    static Difficulty upgradeRewards(String id, Difficulty x, Difficulty def) {
        double[] old = Difficulty.legacyRewards(id);
        if (old == null) return x;
        double drop = upgrade(x.drop(), def.drop(), old[0]);
        double xp = upgrade(x.xp(), def.xp(), old[1]);
        if (drop == x.drop() && xp == x.xp()) return x;
        return new Difficulty(x.id(), x.name(), x.hp(), x.damage(), drop, xp, x.telegraph(), x.ramp());
    }

    private static Difficulty difficultyRaw(String id, ConfigurationSection d, Difficulty def) {
        Difficulty read = new Difficulty(id, d.getString("name", def.name()), d.getDouble("hp", def.hp()),
                d.getDouble("damage", def.damage()), d.getDouble("drop", def.drop()),
                d.getDouble("xp", def.xp()), d.getDouble("telegraph", def.telegraph()));
        ConfigurationSection rs = d.getConfigurationSection("ramp");
        boolean off = Boolean.FALSE.equals(d.get("ramp")) || (rs != null && !rs.getBoolean("enabled", true));
        Difficulty.Ramp r = off ? null : ramp(rs, read);
        if (off || (r != null && !r.equals(Difficulty.Ramp.legacy032(id)))) return read.withRamp(r); // 직접 고친 램프 (끈 것 포함)
        Difficulty old = Difficulty.legacy032(id);
        Difficulty old034 = Difficulty.legacy034(id);
        if (old == null && old034 == null) return read;
        return new Difficulty(id, read.name(), upgrade(read.hp(), def.hp(), old == null ? null : old.hp(), old034 == null ? null : old034.hp()),
                upgrade(read.damage(), def.damage(), old == null ? null : old.damage(), old034 == null ? null : old034.damage()),
                upgrade(read.drop(), def.drop(), old == null ? null : old.drop(), old034 == null ? null : old034.drop()),
                upgrade(read.xp(), def.xp(), old == null ? null : old.xp(), old034 == null ? null : old034.xp()),
                upgrade(read.telegraph(), def.telegraph(), old == null ? null : old.telegraph(), old034 == null ? null : old034.telegraph()));
    }

    /** 예전 판 기본값(0.3.2·0.3.4) 중 하나와 같으면 새 기본값, 아니면 적힌 값. */
    private static double upgrade(double v, double now, Double... legacy) {
        for (Double l : legacy) if (l != null && Math.abs(v - l) < 1e-9) return now;
        return v;
    }

    /**
     * difficulties.&lt;id&gt;.ramp — 키가 없거나 비어 있으면 램프 없음(null). 끄기 = {@code ramp: {enabled: false}}
     * (또는 {@code ramp: false}). from_floor(기본 1)·full_floor(from 이하면 램프 없음)·start.hp/damage/telegraph 중 빠진 값은
     * 0.3.2 때처럼 그 판의 기본 램프 값({@link Difficulty.Ramp#legacy032}, 원래 값보다 세지 않게 자름), 그것도 없는 난이도면
     * 그 난이도 원래 값(= 그 항목은 램프 안 함).
     */
    static Difficulty.Ramp ramp(ConfigurationSection r, Difficulty d) {
        if (r == null || r.getKeys(false).isEmpty()) return null;
        if (!r.getBoolean("enabled", true)) return null;
        Difficulty.Ramp def = Difficulty.Ramp.legacy032(d.id());
        if (def != null) { // hp·damage 를 낮춰 쓰는 서버: 빠진 시작 값이 원래 값보다 세지 않게
            def = new Difficulty.Ramp(def.fromFloor(), def.fullFloor(), Math.min(def.startHp(), d.hp()),
                    Math.min(def.startDamage(), d.damage()), Math.max(def.startTelegraph(), d.telegraph()));
        }
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
        return out.isEmpty() || out.equals(LEGACY_STARTER_KIT_032) || out.equals(LEGACY_STARTER_KIT_033)
                ? DEFAULT_STARTER_KIT : List.copyOf(out);
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

    /** 방어구 겉모습 장단점 (판금·가죽·천 숨은 효과 · 4부위 효과). */
    public ArmorLooks armorLooks() { return armorLooks; }

    /** 야생 막기 (월드 경계 · 마을 월드 스폰). 마을이 있는 주 월드에만 쓰인다. 네더·엔드는 막지 않는다. */
    public Wild wild() { return wild; }

    /** config wild 를 읽다 생긴 경고 (켤 때·reload 때 서버 창에 한 줄씩). */
    public List<String> wildWarnings() { return wildWarnings; }

    /** 맨손 초당 공격 횟수 (config weapon_attack_speed.none). 무기는 저마다 items.yml attack.interval. */
    public double unarmedAttackSpeed() { return unarmedAttackSpeed; }

    /** config weapon_attack_speed 에 남은 예전 종류 키 (0.3.5 부터 읽지 않음 — 켤 때 정보 로그 한 줄). */
    public List<String> ignoredWeaponSpeedKeys() { return ignoredWeaponSpeedKeys; }
}
