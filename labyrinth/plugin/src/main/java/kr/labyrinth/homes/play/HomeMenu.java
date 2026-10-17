package kr.labyrinth.homes.play;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ResolvableProfile;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesResult;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.menus.LabMenu;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** 집 메뉴 공통 (0.3.7): 미궁 메뉴 배경·효과음 + 집 서비스·결과 글. 소유가 바뀌면 열린 집 메뉴는 모두 새로 그린다 ({@link PlayUi#plotChanged}). */
abstract class HomeMenu extends LabMenu {

    protected final PlayUi ui;

    HomeMenu(PlayUi ui, String menuId, int rows, String title) {
        super(ui.services(), menuId, rows, title);
        this.ui = ui;
    }

    protected HomesService homes() { return ui.service(); }

    /** 집 일 결과: 됐으면 보통 글 + 소리, 아니면 빨간 글 + 소리. @return 됐나 */
    protected boolean result(Player p, HomesResult r) {
        if (r == null) return false;
        if (r.ok()) {
            ok(p);
            if (r.message() != null && !r.message().isBlank()) Text.send(p, "<gray>" + r.message());
        } else {
            deny(p);
            if (r.message() != null && !r.message().isBlank()) Text.error(p, r.message());
        }
        return r.ok();
    }

    /** 플레이어 머리 아이콘 (스킨은 클라이언트가 이름·uuid 로 찾음 — 서버가 기다리지 않음). */
    static ItemStack head(UUID id, String name, String title, List<String> lore) {
        ItemStack s = Button.icon(Material.PLAYER_HEAD, title, lore);
        try {
            if (id != null) s.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(Bukkit.createProfile(id, name)));
        } catch (Throwable ignored) {
            // 기본 머리
        }
        return s;
    }

    protected void gold(int slot, Player p) {
        deco(slot, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(services.data().get(p).gold()) + " G", List.of()));
    }
}
