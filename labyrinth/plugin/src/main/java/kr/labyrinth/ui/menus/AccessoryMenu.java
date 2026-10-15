package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.ClickContext;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 장신구 2칸 (PlayerData accessories). 아래 내 인벤토리에서 장신구를 클릭하면 빈 칸(없으면 1번 칸과 교체)에 장착,
 * 위 칸을 클릭하면 해제(인벤토리로). 스탯은 items 담당 EquipmentListener 가 이 칸을 읽어 반영한다.
 */
public final class AccessoryMenu extends LabMenu {

    private static final int[] SLOTS = {21, 23};

    public AccessoryMenu(Services services) {
        super(services, "accessories", 5, "<#c79bff>장신구");
    }

    @Override
    protected boolean allowBottomClicks() { return true; }

    private ItemStack load(PlayerData d, int i) {
        byte[] b = d.accessory(i);
        if (b == null || b.length == 0) return null;
        try {
            return ItemStack.deserializeBytes(b);
        } catch (Throwable t) {
            return null;
        }
    }

    @Override
    protected void draw(Player p) {
        PlayerData d = services.data().get(p);
        deco(4, Button.icon(Material.AMETHYST_CLUSTER, "<#c79bff><b>장신구 2칸</b>",
                List.of("<gray>아래 내 가방에서 장신구를 클릭하면 장착합니다.", "<gray>위 칸을 클릭하면 가방으로 돌려받습니다.",
                        "<dark_gray>장신구는 요구 능력치가 없습니다 — 어느 직업이든 장착할 수 있습니다.")));
        for (int i = 0; i < SLOTS.length; i++) {
            ItemStack acc = load(d, i);
            final int idx = i;
            if (acc == null) {
                set(SLOTS[i], Button.icon(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "<gray>장신구 칸 " + (i + 1),
                        List.of("<dark_gray>비어 있음")), ctx -> deny(ctx.player()));
            } else {
                // 예전 판 설명("요구 레벨" 등)도 지금 규칙으로 다시 그려 보여 준다 (저장된 아이템은 그대로)
                ItemStack shown = acc.clone();
                services.items().refresh(shown);
                set(SLOTS[i], shown, ctx -> unequip(ctx.player(), idx));
            }
        }
        // 합계 미리보기
        List<String> sum = new ArrayList<>();
        for (int i = 0; i < SLOTS.length; i++) {
            ItemStack acc = load(d, i);
            if (acc == null) continue;
            Map<String, Double> st = services.items().rolledStats(acc);
            st.forEach((k, v) -> sum.add("<gray>· " + kr.labyrinth.items.ItemTooltip.statName(k) + " <white>" + kr.labyrinth.items.ItemTooltip.formatStat(k, v)));
        }
        if (!sum.isEmpty()) deco(31, Button.icon(Material.BOOK, "<#7fd8ff>장신구 효과", sum));
        backButton(36, MainMenu::reopen);
    }

    @Override
    protected void onBottomClick(ClickContext ctx) {
        Player p = ctx.player();
        ItemStack clicked = ctx.event().getCurrentItem();
        if (clicked == null || clicked.isEmpty()) return;
        ItemDef def = services.items().defOf(clicked).orElse(null);
        if (def == null || def.type() != ItemType.ACCESSORY) {
            deny(p);
            services.hud().actionBar(p, Text.mm("<#ff6b6b>장신구만 장착할 수 있습니다."), 30);
            return;
        }
        PlayerData d = services.data().get(p);
        // 장신구는 레벨·능력치 조건 없이 장착한다
        int target = -1;
        for (int i = 0; i < SLOTS.length; i++) if (load(d, i) == null) { target = i; break; }
        ItemStack one = clicked.asOne();
        ItemStack previous = null;
        if (target < 0) {
            target = 0;
            previous = load(d, 0);
        }
        int invSlot = ctx.slot();
        ItemStack remain = clicked.getAmount() > 1 ? clicked.asQuantity(clicked.getAmount() - 1) : null;
        p.getInventory().setItem(invSlot, remain);
        d.accessory(target, one.serializeAsBytes());
        if (previous != null) {
            var left = p.getInventory().addItem(previous);
            left.values().forEach(s -> p.getWorld().dropItem(p.getLocation(), s));
        }
        services.stats().markDirty(p);
        services.stats().recalc(p);
        p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.8f, 1.3f);
        refresh();
    }

    private void unequip(Player p, int idx) {
        PlayerData d = services.data().get(p);
        ItemStack acc = load(d, idx);
        if (acc == null) return;
        if (p.getInventory().firstEmpty() < 0) {
            deny(p);
            Text.error(p, "가방에 빈 칸이 없습니다.");
            return;
        }
        d.accessory(idx, null);
        services.items().refresh(acc);
        p.getInventory().addItem(acc);
        services.stats().markDirty(p);
        services.stats().recalc(p);
        click(p);
        refresh();
    }
}
