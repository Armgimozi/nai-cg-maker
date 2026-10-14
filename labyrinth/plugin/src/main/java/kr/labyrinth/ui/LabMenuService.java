package kr.labyrinth.ui;

import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.menus.AccessoryMenu;
import kr.labyrinth.ui.menus.ClassMenu;
import kr.labyrinth.ui.menus.EntranceMenu;
import kr.labyrinth.ui.menus.MainMenu;
import kr.labyrinth.ui.menus.PartyMenu;
import kr.labyrinth.ui.menus.PvpMenu;
import kr.labyrinth.ui.menus.SetupMenu;
import kr.labyrinth.ui.menus.StatsMenu;
import kr.labyrinth.ui.menus.TitlesMenu;
import org.bukkit.entity.Player;

/** 상자 GUI 메뉴 구현 (ui/menus/*). 메뉴를 여는 중 오류가 나면 채팅 메뉴로 대신한다(게임이 멈추지 않게). */
public final class LabMenuService implements MenuService {

    private final Services services;
    private final ChatMenuService fallback;

    public LabMenuService(Services services) {
        this.services = services;
        this.fallback = new ChatMenuService(services);
    }

    private void open(Player p, String what, Runnable gui, Runnable chat) {
        try {
            gui.run();
        } catch (Throwable t) {
            Log.error("메뉴 열기 실패 (" + what + ") — 채팅 메뉴로 대신합니다", t);
            if (chat != null) chat.run();
        }
    }

    @Override
    public void openMain(Player p) { open(p, "main", () -> new MainMenu(services).open(p), () -> fallback.openMain(p)); }

    @Override
    public void openStats(Player p) { open(p, "stats", () -> new StatsMenu(services).open(p), () -> fallback.openStats(p)); }

    @Override
    public void openClass(Player p) { open(p, "class", () -> new ClassMenu(services).open(p), () -> fallback.openClass(p)); }

    @Override
    public void openParty(Player p) { open(p, "party", () -> new PartyMenu(services).open(p), () -> fallback.openParty(p)); }

    @Override
    public void openTitles(Player p) { open(p, "titles", () -> new TitlesMenu(services).open(p), () -> fallback.openTitles(p)); }

    @Override
    public void openEntrance(Player p) { open(p, "entrance", () -> new EntranceMenu(services).open(p), () -> fallback.openEntrance(p)); }

    @Override
    public void openSetup(Player p) {
        if (!p.hasPermission(CommandService.PERM_ADMIN)) {
            Text.error(p, "관리자만 서버 설정을 바꿀 수 있습니다.");
            return;
        }
        open(p, "setup", () -> new SetupMenu(services).open(p), () -> fallback.openSetup(p));
    }

    @Override
    public void openAccessories(Player p) { open(p, "accessories", () -> new AccessoryMenu(services).open(p), null); }

    @Override
    public void openPvp(Player p) { open(p, "pvp", () -> new PvpMenu(services).open(p), null); }

    @Override
    public void openBlacksmith(Player p) { open(p, "blacksmith", () -> services.crafting().openBlacksmith(p), null); }

    @Override
    public void openMerchant(Player p) {
        NpcDef merchant = null;
        for (NpcDef n : services.content().npcs().values()) {
            if ("merchant".equals(n.role()) && n.shop() != null && !n.shop().isEmpty()) {
                merchant = n;
                break;
            }
        }
        if (merchant == null) {
            Text.send(p, "<gray>상인이 아직 도착하지 않았습니다.");
            return;
        }
        NpcDef m = merchant;
        open(p, "merchant", () -> new kr.labyrinth.mobs.npc.ShopMenu(services, m).open(p), null);
    }
}
