package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BundleContents;
import io.papermc.paper.datacomponent.item.UseEffects;
import io.papermc.paper.event.player.PlayerSwapWithEquipmentSlotEvent;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.BowDrawMove;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.ArmorLookMath;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatContributor;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Sound;
import org.bukkit.block.DoubleChest;
import org.bukkit.entity.Player;
import org.bukkit.entity.Vehicle;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockDispenseArmorEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.InventoryAction;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.BlockInventoryHolder;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 장비 → StatService 기여 + 착용 조건(요구 능력치) + 활 화살.
 * <ul>
 *   <li>주손 무기(피해 포함 전 스탯) · 방어구 4칸 · 보조손 방패 · 장신구 2칸(PlayerData) · 세트 효과(착용 개수 이상 누적)
 *       · 방어구 겉모습 수({@link #addLook} — 요구를 맞춘 부위만, 숨은 효과·4부위 효과는 StatCalculator)</li>
 *   <li>요구 능력치({@link EquipRules}, 판정 = 직업 기본 + 분배 + 칭호)를 못 맞춘 방어구·방패는 <b>입는 동작을 막는다</b>
 *       (방어구 칸·보조손 칸에 놓기, 숫자키·F 바꾸기, Shift 클릭 자동 착용, 우클릭 착용, 끌어 놓기, 꾸러미에서 꺼내 놓기, 발사기).
 *       바닐라가 실제로 그 칸에 넣는 경우만 막는다 — 방어구는 제 부위 칸(armor_slot), 방패는 보조손.
 *       남은 빈틈: 크리에이티브 모드 인벤토리(클라이언트가 칸 내용을 직접 보냄) — 그래도 스탯은 contribute 에서 빠진다.</li>
 *   <li>이미 입은 장비가 분배 초기화·전직·칭호 해제로 모자라게 되면 <b>입은 채로 두고</b> 스탯만 빠진다 (한 번 경고).
 *       무기는 들 수 있지만 스탯·무기 스킬이 없다 (손에 들 때 한 번 경고). 아이템을 지우거나 떨구지 않는다. 장신구는 조건 없음.</li>
 *   <li>예전 판 설명("요구 레벨 25")은 지금 규칙으로 다시 그린다 — 접속 때 가방, 엔더 상자·상자 등을 열 때 그 안,
 *       바닥에서 주울 때 ({@link #refreshLore}).</li>
 *   <li>미궁 활을 들면 '미궁 화살'(무한, 1개)을 넣어 준다 — 바닐라 활은 화살이 있어야 당겨진다. 가방이 가득 차면 빈 보조손에,
 *       그것도 없으면 알리고 가방을 닫을 때 다시 넣어 본다.</li>
 *   <li>활 당기며 걷기 ({@link BowDrawMove}, 0.3.6.1): 재계산 때마다 손(주손·보조손)의 미궁 활 {@code use_effects} 를 든 사람에 맞춘다 —
 *       사냥꾼이 미궁 안이면 당김 중 걷기 배율 = 매의 눈 draw_move, 그 밖에는 바닐라 0.2 (구성요소 없음). 다음 틱에 손의 활만 고쳐 쓴다.</li>
 *   <li>재계산 때마다 손 무기와 요구 능력치 충족 여부를 고유 효과 서비스에 알린다 ({@code services.unique().held}).</li>
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
    /** 다음 틱 가방 설명 다시 그리기가 이미 잡힌 플레이어 (주울 때 여러 번 와도 한 번). */
    private final Set<UUID> refreshPending = ConcurrentHashMap.newKeySet();
    /** 다음 틱 손의 활 당기며 걷기 맞추기가 이미 잡힌 플레이어. */
    private final Set<UUID> bowMovePending = ConcurrentHashMap.newKeySet();
    /** 가방이 가득 차 화살을 못 넣은 플레이어 (가방을 닫을 때 다시 넣어 본다 · 알림은 한 번). */
    private final Set<UUID> arrowBlocked = ConcurrentHashMap.newKeySet();

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
        ItemDef mainWeapon = items.defOf(main).filter(ItemDef::isWeapon).orElse(null);
        if (mainWeapon != null) {
            if (EquipRules.usable(mainWeapon, req)) block.addAll(items.rolledStats(main));
            else unmet.put("main:" + mainWeapon.id(), mainWeapon);
        }
        // 손 무기 고유 효과 캐시 (요구 능력치 미달이면 무기 스킬처럼 꺼짐)
        services.unique().held(p, mainWeapon, mainWeapon != null && EquipRules.usable(mainWeapon, req));
        // 활 당기며 걷기: 손의 미궁 활이 든 사람과 맞지 않으면 다음 틱에 고친다 (재계산 도중에는 가방을 건드리지 않음)
        double move = bowMoveWant(p);
        if ((bowMoveWrong(main, move) || bowMoveWrong(inv.getItemInOffHand(), move)) && bowMovePending.add(p.getUniqueId())) {
            Bukkit.getScheduler().runTask(services.plugin(), () -> {
                bowMovePending.remove(p.getUniqueId());
                if (p.isOnline()) applyBowMove(p);
            });
        }
        for (EquipmentSlot slot : new EquipmentSlot[] {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET}) {
            ItemStack it = inv.getItem(slot);
            items.defOf(it).ifPresent(def -> {
                if (def.type() != ItemType.ARMOR || def.isShield()) return;
                if (EquipRules.usable(def, req)) {
                    block.addAll(items.rolledStats(it));
                    if (def.setBonus() != null) setCounts.merge(def.setBonus(), 1, Integer::sum);
                    addLook(block, def.armorLook(), true);
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
                addLook(block, services.settings().armorLooks().shieldCountsAs(), false); // 방패 = 판금 한 부위 (4부위 수에는 안 듦)
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

    // ── 활 당기며 걷기 (BowDrawMove) ─────────────────────────────────────────

    /** 이 사람이 활을 당길 때 원하는 걷기 배율 (사냥꾼 + 미궁 안 = 매의 눈 draw_move, 아니면 바닐라 0.2). */
    private double bowMoveWant(Player p) {
        try {
            return BowDrawMove.want(services.content().classDef(services.data().get(p).classId()), services.dungeon().isInLabyrinth(p));
        } catch (Throwable t) {
            return BowDrawMove.VANILLA;
        }
    }

    /** 미궁 활인데 use_effects 가 원하는 값과 다른가. */
    private boolean bowMoveWrong(ItemStack s, double want) {
        if (isEmpty(s) || s.getType() != Material.BOW) return false;
        ItemDef def = services.items().defOf(s).orElse(null);
        if (def == null || !GearItemService.isBow(def)) return false;
        UseEffects cur = s.getData(DataComponentTypes.USE_EFFECTS);
        return !BowDrawMove.matches(cur != null, cur == null ? 0 : cur.speedMultiplier(), cur != null && cur.canSprint(), want);
    }

    /** 주손·보조손의 미궁 활 use_effects 를 지금 든 사람에 맞춰 다시 쓴다 (바뀐 칸만). */
    private void applyBowMove(Player p) {
        double want = bowMoveWant(p);
        PlayerInventory inv = p.getInventory();
        for (int slot : new int[] {inv.getHeldItemSlot(), 40}) {
            ItemStack it = inv.getItem(slot);
            if (!bowMoveWrong(it, want)) continue;
            ItemStack copy = it.clone();
            setBowMove(copy, want);
            inv.setItem(slot, copy);
        }
    }

    /** 활 하나에 당김 중 걷기 배율을 쓴다 — 바닐라 값이면 구성요소를 지운다 (BOW 기본 = 바닐라 0.2, 달리기 꺼짐). */
    static void setBowMove(ItemStack bow, double want) {
        if (BowDrawMove.custom(want)) {
            bow.setData(DataComponentTypes.USE_EFFECTS, UseEffects.useEffects()
                    .canSprint(false)
                    .interactVibrations(true)
                    .speedMultiplier((float) want)
                    .build());
        } else {
            bow.resetData(DataComponentTypes.USE_EFFECTS);
        }
    }

    /**
     * 겉모습 수 (look_spec §1.2, {@link kr.labyrinth.stats.ArmorLookMath}): 요구를 맞춘 부위마다 {@code look.<id>} +1,
     * 머리·몸·다리·발이면 {@code look_body.<id>} +1. 평상복은 아무것도 안 더하고, any(악몽의 왕관)는 {@code look_body.any} 만.
     */
    static void addLook(StatBlock block, ArmorLook look, boolean body) {
        if (look == null || look == ArmorLook.PLAIN) return;
        if (look.real()) block.add(ArmorLookMath.countKey(look), 1);
        if (body) block.add(ArmorLookMath.bodyKey(look), 1);
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

    /** PlayerInventory 칸 번호 → 장비 칸: 36 장화 · 37 각반 · 38 흉갑 · 39 투구 · 40 보조손. 그 밖은 null. */
    static EquipmentSlot equipSlotOf(int slot) {
        return switch (slot) {
            case 36 -> EquipmentSlot.FEET;
            case 37 -> EquipmentSlot.LEGS;
            case 38 -> EquipmentSlot.CHEST;
            case 39 -> EquipmentSlot.HEAD;
            case 40 -> EquipmentSlot.OFF_HAND;
            default -> null;
        };
    }

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
     * 그 장비가 효과를 내는(= 착용 조건을 보는) 칸 — 방패는 보조손, 나머지 방어구는 armor_slot, 방어구가 아니면 null.
     * 미궁 방어구는 EQUIPPABLE 부위가 armor_slot 과 같으므로(GearItemService) 바닐라도 그 칸에만 넣는다.
     */
    static EquipmentSlot ownSlot(ItemDef def) {
        if (def == null || def.type() != ItemType.ARMOR) return null;
        return def.isShield() ? EquipmentSlot.OFF_HAND : armorSlot(def);
    }

    /**
     * {@code incoming} 을 {@code target} 칸(방어구 4칸 · 보조손)에 들이려 할 때 막아야 하면 알리고 true.
     * 그 장비의 제 칸({@link #ownSlot})일 때만 본다 — 투구를 장화 칸에 대는 것처럼 바닐라가 원래 넣지 않는 동작,
     * 보조손에 든 방어구처럼 효과가 없는 경우는 그냥 둔다 (엉뚱한 "착용할 수 없습니다" 가 나오지 않게).
     */
    private boolean denyEquip(Player p, ItemStack incoming, EquipmentSlot target) {
        if (target == null) return false;
        ItemDef def = services.items().defOf(incoming).orElse(null);
        if (ownSlot(def) != target) return false;
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

    /**
     * 꾸러미 속 장비 중 {@code target} 칸에 막아야 할 것이 있는가. 미궁 장비는 최대 1개짜리라 꾸러미 무게를 다 차지해
     * 꾸러미에는 그것 하나만 들어 있다 — 꺼내질 아이템이 곧 그것이다.
     */
    private boolean denyFromBundle(Player p, ItemStack bundle, EquipmentSlot target) {
        if (target == null || isEmpty(bundle)) return false;
        BundleContents contents = bundle.getData(DataComponentTypes.BUNDLE_CONTENTS);
        if (contents == null) return false;
        for (ItemStack in : contents.contents()) if (denyEquip(p, in, target)) return true;
        return false;
    }

    /** 인벤토리 창: 방어구·보조손 칸에 놓기 / 숫자키·F 로 바꾸기 / Shift 클릭 자동 착용 / 꾸러미에서 꺼내 놓기. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onClick(InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof Player p) || !(e.getClickedInventory() instanceof PlayerInventory inv)) return;
        int slot = e.getSlot();
        ClickType click = e.getClick();
        EquipmentSlot target = equipSlotOf(slot);
        // 꾸러미를 든 채 빈 장비 칸 우클릭 → 바닐라가 꾸러미에서 하나 꺼내 그 칸에 넣는다 (커서는 꾸러미라 아래 검사에 안 걸림)
        if (target != null && isEmpty(e.getCurrentItem())
                && (click == ClickType.RIGHT || e.getAction() == InventoryAction.PLACE_FROM_BUNDLE)
                && denyFromBundle(p, e.getCursor(), target)) {
            e.setCancelled(true);
            return;
        }
        if (target != null && !e.isShiftClick()) {
            ItemStack incoming = switch (click) {
                case NUMBER_KEY -> e.getHotbarButton() >= 0 ? inv.getItem(e.getHotbarButton()) : null;
                case SWAP_OFFHAND -> target == EquipmentSlot.OFF_HAND ? null : inv.getItemInOffHand(); // 보조손 칸 위의 F = 제자리
                default -> e.getCursor();
            };
            if (denyEquip(p, incoming, target)) {
                e.setCancelled(true);
                return;
            }
        }
        // F(보조손 바꾸기)를 아무 칸 위에서 누르면 그 칸 아이템이 보조손으로 간다
        if (click == ClickType.SWAP_OFFHAND && target != EquipmentSlot.OFF_HAND
                && denyEquip(p, e.getCurrentItem(), EquipmentSlot.OFF_HAND)) {
            e.setCancelled(true);
            return;
        }
        // 내 인벤토리 창(방어구 칸이 보이는 창)에서 Shift 클릭 → 비어 있는 제 칸으로 자동 착용
        // (방패는 EQUIPPABLE 이 없어 Shift 클릭으로 보조손에 가지 않는다 — 방어구 4칸만)
        if (e.isShiftClick() && target == null && e.getView().getTopInventory().getType() == InventoryType.CRAFTING) {
            ItemDef def = services.items().defOf(e.getCurrentItem()).orElse(null);
            EquipmentSlot own = def == null || def.isShield() ? null : ownSlot(def);
            if (own != null && isEmpty(inv.getItem(own)) && denyEquip(p, e.getCurrentItem(), own)) e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDrag(InventoryDragEvent e) {
        if (!(e.getWhoClicked() instanceof Player p)) return;
        for (int raw : e.getRawSlots()) {
            if (!(e.getView().getInventory(raw) instanceof PlayerInventory)) continue;
            if (denyEquip(p, e.getOldCursor(), equipSlotOf(e.getView().convertSlot(raw)))) {
                e.setCancelled(true);
                return;
            }
        }
    }

    /** 손에 든 방어구 우클릭 → 입고 있던 것과 바꾸기. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSwapWithEquipment(PlayerSwapWithEquipmentSlotEvent e) {
        if (denyEquip(e.getPlayer(), e.getItemInHand(), e.getSlot())) e.setCancelled(true);
    }

    /** 인벤토리 밖에서 F — 주손 아이템이 보조손으로. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent e) {
        if (denyEquip(e.getPlayer(), e.getOffHandItem(), EquipmentSlot.OFF_HAND)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDispense(BlockDispenseArmorEvent e) {
        if (!(e.getTargetEntity() instanceof Player p)) return;
        if (denyEquip(p, e.getItem(), ownSlot(services.items().defOf(e.getItem()).orElse(null)))) e.setCancelled(true);
    }

    private static boolean isEmpty(ItemStack s) { return s == null || s.isEmpty(); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        // 조건 미달 무기 경고는 다시 계산할 때(contribute → warnUnmet) 한 번 — 여기서는 활 화살만
        Player p = e.getPlayer();
        ItemStack held = p.getInventory().getItem(e.getNewSlot());
        ItemDef def = services.items().defOf(held).orElse(null);
        if (def != null && GearItemService.isBow(def)) Bukkit.getScheduler().runTask(services.plugin(), () -> ensureArrow(p));
        // 손에 든 예전 장비(0.3.5 전 굴림)는 들 때도 옮겨 쓴다 (접속·상자·줍기에서 놓친 것)
        if (def != null && def.isGear()) {
            Integer ver = held.getPersistentDataContainer().get(Keys.ITEM_COMBAT_VER, PersistentDataType.INTEGER);
            if (ItemMigration035.needed(def, ver == null ? 0 : ver)) {
                int slot = e.getNewSlot();
                Bukkit.getScheduler().runTask(services.plugin(), () -> {
                    ItemStack it = p.getInventory().getItem(slot);
                    if (it == null || services.items().defOf(it).map(d -> !d.id().equals(def.id())).orElse(true)) return;
                    ItemStack copy = it.clone();
                    services.items().refresh(copy);
                    if (!copy.equals(it)) p.getInventory().setItem(slot, copy);
                });
            }
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!e.getPlayer().isOnline()) return;
            refreshLore(e.getPlayer().getInventory());
            ensureArrow(e.getPlayer());
        }, 5L);
    }

    /** 엔더 상자·상자·통·셜커 상자·수레 등 진짜 보관함을 열 때 그 안의 예전 장비 설명도 고친다 (미궁 메뉴 창은 건드리지 않음). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        Inventory top = e.getInventory();
        if (isStorage(top)) refreshLore(top);
    }

    /** 바닥에서 주운 예전 장비 — 주운 뒤 다음 틱에 가방을 다시 그린다 (이미 지금 설명이면 아무것도 안 함). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        ItemStack it = e.getItem().getItemStack();
        if (services.items().defOf(it).isEmpty()) return;
        ItemStack copy = it.clone();
        services.items().refresh(copy);
        if (copy.equals(it)) return;
        if (!refreshPending.add(p.getUniqueId())) return;
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            refreshPending.remove(p.getUniqueId());
            if (p.isOnline()) refreshLore(p.getInventory());
        });
    }

    /**
     * 블록 보관함(상자·통·셜커 등, 큰 상자 포함)·엔더 상자·보관함 달린 탈것만 — 플러그인 메뉴 창(holder 가 메뉴 객체이거나 없음)은
     * 아이콘·가격 줄을 덧붙인 사본을 보여 주므로 제외.
     */
    private static boolean isStorage(Inventory inv) {
        if (inv.getType() == InventoryType.ENDER_CHEST) return true;
        InventoryHolder h = inv.getHolder(false);
        return h instanceof BlockInventoryHolder || h instanceof DoubleChest || h instanceof Vehicle;
    }

    /**
     * 보관함 속 미궁 아이템 이름·설명을 지금 규칙으로 다시 쓴다 (굴린 스탯·강화 단계는 그대로). 예전 판에서 받은 장비의 "요구 레벨 25"(옛 착용 제한)
     * 문구가 "요구 힘 60" 으로 바뀌는 식 — 생성·강화 때와 같은 렌더러(ItemService.refresh)로 그리고, 결과가 같으면 건드리지 않는다.
     */
    private void refreshLore(Inventory inv) {
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
        refreshPending.remove(u);
        bowMovePending.remove(u);
        arrowBlocked.remove(u);
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
        PlayerInventory inv = p.getInventory();
        Map<Integer, ItemStack> left = inv.addItem(arrow);
        if (left.isEmpty()) {
            arrowBlocked.remove(p.getUniqueId());
            return;
        }
        // 가방이 가득 참 (0.3.6 까지는 여기서 조용히 화살이 없어 활을 못 당겼다): 빈 보조손에 — 바닐라 활은 보조손 화살을 먼저 쓴다
        if (isEmpty(inv.getItemInOffHand())) {
            inv.setItemInOffHand(left.values().iterator().next());
            arrowBlocked.remove(p.getUniqueId());
            return;
        }
        if (arrowBlocked.add(p.getUniqueId())) {
            services.hud().actionBar(p, Text.mm("<#ff6b6b>⚠ 가방이 가득 차 미궁 화살을 넣지 못했습니다 <gray>— 한 칸 비우고 가방을 닫으면 넣습니다"), 80);
        }
    }

    /** 가방이 가득 차 화살을 못 넣었던 사람이 가방을 닫으면 다시 넣어 본다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onCloseRetryArrow(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof Player p) || !arrowBlocked.contains(p.getUniqueId())) return;
        Bukkit.getScheduler().runTask(services.plugin(), () -> ensureArrow(p));
    }
}
