package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * 관리인 메뉴 (0.3.7, plan §8) — 마을 관리인 모아 · 노점 계산대 · {@code /미궁 집} · 대문 표지판(내 집) · 메인 메뉴 "집".
 * npcs.yml 정의가 없어도 열린다 (R20). 윗줄: 내 집 (가기·이름·손님·초대·시작 선물·비우기) · 아랫줄: 집 고르기 · 자재 · 맡긴 짐.
 */
final class EstateMenu extends HomeMenu {

    EstateMenu(PlayUi ui) { super(ui, "estate", 6, "<#ffd36b>마을 관리인 모아"); }

    @Override
    protected void draw(Player p) {
        var s = homes();
        HomesConfig c = s.config();
        List<PlotGeom> plots = s.plots();
        int vacant = ui.vacantCount();
        List<String> about = new ArrayList<>();
        about.add("<gray>마을 남쪽 등불 골목의 집터입니다.");
        about.add("<gray>한 사람 한 채" + (c.claimCost() > 0 ? " · " + Text.num(c.claimCost()) + "G" : ", 값은 받지 않습니다."));
        about.add("<gray>집 안에서는 짓고 부수고 상자를 씁니다.");
        about.add("<gray>집 안에 있으면 HP·MP 가 천천히 찹니다.");
        if (s.isTerrainLocked(p.getWorld())) about.add("<gray>집 밖 땅은 부수거나 지을 수 없습니다.");
        deco(4, Button.icon(Material.LANTERN, "<#ffd36b><b>등불 골목</b>", about));

        PlotGeom home = s.homeOf(p.getUniqueId());
        if (home != null) drawHome(p, home);
        else drawNoHome(p, plots, vacant);

        set(29, Button.icon(Material.FILLED_MAP, "<#7fd8ff><b>집 고르기</b>",
                List.of("<gray>집터 " + plots.size() + "채 · 빈 집 <white>" + vacant + "</white>", "<gray>지도에서 누구 집인지 봅니다.", "",
                        "<#ffd36b>클릭: 지도")), ctx -> {
                    click(ctx.player());
                    ui.openClaim(ctx.player());
                });
        HousingCatalog cat = ui.catalog();
        set(31, Button.icon(Material.BRICKS, "<#e8c58a><b>자재</b>",
                List.of("<gray>집 짓는 블록 <white>" + cat.size() + "</white>가지", "<gray>한 칸에 0.25~1G 쯤입니다.",
                        "<dark_gray>바닐라 블록은 되팔 수 없습니다.", "", "<#ffd36b>클릭: 사기")), ctx -> {
                    click(ctx.player());
                    ui.openShop(ctx.player());
                });
        int parcel = ui.parcelCount(p);
        set(33, UiTheme.glint(Button.icon(Material.BARREL, "<#c9a2ff><b>맡긴 짐</b>",
                List.of(parcel > 0 ? "<gray>맡긴 물건 <white>" + parcel + "</white>묶음" : "<dark_gray>맡긴 물건이 없습니다.",
                        "<gray>집을 비우면 집 안 물건이 여기로 옵니다.", "", "<#ffd36b>클릭: 보기")), parcel > 0), ctx -> {
                    click(ctx.player());
                    ui.openParcel(ctx.player());
                });
        deco(40, Button.icon(Material.BOOK, "<#ffd36b>명령",
                List.of("<white>/미궁 집</white> <gray>이 메뉴", "<white>/미궁 집 가기</white> <gray>내 집으로", "<white>/미궁 집 방문 <이름></white> <gray>친구 집으로",
                        "<white>/미궁 집 초대 <이름></white> <gray>· <white>내보내기 <이름>", "<white>/미궁 집 이름 <글></white> <gray>· <white>손님",
                        "<white>/미궁 집 짐</white> <gray>· <white>비우기</white> <gray>· <white>여기")));
        set(45, UiTheme.back(), ctx -> {
            click(ctx.player());
            services.menus().openMain(ctx.player());
        });
        gold(49, p);
        set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private void drawNoHome(Player p, List<PlotGeom> plots, int vacant) {
        var s = homes();
        if (plots.isEmpty()) {
            deco(13, Button.icon(Material.BARRIER, "<#ff6b6b>아직 집터가 없습니다",
                    List.of("<gray>이 서버에는 집 구역이 지어지지 않았습니다.", "<gray>관리자에게 물어보세요.")));
            return;
        }
        if (!s.active()) {
            deco(13, Button.icon(Material.BARRIER, "<#ff6b6b>집터를 준비하는 중입니다", List.of("<gray>조금 뒤 다시 와 주세요.")));
            return;
        }
        set(13, UiTheme.glint(Button.icon(Material.LIME_CONCRETE, "<#7fe07f><b>집 받기</b>",
                List.of("<gray>빈 집 <white>" + vacant + "</white> / " + plots.size(), "<gray>지도에서 고르거나 아무 데나 받습니다.", "",
                        vacant > 0 ? "<#ffd36b>클릭: 고르기" : "<#ff6b6b>빈 집이 없습니다")), vacant > 0), ctx -> {
                    click(ctx.player());
                    ui.openClaim(ctx.player());
                });
    }

    private void drawHome(Player p, PlotGeom home) {
        var s = homes();
        HomesConfig c = s.config();
        PlotInfo info = s.info(home);
        String name = info.name().isBlank() ? p.getName() + "의 집" : info.name();
        List<String> lore = new ArrayList<>();
        lore.add("<gray>" + Text.escape(name));
        lore.add("<gray>초대한 사람 <white>" + info.trusted().size() + "</white>/" + c.maxTrusted());
        lore.add("<gray>손님 " + (info.guests() ? "<#7fe07f>받음" : "<#ff8a8a>안 받음"));
        if (home.custom()) lore.add("<dark_gray>관리자가 정한 집터");
        else lore.add("<dark_gray>바닥 아래 " + c.heightBelow() + "칸 ~ 위 " + c.heightAbove() + "칸까지 지을 수 있습니다.");
        deco(10, UiTheme.glint(Button.icon(Material.OAK_DOOR, "<#ffd36b><b>" + Text.escape(home.label()) + "</b> <gray>· 내 집", lore), true));

        boolean go = ui.travel().goAllowed(p);
        set(11, Button.icon(Material.ENDER_PEARL, "<#7fd8ff><b>집 가기</b>",
                go ? List.of("<gray>대문 앞으로 갑니다.", "", "<#ffd36b>클릭: 가기 <dark_gray>(/미궁 집 가기)")
                        : List.of("<dark_gray>이 서버에서는 집 가기를 쓰지 않습니다.")), ctx -> {
                    click(ctx.player());
                    ctx.player().closeInventory();
                    ui.travel().goHome(ctx.player());
                });
        set(12, Button.icon(Material.NAME_TAG, "<#ffd36b><b>이름 바꾸기</b>",
                List.of("<gray>지금 이름: <white>" + Text.escape(name), "<gray>" + 16 + "자까지, " + c.renameCooldownMinutes() + "분에 한 번.", "",
                        "<#ffd36b>클릭: 채팅창에 명령 넣기")), ctx -> {
                    click(ctx.player());
                    ctx.player().closeInventory();
                    ui.suggest(ctx.player(), "/미궁 집 이름 ", "새 이름을 적어 보내세요.");
                });
        set(13, Button.icon(info.guests() ? Material.OAK_FENCE_GATE : Material.IRON_BARS,
                "<#ffd36b><b>손님</b> " + (info.guests() ? "<#7fe07f>받음" : "<#ff8a8a>안 받음"),
                List.of("<gray>손님은 문·작업대·종만 쓰고", "<gray>방문으로 올 수 있습니다.", "", "<#ffd36b>클릭: " + (info.guests() ? "안 받기" : "받기"))),
                ctx -> {
                    result(ctx.player(), homes().setGuests(ctx.player(), !info.guests()));
                    refresh();
                });
        set(14, head(p.getUniqueId(), p.getName(), "<#ffd36b><b>초대한 사람</b>",
                List.of("<gray>초대한 사람은 짓고 부수고 상자를 씁니다.", "<gray>지금 <white>" + info.trusted().size() + "</white>/" + c.maxTrusted(), "",
                        "<#ffd36b>클릭: 목록")), ctx -> {
            click(ctx.player());
            ui.openTrust(ctx.player());
        });
        if (ui.gift().available(p, home)) {
            set(15, UiTheme.glint(Button.icon(Material.CHEST, "<#7fe07f><b>시작 선물</b>",
                    List.of("<gray>작은 오두막이나 집들이 꾸러미 중", "<gray>하나를 한 번 받습니다.", "", "<#ffd36b>클릭: 고르기")), true), ctx -> {
                click(ctx.player());
                ui.openStarter(ctx.player(), home);
            });
        }
        set(16, Button.icon(Material.RED_DYE, "<#ff6b6b><b>집 비우기</b>",
                List.of(home.custom() ? "<gray>지은 것은 그대로 두고 집만 내놓습니다." : "<gray>집 안 블록과 물건은 맡긴 짐으로 갑니다.",
                        "<gray>다시 받기는 " + PlayUi.duration(c.reclaimCooldownMinutes()) + " 뒤에 됩니다.", "", "<#ffd36b>클릭: 비우기")), ctx -> {
            click(ctx.player());
            ui.confirmVacate(ctx.player());
        });
    }
}
