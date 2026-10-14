package kr.labyrinth.ui;

import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;

/**
 * 상자 GUI 메뉴 기반 클래스 (InventoryHolder 방식). {@link MenuListener} 가 모든 클릭을 취소하고
 * 버튼 콜백만 실행하므로 아이템을 빼 갈 수 없다(클릭 보호).
 * <pre>
 * class StatsMenu extends Menu {
 *     StatsMenu(Player p) { super(6, Text.mm("스탯")); }
 *     protected void build(Player viewer) {
 *         set(13, Button.icon(Material.IRON_SWORD, "&lt;red&gt;힘", List.of()), ctx -> { ...; refresh(); });
 *     }
 * }
 * new StatsMenu(p).open(p);
 * </pre>
 * 플레이어 인벤토리 쪽 클릭을 받아야 하는 메뉴(장신구 장착 등)는 {@link #allowBottomClicks()} 를 true 로 하고
 * {@link #onBottomClick} 을 구현한다.
 */
public abstract class Menu implements InventoryHolder {

    private final Inventory inventory;
    private final Map<Integer, Button> buttons = new HashMap<>();
    private Player viewer;

    protected Menu(int rows, Component title) {
        this.inventory = Bukkit.createInventory(this, Math.max(1, Math.min(6, rows)) * 9, title);
    }

    @Override
    public Inventory getInventory() { return inventory; }

    public Player viewer() { return viewer; }

    /** 내용을 채운다. open/refresh 때마다 비운 뒤 호출된다. */
    protected abstract void build(Player viewer);

    public void open(Player player) {
        this.viewer = player;
        redraw();
        player.openInventory(inventory);
        onOpen(player);
    }

    /** 다시 그리기 (버튼 상태가 바뀐 뒤). */
    public void refresh() {
        if (viewer != null) redraw();
    }

    private void redraw() {
        buttons.clear();
        inventory.clear();
        build(viewer);
    }

    public void set(int slot, ItemStack icon, Consumer<ClickContext> action) {
        set(slot, new Button(icon, action));
    }

    public void set(int slot, Button button) {
        if (slot < 0 || slot >= inventory.getSize()) return;
        inventory.setItem(slot, button.icon());
        if (button.action() != null) buttons.put(slot, button);
        else buttons.remove(slot);
    }

    public void deco(int slot, ItemStack icon) { set(slot, Button.deco(icon)); }

    /** 비어 있는 칸을 채운다. */
    public void fillEmpty(ItemStack filler) {
        for (int i = 0; i < inventory.getSize(); i++) {
            if (inventory.getItem(i) == null) inventory.setItem(i, filler);
        }
    }

    public int size() { return inventory.getSize(); }

    Button button(int slot) { return buttons.get(slot); }

    protected void onOpen(Player player) {}

    protected void onClose(Player player) {}

    /** true 면 아래(플레이어 인벤토리) 클릭을 취소하지 않고 {@link #onBottomClick} 에 넘긴다. */
    protected boolean allowBottomClicks() { return false; }

    protected void onBottomClick(ClickContext ctx) {}
}
