package kr.souls;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

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
     * hideDelay: 대역을 띄우고 몇 틱 뒤에 진짜 몸을 감추는가 (0: 같은 틱. 1: 클라이언트가 대역을 처음 그린 뒤),
     * duck: combat.roll.crawl 일 때 기어가기 막힘을 두는 틱 수 (1인칭 시야가 바닥으로 내려갔다 대역의 머리와 함께 올라온다. 0 이면 깔지 않는다).
     */
    public record TumbleCfg(int riseAt, int riseTurn, int reveal, int handBack, int hideDelay, int duck) {}

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
     * HUD (10.2). 막대 셋 (체력·온기·스태미나) 의 길이는 최대치 × px 배율 (GUI 픽셀, minPx..maxPx). warmthPlaceholder 는 술이 없을
     * 때 (M5 전) 온기 막대를 이 최대치로 가득 찬 채 보인다 (0 이면 숨긴다). barRefresh: 막대가 바뀌지 않아도 이 틱마다 다시 보낸다.
     */
    public record HudCfg(boolean showSouls, int actionbarRefresh, double healthPx, double warmthPx, double staminaPx,
                         int minPx, int maxPx, double warmthPlaceholder, int barRefresh) {}

    public record DeathCfg(boolean title, String titleGlyphs, String fallbackColor, int fadeIn, int stay, int fadeOut) {}

    public record PackCfg(boolean enabled, String url, boolean required, String sendAt, int joinDelay,
                          int configureTimeout, boolean selfCheck, int servePort) {}

    public final StaminaCfg stamina;
    public final RollCfg roll;
    public final WorldCfg world;
    public final HudCfg hud;
    public final DeathCfg death;
    public final PackCfg pack;
    public final boolean testMode, logTestLines;
    public final double enemyDamage;
    public final int parryWindowBonus, estusStart;

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
            curve.put(10, 100.0); curve.put(20, 130.0); curve.put(30, 150.0);
            curve.put(40, 165.0); curve.put(50, 175.0); curve.put(99, 200.0);
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
        roll = new RollCfg(c.getString("combat.roll.load", "light").toLowerCase(Locale.ROOT),
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
                c.getDouble("hud.bars.health-px", 5.0), c.getDouble("hud.bars.warmth-px", 1.0), c.getDouble("hud.bars.stamina-px", 0.9),
                minPx, Math.max(minPx, Math.min(255, c.getInt("hud.bars.max-px", 190))),
                c.getDouble("hud.bars.warmth-placeholder", 60), Math.max(1, c.getInt("hud.bars.refresh", 100)));

        death = new DeathCfg(c.getBoolean("death.title", false), c.getString("death.title-glyphs", "you_died_title"),
                c.getString("death.fallback-color", "#cc2418"), c.getInt("death.fade-in", 20),
                c.getInt("death.stay", 6000), c.getInt("death.fade-out", 10));

        pack = new PackCfg(c.getBoolean("pack.enabled", true), c.getString("pack.url", ""),
                c.getBoolean("pack.required", true), c.getString("pack.send-at", "join").toLowerCase(Locale.ROOT),
                Math.max(0, c.getInt("pack.join-delay", 20)), Math.max(1, c.getInt("pack.configure-timeout", 10)),
                c.getBoolean("pack.self-check", true), c.getInt("pack.serve-port", 0));

        testMode = c.getBoolean("debug.test-mode", false);
        logTestLines = c.getBoolean("debug.log-test-lines", true);
        enemyDamage = c.getDouble("difficulty.enemy-damage", 1.0);
        parryWindowBonus = c.getInt("difficulty.parry-window-bonus", 0);
        estusStart = c.getInt("difficulty.estus-start", 4);
    }

    /** combat.roll.tumble (때만. 자세는 자원 roll_anim.yml). */
    private static TumbleCfg tumble(FileConfiguration c) {
        int reveal = Math.max(1, c.getInt("combat.roll.tumble.reveal", 11));
        return new TumbleCfg(c.getInt("combat.roll.tumble.rise-at", 8), Math.max(0, c.getInt("combat.roll.tumble.rise-turn", 3)), reveal,
                Math.min(reveal, Math.max(0, c.getInt("combat.roll.tumble.hand-back", 8))),
                Math.max(0, Math.min(2, c.getInt("combat.roll.tumble.hide-delay", 0))),
                Math.max(0, Math.min(reveal, c.getInt("combat.roll.tumble.duck", 5))));
    }
}
