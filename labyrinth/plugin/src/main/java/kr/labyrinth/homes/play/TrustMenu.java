package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * 초대 목록 (0.3.7): 윗줄 = 초대한 사람 (머리 클릭 = 내보내기) · 아랫줄 = 지금 접속한 사람 (클릭 = 초대).
 * 초대한 사람은 짓기·부수기·상자를 쓴다 (이름·초대·손님·비우기는 주인만).
 */
final class TrustMenu extends HomeMenu {

    private static final int[] TRUSTED_SLOTS = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25};
    private static final int[] ONLINE_SLOTS = {28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};

    TrustMenu(PlayUi ui) { super(ui, "home_trust", 6, "<#ffd36b>초대한 사람"); }

    @Override
    protected void draw(Player p) {
        var s = homes();
        PlotGeom home = s.homeOf(p.getUniqueId());
        if (home == null) {
            deco(22, Button.icon(Material.BARRIER, "<#ff6b6b>집이 없습니다", List.of("<gray>먼저 집을 받으세요.")));
            backAndClose();
            return;
        }
        PlotInfo info = s.info(home);
        int max = s.config().maxTrusted();
        deco(4, Button.icon(Material.OAK_DOOR, "<#ffd36b>" + Text.escape(home.label()) + " <gray>초대 " + info.trusted().size() + "/" + max,
                List.of("<gray>초대한 사람은 짓고 부수고 상자를 씁니다.", "<gray>머리를 누르면 내보냅니다.")));
        Set<UUID> trusted = new HashSet<>(info.trusted());
        for (int i = 0; i < info.trusted().size() && i < TRUSTED_SLOTS.length; i++) {
            UUID id = info.trusted().get(i);
            String name = i < info.trustedNames().size() ? info.trustedNames().get(i) : id.toString().substring(0, 8);
            set(TRUSTED_SLOTS[i], head(id, name, "<white>" + Text.escape(name),
                    List.of("<gray>초대함", "", "<#ff8a8a>클릭: 내보내기")), ctx -> {
                result(ctx.player(), homes().kick(ctx.player(), name));
                refresh();
            });
        }
        List<Player> online = new ArrayList<>();
        for (Player o : Bukkit.getOnlinePlayers()) {
            if (o.getUniqueId().equals(p.getUniqueId()) || trusted.contains(o.getUniqueId())) continue;
            online.add(o);
        }
        if (online.isEmpty()) {
            deco(31, Button.icon(Material.GRAY_DYE, "<gray>초대할 사람이 접속해 있지 않습니다",
                    List.of("<dark_gray>접속하지 않은 사람은 <white>/미궁 집 초대 <이름>")));
        }
        boolean full = info.trusted().size() >= max;
        for (int i = 0; i < online.size() && i < ONLINE_SLOTS.length; i++) {
            Player o = online.get(i);
            set(ONLINE_SLOTS[i], head(o.getUniqueId(), o.getName(), "<#7fe07f>" + Text.escape(o.getName()),
                    List.of("<gray>접속 중", "", full ? "<dark_gray>초대 자리가 다 찼습니다" : "<#ffd36b>클릭: 초대")), ctx -> {
                result(ctx.player(), homes().invite(ctx.player(), o.getName()));
                refresh();
            });
        }
        set(49, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b>이름으로 초대",
                List.of("<gray>접속하지 않은 사람도 초대할 수 있습니다.", "", "<#ffd36b>클릭: 채팅창에 명령 넣기")), ctx -> {
            click(ctx.player());
            ctx.player().closeInventory();
            ui.suggest(ctx.player(), "/미궁 집 초대 ", "초대할 사람 이름을 적어 보내세요.");
        });
        backAndClose();
    }

    private void backAndClose() {
        set(45, UiTheme.back(), ctx -> {
            click(ctx.player());
            ui.openEstate(ctx.player());
        });
        set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }
}
