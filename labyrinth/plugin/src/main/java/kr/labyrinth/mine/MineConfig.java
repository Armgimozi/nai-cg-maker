package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.bukkit.configuration.ConfigurationSection;

/**
 * config.yml {@code mine:} — 광산 손잡이만 (R §3-16). 층·광석·블록·바이옴·초는 content/mine.yml.
 * 키가 없거나 config 에 {@code mine:} 절이 없으면 코드 기본값 ({@link #DEFAULT}) = 계약 mine.json {@code config_defaults}.
 * <p>
 * 주인 늦은 결정 (계약 §0): 기력·매크로 막기(1시간 알림 {@code alert_per_hour} 포함)는 없다. 광맥은 모두가 함께 쓰고,
 * 다시 차는 시간 = 기본 ÷ min(광산 월드 사람 수, {@link #regenPlayersCap}) — 여럿이 캐도 한 사람 몫이 혼자일 때와 비슷하다.
 * 순수 (서버 없이 시험).
 */
public record MineConfig(boolean enabled, String world, Teleport teleportCommand, double liftSeconds, List<Integer> regenMinutes,
                         int gemNodeRegenMinutes, int regenPlayersCap, double gemChance, double richChance, int richMultiplier,
                         boolean fxPop, boolean noHunger, boolean safe, District district) {

    /** {@code /미궁 광산} 을 켤지: auto = village.teleport_command 를 따름. */
    public enum Teleport {
        AUTO, ON, OFF;

        static Teleport of(Object v) {
            if (v instanceof Boolean b) return b ? ON : OFF;
            String s = v == null ? "auto" : String.valueOf(v).trim().toLowerCase(Locale.ROOT);
            return switch (s) {
                case "true", "on", "yes" -> ON;
                case "false", "off", "no" -> OFF;
                default -> AUTO;
            };
        }

        public String id() {
            return switch (this) {
                case AUTO -> "auto";
                case ON -> "true";
                case OFF -> "false";
            };
        }
    }

    /** 광산 마을 자동 짓기 (Q2 가 읽는다 — 값 모양만 여기서). */
    public record District(boolean autoBuild, List<String> sites, int blocksPerTick, boolean notifyAdmins) {
        public District {
            sites = sites == null ? List.of() : List.copyOf(sites);
        }
    }

    public static final List<Integer> DEFAULT_REGEN = List.of(8, 9, 9, 10, 10, 10);
    public static final District DEFAULT_DISTRICT = new District(true, List.of("east", "south_east"), 3000, true);
    public static final MineConfig DEFAULT = new MineConfig(true, MineNames.WORLD, Teleport.AUTO, 2.0, DEFAULT_REGEN, 30, 4, 0.022,
            0.04, 3, true, true, true, DEFAULT_DISTRICT);

    public MineConfig {
        world = world == null || world.isBlank() ? MineNames.WORLD : world.trim();
        teleportCommand = teleportCommand == null ? Teleport.AUTO : teleportCommand;
        liftSeconds = clamp(liftSeconds, 0, 10);
        List<Integer> r = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            int v = regenMinutes != null && i < regenMinutes.size() && regenMinutes.get(i) != null ? regenMinutes.get(i)
                    : DEFAULT_REGEN.get(i);
            r.add(Math.max(1, Math.min(24 * 60, v)));
        }
        regenMinutes = List.copyOf(r);
        gemNodeRegenMinutes = Math.max(1, Math.min(24 * 60, gemNodeRegenMinutes));
        regenPlayersCap = Math.max(1, Math.min(20, regenPlayersCap));
        gemChance = clamp(gemChance, 0, 1);
        richChance = clamp(richChance, 0, 1);
        richMultiplier = Math.max(1, Math.min(10, richMultiplier));
        district = district == null ? DEFAULT_DISTRICT : district;
    }

    private static double clamp(double v, double lo, double hi) {
        return Double.isNaN(v) ? lo : Math.max(lo, Math.min(hi, v));
    }

    /** 층 n(1부터)의 광맥 기본 재생 초 (한 사람일 때). */
    public double regenSeconds(int level) {
        int i = Math.max(1, Math.min(6, level)) - 1;
        return regenMinutes.get(i) * 60.0;
    }

    public double gemRegenSeconds() { return gemNodeRegenMinutes * 60.0; }

    /** {@code /미궁 광산} 을 쓸 수 있나 (villageTeleport = config village.teleport_command). */
    public boolean teleportAllowed(boolean villageTeleport) {
        return switch (teleportCommand) {
            case ON -> true;
            case OFF -> false;
            case AUTO -> villageTeleport;
        };
    }

    /** config 루트에서: {@code mine: false} 면 꺼짐, 절이 없으면 기본값. */
    public static MineConfig fromRoot(ConfigurationSection root) {
        if (root == null) return DEFAULT;
        Object v = root.get("mine");
        if (v instanceof Boolean b && !b) return withEnabled(DEFAULT, false);
        return from(root.getConfigurationSection("mine"));
    }

    static MineConfig withEnabled(MineConfig c, boolean on) {
        return new MineConfig(on, c.world, c.teleportCommand, c.liftSeconds, c.regenMinutes, c.gemNodeRegenMinutes, c.regenPlayersCap,
                c.gemChance, c.richChance, c.richMultiplier, c.fxPop, c.noHunger, c.safe, c.district);
    }

    /** config.yml 의 {@code mine:} 절 (없으면 null → 기본값). 틀린 값은 범위 안으로. */
    public static MineConfig from(ConfigurationSection s) {
        if (s == null) return DEFAULT;
        MineConfig d = DEFAULT;
        List<Integer> regen = new ArrayList<>();
        if (s.isList("regen_minutes")) {
            for (Object o : s.getList("regen_minutes", List.of())) {
                try {
                    regen.add((int) Math.round(Double.parseDouble(String.valueOf(o))));
                } catch (NumberFormatException e) {
                    regen.add(null);
                }
            }
        } else if (s.isInt("regen_minutes") || s.isDouble("regen_minutes")) {
            int all = (int) Math.round(s.getDouble("regen_minutes"));
            for (int i = 0; i < 6; i++) regen.add(all);
        }
        ConfigurationSection rich = s.getConfigurationSection("rich");
        ConfigurationSection fx = s.getConfigurationSection("fx");
        ConfigurationSection ds = s.getConfigurationSection("district");
        District dist = d.district();
        if (ds != null) {
            List<String> sites = ds.isList("sites") ? ds.getStringList("sites") : dist.sites();
            dist = new District(ds.getBoolean("auto_build", dist.autoBuild()), sites, ds.getInt("blocks_per_tick", dist.blocksPerTick()),
                    ds.getBoolean("notify_admins", dist.notifyAdmins()));
        }
        return new MineConfig(
                s.getBoolean("enabled", d.enabled()),
                s.getString("world", d.world()),
                s.contains("teleport_command") ? Teleport.of(s.get("teleport_command")) : d.teleportCommand(),
                s.getDouble("lift_seconds", d.liftSeconds()),
                regen.isEmpty() ? d.regenMinutes() : regen,
                s.getInt("gem_node_regen_minutes", d.gemNodeRegenMinutes()),
                s.getInt("regen_players_cap", d.regenPlayersCap()),
                s.getDouble("gem_chance", d.gemChance()),
                rich == null ? d.richChance() : rich.getDouble("chance", d.richChance()),
                rich == null ? d.richMultiplier() : rich.getInt("multiplier", d.richMultiplier()),
                fx == null ? d.fxPop() : fx.getBoolean("pop", d.fxPop()),
                s.getBoolean("no_hunger", d.noHunger()),
                s.getBoolean("safe", d.safe()),
                dist);
    }

    /** 이 값을 config.yml 모양으로 (시험·/labadmin mine 이 비교). */
    public java.util.Map<String, Object> toMap() {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("enabled", enabled);
        m.put("world", world);
        m.put("teleport_command", teleportCommand.id());
        m.put("lift_seconds", liftSeconds);
        m.put("regen_minutes", regenMinutes);
        m.put("gem_node_regen_minutes", gemNodeRegenMinutes);
        m.put("regen_players_cap", regenPlayersCap);
        m.put("gem_chance", gemChance);
        m.put("rich", java.util.Map.of("chance", richChance, "multiplier", richMultiplier));
        m.put("fx", java.util.Map.of("pop", fxPop));
        m.put("no_hunger", noHunger);
        m.put("safe", safe);
        m.put("district", java.util.Map.of("auto_build", district.autoBuild(), "sites", district.sites(), "blocks_per_tick",
                district.blocksPerTick(), "notify_admins", district.notifyAdmins()));
        return m;
    }
}
