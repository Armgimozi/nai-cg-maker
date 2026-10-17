package kr.labyrinth.homes.rules;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesApi;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.village.VillageService;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.type.Leaves;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.projectiles.ProjectileSource;

/**
 * 리스너 셋이 같이 쓰는 판단·글 (0.3.7). 소유: 묶음 B.
 * "어디서 (Where)" 를 구하고 {@link PlotRules#decide} 를 부르고, 막으면 글을 2초에 한 번 보낸다.
 */
public final class Guard {

    private final HomesService s;
    private final Map<UUID, Long> lastWarn = new HashMap<>();

    public Guard(HomesService s) { this.s = s; }

    public HomesService service() { return s; }

    /** 크리에이티브 관리자 (labyrinth.admin + CREATIVE) — 막지 않는다 (밭 밟기만 빼고). */
    public static boolean bypass(Player p) {
        return p != null && p.hasPermission(CommandService.PERM_ADMIN) && p.getGameMode() == GameMode.CREATIVE;
    }

    public PlotRules.Where where(Player p, Block b) { return where(p, b.getWorld(), b.getX(), b.getY(), b.getZ()); }

    public PlotRules.Where where(Player p, Location l) { return where(p, l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ()); }

    public PlotRules.Where where(Player p, World w, int x, int y, int z) {
        PlotGeom plot = s.plotAt(w, x, y, z);
        if (plot != null) return TerrainLock.where(plot.key(), p == null ? PlotRole.NONE : s.roleOf(p.getUniqueId(), plot), s.lockedNow());
        return TerrainLock.where(s.zone(w, x, y, z), null, s.lockedNow());
    }

    /**
     * 여러 칸 (두 칸 블록 · 걸개 받침과 걸개 칸): 모두 같은 zone 이면 그 Where, 아니면 null (가로지름 — 관리자가 아니면 막음).
     */
    public PlotRules.Where whereAll(Player p, List<Block> cells) {
        PlotRules.Where first = null;
        int zone = Integer.MIN_VALUE;
        for (Block b : cells) {
            int z = s.zone(b.getWorld(), b.getX(), b.getY(), b.getZ());
            if (zone == Integer.MIN_VALUE) {
                zone = z;
                first = where(p, b);
            } else if (z != zone) return null;
        }
        return first;
    }

    /**
     * 이사 기간이고 그 블록이 사람이 놓은 것인가. 구역(광산 마을·집 구역)이 놓은 블록은 보호 상자 밖이어도 빼다 (옹벽·기초 — verify 찾은 것 2).
     */
    public boolean graceBreakable(Block b) {
        if (!s.graceActive()) return false;
        boolean persistent = b.getBlockData() instanceof Leaves l && l.isPersistent();
        if (!TerrainLock.graceBreakable(b.getType().name(), persistent)) return false;
        VillageService v = VillageService.get();
        return v == null || !v.districtPlaced(b);
    }

    /** 이사 기간에 잠긴 들판의 걸개·거치대·탈것을 부숴도 되나 (옛 건물의 것을 옮기게 — 놓기는 아님). */
    public boolean graceEntity(PlotRules.Where where) { return where == PlotRules.Where.WILD_LOCKED && s.graceActive(); }

    /**
     * 판단하고 막으면 글. @return 막았나 (호출하는 쪽이 취소)
     */
    public boolean deny(Player p, PlotRules.Act act, PlotRules.Where where, Block at, boolean grace) {
        if (s.guardOnly() && where != null && !where.inPlot()) return false; // 집 기능을 꺼도 집터만은 지킴 (live 7) — 그 밖은 예전처럼
        boolean bypass = bypass(p);
        if (where == null) {
            if (bypass && act != PlotRules.Act.TRAMPLE) return false;
            warnText(p, "집터 경계를 넘어 놓을 수 없습니다.");
            return true;
        }
        if (s.storeBroken() && !bypass && where == PlotRules.Where.WILD_LOCKED && act == PlotRules.Act.CONTAINER) {
            warnText(p, BROKEN); // 기록을 못 읽으면 convert 집도 모름 → 들판 상자도 잠금 (live 6)
            return true;
        }
        if (PlotRules.decide(act, where, bypass, grace) != PlotRules.Verdict.DENY) return false;
        if (act == PlotRules.Act.TRAMPLE) return true; // 밭은 글 없이
        if (act == PlotRules.Act.BREAK && where == PlotRules.Where.WILD_LOCKED && at != null && TerrainLock.silent(at.getType().name())) return true;
        warn(p, act, where, at);
        return true;
    }

    public void warn(Player p, PlotRules.Act act, PlotRules.Where where, Block at) {
        if (p == null) return;
        String msg = switch (where) {
            case OWN -> switch (act) {
                case PRIME -> "TNT 와 리스폰 정박기는 쓸 수 없습니다.";
                case FIRE -> "불은 모닥불·초·차원문에만 붙일 수 있습니다.";
                default -> "그것은 이 서버에서 쓸 수 없습니다.";
            };
            case GUEST, STRANGER -> {
                PlotGeom plot = at == null ? null : s.plotAt(at.getWorld(), at.getX(), at.getY(), at.getZ());
                if (s.storeBroken()) yield BROKEN;
                if (plot == null) yield "남의 집입니다.";
                if (s.ownerOf(plot) == null) yield ClaimRules.topic(plot) + " 빈 집입니다. /미궁 집 에서 받을 수 있습니다.";
                yield act == PlotRules.Act.PRIME ? "TNT 와 리스폰 정박기는 쓸 수 없습니다." : ClaimRules.topic(plot) + " 남의 집입니다.";
            }
            case PROTECTED -> act == PlotRules.Act.PRIME ? "TNT 와 리스폰 정박기는 쓸 수 없습니다." : "마을은 부수거나 바꿀 수 없습니다.";
            case WILD_LOCKED -> {
                if (act == PlotRules.Act.PRIME) yield "TNT 와 리스폰 정박기는 쓸 수 없습니다.";
                if (act == PlotRules.Act.USE_BANNED || act == PlotRules.Act.PLACE_BANNED) yield "그것은 이 서버에서 쓸 수 없습니다.";
                PlotGeom col = at == null ? null : s.columnPlot(at.getWorld(), at.getX(), at.getZ());
                if (col != null && s.roleOf(p.getUniqueId(), col).builds()) {
                    yield "집은 바닥 " + (col.floorY() - col.yMin()) + "칸 아래부터 " + (col.yMax() - col.floorY()) + "칸 위까지 지을 수 있습니다.";
                }
                yield "집터 밖은 부수거나 지을 수 없습니다 — /미궁 집";
            }
            case WILD_OPEN -> act == PlotRules.Act.PRIME ? "TNT 와 리스폰 정박기는 쓸 수 없습니다." : "여기서는 할 수 없습니다.";
        };
        warnText(p, msg);
    }

    /** 집 주인 기록을 못 읽었을 때 (live 6 안전 모드). */
    public static final String BROKEN = "집 기록을 읽지 못해 지금은 집을 쓸 수 없습니다. 관리자에게 알려 주세요.";

    /** 2초에 한 번. */
    public void warnText(Player p, String msg) {
        if (p == null || msg == null) return;
        long now = System.currentTimeMillis();
        Long last = lastWarn.get(p.getUniqueId());
        if (last != null && now - last < 2000) return;
        lastWarn.put(p.getUniqueId(), now);
        Text.error(p, msg);
    }

    public void forget(UUID u) { lastWarn.remove(u); }

    /** 엔티티를 친 플레이어 (직접 · 쏜 사람 · 물약 구름을 남긴 사람), 없으면 null. */
    public static Player playerOf(Entity damager) {
        if (damager instanceof Player p) return p;
        if (damager instanceof Projectile pr) {
            ProjectileSource src = pr.getShooter();
            if (src instanceof Player p) return p;
        }
        if (damager instanceof AreaEffectCloud c && c.getSource() instanceof Player p) return p; // 오래 남는 물약 (exploit L7)
        return null;
    }

    // ── 집 동물·탈것 표시 (exploit M1) ───────────────────────────────────

    private NamespacedKey homeKey;

    private NamespacedKey homeKey() {
        if (homeKey == null) homeKey = new NamespacedKey(s.plugin(), "home_plot");
        return homeKey;
    }

    /** 집터 안에서 사는 동물·탈것에 그 집 id 를 적는다 (집 밖으로 나가도 그 집 권한으로 봄). */
    public void tag(Entity e, PlotGeom plot) {
        if (e == null || plot == null || e instanceof Player) return;
        try {
            String now = e.getPersistentDataContainer().get(homeKey(), PersistentDataType.STRING);
            if (!plot.id().equals(now)) e.getPersistentDataContainer().set(homeKey(), PersistentDataType.STRING, plot.id());
        } catch (Throwable ignored) {
            // 서버 없이 (시험)
        }
    }

    /** 그 엔티티가 사는 집 (표시가 있고 그 집터가 아직 있을 때), 없으면 null. */
    public PlotGeom homePlot(Entity e) {
        if (e == null || e instanceof Player) return null;
        try {
            String id = e.getPersistentDataContainer().get(homeKey(), PersistentDataType.STRING);
            return id == null ? null : s.plot(id);
        } catch (Throwable t) {
            return null;
        }
    }

    /** 그 엔티티를 따질 집 — 지금 서 있는 집터, 아니면 표시된 집 (집 밖으로 나간 동물·보트). */
    public PlotGeom plotOf(Entity e) {
        Location l = e.getLocation();
        PlotGeom here = s.plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
        return here != null ? here : homePlot(e);
    }

    /**
     * 집 밖으로 나간 표시된 동물·탈것: 그 집의 주인·초대만 (손님·남은 막음, 글 "n번지 것입니다."). @return 막았나
     */
    public boolean denyTagged(Player p, PlotRules.Act act, PlotGeom home) {
        if (p == null || home == null) return false;
        boolean bypass = bypass(p);
        PlotRules.Where w = TerrainLock.where(home.key(), s.roleOf(p.getUniqueId(), home), true);
        if (PlotRules.decide(act, w, bypass, false) != PlotRules.Verdict.DENY) return false;
        warnText(p, s.storeBroken() ? BROKEN : home.label() + " 것입니다.");
        return true;
    }

    /** 엔티티 칸 zone. */
    public int zone(Entity e) {
        Location l = e.getLocation();
        return s.zone(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
    }

    public int zone(Block b) { return s.zone(b.getWorld(), b.getX(), b.getY(), b.getZ()); }

    public static boolean inPlot(int zone) { return zone > HomesApi.ZONE_PROTECTED; }
}
