package kr.labyrinth.homes.play;

import java.util.UUID;
import java.util.function.IntBinaryOperator;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Teleports;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.mine.MineGameModeRule;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.OfflinePlayer;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.Player;

/**
 * 집 가기 · 방문 (0.3.7, plan §0·설계 §8, review R11·R12).
 * <ul>
 *   <li>{@code /미궁 집 가기} → 내 대문 바깥 거리 칸, 대문을 봄. 쿨다운 없음 (/미궁 마을 과 같음).</li>
 *   <li>{@code /미궁 집 방문 <이름>} → 그 집 대문 바깥 칸. 손님을 받지 않는 집은 주인·초대받은 사람만.</li>
 *   <li>{@code homes.home_teleport}·{@code homes.visit}: auto = {@code village.teleport_command} 를 따른다 (R11). 관리자는 늘 됨.</li>
 *   <li>미궁·인스턴스 안, PvP 전투 중에는 안 됨. 광산 월드에서는 됨 — 광산(어드벤처)에서 오면 {@link MineGameModeRule} 로 서바이벌 (R12).</li>
 * </ul>
 */
public final class HomeTravel {

    private final Services services;
    private final HomesService service;

    public HomeTravel(Services services, HomesService service) {
        this.services = services;
        this.service = service;
    }

    // ── 순수 규칙 ─────────────────────────────────────────────────────────

    /** 집 가기를 막는 이유 (되면 null). */
    public static String denyGo(boolean enabled, HomesConfig.Toggle toggle, boolean villageTeleport, boolean admin, boolean inDungeon,
                                boolean inCombat, boolean hasHome) {
        if (!enabled) return "이 서버에서는 집 기능을 쓰지 않습니다.";
        if (!hasHome) return "집이 없습니다. <white>/미궁 집</white> 에서 받을 수 있습니다.";
        if (!admin && (toggle == null || !toggle.allowed(villageTeleport))) return "이 서버에서는 집 가기를 쓰지 않습니다.";
        if (inDungeon) return "미궁 안에서는 쓸 수 없습니다. 먼저 <white>/미궁 귀환</white>";
        if (inCombat) return "싸우는 중에는 갈 수 없습니다.";
        return null;
    }

    /** 방문을 막는 이유 (되면 null). role = 방문하는 사람의 그 집에서의 자리. */
    public static String denyVisit(boolean enabled, HomesConfig.Toggle toggle, boolean villageTeleport, boolean admin, boolean inDungeon,
                                   boolean inCombat, boolean targetHasHome, PlotRole role) {
        if (!enabled) return "이 서버에서는 집 기능을 쓰지 않습니다.";
        if (!admin && (toggle == null || !toggle.allowed(villageTeleport))) return "이 서버에서는 방문을 쓰지 않습니다.";
        if (!targetHasHome) return "그 사람은 집이 없습니다.";
        if (!admin && (role == null || role == PlotRole.NONE)) return "손님을 받지 않는 집입니다.";
        if (inDungeon) return "미궁 안에서는 쓸 수 없습니다. 먼저 <white>/미궁 귀환</white>";
        if (inCombat) return "싸우는 중에는 갈 수 없습니다.";
        return null;
    }

    /**
     * 도착 칸 {x, y, z, yaw}: 구역 기록의 집 가기 칸 (아는 때) · 모르면 대문 바깥 칸 (앞 방향 한 칸) 가운데, 높이 = topY(x, z)
     * (그 열의 가장 높은 고체 블록 + 1), 대문을 봄.
     */
    public static double[] destination(PlotGeom p, IntBinaryOperator topY) {
        if (p.homeKnown()) return new double[] {p.homeX(), p.homeY(), p.homeZ(), p.homeYaw()};
        int x = p.gateX(), z = p.gateZ();
        float yaw;
        switch (p.front()) {
            case "N" -> { z -= 1; yaw = 0f; }
            case "E" -> { x += 1; yaw = 90f; }
            case "W" -> { x -= 1; yaw = -90f; }
            default -> { z += 1; yaw = 180f; }
        }
        int y = topY == null ? p.floorY() + 1 : topY.applyAsInt(x, z);
        return new double[] {x + 0.5, y, z + 0.5, yaw};
    }

    /** 광산(어드벤처)에서 왔을 때 바꿀 게임 모드 (R12 — 광산 규칙 그대로, 바꿀 필요 없으면 null). */
    public static GameMode modeAfter(GameMode current, boolean inMineWorld) { return MineGameModeRule.target(current, inMineWorld); }

    // ── 실제 이동 ─────────────────────────────────────────────────────────

    private boolean villageTeleport() { return services.plugin().getConfig().getBoolean("village.teleport_command", true); }

    private boolean inDungeon(Player p) {
        try {
            return services.dungeon().isInLabyrinth(p) || services.dungeon().currentInstance(p).isPresent();
        } catch (Throwable t) {
            return false;
        }
    }

    private boolean inCombat(Player p) {
        try {
            return services.targets().pvp().inCombat(p);
        } catch (Throwable t) {
            return false;
        }
    }

    static boolean admin(Player p) { return p.hasPermission(CommandService.PERM_ADMIN); }

    /** 집 가기를 쓸 수 있나 (메뉴 단추 표시용 — 집 여부는 보지 않음). */
    public boolean goAllowed(Player p) {
        return admin(p) || service.config().homeTeleport().allowed(villageTeleport());
    }

    public boolean visitAllowed(Player p) {
        return admin(p) || service.config().visit().allowed(villageTeleport());
    }

    public String toggleLine(HomesConfig.Toggle t) {
        boolean on = t.allowed(villageTeleport());
        return t.id() + "(" + (on ? "켬" : "끔") + ")";
    }

    public void goHome(Player p) {
        PlotGeom home = service.homeOf(p.getUniqueId());
        String err = denyGo(service.enabled(), service.config().homeTeleport(), villageTeleport(), admin(p), inDungeon(p), inCombat(p),
                home != null);
        if (err != null) {
            Text.error(p, err);
            return;
        }
        move(p, home, home.label() + "에 왔습니다.");
    }

    public void visit(Player p, String name) {
        OfflinePlayer target = findPlayer(name);
        if (target == null) {
            Text.error(p, "그 이름의 플레이어를 찾지 못했습니다: " + Text.escape(name));
            return;
        }
        if (target.getUniqueId().equals(p.getUniqueId())) {
            goHome(p);
            return;
        }
        visit(p, service.homeOf(target.getUniqueId()), target.getName());
    }

    /** 그 집터로 방문 (지도 메뉴에서). */
    public void visit(Player p, PlotGeom plot, String ownerName) {
        PlotRole role = plot == null ? PlotRole.NONE : service.roleIn(p, plot);
        String err = denyVisit(service.enabled(), service.config().visit(), villageTeleport(), admin(p), inDungeon(p), inCombat(p),
                plot != null, role);
        if (err != null) {
            Text.error(p, err);
            return;
        }
        if (role == PlotRole.OWNER) {
            move(p, plot, plot.label() + "에 왔습니다.");
            return;
        }
        move(p, plot, Text.escape(ownerName == null ? "" : ownerName) + "의 집 (" + plot.label() + ") 에 왔습니다.");
    }

    private void move(Player p, PlotGeom plot, String msg) {
        World w = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0);
        if (w == null) {
            Text.error(p, "월드를 찾지 못했습니다.");
            return;
        }
        double[] d = destination(plot, (x, z) -> w.getHighestBlockYAt(x, z) + 1);
        Location to = new Location(w, d[0], d[1], d[2], (float) d[3], 0f);
        p.setFallDistance(0);
        if (!Teleports.to(p, to)) {
            Text.error(p, "옮기지 못했습니다. 잠시 뒤 다시 해 보세요.");
            return;
        }
        GameMode m = modeAfter(p.getGameMode(), services.mine().isMineWorld(p.getWorld()));
        if (m != null) p.setGameMode(m);
        p.playSound(to, Sound.ENTITY_ENDERMAN_TELEPORT, 0.6f, 1.3f);
        w.spawnParticle(Particle.PORTAL, to.clone().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.3);
        Text.send(p, "<gray>" + msg);
    }

    static OfflinePlayer findPlayer(String name) {
        if (name == null || name.isBlank()) return null;
        Player online = Bukkit.getPlayerExact(name.trim());
        if (online != null) return online;
        OfflinePlayer op = Bukkit.getOfflinePlayerIfCached(name.trim());
        return op == null || op.getName() == null ? null : op;
    }

    static UUID uuidOf(String name) {
        OfflinePlayer op = findPlayer(name);
        return op == null ? null : op.getUniqueId();
    }
}
