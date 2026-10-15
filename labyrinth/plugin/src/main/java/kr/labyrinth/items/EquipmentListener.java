package kr.labyrinth.items;

import com.destroystokyo.paper.event.player.PlayerArmorChangeEvent;
import io.papermc.paper.datacomponent.DataComponentTypes;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatContributor;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 장비 → StatService 기여 + 착용 조건 + 활 화살.
 * <ul>
 *   <li>주손 무기(피해 포함 전 스탯) · 방어구 4칸 · 보조손 방패 · 장신구 2칸(PlayerData) · 세트 효과(착용 개수 이상 누적)</li>
 *   <li>레벨 조건을 못 맞춘 장비는 스탯이 들어가지 않는다(직업 제한은 없음). 방어구는 착용 즉시 인벤토리로 되돌린다.</li>
 *   <li>미궁 활을 들면 '미궁 화살'(무한, 1개)을 넣어 준다 — 바닐라 활은 화살이 있어야 당겨진다.</li>
 * </ul>
 */
final class EquipmentListener implements Listener, StatContributor {

    static final NamespacedKey LAB_ARROW = Keys.key("lab_arrow");

    private final Services services;
    /** 장신구 역직렬화 캐시: uuid → (슬롯 → [바이트 해시, 스택]). */
    private final Map<UUID, Object[][]> accessoryCache = new ConcurrentHashMap<>();

    EquipmentListener(Services services) { this.services = services; }

    // ── StatContributor ──────────────────────────────────────────────────

    @Override
    public void contribute(Player p, StatBlock block) {
        PlayerData d = services.data().get(p);
        int level = d.level();
        String cls = d.classId();
        ItemService items = services.items();
        Map<String, Integer> setCounts = new HashMap<>();
        PlayerInventory inv = p.getInventory();

        ItemStack main = inv.getItemInMainHand();
        items.defOf(main).ifPresent(def -> {
            if (def.isWeapon() && EquipRules.usable(def, level, cls)) block.addAll(items.rolledStats(main));
        });
        for (EquipmentSlot slot : new EquipmentSlot[] {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET}) {
            ItemStack it = inv.getItem(slot);
            items.defOf(it).ifPresent(def -> {
                if (def.type() == ItemType.ARMOR && !def.isShield() && EquipRules.usable(def, level, cls)) {
                    block.addAll(items.rolledStats(it));
                    if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
                }
            });
        }
        ItemStack off = inv.getItemInOffHand();
        items.defOf(off).ifPresent(def -> {
            if (def.isShield() && EquipRules.usable(def, level, cls)) {
                block.addAll(items.rolledStats(off));
                if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
            }
        });
        for (int i = 0; i < PlayerData.ACCESSORY_SLOTS; i++) {
            ItemStack acc = accessory(p, d, i);
            if (acc == null) continue;
            items.defOf(acc).ifPresent(def -> {
                if (def.type() == ItemType.ACCESSORY && EquipRules.usable(def, level, cls)) {
                    block.addAll(items.rolledStats(acc));
                    if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
                }
            });
        }
        setCounts.forEach((setId, count) -> {
            ItemSetDef set = services.content().sets().get(setId);
            if (set == null) return;
            set.bonuses().headMap(count, true).values().forEach(block::addAll);
        });
    }

    private ItemStack accessory(Player p, PlayerData d, int slot) {
        byte[] bytes = d.accessory(slot);
        if (bytes == null || bytes.length == 0) return null;
        int hash = java.util.Arrays.hashCode(bytes);
        Object[][] cache = accessoryCache.computeIfAbsent(p.getUniqueId(), u -> new Object[PlayerData.ACCESSORY_SLOTS][]);
        Object[] c = cache[slot];
        if (c != null && (int) c[0] == hash) return (ItemStack) c[1];
        ItemStack s;
        try {
            s = ItemStack.deserializeBytes(bytes);
        } catch (Throwable t) {
            s = null;
        }
        cache[slot] = new Object[] {hash, s};
        return s;
    }

    // ── 착용 조건 ─────────────────────────────────────────────────────────

    /** 착용 조건 문구 (직업 제한은 없어 레벨뿐). */
    static String problemText(Services services, ItemDef def, EquipRules.Problem problem) {
        if (problem == EquipRules.Problem.LEVEL) return "레벨 " + def.levelReq() + " 이상 필요";
        return "";
    }

    EquipRules.Problem problem(Player p, ItemDef def) {
        PlayerData d = services.data().get(p);
        return EquipRules.check(def, d.level(), d.classId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onArmor(PlayerArmorChangeEvent e) {
        Player p = e.getPlayer();
        ItemStack now = e.getNewItem();
        ItemDef def = services.items().defOf(now).orElse(null);
        if (def == null || def.type() != ItemType.ARMOR) return;
        EquipRules.Problem problem = problem(p, def);
        if (problem == EquipRules.Problem.NONE) return;
        EquipmentSlot slot = e.getSlot();
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (!p.isOnline()) return;
            ItemStack cur = p.getInventory().getItem(slot);
            ItemDef curDef = services.items().defOf(cur).orElse(null);
            if (curDef == null || !curDef.id().equals(def.id())) return;
            p.getInventory().setItem(slot, null);
            GearItemService.deliver(p, cur);
            Text.error(p, def.name() + " <gray>— " + problemText(services, def, problem) + " — 착용할 수 없습니다.");
            services.stats().markDirty(p);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        Player p = e.getPlayer();
        ItemStack it = p.getInventory().getItem(e.getNewSlot());
        ItemDef def = services.items().defOf(it).orElse(null);
        if (def == null || !def.isWeapon()) return;
        EquipRules.Problem problem = problem(p, def);
        if (problem != EquipRules.Problem.NONE) {
            services.hud().actionBar(p, Text.mm("<#ff6b6b>⚠ " + def.name() + " <gray>— " + problemText(services, def, problem)
                    + " (능력치·무기 스킬 미적용)"), 50);
        }
        if (GearItemService.isBow(def)) Bukkit.getScheduler().runTask(services.plugin(), () -> ensureArrow(p));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            refreshLore(e.getPlayer());
            ensureArrow(e.getPlayer());
        }, 5L);
    }

    /**
     * 가방 속 미궁 아이템 이름·설명을 지금 규칙으로 다시 쓴다 (굴린 스탯·강화 단계는 그대로). 예전 판에서 받은 장비의 "직업 ○○"(옛 착용 제한)
     * 문구가 "추천 직업" 으로 바뀌는 식 — 생성·강화 때와 같은 렌더러(ItemService.refresh)로 그리고, 결과가 같으면 건드리지 않는다.
     */
    private void refreshLore(Player p) {
        if (!p.isOnline()) return;
        PlayerInventory inv = p.getInventory();
        for (int i = 0; i < inv.getSize(); i++) {
            ItemStack it = inv.getItem(i);
            ItemDef def = services.items().defOf(it).orElse(null);
            if (def == null) continue;
            ItemStack copy = it.clone();
            services.items().refresh(copy);
            if (copy.equals(it)) continue;
            inv.setItem(i, copy);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerRespawnEvent e) {
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> ensureArrow(e.getPlayer()), 2L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { accessoryCache.remove(e.getPlayer().getUniqueId()); }

    /** 미궁 화살은 버릴 수 없다(무한 1개짜리라 의미 없음, 바닥 쓰레기 방지). */
    @EventHandler(ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent e) {
        if (isLabArrow(e.getItemDrop().getItemStack())) e.getItemDrop().remove();
    }

    static boolean isLabArrow(ItemStack s) {
        return s != null && s.getType() == Material.ARROW
                && s.getPersistentDataContainer().has(LAB_ARROW, PersistentDataType.BYTE);
    }

    /** 미궁 활을 들고 있는데 화살이 없으면 무한 화살 1개를 넣어 준다. */
    void ensureArrow(Player p) {
        if (!p.isOnline()) return;
        ItemDef def = services.items().defOf(p.getInventory().getItemInMainHand()).orElse(null);
        if (def == null || !GearItemService.isBow(def)) return;
        for (ItemStack s : p.getInventory().getContents()) {
            if (s != null && (s.getType() == Material.ARROW || s.getType() == Material.SPECTRAL_ARROW
                    || s.getType() == Material.TIPPED_ARROW)) return;
        }
        ItemStack arrow = ItemStack.of(Material.ARROW);
        arrow.setData(DataComponentTypes.ITEM_NAME, Text.item("<#c8d6ff>미궁 화살 <dark_gray>(무한)"));
        arrow.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        arrow.editPersistentDataContainer(pdc -> pdc.set(LAB_ARROW, PersistentDataType.BYTE, (byte) 1));
        arrow.setData(DataComponentTypes.LORE, io.papermc.paper.datacomponent.item.ItemLore.lore(
                Text.itemLines(java.util.List.of("<gray>미궁 활이 쓰는 마력 화살. 줄지 않는다."))));
        p.getInventory().addItem(arrow);
    }
}
