package kr.labyrinth.items.loot;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.items.GearItemService;
import kr.labyrinth.items.LootService;
import kr.labyrinth.stats.Stat;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryPickupItemEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Vector;

/**
 * 개인 루팅 (GDD §11.10). 처치 기여자 각자 따로 굴리고, 결과는 <b>그 사람에게만 보이는</b> 아이템 엔티티로 떨군다
 * (setVisibleByDefault(false) + showEntity, 주인만 줍기). 위치가 없거나 다른 월드면 바로 인벤토리로.
 * 줍는 순간 {@link ItemObtainEvent} + 전설 이상 파티 알림 / 신화 서버 방송.
 */
public final class LabLootService implements LootService, Listener {

    static final NamespacedKey LOOT_SOURCE = Keys.key("loot_source");

    private final Services services;

    public LabLootService(Services services) { this.services = services; }

    /** @param extraMult 추가 확률 배율 (솔로·2인 전투방 몹 보상 배율, 기본 1) */
    private LootRoller.Request request(Player looter, InstanceContext ctx, double extraMult) {
        Difficulty diff = ctx != null ? ctx.difficulty() : services.settings().difficulty();
        double mult = (ctx != null ? ctx.dropMultiplier()
                : diff.drop() * services.settings().party().reward(services.party().size(looter))) * extraMult;
        int luck = looter == null ? 0 : services.stats().get(looter).stat(Stat.LUK);
        // 빌드 편향(own_build_bias)은 요구치 판정 능력치(직업 기본 + 분배 + 칭호)의 상위 2개로 본다
        Map<Stat, Integer> build = looter == null ? null : services.stats().requirementStats(looter);
        return new LootRoller.Request(diff.id(), mult, luck, build);
    }

    /** 굴림만 (아이템 id → 개수, 같은 id 는 합침). */
    public Map<String, Integer> rollIds(String tableId, Player looter, InstanceContext ctx) {
        return rollIds(tableId, looter, ctx, 1.0);
    }

    private Map<String, Integer> rollIds(String tableId, Player looter, InstanceContext ctx, double extraMult) {
        LootRoller roller = new LootRoller(services.content(), ThreadLocalRandom.current());
        Map<String, Integer> merged = new LinkedHashMap<>();
        for (LootRoller.Drop d : roller.roll(tableId, request(looter, ctx, extraMult))) {
            // 도안 (0.3.6 Q6): 레시피마다 따로 — 열쇠 "blueprint@<레시피>"
            String key = d.recipe() == null ? d.itemId() : BLUEPRINT_PREFIX + d.recipe();
            merged.merge(key, d.amount(), Integer::sum);
        }
        return merged;
    }

    @Override
    public List<ItemStack> roll(String tableId, Player looter, InstanceContext ctx) {
        List<ItemStack> out = new ArrayList<>();
        rollIds(tableId, looter, ctx).forEach((id, amount) -> out.addAll(stacks(id, amount)));
        return out;
    }

    /** {@link #rollIds} 열쇠 중 도안 (0.3.6 Q6): "blueprint@&lt;레시피 id&gt;". */
    public static final String BLUEPRINT_PREFIX = kr.labyrinth.items.blueprint.BlueprintRules.ITEM_ID + "@";

    /** rollIds 열쇠 → 아이템 정의 (도안이면 blueprint). */
    private ItemDef defOfKey(String key) {
        return services.content().item(key.startsWith(BLUEPRINT_PREFIX) ? kr.labyrinth.items.blueprint.BlueprintRules.ITEM_ID : key);
    }

    private List<ItemStack> stacks(String id, int amount) {
        List<ItemStack> out = new ArrayList<>();
        if (id.startsWith(BLUEPRINT_PREFIX)) {
            ItemStack bp = kr.labyrinth.items.blueprint.BlueprintItems.create(services, id.substring(BLUEPRINT_PREFIX.length()), amount);
            if (bp != null) out.add(bp);
            return out;
        }
        ItemDef def = services.content().item(id);
        if (def == null) return out;
        int max = GearItemService.maxStack(def);
        int left = amount;
        while (left > 0) {
            int n = def.isGear() ? 1 : Math.min(max, left);
            ItemStack s = services.items().create(id, n);
            if (s == null) break;
            out.add(s);
            left -= n;
        }
        return out;
    }

    @Override
    public void drop(String tableId, Collection<Player> looters, Location location, InstanceContext ctx, String source) {
        drop(tableId, looters, location, ctx, source, 1.0);
    }

    @Override
    public void drop(String tableId, Collection<Player> looters, Location location, InstanceContext ctx, String source,
                     double extraMult) {
        LootTable table = services.content().lootTable(tableId);
        if (table == null || looters == null) return;
        double extra = Double.isFinite(extraMult) ? Math.max(0, extraMult) : 1.0;
        for (Player p : looters) {
            if (p == null || !p.isOnline()) continue;
            try {
                dropFor(p, table, location, ctx, source == null ? "drop" : source, extra);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("루팅 실패: " + tableId + " → " + p.getName(), t);
            }
        }
    }

    private void dropFor(Player p, LootTable table, Location location, InstanceContext ctx, String source, double extraMult) {
        Map<String, Integer> ids = rollIds(table.id(), p, ctx, extraMult);
        boolean direct = location == null || location.getWorld() == null || !location.getWorld().equals(p.getWorld())
                || location.distanceSquared(p.getLocation()) > 64 * 64 || p.isDead();
        int count = 0;
        Rarity best = null;
        for (Map.Entry<String, Integer> e : ids.entrySet()) {
            ItemDef def = defOfKey(e.getKey());
            if (def == null) continue;
            for (ItemStack s : stacks(e.getKey(), e.getValue())) {
                count += s.getAmount();
                if (best == null || def.rarity().ordinal() > best.ordinal()) best = def.rarity();
                if (direct) {
                    GearItemService.deliver(p, s);
                    obtained(p, def, s, source);
                } else {
                    spawnPersonal(p, s, def, location, source);
                }
            }
        }
        // 상자 골드
        if (table.gold() != null && table.gold().max() > 0) {
            double mult = (ctx != null ? ctx.goldMultiplier() : 1.0) * extraMult * (1.0 + services.stats().get(p).goldBonus());
            long gold = Math.max(0, Math.round(table.gold().roll(ThreadLocalRandom.current()) * mult));
            if (gold > 0) {
                services.data().get(p).addGold(gold);
                services.hud().refresh(p);
                p.sendMessage(Text.mm(Text.PREFIX + "<#ffd27a>+" + Text.num(gold) + " 골드"));
            }
        }
        if (count > 0 && !direct && best != null && best.atLeast(Rarity.RARE)) {
            p.playSound(location, Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.6f, best.atLeast(Rarity.LEGENDARY) ? 0.6f : 1.4f);
        }
    }

    /** 그 플레이어에게만 보이고 그 플레이어만 주울 수 있는 아이템 엔티티. */
    private void spawnPersonal(Player owner, ItemStack stack, ItemDef def, Location at, String source) {
        Location loc = at.clone().add(0, 0.4, 0);
        Item item = loc.getWorld().dropItem(loc, stack, it -> {
            it.setVisibleByDefault(false);
            it.setOwner(owner.getUniqueId());
            it.setCanMobPickup(false);
            it.setPickupDelay(15);
            it.getPersistentDataContainer().set(Keys.LOOT_OWNER, PersistentDataType.STRING, owner.getUniqueId().toString());
            it.getPersistentDataContainer().set(LOOT_SOURCE, PersistentDataType.STRING, source);
            if (def.isGear() && def.rarity().atLeast(Rarity.UNCOMMON)) {
                it.customName(Text.mm("<" + def.rarity().color() + ">" + def.name()));
                it.setCustomNameVisible(true);
            }
            if (def.rarity().atLeast(Rarity.EPIC)) it.setGlowing(true);
            ThreadLocalRandom r = ThreadLocalRandom.current();
            it.setVelocity(new Vector(r.nextDouble(-0.12, 0.12), 0.25, r.nextDouble(-0.12, 0.12)));
        });
        owner.showEntity(services.plugin(), item);
        if (def.rarity().atLeast(Rarity.LEGENDARY)) {
            owner.spawnParticle(Particle.END_ROD, loc, 30, 0.2, 0.8, 0.2, 0.05);
        }
    }

    // ── 줍기 ──────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        Item item = e.getItem();
        String owner = item.getPersistentDataContainer().get(Keys.LOOT_OWNER, PersistentDataType.STRING);
        if (owner == null) return;
        if (!(e.getEntity() instanceof Player p) || !owner.equals(p.getUniqueId().toString())) {
            e.setCancelled(true);
            return;
        }
        String source = item.getPersistentDataContainer().getOrDefault(LOOT_SOURCE, PersistentDataType.STRING, "drop");
        ItemStack s = item.getItemStack();
        services.items().defOf(s).ifPresent(def -> obtained(p, def, s, source));
    }

    /** 호퍼 등으로 개인 루팅이 빨려 들어가지 않게. */
    @EventHandler(ignoreCancelled = true)
    public void onHopper(InventoryPickupItemEvent e) {
        if (e.getItem().getPersistentDataContainer().has(Keys.LOOT_OWNER, PersistentDataType.STRING)) e.setCancelled(true);
    }

    private void obtained(Player p, ItemDef def, ItemStack s, String source) {
        Bukkit.getPluginManager().callEvent(new ItemObtainEvent(p, def, s, source));
        Rarity announce = services.content().lootSettings().announceRarity();
        if (announce == null || !def.isGear() || !def.rarity().atLeast(announce)) return;
        Component msg = Text.mm(Text.PREFIX + "<white>" + Text.escape(p.getName()) + "</white><gray> 님이 </gray><"
                + def.rarity().color() + "><b>[" + def.rarity().displayName() + "]</b> " + def.name() + "<gray> 을(를) 얻었습니다!");
        if (def.rarity() == Rarity.MYTHIC) {
            Bukkit.getServer().sendMessage(msg);
            for (Player o : Bukkit.getOnlinePlayers()) o.playSound(o.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 0.8f);
        } else {
            for (Player m : services.party().onlineMembers(p)) {
                m.sendMessage(msg);
                m.playSound(m.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.6f, 1.6f);
            }
        }
    }

    /** 관리자 테스트: 테이블을 굴려 바로 지급하고 결과를 알려 준다. */
    public void adminTest(Player target, String tableId) {
        Vector fwd = target.getLocation().getDirection().setY(0);
        if (fwd.lengthSquared() < 1e-6) fwd = new Vector(0, 0, 1);
        drop(tableId, List.of(target), target.getLocation().add(fwd.normalize().multiply(1.5)), null, "admin");
        Text.send(target, "<gray>" + Text.escape(tableId) + " 테이블을 굴렸습니다 (개인 루팅 — 본인에게만 보임).");
    }
}
