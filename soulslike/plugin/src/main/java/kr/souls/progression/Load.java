package kr.souls.progression;

import com.destroystokyo.paper.event.player.PlayerArmorChangeEvent;
import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import kr.souls.Keys;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.item.Weapons;
import kr.souls.util.Items;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 장비 무게 (5.8). 무게 = 단축 슬롯 아홉 칸과 왼손의 souls 무기·방패·활·촉매 (weapons.yml 의 weight) + 입은 방어구 (M3). 가방 (안쪽
 * 27칸) 은 들지 않는다 (다크 소울의 "장비한 것만 무게가 있다". 단축 슬롯이 장비 칸이다). 에스트·소모품·열쇠·바닐라 아이템은 0.
 * 한도 = 근력 한도 (stats.strength.equip-load). 단계 (load.tiers): 구르기 종류, 스태미나 회복 배율, 걷기 배율 (MOVEMENT_SPEED 임시 수정자
 * souls:load), 달리기 (너무 무거우면 Stamina 가 허기를 6 으로 둔다: 허기는 Stamina 한 곳만 쓴다, 검토 T13).
 * 다시 셈하는 때: 인벤토리 닫기·클릭 다음 틱, 방어구 바꾸기, 줍기, 슬롯 바꾸기, 손 바꾸기, 접속·부활, 레벨업 (refresh), 그리고 10틱마다.
 * 단계가 바뀌면 회색 부제목 한 번 ("짐이 무거워졌다 · 무거움"). Roll 은 rollKind 를 읽기만 한다.
 */
public final class Load implements Listener {
    public static final NamespacedKey MOD = Keys.of("load");

    private record State(double weight, double cap, LoadTiers.Tier tier) {}

    private final Souls plugin;
    private final Map<UUID, State> states = new HashMap<>();

    public Load(Souls plugin) {
        this.plugin = plugin;
    }

    /** 장비 무게 (단축 슬롯 아홉 칸 + 왼손 + 방어구). */
    public double weight(Player p) {
        PlayerInventory inv = p.getInventory();
        double w = 0;
        for (int i = 0; i < 9; i++) w += weightOf(inv.getItem(i));
        w += weightOf(inv.getItemInOffHand());
        for (ItemStack a : inv.getArmorContents()) w += weightOf(a);
        return w;
    }

    private double weightOf(ItemStack it) {
        if (it == null || it.isEmpty()) return 0;
        Weapons.Def d = plugin.weapons().of(it);
        if (d != null) return d.weight();
        // 방어구 (Keys.ARMOR) 무게는 방어구가 생기는 M3 에 (9.3)
        return 0;
    }

    public LoadTiers.Tier tier(Player p) {
        State s = states.get(p.getUniqueId());
        return s != null ? s.tier() : refresh(p);
    }

    /** 이 사람의 구르기 종류 (combat.roll.kinds 의 열쇠, 너무 무거우면 backstep). */
    public String rollKind(Player p) {
        return tier(p).roll();
    }

    public double regen(Player p) {
        return tier(p).regen();
    }

    /** 달릴 수 없을 만큼 무겁다 (너무 무거움). */
    public boolean noSprint(Player p) {
        return !tier(p).sprint();
    }

    /** 지금 다시 셈한다. 단계가 바뀌면 걷기 수정자를 바꾸고 시험 줄 LOAD 와 회색 부제목. */
    public LoadTiers.Tier refresh(Player p) {
        double w = weight(p);
        double cap = plugin.cfg().stats.equipLoad.at(plugin.stats().of(p).str());
        LoadTiers.Tier t = plugin.cfg().load.of(w, cap);
        State old = states.put(p.getUniqueId(), new State(w, cap, t));
        boolean tierChanged = old == null || !old.tier().id().equals(t.id());
        if (tierChanged) {
            AttributeInstance speed = p.getAttribute(Attribute.MOVEMENT_SPEED);
            if (speed != null) {
                speed.removeModifier(MOD);
                if (Math.abs(t.walk() - 1) > 1e-9) {
                    speed.addTransientModifier(new AttributeModifier(MOD, t.walk() - 1, AttributeModifier.Operation.ADD_MULTIPLIED_TOTAL,
                            EquipmentSlotGroup.ANY));
                }
            }
            // 처음 셈한 때 (접속) 는 알리지 않는다. 무거워지면 "짐이 무거워졌다", 가벼워지면 "짐이 가벼워졌다" 와 단계 이름
            if (old != null && plugin.profiles().of(p).born()) {
                boolean heavier = plugin.cfg().load.all().indexOf(t) > plugin.cfg().load.all().indexOf(old.tier());
                Component name = Lang.c(p, "load." + t.id()); // lang-dyn: load.*
                Component msg = heavier ? Lang.c(p, "load.heavier", "tier", name) : Lang.c(p, "load.lighter", "tier", name);
                plugin.titles().notice(p, plugin.ticker().now(), msg);
            }
        }
        if (old == null || tierChanged || Math.abs(old.weight() - w) > 1e-6 || Math.abs(old.cap() - cap) > 1e-6) {
            plugin.test(p, String.format(Locale.ROOT, "LOAD weight=%.1f cap=%.1f ratio=%.2f tier=%s t=%d", w, cap, cap <= 0 ? 0 : w / cap,
                    t.id(), plugin.ticker().now()));
        }
        return t;
    }

    /** Ticker: 10틱마다 모두 (열네 칸 훑기는 싸다). */
    public void tick(long now) {
        if (now % 10 != 0) return;
        for (Player p : Bukkit.getOnlinePlayers()) refresh(p);
    }

    private void later(Player p) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) refresh(p);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        later(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        states.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerPostRespawnEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (e.getPlayer() instanceof Player p) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onClick(InventoryClickEvent e) {
        if (e.getWhoClicked() instanceof Player p) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (e.getEntity() instanceof Player p && Items.isCustom(e.getItem().getItemStack())) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onArmor(PlayerArmorChangeEvent e) {
        later(e.getPlayer());
    }
}
