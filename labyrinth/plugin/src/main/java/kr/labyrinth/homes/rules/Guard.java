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
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.type.Leaves;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
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

    /** 이사 기간이고 그 블록이 사람이 놓은 것인가. */
    public boolean graceBreakable(Block b) {
        if (!s.graceActive()) return false;
        boolean persistent = b.getBlockData() instanceof Leaves l && l.isPersistent();
        return TerrainLock.graceBreakable(b.getType().name(), persistent);
    }

    /**
     * 판단하고 막으면 글. @return 막았나 (호출하는 쪽이 취소)
     */
    public boolean deny(Player p, PlotRules.Act act, PlotRules.Where where, Block at, boolean grace) {
        boolean bypass = bypass(p);
        if (where == null) {
            if (bypass && act != PlotRules.Act.TRAMPLE) return false;
            warnText(p, "집터 경계를 넘어 놓을 수 없습니다.");
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

    /** 엔티티를 친 플레이어 (직접 · 쏜 사람), 없으면 null. */
    public static Player playerOf(Entity damager) {
        if (damager instanceof Player p) return p;
        if (damager instanceof Projectile pr) {
            ProjectileSource src = pr.getShooter();
            if (src instanceof Player p) return p;
        }
        return null;
    }

    /** 엔티티 칸 zone. */
    public int zone(Entity e) {
        Location l = e.getLocation();
        return s.zone(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
    }

    public int zone(Block b) { return s.zone(b.getWorld(), b.getX(), b.getY(), b.getZ()); }

    public static boolean inPlot(int zone) { return zone > HomesApi.ZONE_PROTECTED; }
}
