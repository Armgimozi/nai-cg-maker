package kr.souls;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.Collections;
import java.util.LinkedHashMap;
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

    public record RollCfg(String load, boolean spinVisual, boolean crawl, Map<String, RollKind> kinds, String sound, float volume, float pitch) {
        public RollKind kind(String id) {
            RollKind k = kinds.get(id);
            return k != null ? k : kinds.get("light");
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
                c.getBoolean("combat.roll.spin-visual", false), c.getBoolean("combat.roll.crawl", true),
                Collections.unmodifiableMap(kinds),
                c.getString("combat.roll.sound", "item.armor.equip_leather"),
                (float) c.getDouble("combat.roll.sound-volume", 0.6), (float) c.getDouble("combat.roll.sound-pitch", 0.7));

        world = new WorldCfg(c.getString("world.name", "souls_world"), c.getLong("world.seed", 7707),
                c.getInt("world.test-room.x", 200), c.getInt("world.test-room.y", 100), c.getInt("world.test-room.z", -200),
                c.getLong("world.time", 13000), c.getDouble("world.border.x", 0), c.getDouble("world.border.z", 20),
                c.getDouble("world.border.size", 640), c.getBoolean("world.force-adventure", true));

        hud = new HudCfg(c.getBoolean("hud.show-souls", true), Math.max(1, c.getInt("hud.actionbar-refresh", 20)));

        death = new DeathCfg(c.getBoolean("death.title", true), c.getString("death.title-glyphs", "you_died"),
                c.getString("death.fallback-color", "#b81a12"), c.getInt("death.fade-in", 20),
                c.getInt("death.stay", 70), c.getInt("death.fade-out", 30));

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
}
