package kr.labyrinth.classes;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.BerserkerSkills;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCreativeEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.ItemStack;

/**
 * 직업 스킬 키 (ARCHITECTURE §4 스킬 입력): 미궁 무기를 들고 있을 때
 * F(손 바꾸기)=SWAP, 웅크리기+F=SNEAK_SWAP, Q(버리기)=DROP, 웅크리기+Q=SNEAK_DROP.
 * 손 바꾸기·Q 버리기는 취소한다. <b>인벤토리 창에서 끌어서/Q 로 버리기는 허용</b>(같은 틱의 인벤토리 클릭으로 구분).
 * 좌·우클릭(무기 스킬, items 담당)은 건드리지 않는다.
 */
final class SkillInputListener implements Listener {

    private final Services services;
    private final LabyrinthClassService classes;
    /** 마지막 인벤토리 창 조작 틱 (창에서 버린 것인지 구분). */
    private final Map<UUID, Integer> lastWindowTick = new ConcurrentHashMap<>();

    SkillInputListener(Services services, LabyrinthClassService classes) {
        this.services = services;
        this.classes = classes;
    }

    private boolean holdsWeapon(Player p) {
        return services.items().isLabyrinthWeapon(p.getInventory().getItemInMainHand());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        if (!holdsWeapon(p)) return;
        e.setCancelled(true);
        classes.handleSkillInput(p, p.isSneaking() ? "SNEAK_SWAP" : "SWAP");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWindowClick(InventoryClickEvent e) { markWindow(e.getWhoClicked()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWindowDrag(InventoryDragEvent e) { markWindow(e.getWhoClicked()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onCreative(InventoryCreativeEvent e) { markWindow(e.getWhoClicked()); }

    /** 창을 닫을 때 커서에 든 아이템이 떨어지는 경우도 창 조작으로 본다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onWindowClose(org.bukkit.event.inventory.InventoryCloseEvent e) { markWindow(e.getPlayer()); }

    private void markWindow(org.bukkit.entity.HumanEntity h) {
        lastWindowTick.put(h.getUniqueId(), Bukkit.getCurrentTick());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent e) {
        Player p = e.getPlayer();
        Integer windowTick = lastWindowTick.get(p.getUniqueId());
        if (windowTick != null && Bukkit.getCurrentTick() - windowTick <= 1) return; // 인벤토리 창에서 버림 → 허용
        ItemStack dropped = e.getItemDrop().getItemStack();
        if (!services.items().isLabyrinthWeapon(dropped)) return;
        ItemStack hand = p.getInventory().getItemInMainHand();
        // Q 는 주 손 아이템을 버린다: 버린 직후 주 손은 비어 있거나(장비는 1개) 같은 아이템의 나머지
        if (!(hand.getType().isAir() || hand.isSimilar(dropped))) return;
        e.setCancelled(true);
        classes.handleSkillInput(p, p.isSneaking() ? "SNEAK_DROP" : "DROP");
    }

    /** 미궁 무기로 바꿔 들면 스킬 키 안내를 잠깐 보여 준다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        Player p = e.getPlayer();
        ItemStack next = p.getInventory().getItem(e.getNewSlot());
        if (next != null && services.items().isLabyrinthWeapon(next)) {
            Bukkit.getScheduler().runTask(services.plugin(), () -> {
                if (p.isOnline() && holdsWeapon(p)) classes.showSkillBar(p);
            });
        }
    }

    /** 도약·순간이동 계열 스킬 직후 낙하 피해 무시. */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFall(EntityDamageEvent e) {
        if (e.getCause() == EntityDamageEvent.DamageCause.FALL && e.getEntity() instanceof Player p
                && BerserkerSkills.LEAPING.contains(p.getUniqueId())) {
            e.setCancelled(true);
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        lastWindowTick.remove(e.getPlayer().getUniqueId());
        BerserkerSkills.LEAPING.remove(e.getPlayer().getUniqueId());
    }
}
