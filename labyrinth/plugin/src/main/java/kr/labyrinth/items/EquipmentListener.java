package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.event.player.PlayerSwapWithEquipmentSlotEvent;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatContributor;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockDispenseArmorEvent;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 장비 → StatService 기여 + 착용 조건(요구 능력치) + 활 화살.
 * <ul>
 *   <li>주손 무기(피해 포함 전 스탯) · 방어구 4칸 · 보조손 방패 · 장신구 2칸(PlayerData) · 세트 효과(착용 개수 이상 누적)</li>
 *   <li>요구 능력치({@link EquipRules}, 판정 = 직업 기본 + 분배 + 칭호)를 못 맞춘 방어구·방패는 <b>입는 동작을 막는다</b>
 *       (방어구 칸·보조손 칸에 놓기, 숫자키·F 바꾸기, Shift 클릭 자동 착용, 우클릭 착용, 끌어 놓기, 발사기).</li>
 *   <li>이미 입은 장비가 분배 초기화·전직·칭호 해제로 모자라게 되면 <b>입은 채로 두고</b> 스탯만 빠진다 (한 번 경고).
 *       무기는 들 수 있지만 스탯·무기 스킬이 없다 (손에 들 때 한 번 경고). 아이템을 지우거나 떨구지 않는다. 장신구는 조건 없음.</li>
 *   <li>미궁 활을 들면 '미궁 화살'(무한, 1개)을 넣어 준다 — 바닐라 활은 화살이 있어야 당겨진다.</li>
 * </ul>
 */
final class EquipmentListener implements Listener, StatContributor {

    static final NamespacedKey LAB_ARROW = Keys.key("lab_arrow");

    private final Services services;
    /** 장신구 역직렬화 캐시: uuid → (슬롯 → [바이트 해시, 스택]). */
    private final Map<UUID, Object[][]> accessoryCache = new ConcurrentHashMap<>();
    /** 이미 경고한 '조건 미달로 스탯이 빠진 장비' (uuid → "칸:아이템 id"). 다시 맞췄다가 또 모자라게 되면 다시 경고. */
    private final Map<UUID, Set<String>> unmetWarned = new ConcurrentHashMap<>();
    /** 착용 거절 메시지 중복 방지 (한 번의 클릭이 이벤트 둘로 올 때) — uuid → 서버 틱. */
    private final Map<UUID, Integer> lastDeny = new ConcurrentHashMap<>();

    EquipmentListener(Services services) { this.services = services; }

    // ── StatContributor ──────────────────────────────────────────────────

    @Override
    public void contribute(Player p, StatBlock block) {
        PlayerData d = services.data().get(p);
        Map<Stat, Integer> req = services.stats().requirementStats(p);
        ItemService items = services.items();
        Map<String, Integer> setCounts = new HashMap<>();
        Map<String, ItemDef> unmet = new LinkedHashMap<>();
        PlayerInventory inv = p.getInventory();

        ItemStack main = inv.getItemInMainHand();
        items.defOf(main).ifPresent(def -> {
            if (!def.isWeapon()) return;
            if (EquipRules.usable(def, req)) block.addAll(items.rolledStats(main));
            else unmet.put("main:" + def.id(), def);
        });
        for (EquipmentSlot slot : new EquipmentSlot[] {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET}) {
            ItemStack it = inv.getItem(slot);
            items.defOf(it).ifPresent(def -> {
                if (def.type() != ItemType.ARMOR || def.isShield()) return;
                if (EquipRules.usable(def, req)) {
                    block.addAll(items.rolledStats(it));
                    if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
                } else {
                    unmet.put(slot.name() + ":" + def.id(), def);
                }
            });
        }
        ItemStack off = inv.getItemInOffHand();
        items.defOf(off).ifPresent(def -> {
            if (!def.isShield()) return;
            if (EquipRules.usable(def, req)) {
                block.addAll(items.rolledStats(off));
                if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
            } else {
                unmet.put("OFF_HAND:" + def.id(), def);
            }
        });
        // 장신구는 요구 능력치가 없다 (EquipRules 가 언제나 통과)
        for (int i = 0; i < PlayerData.ACCESSORY_SLOTS; i++) {
            ItemStack acc = accessory(p, d, i);
            if (acc == null) continue;
            items.defOf(acc).ifPresent(def -> {
                if (def.type() == ItemType.ACCESSORY && EquipRules.usable(def, req)) {
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
        warnUnmet(p, unmet, req);
    }

    /**
     * 조건 미달로 스탯이 빠진 장비를 처음 볼 때만 알린다 — 입은 방어구·방패는 채팅(분배 초기화·전직·칭호 해제·접속 때),
     * 손에 든 무기는 행동 막대(들 때마다 한 번). 이미 알린 것은 다시 맞출 때까지 조용하다.
     */
    private void warnUnmet(Player p, Map<String, ItemDef> unmet, Map<Stat, Integer> req) {
        Set<String> before = unmetWarned.getOrDefault(p.getUniqueId(), Set.of());
        if (unmet.isEmpty()) {
            if (!before.isEmpty()) unmetWarned.remove(p.getUniqueId());
            return;
        }
        unmet.forEach((key, def) -> {
            if (before.contains(key)) return;
            String why = EquipRules.problemText(def, req);
            if (key.startsWith("main:")) {
                services.hud().actionBar(p, Text.mm("<#ff6b6b>⚠ " + def.name() + " <gray>— " + why + " (능력치·무기 스킬 미적용)"), 60);
            } else {
                Text.error(p, def.name() + " <gray>— " + why + " · 입은 채로 두지만 능력치가 적용되지 않습니다.");
            }
        });
        unmetWarned.put(p.getUniqueId(), Set.copyOf(unmet.keySet()));
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

    // ── 착용 조건: 못 맞춘 방어구·방패는 새로 입지 못한다 ─────────────────────

    /** PlayerInventory 칸 번호: 36 장화 · 37 각반 · 38 흉갑 · 39 투구 · 40 보조손. */
    private static final int ARMOR_FIRST = 36, OFFHAND_SLOT = 40;

    private static EquipmentSlot armorSlot(ItemDef def) {
        return switch (def.armorSlot() == null ? "" : def.armorSlot()) {
            case "head" -> EquipmentSlot.HEAD;
            case "chest" -> EquipmentSlot.CHEST;
            case "legs" -> EquipmentSlot.LEGS;
            case "feet" -> EquipmentSlot.FEET;
            default -> null;
        };
    }

    /**
     * {@code incoming} 을 방어구 칸(offhand = false) 또는 보조손(true)에 들이려 할 때 막아야 하면 알리고 true.
     * 방어구는 방어구 칸에서만, 방패는 보조손에서만 효과가 있으므로 그 경우만 본다 (보조손에 든 방어구 등은 그냥 둔다).
     */
    private boolean denyEquip(Player p, ItemStack incoming, boolean offhand) {
        ItemDef def = services.items().defOf(incoming).orElse(null);
        if (def == null || def.type() != ItemType.ARMOR || offhand != def.isShield()) return false;
        Map<Stat, Integer> req = services.stats().requirementStats(p);
        if (EquipRules.usable(def, req)) return false;
        int now = Bukkit.getCurrentTick();
        Integer last = lastDeny.put(p.getUniqueId(), now);
        if (last == null || now - last > 2) {
            Text.error(p, def.name() + " <gray>— " + EquipRules.problemText(def, req) + " · 착용할 수 없습니다.");
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
        }
        return true;
    }

    /** 인벤토리 창: 방어구·보조손 칸에 놓기 / 숫자키·F 로 바꾸기 / Shift 클릭 자동 착용. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onClick(InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof Player p) || !(e.getClickedInventory() instanceof PlayerInventory inv)) return;
        int slot = e.getSlot();
        ClickType click = e.getClick();
        boolean equipSlot = slot >= ARMOR_FIRST && slot <= OFFHAND_SLOT;
        if (equipSlot && !e.isShiftClick()) {
            ItemStack incoming = switch (click) {
                case NUMBER_KEY -> e.getHotbarButton() >= 0 ? inv.getItem(e.getHotbarButton()) : null;
                case SWAP_OFFHAND -> slot == OFFHAND_SLOT ? null : inv.getItemInOffHand(); // 보조손 칸 위의 F = 제자리
                default -> e.getCursor();
            };
            if (denyEquip(p, incoming, slot == OFFHAND_SLOT)) {
                e.setCancelled(true);
                return;
            }
        }
        // F(보조손 바꾸기)를 아무 칸 위에서 누르면 그 칸 아이템이 보조손으로 간다
        if (click == ClickType.SWAP_OFFHAND && slot != OFFHAND_SLOT && denyEquip(p, e.getCurrentItem(), true)) {
            e.setCancelled(true);
            return;
        }
        // 내 인벤토리 창(방어구 칸이 보이는 창)에서 Shift 클릭 → 비어 있는 제 칸으로 자동 착용
        if (e.isShiftClick() && !equipSlot && e.getView().getTopInventory().getType() == InventoryType.CRAFTING) {
            ItemDef def = services.items().defOf(e.getCurrentItem()).orElse(null);
            EquipmentSlot target = def == null || def.type() != ItemType.ARMOR ? null : armorSlot(def);
            if (target != null && isEmpty(inv.getItem(target)) && denyEquip(p, e.getCurrentItem(), false)) e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDrag(InventoryDragEvent e) {
        if (!(e.getWhoClicked() instanceof Player p)) return;
        for (int raw : e.getRawSlots()) {
            if (!(e.getView().getInventory(raw) instanceof PlayerInventory)) continue;
            int slot = e.getView().convertSlot(raw);
            if (slot >= ARMOR_FIRST && slot <= OFFHAND_SLOT && denyEquip(p, e.getOldCursor(), slot == OFFHAND_SLOT)) {
                e.setCancelled(true);
                return;
            }
        }
    }

    /** 손에 든 방어구 우클릭 → 입고 있던 것과 바꾸기. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSwapWithEquipment(PlayerSwapWithEquipmentSlotEvent e) {
        if (denyEquip(e.getPlayer(), e.getItemInHand(), e.getSlot() == EquipmentSlot.OFF_HAND)) e.setCancelled(true);
    }

    /** 인벤토리 밖에서 F — 주손 아이템이 보조손으로. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent e) {
        if (denyEquip(e.getPlayer(), e.getOffHandItem(), true)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDispense(BlockDispenseArmorEvent e) {
        if (e.getTargetEntity() instanceof Player p && denyEquip(p, e.getItem(), false)) e.setCancelled(true);
    }

    private static boolean isEmpty(ItemStack s) { return s == null || s.isEmpty(); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        // 조건 미달 무기 경고는 다시 계산할 때(contribute → warnUnmet) 한 번 — 여기서는 활 화살만
        Player p = e.getPlayer();
        ItemDef def = services.items().defOf(p.getInventory().getItem(e.getNewSlot())).orElse(null);
        if (def != null && GearItemService.isBow(def)) Bukkit.getScheduler().runTask(services.plugin(), () -> ensureArrow(p));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            refreshLore(e.getPlayer());
            ensureArrow(e.getPlayer());
        }, 5L);
    }

    /**
     * 가방 속 미궁 아이템 이름·설명을 지금 규칙으로 다시 쓴다 (굴린 스탯·강화 단계는 그대로). 예전 판에서 받은 장비의 "요구 레벨 25"(옛 착용 제한)
     * 문구가 "요구 힘 60" 으로 바뀌는 식 — 생성·강화 때와 같은 렌더러(ItemService.refresh)로 그리고, 결과가 같으면 건드리지 않는다.
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
    public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        accessoryCache.remove(u);
        unmetWarned.remove(u);
        lastDeny.remove(u);
    }

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
