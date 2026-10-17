package kr.labyrinth.homes;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.bukkit.configuration.ConfigurationSection;

/**
 * config.yml {@code homes:} (0.3.7 집 구역 + 지형 잠금) — 순수. 키가 없으면 이 기본값, {@code homes: false} 면 통째로 끔.
 * 틀린 값은 범위 안으로 자른다 (review R16). 소유: 묶음 C (묶음 A 는 {@link #district()} 를 읽기만).
 * <p>
 * 기능은 집 구역이 지어진 뒤에만 움직인다: {@code enabled} 는 "쓸 수 있음" 이고, 잠금·받기·회복은 구역 state built (또는 관리자 lock on / convert 집) 일 때만.
 */
public record HomesConfig(boolean enabled, boolean terrainLock, District district, int claimCost, int maxTrusted, boolean guestsDefault,
                          int heightBelow, int heightAbove, int reclaimCooldownMinutes, int renameCooldownMinutes, int inactiveDays,
                          int legacyGraceDays, Regen regen, BedRest bedRest, Toggle homeTeleport, Toggle visit, Starter starter,
                          TickParts tickParts, EntityCaps entityCaps, List<String> denyPlace, List<String> denyUse, double shopPriceMultiplier,
                          boolean enterActionbar) {

    /** auto = config village.teleport_command 를 따름 (review R11) · on · off. 관리자는 늘 됨. */
    public enum Toggle {
        AUTO, ON, OFF;

        public static Toggle of(Object v) {
            if (v instanceof Boolean b) return b ? ON : OFF;
            String s = String.valueOf(v).trim().toLowerCase(Locale.ROOT);
            return switch (s) {
                case "true", "on", "yes", "켬" -> ON;
                case "false", "off", "no", "끔" -> OFF;
                default -> AUTO;
            };
        }

        public String id() { return name().toLowerCase(Locale.ROOT); }

        /** 쓸 수 있나 (villageTeleport = config village.teleport_command). */
        public boolean allowed(boolean villageTeleport) {
            return this == ON || (this == AUTO && villageTeleport);
        }
    }

    /** 집 구역 짓기 (구역 기계가 읽음 — mine.district 와 같은 모양). */
    public record District(boolean autoBuild, List<String> sites, int blocksPerTick, boolean notifyAdmins) {
        public District {
            sites = sites == null || sites.isEmpty() ? List.of("south_west") : List.copyOf(sites);
            blocksPerTick = Math.max(200, blocksPerTick);
        }
    }

    /** 집 안 회복: 마지막 피해 뒤 calmSeconds 가 지나면 1초마다 최대 HP·MP 의 hp·mp 비율. */
    public record Regen(double hp, double mp, int calmSeconds) {
        public Regen {
            hp = clamp(hp, 0, 1);
            mp = clamp(mp, 0, 1);
            calmSeconds = Math.max(0, Math.min(600, calmSeconds));
        }
    }

    /** 내 침대 우클릭 seconds 초 → 가득 (cooldownSeconds 에 한 번). */
    public record BedRest(int seconds, int cooldownSeconds) {
        public BedRest {
            seconds = Math.max(0, Math.min(30, seconds));
            cooldownSeconds = Math.max(0, cooldownSeconds);
        }
    }

    public record Starter(boolean cottage, boolean kit) {}

    /** 집당 틱 부품 (깔때기·공급기·제작기·피스톤·끈끈이 피스톤·관측기) 합 · 그중 깔때기. */
    public record TickParts(int total, int hoppers) {
        public TickParts {
            total = Math.max(0, total);
            hoppers = Math.max(0, Math.min(total, hoppers));
        }
    }

    /** 집당 동물 · 장식 엔티티(갑옷 거치대 + 액자 + 그림) (review R15). */
    public record EntityCaps(int animals, int decorations) {
        public EntityCaps {
            animals = Math.max(0, animals);
            decorations = Math.max(0, decorations);
        }
    }

    public static final District DEFAULT_DISTRICT = new District(true, List.of("south_west"), 3000, true);

    public static final HomesConfig DEFAULT = new HomesConfig(true, true, DEFAULT_DISTRICT, 0, 8, true, 6, 24, 1440, 5, 60, 14,
            new Regen(0.05, 0.05, 5), new BedRest(2, 60), Toggle.AUTO, Toggle.AUTO, new Starter(true, true), new TickParts(16, 8),
            new EntityCaps(24, 64), List.of("tnt", "tnt_minecart", "respawn_anchor", "end_crystal", "dispenser"),
            List.of("lava_bucket", "fire_charge"), 1.0, true);

    public HomesConfig {
        district = district == null ? DEFAULT_DISTRICT : district;
        claimCost = Math.max(0, claimCost);
        maxTrusted = Math.max(0, Math.min(32, maxTrusted));
        heightBelow = Math.max(0, Math.min(16, heightBelow));
        heightAbove = Math.max(4, Math.min(64, heightAbove));
        reclaimCooldownMinutes = Math.max(0, reclaimCooldownMinutes);
        renameCooldownMinutes = Math.max(0, renameCooldownMinutes);
        inactiveDays = Math.max(0, inactiveDays);
        legacyGraceDays = Math.max(0, Math.min(365, legacyGraceDays));
        regen = regen == null ? new Regen(0.05, 0.05, 5) : regen;
        bedRest = bedRest == null ? new BedRest(2, 60) : bedRest;
        homeTeleport = homeTeleport == null ? Toggle.AUTO : homeTeleport;
        visit = visit == null ? Toggle.AUTO : visit;
        starter = starter == null ? new Starter(true, true) : starter;
        tickParts = tickParts == null ? new TickParts(16, 8) : tickParts;
        entityCaps = entityCaps == null ? new EntityCaps(24, 64) : entityCaps;
        denyPlace = ids(denyPlace);
        denyUse = ids(denyUse);
        shopPriceMultiplier = Double.isNaN(shopPriceMultiplier) ? 1.0 : clamp(shopPriceMultiplier, 0.1, 100);
    }

    /** config 루트에서: {@code homes: false} 면 꺼짐, 절이 없으면 기본값. */
    public static HomesConfig fromRoot(ConfigurationSection root) {
        if (root == null) return DEFAULT;
        Object v = root.get("homes");
        if (v instanceof Boolean b && !b) return DEFAULT.withEnabled(false);
        return from(root.getConfigurationSection("homes"));
    }

    public HomesConfig withEnabled(boolean on) {
        return new HomesConfig(on, terrainLock, district, claimCost, maxTrusted, guestsDefault, heightBelow, heightAbove, reclaimCooldownMinutes,
                renameCooldownMinutes, inactiveDays, legacyGraceDays, regen, bedRest, homeTeleport, visit, starter, tickParts, entityCaps,
                denyPlace, denyUse, shopPriceMultiplier, enterActionbar);
    }

    /** {@code homes:} 절 (null → 기본값). */
    public static HomesConfig from(ConfigurationSection s) {
        if (s == null) return DEFAULT;
        HomesConfig d = DEFAULT;
        ConfigurationSection ds = s.getConfigurationSection("district");
        District dist = d.district();
        if (ds != null) {
            dist = new District(ds.getBoolean("auto_build", dist.autoBuild()), ds.isList("sites") ? ds.getStringList("sites") : dist.sites(),
                    ds.getInt("blocks_per_tick", dist.blocksPerTick()), ds.getBoolean("notify_admins", dist.notifyAdmins()));
        }
        ConfigurationSection h = s.getConfigurationSection("height");
        ConfigurationSection rg = s.getConfigurationSection("home_regen");
        ConfigurationSection br = s.getConfigurationSection("bed_rest");
        ConfigurationSection st = s.getConfigurationSection("starter");
        ConfigurationSection tp = s.getConfigurationSection("tick_parts");
        ConfigurationSection ec = s.getConfigurationSection("entity_caps");
        return new HomesConfig(
                s.getBoolean("enabled", d.enabled()),
                s.getBoolean("terrain_lock", d.terrainLock()),
                dist,
                s.getInt("claim_cost", d.claimCost()),
                s.getInt("max_trusted", d.maxTrusted()),
                s.getBoolean("guests_default", d.guestsDefault()),
                h == null ? d.heightBelow() : h.getInt("below", d.heightBelow()),
                h == null ? d.heightAbove() : h.getInt("above", d.heightAbove()),
                s.getInt("reclaim_cooldown_minutes", d.reclaimCooldownMinutes()),
                s.getInt("rename_cooldown_minutes", d.renameCooldownMinutes()),
                s.getInt("inactive_days", d.inactiveDays()),
                s.getInt("legacy_grace_days", d.legacyGraceDays()),
                rg == null ? d.regen() : new Regen(rg.getDouble("hp", d.regen().hp()), rg.getDouble("mp", d.regen().mp()),
                        rg.getInt("calm_seconds", d.regen().calmSeconds())),
                br == null ? d.bedRest() : new BedRest(br.getInt("seconds", d.bedRest().seconds()),
                        br.getInt("cooldown_seconds", d.bedRest().cooldownSeconds())),
                s.contains("home_teleport") ? Toggle.of(s.get("home_teleport")) : d.homeTeleport(),
                s.contains("visit") ? Toggle.of(s.get("visit")) : d.visit(),
                st == null ? d.starter() : new Starter(st.getBoolean("cottage", d.starter().cottage()), st.getBoolean("kit", d.starter().kit())),
                tp == null ? d.tickParts() : new TickParts(tp.getInt("total", d.tickParts().total()), tp.getInt("hoppers", d.tickParts().hoppers())),
                ec == null ? d.entityCaps() : new EntityCaps(ec.getInt("animals", d.entityCaps().animals()),
                        ec.getInt("decorations", d.entityCaps().decorations())),
                s.isList("deny_place") ? s.getStringList("deny_place") : d.denyPlace(),
                s.isList("deny_use") ? s.getStringList("deny_use") : d.denyUse(),
                s.getDouble("shop_price_multiplier", d.shopPriceMultiplier()),
                s.getBoolean("enter_actionbar", d.enterActionbar()));
    }

    /** 바닥 높이 → 짓기 높이 창 [바닥 − below, 바닥 + above]. */
    public int[] window(int floorY) { return new int[] {floorY - heightBelow, floorY + heightAbove}; }

    private static List<String> ids(List<String> in) {
        List<String> out = new ArrayList<>();
        if (in != null) for (String s : in) {
            if (s == null || s.isBlank()) continue;
            String k = s.trim().toLowerCase(Locale.ROOT);
            if (k.startsWith("minecraft:")) k = k.substring("minecraft:".length());
            if (!out.contains(k)) out.add(k);
        }
        return List.copyOf(out);
    }

    private static double clamp(double v, double lo, double hi) { return Double.isNaN(v) ? lo : Math.max(lo, Math.min(hi, v)); }
}
