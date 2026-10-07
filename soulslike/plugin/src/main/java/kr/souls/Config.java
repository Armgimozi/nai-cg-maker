package kr.souls;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
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

    /** 대역이 도는 한 마디: 구르기 tick 틱째에 앞으로 angle 도 (구르기 시작 자세에서 잰 각) 까지 duration 틱 동안 돈다. */
    public record TumbleStep(int tick, float angle, int duration) {}

    /**
     * 대역 (combat/Tumble). pivot: 회전 중심의 발 위 높이 (블록), scale: 대역 크기, steps: 도는 마디 (틱 차례),
     * reveal: 이 틱에 대역을 거두고 진짜 몸을 보인다, crawlCamera: 방벽도 깐다 (1인칭 시야를 바닥으로).
     */
    public record TumbleCfg(double pivot, float scale, List<TumbleStep> steps, int reveal, boolean crawlCamera) {}

    public record RollCfg(String load, RollVisual visual, boolean crawl, TumbleCfg tumble, int spinTicks,
                          Map<String, RollKind> kinds, String sound, float volume, float pitch) {
        public RollKind kind(String id) {
            RollKind k = kinds.get(id);
            return k != null ? k : kinds.get("light");
        }

        /** 이 구르기에 방벽을 까는가 (뒷걸음은 늘 아니다). */
        public boolean barrier() {
            return crawl && (visual == RollVisual.CRAWL || (visual == RollVisual.TUMBLE && tumble.crawlCamera()));
        }
    }

    public record WorldCfg(String name, long seed, int roomX, int roomY, int roomZ, long time,
                           double borderX, double borderZ, double borderSize, boolean forceAdventure) {}

    public record HudCfg(boolean showSouls, int actionbarRefresh) {}

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

        hud = new HudCfg(c.getBoolean("hud.show-souls", true), Math.max(1, c.getInt("hud.actionbar-refresh", 20)));

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

    /** combat.roll.tumble. steps 는 [[틱, 각, 걸리는 틱], ...]. 틀린 줄은 건너뛰고, 하나도 없으면 3.3 의 기본 네 마디. */
    private static TumbleCfg tumble(FileConfiguration c) {
        List<TumbleStep> steps = new ArrayList<>();
        for (Object o : c.getList("combat.roll.tumble.steps", List.of())) {
            if (!(o instanceof List<?> l) || l.size() < 3) continue;
            try {
                int tick = Integer.parseInt(String.valueOf(l.get(0)).trim());
                float angle = Float.parseFloat(String.valueOf(l.get(1)).trim());
                int dur = Integer.parseInt(String.valueOf(l.get(2)).trim());
                if (tick >= 0 && dur >= 0) steps.add(new TumbleStep(tick, angle, dur));
            } catch (NumberFormatException ignored) {
                // 숫자가 아닌 줄은 건너뛴다
            }
        }
        if (steps.isEmpty()) {
            steps.add(new TumbleStep(1, 90, 2));
            steps.add(new TumbleStep(3, 180, 2));
            steps.add(new TumbleStep(5, 270, 2));
            steps.add(new TumbleStep(7, 360, 2));
        }
        steps.sort(Comparator.comparingInt(TumbleStep::tick));
        return new TumbleCfg(c.getDouble("combat.roll.tumble.pivot", 0.5), (float) c.getDouble("combat.roll.tumble.scale", 1.0),
                List.copyOf(steps), Math.max(1, c.getInt("combat.roll.tumble.reveal", 10)),
                c.getBoolean("combat.roll.tumble.crawl-camera", false));
    }
}
