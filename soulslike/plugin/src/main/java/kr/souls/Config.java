package kr.souls;

import kr.souls.progression.LevelCost;
import kr.souls.progression.LoadTiers;
import kr.souls.progression.StatCurves;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * config.yml 을 한 번 읽어 굳힌 값. 틱마다 YAML 을 다시 읽지 않게 한다. /souls reload 때 새로 만든다.
 * 값이 없거나 틀리면 설계 문서의 기본값을 쓴다.
 */
public final class Config {
    /** 구르기 한 종류 (3.3 표). 틱은 구르기 시작 틱 0 기준. horizontal 은 glide 틱 동안 매 틱 미는 속도 (블록/틱). */
    public record RollKind(String id, int iframes, double horizontal, double vertical, int glide, int next, int end, double cost) {}

    public record StaminaCfg(int endurance, TreeMap<Integer, Double> curve, double regenPerTick, int regenDelay,
                             int exhaustedDelay, double exhaustedSprintUntil, double guardRegenScale, double sprintPerTick) {}

    /** 구르기가 3인칭과 남에게 어떻게 보이는가 (3.3 "보이는 모습"). */
    public enum RollVisual {
        /** 진짜 몸을 감추고 웅크린 대역이 앞으로 한 바퀴 돈다 (combat/Tumble) */
        TUMBLE,
        /** 바닐라 급류 회전 (흰 소용돌이는 팩이 감춘다) */
        SPIN,
        /** 머리 위 방벽으로 기어가기 자세 (몸이 눕고 미끄러진다) */
        CRAWL;

        public static RollVisual parse(String s, RollVisual def) {
            if (s == null) return def;
            try {
                return valueOf(s.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return def;
            }
        }
    }

    /**
     * 대역 (combat/Tumble). 움직임 (열쇠 자세) 은 팩 생성기가 쓰는 자원 roll_anim.yml 에 있고, 여기는 때만 정한다.
     * riseAt·riseTurn: riseAt 틱 뒤에 닿는 자세부터 riseTurn 틱에 걸쳐 구르는 쪽에서 몸 방향으로 돈다,
     * reveal: 이 틱에 대역을 거두고 진짜 몸을 보인다, handBack: 이 틱에 그 사람 화면에만 주손을 돌려준다 (0 이면 reveal 과 같이),
     * hideDelay: 대역을 띄우고 몇 틱 뒤에 진짜 몸을 감추고 대역을 보이게 하는가 (0: 다음 틱. 1: 클라이언트가 대역을 한 틱 다룬 뒤),
     * duck: combat.roll.crawl 일 때 기어가기 막힘을 두는 틱 수 (1인칭 시야가 바닥으로 내려갔다 대역의 머리와 함께 올라온다. 0 이면 깔지 않는다),
     * duckCamera: 숙인 눈 (발 위 0.4) 에서 F5 등 뒤 카메라가 이 거리 (블록) 안에서 막히면 숙이지 않는다 (올려다볼 때, 등 뒤에 턱·벽이
     * 있을 때: 카메라가 대역 곁으로 당겨지면 1인칭으로 여겨 감춘다). 0 이면 보지 않는다.
     */
    public record TumbleCfg(int riseAt, int riseTurn, int reveal, int handBack, int hideDelay, int duck, double duckCamera) {}

    public record RollCfg(String load, RollVisual visual, boolean crawl, TumbleCfg tumble, int spinTicks,
                          Map<String, RollKind> kinds, String sound, float volume, float pitch) {
        public RollKind kind(String id) {
            RollKind k = kinds.get(id);
            return k != null ? k : kinds.get("light");
        }

        /**
         * 이 구르기에 기어가기 막힘을 까는가 (뒷걸음은 늘 아니다). tumble 과 crawl 모습: 그 사람 화면에만 머리 위 막힘을 깔아
         * 클라이언트가 기어가기 자세 (눈 0.4) 로 구른다 (1인칭 시야가 바닥까지 내려갔다 올라온다). 막힘은 3인칭 카메라가 지나가는
         * 블록이라 (Roll.CEILING) 예전 방벽처럼 카메라를 머리 속으로 당기지 않는다. spin 은 급류 회전 자세가 따로 있다.
         */
        public boolean barrier() {
            return crawl && (visual == RollVisual.CRAWL || visual == RollVisual.TUMBLE);
        }
    }

    public record WorldCfg(String name, long seed, int roomX, int roomY, int roomZ, long time,
                           double borderX, double borderZ, double borderSize, boolean forceAdventure) {}

    /**
     * HUD (10.2). 막대 셋 (체력·마나·스태미나) 의 길이는 최대치 × px 배율 (GUI 픽셀, minPx..maxPx). warmthPlaceholder 는 술이 없을
     * 때 (M5 전) 마나 막대를 이 최대치로 가득 찬 채 보인다 (0 이면 숨긴다). barRefresh: 막대가 바뀌지 않아도 이 틱마다 다시 보낸다.
     */
    public record HudCfg(boolean showSouls, int actionbarRefresh, double healthPx, double warmthPx, double staminaPx,
                         int minPx, int maxPx, double warmthPlaceholder, int barRefresh) {}

    /**
     * 사망 화면 YOU DIED (5.6). title: 플러그인 화면 제목 판. screenFade: 서서히 나타나는 판 (사망 화면 문구 줄). 팩은 이 둘을
     * 읽어 만들고 (gen_pack), 플러그인은 jar 안 팩의 사망 화면 제목이 비었는지를 따른다 (DeathFlow: 둘이 어긋나도 겹치지 않게).
     */
    public record DeathCfg(boolean title, boolean screenFade, String titleGlyphs, String fallbackColor, int fadeIn, int stay,
                           int fadeOut) {}

    public record PackCfg(boolean enabled, String url, boolean required, String sendAt, int joinDelay,
                          int configureTimeout, boolean selfCheck, int servePort) {}

    /**
     * 조작 (2.1, 2.3 의 11, 3.3). rollKey: sneak (웅크리기 키를 짧게 눌렀다 떼면 구른다, 기본) | f (예전 판: F 가 구르기) | both.
     * 짧은 누름: 누름에서 뗌까지 tapMaxTicks 틱 안 (핑이 lagPing ms 를 넘으면 lagExtraTicks 를 더한다). 회복 중에 뗀 짧은 누름은
     * buffer 틱 동안 기억했다가 되는 첫 틱에 구른다.
     */
    public record ControlsCfg(String rollKey, int tapMaxTicks, int lagPing, int lagExtraTicks, int buffer) {
        public boolean sneakRolls() {
            return !"f".equals(rollKey);
        }

        public boolean fRolls() {
            return "f".equals(rollKey) || "both".equals(rollKey);
        }
    }

    /**
     * 시작 흐름 (5.7, 5.10). setupBy: first (세계를 처음 연 사람) | op. reopenCooldown: 창을 닫은 사람에게 다시 띄우는 가장 짧은 틈.
     * auto / autoOrigin 은 시험 모드에서만 듣는다 (봇 묶음이 창에 막히지 않게). unbornRadius: 출신을 고르기 전에 시작 자리에서 이만큼만
     * 걸을 수 있다 (0 이면 막지 않는다). packWait: 팩을 다 싣고 창을 띄우기까지 틱, noPackWait: 팩을 싣지 않은 사람 (선택 팩을 거절,
     * 팩이 꺼짐) 은 접속 뒤 이만큼. hintEvery: 출신 창을 닫은 사람이 걷는 동안 "고르려면 · 웅크리기 짧게" 를 다시 알리는 틈 (0 이면 닫을
     * 때만).
     */
    public record StartCfg(String setupBy, int reopenCooldown, String auto, String autoOrigin, List<String> autoNames, int unbornRadius,
                           int packWait, int noPackWait, int hintEvery) {
        /** 시험 모드의 auto-origin 을 받는 이름인가 (auto-names 의 앞머리 가운데 하나로 시작한다). */
        public boolean autoName(String name) {
            for (String n : autoNames) if (!n.isEmpty() && name.startsWith(n)) return true;
            return false;
        }
    }

    /** 난이도 하나 (5.7 의 표, difficulty.levels.&lt;id&gt;.*). 바닐라 난이도는 늘 normal 이다 (3.9). */
    public record Difficulty(String id, double enemyDamage, double enemyHealth, double enemyPoise, int parryWindowBonus, int estusStart,
                             double souls, int attackTokens) {}

    /**
     * PvP (5.7). def: 세계 설정이 없을 때의 값. damageScale: 플레이어 → 플레이어 피해 배율. respawnGrace: 접속·부활·명령 순간이동 뒤 남에게
     * 맞지 않는 틱. keepSouls: PvP 로 죽으면 소울을 잃지 않고 적도 되살아나지 않는다 (혈흔이 생기는 M2 부터 뜻이 있다).
     */
    public record PvpCfg(boolean def, double damageScale, int respawnGrace, boolean keepSouls) {}

    /**
     * 적과의 싸움 (M1 의 동작 실행기 전의 다리, 3.7). bridgeScale: souls 근접 무기로 플레이어가 아닌 것을 치면 바닐라 피해를
     * 공격력 × (0.2 + 0.8 × 회복²) × bridgeScale 로 바꾼다 (직검 71 → 약 6.4, 바닐라 철검쯤). swingTicks: 분류마다 약공격 한 주기 (틱).
     * 든 무기의 바닐라 공격 속도 = 20 / 주기 (AttributeApplier.weaponSpeed), 민첩이 그것을 곱한다.
     */
    public record PveCfg(double bridgeScale, Map<String, Integer> swingTicks) {
        /** 분류의 약공격 한 주기 (틱, 3.6 의 준비 + 판정 + 회복). 모르는 분류면 null (공격 속도를 걸지 않는다). */
        public Integer swingTicks(String cls) {
            return cls == null ? null : swingTicks.get(cls);
        }
    }

    /** 레벨 올리기 창의 "올린다" 소리 (5.9). */
    public record LevelUpCfg(String sound, float volume, float pitch) {}

    public final ControlsCfg controls;
    public final StartCfg start;
    /** 정하기 전·창을 닫았을 때의 난이도 */
    public final String difficultyDefault;
    /** 난이도 넷 (차례 그대로: easy, normal, hard, very_hard) */
    public final Map<String, Difficulty> difficulties;
    public final PvpCfg pvp;
    public final PveCfg pve;
    public final StatCurves stats;
    public final LevelCost levelCost;
    public final LoadTiers load;
    public final LevelUpCfg levelup;
    public final StaminaCfg stamina;
    public final RollCfg roll;
    public final WorldCfg world;
    public final HudCfg hud;
    public final DeathCfg death;
    public final PackCfg pack;
    public final boolean testMode, logTestLines;

    public Config(FileConfiguration c) {
        TreeMap<Integer, Double> curve = new TreeMap<>();
        ConfigurationSection cs = c.getConfigurationSection("combat.stamina.curve");
        if (cs != null) {
            for (String k : cs.getKeys(false)) {
                try {
                    curve.put(Integer.parseInt(k.trim()), cs.getDouble(k));
                } catch (NumberFormatException ignored) {
                    // 숫자가 아닌 열쇠는 건너뛴다
                }
            }
        }
        if (curve.isEmpty()) {
            curve.put(1, 82.0); curve.put(10, 100.0); curve.put(20, 130.0); curve.put(30, 150.0);
            curve.put(40, 165.0); curve.put(60, 180.0); curve.put(99, 200.0);
        }
        stamina = new StaminaCfg(
                c.getInt("combat.stamina.endurance", 10), curve,
                c.getDouble("combat.stamina.regen-per-tick", 2.2),
                c.getInt("combat.stamina.regen-delay", 12),
                c.getInt("combat.stamina.exhausted-delay", 24),
                c.getDouble("combat.stamina.exhausted-sprint-until", 25),
                c.getDouble("combat.stamina.guard-regen-scale", 0.35),
                c.getDouble("combat.stamina.sprint-per-tick", 0.6));

        Map<String, RollKind> kinds = new LinkedHashMap<>();
        kinds.put("light", new RollKind("light", 8, 0.42, 0.0, 7, 10, 12, 18));
        kinds.put("medium", new RollKind("medium", 7, 0.38, 0.0, 7, 12, 14, 20));
        kinds.put("heavy", new RollKind("heavy", 5, 0.30, 0.0, 7, 16, 18, 24));
        kinds.put("backstep", new RollKind("backstep", 4, 0.40, 0.08, 4, 8, 10, 12));
        ConfigurationSection ks = c.getConfigurationSection("combat.roll.kinds");
        if (ks != null) {
            for (String id : ks.getKeys(false)) {
                ConfigurationSection k = ks.getConfigurationSection(id);
                if (k == null) continue;
                RollKind d = kinds.getOrDefault(id, kinds.get("light"));
                kinds.put(id, new RollKind(id, k.getInt("iframes", d.iframes()), k.getDouble("horizontal", d.horizontal()),
                        k.getDouble("vertical", d.vertical()), k.getInt("glide", d.glide()), k.getInt("next", d.next()), k.getInt("end", d.end()),
                        k.getDouble("cost", d.cost())));
            }
        }
        roll = new RollCfg(c.getString("combat.roll.load", "auto").toLowerCase(Locale.ROOT),
                RollVisual.parse(c.getString("combat.roll.visual"), RollVisual.TUMBLE), c.getBoolean("combat.roll.crawl", true),
                tumble(c), Math.max(1, c.getInt("combat.roll.spin-ticks", 8)),
                Collections.unmodifiableMap(kinds),
                c.getString("combat.roll.sound", "item.armor.equip_leather"),
                (float) c.getDouble("combat.roll.sound-volume", 0.6), (float) c.getDouble("combat.roll.sound-pitch", 0.7));

        world = new WorldCfg(c.getString("world.name", "souls_world"), c.getLong("world.seed", 7707),
                c.getInt("world.test-room.x", 200), c.getInt("world.test-room.y", 100), c.getInt("world.test-room.z", -200),
                c.getLong("world.time", 13000), c.getDouble("world.border.x", 0), c.getDouble("world.border.z", 20),
                c.getDouble("world.border.size", 640), c.getBoolean("world.force-adventure", true));

        int minPx = Math.max(4, c.getInt("hud.bars.min-px", 24));
        hud = new HudCfg(c.getBoolean("hud.show-souls", true), Math.max(1, c.getInt("hud.actionbar-refresh", 20)),
                c.getDouble("hud.bars.health-px", 0.17), c.getDouble("hud.bars.warmth-px", 0.8), c.getDouble("hud.bars.stamina-px", 0.65),
                minPx, Math.max(minPx, Math.min(255, c.getInt("hud.bars.max-px", 190))),
                c.getDouble("hud.bars.warmth-placeholder", 60), Math.max(1, c.getInt("hud.bars.refresh", 100)));

        death = new DeathCfg(c.getBoolean("death.title", false), c.getBoolean("death.screen-fade", true),
                c.getString("death.title-glyphs", "you_died_title"),
                c.getString("death.fallback-color", "#cc2418"), c.getInt("death.fade-in", 20),
                c.getInt("death.stay", 6000), c.getInt("death.fade-out", 10));

        pack = new PackCfg(c.getBoolean("pack.enabled", true), c.getString("pack.url", ""),
                c.getBoolean("pack.required", true), c.getString("pack.send-at", "join").toLowerCase(Locale.ROOT),
                Math.max(0, c.getInt("pack.join-delay", 20)), Math.max(1, c.getInt("pack.configure-timeout", 10)),
                c.getBoolean("pack.self-check", true), c.getInt("pack.serve-port", 0));

        testMode = c.getBoolean("debug.test-mode", false);
        logTestLines = c.getBoolean("debug.log-test-lines", true);

        String rk = c.getString("controls.roll-key", "sneak").toLowerCase(Locale.ROOT).trim();
        if (!List.of("sneak", "f", "both").contains(rk)) rk = "sneak";
        controls = new ControlsCfg(rk, Math.max(1, c.getInt("controls.roll-tap.max-ticks", 5)), Math.max(0, c.getInt("controls.roll-tap.lag-ping", 100)),
                Math.max(0, c.getInt("controls.roll-tap.lag-extra-ticks", 1)), Math.max(0, c.getInt("controls.roll-tap.buffer", 6)));
        String by = c.getString("start.setup-by", "first").toLowerCase(Locale.ROOT).trim();
        start = new StartCfg("op".equals(by) ? "op" : "first", Math.max(1, c.getInt("start.reopen-cooldown", 40)),
                c.getString("start.auto", "").trim(), c.getString("start.auto-origin", "").trim().toLowerCase(Locale.ROOT),
                java.util.Arrays.stream(c.getString("start.auto-names", "Souls").split(",")).map(String::trim).filter(x -> !x.isEmpty()).toList(),
                Math.max(0, c.getInt("start.unborn-radius", 8)), Math.max(0, c.getInt("start.pack-wait", 20)),
                Math.max(0, c.getInt("start.no-pack-wait", 200)), Math.max(0, c.getInt("start.hint-every", 1200)));
        difficulties = difficulties(c);
        String dd = c.getString("difficulty.default", "normal").toLowerCase(Locale.ROOT).trim();
        difficultyDefault = difficulties.containsKey(dd) ? dd : difficulties.keySet().iterator().next();
        pvp = new PvpCfg(c.getBoolean("pvp.default", false), c.getDouble("pvp.damage-scale", 1.0), Math.max(0, c.getInt("pvp.respawn-grace", 100)),
                c.getBoolean("pvp.death.keep-souls", true));
        Map<String, Integer> swing = new LinkedHashMap<>();
        swing.put("dagger", 10); swing.put("straight_sword", 13); swing.put("curved_sword", 12); swing.put("greatsword", 22);
        swing.put("ultra_greatsword", 30); swing.put("axe", 18); swing.put("hammer", 18); swing.put("spear", 13); swing.put("halberd", 20);
        ConfigurationSection sw = c.getConfigurationSection("pve.swing-ticks");
        if (sw != null) {
            for (String k : sw.getKeys(false)) {
                int v = sw.getInt(k, 0);
                if (v > 0) swing.put(k, Math.max(2, v));
                else swing.remove(k);
            }
        }
        pve = new PveCfg(Math.max(0, c.getDouble("pve.bridge-scale", 0.09)), Collections.unmodifiableMap(swing));
        stats = statCurves(c, curve);
        List<?> cubic = c.getList("level.cost.cubic");
        double[] cu = {0.02, 3.06, 105.6, -895};
        if (cubic != null && cubic.size() == 4) {
            for (int i = 0; i < 4; i++) if (cubic.get(i) instanceof Number n) cu[i] = n.doubleValue();
        }
        levelCost = new LevelCost(c.getInt("level.cost.flat-until", 11), c.getDouble("level.cost.flat-base", 300),
                c.getDouble("level.cost.flat-per-level", 20), cu, c.getDouble("level.cost.scale", 0.6));
        load = loadTiers(c);
        levelup = new LevelUpCfg(c.getString("levelup.sound", "block.beacon.power_select"), (float) c.getDouble("levelup.sound-volume", 0.5),
                (float) c.getDouble("levelup.sound-pitch", 0.6));
    }

    /** 이 난이도 (모르는 id 면 기본 난이도). */
    public Difficulty difficulty(String id) {
        Difficulty d = id == null ? null : difficulties.get(id);
        return d != null ? d : difficulties.get(difficultyDefault);
    }

    /**
     * difficulty.levels.* (5.7). 없으면 문서의 넷. 옛 열쇠 difficulty.enemy-damage·parry-window-bonus·estus-start 는 levels 가 없을 때
     * 보통 난이도의 값으로 읽는다 (예전 설정 파일과 맞춘다).
     */
    private static Map<String, Difficulty> difficulties(FileConfiguration c) {
        Map<String, Difficulty> out = new LinkedHashMap<>();
        out.put("easy", new Difficulty("easy", 0.70, 0.80, 0.80, 2, 5, 1.0, 1));
        out.put("normal", new Difficulty("normal", c.getDouble("difficulty.enemy-damage", 1.0), 1.0, 1.0,
                c.getInt("difficulty.parry-window-bonus", 0), c.getInt("difficulty.estus-start", 4), 1.0, 2));
        out.put("hard", new Difficulty("hard", 1.25, 1.20, 1.15, 0, 4, 1.0, 2));
        out.put("very_hard", new Difficulty("very_hard", 1.50, 1.40, 1.30, -1, 3, 1.0, 2));
        ConfigurationSection ls = c.getConfigurationSection("difficulty.levels");
        if (ls == null) return Collections.unmodifiableMap(out);
        Map<String, Difficulty> read = new LinkedHashMap<>();
        for (String id : ls.getKeys(false)) {
            ConfigurationSection s = ls.getConfigurationSection(id);
            if (s == null) continue;
            String k = id.toLowerCase(Locale.ROOT);
            Difficulty d = out.getOrDefault(k, out.get("normal"));
            read.put(k, new Difficulty(k, s.getDouble("enemy-damage", d.enemyDamage()), s.getDouble("enemy-health", d.enemyHealth()),
                    s.getDouble("enemy-poise", d.enemyPoise()), s.getInt("parry-window-bonus", d.parryWindowBonus()),
                    s.getInt("estus-start", d.estusStart()), s.getDouble("souls", d.souls()), s.getInt("attack-tokens", d.attackTokens())));
        }
        return Collections.unmodifiableMap(read.isEmpty() ? out : read);
    }

    /** stats.* (5.2). 최대 스태미나는 combat.stamina.curve 하나만 쓴다 (기력). */
    private static StatCurves statCurves(FileConfiguration c, TreeMap<Integer, Double> stamina) {
        StatCurves d = StatCurves.defaults();
        Map<Integer, Integer> slots = new TreeMap<>();
        ConfigurationSection ms = c.getConfigurationSection("stats.mind.memory-slots");
        if (ms != null) {
            for (String k : ms.getKeys(false)) {
                try {
                    slots.put(Integer.parseInt(k.trim()), ms.getInt(k));
                } catch (NumberFormatException ignored) {
                    // 숫자가 아닌 열쇠는 건너뛴다
                }
            }
        }
        return new StatCurves(c.getInt("stats.max", d.max), grades(c, "stats.grades", d.grades), grades(c, "stats.speed-grades", d.speedGrades),
                curve(c, "stats.scaling-curve", d.scaling), c.getDouble("stats.defense-base", d.defenseBase),
                c.getDouble("stats.defense-per-level", d.defensePerLevel), c.getDouble("stats.unfit-penalty", d.unfitPenalty),
                c.getDouble("stats.unfit-speed", d.unfitSpeed),
                curve(c, "stats.vigor.max-health", d.maxHealth), curve(c, "stats.vigor.defense", d.vigorDefense),
                curve(c, "stats.mind.max-mana", d.maxMana), curve(c, "stats.mind.magic-defense", d.magicDefense),
                slots.isEmpty() ? d.memorySlots : new StatCurves.Steps(slots), new StatCurves.Curve(stamina),
                curve(c, "stats.endurance.regen-scale", d.regenScale), curve(c, "stats.strength.equip-load", d.equipLoad),
                curve(c, "stats.dexterity.move-speed", d.moveSpeed), curve(c, "stats.dexterity.attack-speed", d.attackSpeed),
                curve(c, "stats.intelligence.status-resist", d.statusResist));
    }

    private static StatCurves.Curve curve(FileConfiguration c, String path, StatCurves.Curve def) {
        ConfigurationSection s = c.getConfigurationSection(path);
        if (s == null) return def;
        Map<Integer, Double> m = new TreeMap<>();
        for (String k : s.getKeys(false)) {
            try {
                m.put(Integer.parseInt(k.trim()), s.getDouble(k));
            } catch (NumberFormatException ignored) {
                // 숫자가 아닌 열쇠는 건너뛴다
            }
        }
        return m.isEmpty() ? def : new StatCurves.Curve(m);
    }

    private static Map<String, Double> grades(FileConfiguration c, String path, Map<String, Double> def) {
        ConfigurationSection s = c.getConfigurationSection(path);
        if (s == null) return def;
        Map<String, Double> m = new LinkedHashMap<>();
        for (String k : s.getKeys(false)) m.put(k.toUpperCase(Locale.ROOT), s.getDouble(k));
        return m.isEmpty() ? def : m;
    }

    /** load.* (5.8). 경계는 load.tiers, 단계 값은 load.&lt;단계&gt;.{roll, regen, walk, sprint}. */
    private static LoadTiers loadTiers(FileConfiguration c) {
        LoadTiers d = LoadTiers.defaults();
        List<LoadTiers.Tier> out = new ArrayList<>();
        for (LoadTiers.Tier t : d.all()) {
            double upTo = "over".equals(t.id()) ? t.upTo() : c.getDouble("load.tiers." + t.id(), t.upTo());
            String p = "load." + t.id() + ".";
            out.add(new LoadTiers.Tier(t.id(), upTo, t.inclusive(), c.getString(p + "roll", t.roll()).toLowerCase(Locale.ROOT),
                    c.getDouble(p + "regen", t.regen()), c.getDouble(p + "walk", t.walk()), c.getBoolean(p + "sprint", t.sprint())));
        }
        return new LoadTiers(out);
    }

    /** combat.roll.tumble (때만. 자세는 자원 roll_anim.yml). */
    private static TumbleCfg tumble(FileConfiguration c) {
        int reveal = Math.max(1, c.getInt("combat.roll.tumble.reveal", 11));
        return new TumbleCfg(c.getInt("combat.roll.tumble.rise-at", 8), Math.max(0, c.getInt("combat.roll.tumble.rise-turn", 3)), reveal,
                Math.min(reveal, Math.max(0, c.getInt("combat.roll.tumble.hand-back", 6))),
                Math.max(0, Math.min(2, c.getInt("combat.roll.tumble.hide-delay", 1))),
                Math.max(0, Math.min(reveal, c.getInt("combat.roll.tumble.duck", 5))),
                Math.max(0.0, Math.min(4.0, c.getDouble("combat.roll.tumble.duck-camera", 3.0))));
    }
}
