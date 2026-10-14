package kr.labyrinth.ui.menus;

import java.util.List;
import java.util.function.Consumer;
import kr.labyrinth.Services;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.ClickContext;
import kr.labyrinth.ui.Menu;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 미궁 메뉴 공통 기반: 글리프 배경 제목({@link UiTheme#title}), 글리프가 없을 때 테두리, 효과음, 돌아가기 버튼.
 */
public abstract class LabMenu extends Menu {

    protected final Services services;
    protected final String menuId;
    protected final int rows;

    protected LabMenu(Services services, String menuId, int rows, String miniTitle) {
        super(rows, UiTheme.title(menuId, rows, miniTitle));
        this.services = services;
        this.menuId = menuId;
        this.rows = rows;
    }

    /** 테두리(글리프 없을 때만) 후 내용. */
    @Override
    protected final void build(Player viewer) {
        UiTheme.frame(this, menuId, rows);
        draw(viewer);
    }

    protected abstract void draw(Player viewer);

    protected void click(Player p) { p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.5f, 1.3f); }

    protected void ok(Player p) { p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.6f, 1.2f); }

    protected void deny(Player p) { p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.0f); }

    /** 아래 줄 왼쪽: 돌아가기 (back 이 null 이면 닫기). */
    protected void backButton(int slot, Consumer<Player> back) {
        if (back == null) {
            set(slot, UiTheme.close(), ctx -> ctx.player().closeInventory());
        } else {
            set(slot, UiTheme.back(), ctx -> {
                click(ctx.player());
                back.accept(ctx.player());
            });
        }
    }

    protected ItemStack icon(Material m, String name, List<String> lore) { return Button.icon(m, name, lore); }

    protected ItemStack model(String itemId, Material fallback, String name, List<String> lore) {
        return UiTheme.item(itemId, fallback, name, lore);
    }

    /** 긴 설명을 약 width 글자로 줄바꿈 (MiniMessage 태그는 걷어 낸 뒤, 앞에 prefix). */
    public static List<String> wrap(String text, int width, String prefix) {
        List<String> out = new java.util.ArrayList<>();
        if (text == null) return out;
        String plain = kr.labyrinth.core.Text.strip(text).replace('\n', ' ').trim();
        StringBuilder line = new StringBuilder();
        for (String word : plain.split(" ")) {
            if (line.length() > 0 && line.length() + 1 + word.length() > width) {
                out.add(prefix + kr.labyrinth.core.Text.escape(line.toString()));
                line.setLength(0);
            }
            if (line.length() > 0) line.append(' ');
            line.append(word);
        }
        if (line.length() > 0) out.add(prefix + kr.labyrinth.core.Text.escape(line.toString()));
        return out;
    }

    /** 명령 실행 후 메뉴 갱신 (다른 모듈 기능을 명령으로 부를 때 — 메시지·검사는 그쪽이 한다). */
    protected void command(ClickContext ctx, String command, boolean close) {
        Player p = ctx.player();
        click(p);
        if (close) p.closeInventory();
        p.performCommand(command);
        if (!close) services.plugin().getServer().getScheduler().runTaskLater(services.plugin(), this::refresh, 2L);
    }
}
