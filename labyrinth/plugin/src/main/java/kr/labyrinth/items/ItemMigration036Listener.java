package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BundleContents;
import io.papermc.paper.datacomponent.item.ItemContainerContents;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Predicate;
import kr.labyrinth.Services;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.mine.MineNames;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.DoubleChest;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.ItemFrame;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Vehicle;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.inventory.BlockInventoryHolder;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 0.3.6 옛 광물 재료 바꾸기의 입구 ({@link ItemMigration036}, 계약 §2.10 · R §2-7):
 * <ul>
 *   <li>접속: 가방(방어구·보조손 칸 포함)·엔더 상자 + 첫 접속 안내 1번 (ext {@code mat036.notice}, 예전에 들어온 적 있는 사람만)</li>
 *   <li>보관함(상자·통·셜커·수레 등, 엔더 상자 포함)을 열 때 · 바닥에서 주운 뒤 · 손에 들 때 · 창을 닫은 뒤(판매 바구니·대장간 창에서 돌려받은 것)</li>
 *   <li>셜커 상자·꾸러미 안 — 아이템 안에 든 것까지</li>
 *   <li>액자·갑옷 거치대·바닥 아이템·보관함 달린 탈것: 청크의 엔티티가 올라올 때 ({@code EntitiesLoadEvent}) + 켤 때 이미 올라온 것</li>
 * </ul>
 * 바꾼 아이템은 ItemService 로 새로 만든 것이라 원래 있던 같은 재료와 겹쳐진다. 새 id 가 content 에 없으면(손으로 고친 items.yml)
 * 아무것도 바꾸지 않고 시작 때 경고만 한다.
 */
final class ItemMigration036Listener implements Listener {

    private final Services services;
    private final StackAccess access;
    private final Set<UUID> pending = ConcurrentHashMap.newKeySet();

    ItemMigration036Listener(Services services) {
        this.services = services;
        this.access = new StackAccess(services);
    }

    private Predicate<String> exists() { return id -> services.content().item(id) != null; }

    /** 켤 때·다시 읽을 때: 새 id 가 없으면 경고 1줄, 이미 접속한 사람·이미 올라온 엔티티를 한 번 훑는다. */
    void start() {
        List<String> missing = ItemMigration036.missingTargets(exists());
        if (!missing.isEmpty()) {
            Log.warn("[0.3.6 재료 바꿈] content/items.yml 에 새 재료가 없어 옛 광물 재료를 바꾸지 않습니다: " + String.join(", ", missing)
                    + " — items.yml 을 새 판으로 바꾸고 /labadmin reload 하세요.");
        }
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            for (Player p : Bukkit.getOnlinePlayers()) sweepPlayer(p);
            for (World w : Bukkit.getWorlds()) for (Entity e : w.getEntities()) sweepEntity(e);
        });
    }

    // ── 플레이어 ─────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        boolean old = p.hasPlayedBefore();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline()) return;
            int n = sweepPlayer(p);
            notice(p, old || n > 0);
        }, 3L);
    }

    private void notice(Player p, boolean show) {
        PlayerData d = services.data().get(p);
        if (Boolean.TRUE.equals(d.ext().get(MineNames.EXT_MAT036_NOTICE))) return;
        d.ext().put(MineNames.EXT_MAT036_NOTICE, true);
        d.markDirty();
        if (show) Text.send(p, ItemMigration036.NOTICE);
    }

    /** 가방(방어구·보조손 포함) · 엔더 상자 · 커서. → 바꾼 칸 수. */
    int sweepPlayer(Player p) {
        int n = sweep(p.getInventory());
        n += sweep(p.getEnderChest());
        ItemStack cursor = p.getItemOnCursor();
        ItemStack c = convert(cursor);
        if (c != cursor) {
            p.setItemOnCursor(c);
            n++;
        }
        return n;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        Inventory top = e.getInventory();
        if (isStorage(top)) sweep(top);
    }

    /** 창을 닫으면(판매 바구니·대장간 창이 돌려준 것 포함) 다음 틱에 가방을 훑는다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (e.getPlayer() instanceof Player p) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        String id = access.itemId(e.getItem().getItemStack());
        if (ItemMigration036.retired(id) || access.contents(e.getItem().getItemStack()) != null) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        Player p = e.getPlayer();
        int slot = e.getNewSlot();
        ItemStack held = p.getInventory().getItem(slot);
        if (held == null || held.isEmpty()) return;
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            ItemStack it = p.getInventory().getItem(slot);
            ItemStack c = convert(it);
            if (c != it) p.getInventory().setItem(slot, c);
        });
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { pending.remove(e.getPlayer().getUniqueId()); }

    private void later(Player p) {
        if (!pending.add(p.getUniqueId())) return;
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            pending.remove(p.getUniqueId());
            if (p.isOnline()) sweepPlayer(p);
        });
    }

    // ── 엔티티 (액자 · 갑옷 거치대 · 바닥 아이템 · 보관함 달린 탈것) ─────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) sweepEntity(en);
    }

    void sweepEntity(Entity en) {
        try {
            if (en instanceof Item it) {
                ItemStack s = it.getItemStack();
                ItemStack c = convert(s);
                if (c != s) it.setItemStack(c);
            } else if (en instanceof ItemFrame f) {
                ItemStack s = f.getItem();
                ItemStack c = convert(s);
                if (c != s) f.setItem(c, false);
            } else if (en instanceof LivingEntity le && !(en instanceof Player)) {
                EntityEquipment eq = le.getEquipment();
                if (eq != null) {
                    for (EquipmentSlot slot : EquipmentSlot.values()) {
                        if (!le.canUseEquipmentSlot(slot)) continue;
                        ItemStack s = eq.getItem(slot);
                        ItemStack c = convert(s);
                        if (c != s) eq.setItem(slot, c);
                    }
                }
            }
            if (en instanceof InventoryHolder h && !(en instanceof Player)) sweep(h.getInventory());
        } catch (RuntimeException ex) {
            Log.warnOnce("mat036-entity-" + en.getType(), "[0.3.6 재료 바꿈] " + en.getType() + " 의 아이템을 바꾸지 못했습니다: " + ex);
        }
    }

    // ── 공통 ─────────────────────────────────────────────────────────────

    private ItemStack convert(ItemStack s) {
        if (s == null || s.isEmpty()) return s;
        return ItemMigration036.convert(s, access, exists());
    }

    /** 보관함 칸을 모두 바꾼다 (바뀐 칸만 다시 넣음). → 바꾼 칸 수. */
    private int sweep(Inventory inv) {
        if (inv == null) return 0;
        ItemStack[] before = inv.getContents();
        ItemStack[] after = before.clone();
        int n = ItemMigration036.convertAll(after, access, exists());
        if (n == 0) return 0;
        for (int i = 0; i < after.length; i++) if (after[i] != before[i]) inv.setItem(i, after[i]);
        return n;
    }

    /** 블록 보관함·엔더 상자·보관함 달린 탈것만 (플러그인 메뉴 창은 아이콘 사본이라 건드리지 않음). */
    private static boolean isStorage(Inventory inv) {
        if (inv.getType() == InventoryType.ENDER_CHEST) return true;
        InventoryHolder h = inv.getHolder(false);
        return h instanceof BlockInventoryHolder || h instanceof DoubleChest || h instanceof Vehicle;
    }

    /** ItemStack 보기 — PDC item_id · 셜커 상자(CONTAINER)·꾸러미(BUNDLE_CONTENTS) 안 · ItemService 로 새로 만들기. */
    static final class StackAccess implements ItemMigration036.Access<ItemStack> {
        private final Services services;

        StackAccess(Services services) { this.services = services; }

        @Override
        public String itemId(ItemStack s) {
            if (s == null || s.isEmpty()) return null;
            return s.getPersistentDataContainer().get(Keys.ITEM_ID, PersistentDataType.STRING);
        }

        @Override
        public int amount(ItemStack s) { return s == null ? 0 : s.getAmount(); }

        @Override
        public List<ItemStack> contents(ItemStack s) {
            if (s == null || s.isEmpty()) return null;
            ItemContainerContents box = s.getData(DataComponentTypes.CONTAINER);
            if (box != null) return new ArrayList<>(box.contents());
            BundleContents bundle = s.getData(DataComponentTypes.BUNDLE_CONTENTS);
            if (bundle != null) return new ArrayList<>(bundle.contents());
            return null;
        }

        @Override
        public ItemStack withContents(ItemStack s, List<ItemStack> contents) {
            ItemStack copy = s.clone();
            List<ItemStack> in = new ArrayList<>(contents.size());
            for (ItemStack c : contents) in.add(c == null ? ItemStack.empty() : c);
            if (s.hasData(DataComponentTypes.CONTAINER)) copy.setData(DataComponentTypes.CONTAINER, ItemContainerContents.containerContents(in));
            else copy.setData(DataComponentTypes.BUNDLE_CONTENTS, BundleContents.bundleContents(in));
            return copy;
        }

        @Override
        public ItemStack fresh(String id, int amount) { return services.items().create(id, amount); }
    }
}
