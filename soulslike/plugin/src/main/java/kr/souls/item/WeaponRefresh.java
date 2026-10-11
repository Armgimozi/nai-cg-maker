package kr.souls.item;

import com.destroystokyo.paper.event.inventory.PrepareResultEvent;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.PrepareAnvilEvent;
import org.bukkit.event.inventory.PrepareGrindstoneEvent;
import org.bukkit.event.inventory.PrepareItemCraftEvent;
import org.bukkit.event.inventory.PrepareSmithingEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 예전 판의 souls 무기를 지금 판으로 (9.8, 검토 stale-weapons-outside-inventory). 아이템에는 설명 칸 (번역 열쇠와 그 대체 글) 이 구워져
 * 있어서, 판이 바뀌거나 weapons.yml 을 고쳐도 이미 만든 아이템은 옛 줄을 보인다 (없어진 열쇠는 영어 대체 글로). 그래서 아이템이 손에
 * 들어올 수 있는 길마다 ItemFactory.refreshed 로 견주어 바꾼다:
 * <ul>
 *   <li>접속 (StartFlow 가 출신 단계에서 부른다), /souls reload (Souls.reloadAll): 그 사람의 인벤토리 전체.</li>
 *   <li>줍기: 땅에 떨어진 예전 무기를 주우면 다음 틱에 인벤토리를 (줍는 사건의 아이템은 이미 넣을 사본이 정해져 있어 바꿀 수 없다).</li>
 *   <li>상자·엔더 상자 같은 창을 열 때: 그 창 (위쪽) 의 칸.</li>
 * </ul>
 * 바꾼 것이 있으면 주손 막기 성분 (WeaponGuard) 과 무게 (Load) 를 다시 맞추고 시험 줄 {@code WEAPON_REFRESH n= where=join|reload|pickup|container}.
 * <p>
 * souls 무기는 모루·대장장이 작업대·숫돌·제작대의 재료가 되지 않는다 (검토 P0-5): 결과 칸을 비운다. 창·미늘창의 껍데기 돌창은
 * #minecraft:spears 라 모루가 화염·밀치기·약탈·날카로움·강타·돌진·내구성·수선 책을 붙일 수 있고 (부싯돌 무기는 아무것도 받지 않았다),
 * 방패 껍데기는 제작대에서 깃발을 받으면 이름이 바닐라 방패 이름 ("빨간 방패") 으로 바뀌며, 부싯돌 껍데기는 부싯돌과 부시의 재료다.
 * 이미 붙은 것은 ItemFactory.refreshed 가 지운다. 시험 줄 {@code WEAPON_CRAFT_DENY where=anvil|smithing|grindstone|craft}.
 */
public final class WeaponRefresh implements Listener {
    private final Souls plugin;

    public WeaponRefresh(Souls plugin) {
        this.plugin = plugin;
    }

    /** p 의 인벤토리를 지금 판으로. 바꾼 수. */
    public int player(Player p, String where) {
        int n = ItemFactory.refreshWeapons(p.getInventory(), plugin.weapons());
        if (n > 0) {
            if (plugin.weaponGuard() != null) plugin.weaponGuard().refresh(p);
            if (plugin.load() != null) plugin.load().refresh(p);
            plugin.test(p, "WEAPON_REFRESH n=" + n + " where=" + where);
        }
        return n;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        if (ItemFactory.refreshed(e.getItem().getItemStack(), plugin.weapons()) == null) return;
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) player(p, "pickup");
        });
    }

    private boolean anyWeapon(ItemStack[] items) {
        for (ItemStack it : items) {
            if (it != null && !it.isEmpty() && plugin.weapons().of(it) != null) return true;
        }
        return false;
    }

    private void deny(InventoryView view, String where) {
        if (view.getPlayer() instanceof Player p) plugin.test(p, "WEAPON_CRAFT_DENY where=" + where);
    }

    private void denyResult(PrepareResultEvent e, String where) {
        if (!anyWeapon(e.getInventory().getContents())) return;
        e.setResult(null);
        deny(e.getView(), where);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onAnvil(PrepareAnvilEvent e) {
        denyResult(e, "anvil");
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onSmithing(PrepareSmithingEvent e) {
        denyResult(e, "smithing");
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onGrindstone(PrepareGrindstoneEvent e) {
        denyResult(e, "grindstone");
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCraft(PrepareItemCraftEvent e) {
        if (!anyWeapon(e.getInventory().getMatrix())) return;
        e.getInventory().setResult(null);
        deny(e.getView(), "craft");
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        Inventory top = e.getView().getTopInventory();
        if (top instanceof PlayerInventory) return;
        int n = ItemFactory.refreshWeapons(top, plugin.weapons());
        if (n > 0 && e.getPlayer() instanceof Player p) plugin.test(p, "WEAPON_REFRESH n=" + n + " where=container");
    }
}
