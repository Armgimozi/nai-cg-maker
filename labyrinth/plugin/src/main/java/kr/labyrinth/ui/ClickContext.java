package kr.labyrinth.ui;

import org.bukkit.entity.Player;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.InventoryClickEvent;

/** 메뉴 버튼 클릭 정보. event 는 이미 취소된 상태다. */
public record ClickContext(Player player, Menu menu, int slot, ClickType click, InventoryClickEvent event) {
    public boolean isLeft() { return click.isLeftClick(); }
    public boolean isRight() { return click.isRightClick(); }
    public boolean isShift() { return click.isShiftClick(); }
}
