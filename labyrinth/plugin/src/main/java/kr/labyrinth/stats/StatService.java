package kr.labyrinth.stats;

import com.destroystokyo.paper.event.player.PlayerArmorChangeEvent;
import io.papermc.paper.event.player.PlayerInventorySlotChangeEvent;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Settings;
import kr.labyrinth.data.PlayerData;
import org.bukkit.Bukkit;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 플레이어 파생 능력치 캐시 + 바닐라 속성 반영.
 * <p>
 * <b>HP 계약</b>: 플레이어 HP 는 바닐라 체력을 쓴다. 바닐라 max_health = min(최대 HP, 1024), 하트는 항상 10칸으로 표시
 * (health scale 20). 최대 HP 가 1024 를 넘으면 비율 {@link #hpRatio}(= 바닐라/커스텀) 로 환산하므로
 * HP 를 직접 만질 때는 반드시 {@link #currentHp}/{@link #heal}/{@code DamageService} 를 쓴다.
 * <p>
 * 장비·칭호·버프 모듈은 {@link #addContributor} 로 가산 스탯을 보태고, 값이 바뀌면 {@link #markDirty} 를 부른다
 * (손에 든 아이템·방어구·인벤토리 닫기·월드 이동은 여기서 자동 감지).
 */
public final class StatService implements Module, Listener {

    public static final double VANILLA_MAX_HEALTH_CAP = 1024.0;
    private static final double BASE_MOVE_SPEED = 0.1;
    /** PlayerInventory 보조손 칸 번호. */
    private static final int OFFHAND_SLOT = 40;

    private final Services services;
    private final List<StatContributor> contributors = new CopyOnWriteArrayList<>();
    private final Map<UUID, DerivedStats> cache = new ConcurrentHashMap<>();
    private final Set<UUID> dirty = ConcurrentHashMap.newKeySet();
    private BukkitTask task;
    private int tickCounter;

    public StatService(Services services) { this.services = services; }

    @Override
    public String name() { return "stats"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 1L, 1L);
        for (Player p : Bukkit.getOnlinePlayers()) recalc(p);
    }

    @Override
    public void disable() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        cache.clear();
    }

    @Override
    public void reload() {
        for (Player p : Bukkit.getOnlinePlayers()) recalc(p);
    }

    public void addContributor(StatContributor c) { contributors.add(c); }

    public void removeContributor(StatContributor c) { contributors.remove(c); }

    /** 캐시된 파생 능력치 (없으면 즉시 계산). */
    public DerivedStats get(Player p) {
        DerivedStats s = cache.get(p.getUniqueId());
        return s != null ? s : recalc(p);
    }

    /**
     * 장비 요구 능력치 판정용 능력치 = 직업 기본 + 분배 포인트 + 장착 칭호 보너스 (장비·버프 제외 — 장비가 스스로 조건을 채우지 않게).
     * {@code items.EquipRules} 와 무기 스킬·직업 스킬 무기 판정이 같이 쓴다.
     */
    public Map<Stat, Integer> requirementStats(Player p) {
        PlayerData d = services.data().get(p);
        ClassDef cls = services.content().classDef(d.classId());
        Map<String, Double> title = Map.of();
        try {
            AchievementDef t = services.titles() == null ? null : services.titles().equipped(p);
            if (t != null && t.bonus() != null) title = t.bonus();
        } catch (Throwable e) {
            Log.error("칭호 보너스 읽기 오류", e);
        }
        return StatRequirement.playerStats(cls, d.allocated(), title);
    }

    /** 다음 틱에 다시 계산 (같은 틱 여러 번 호출해도 1회). */
    public void markDirty(Player p) { dirty.add(p.getUniqueId()); }

    /** 즉시 다시 계산하고 바닐라 속성 반영. */
    public DerivedStats recalc(Player p) {
        PlayerData d = services.data().get(p);
        ClassDef cls = services.content().classDef(d.classId());
        StatBlock bonus = new StatBlock();
        for (StatContributor c : contributors) {
            try {
                c.contribute(p, bonus);
            } catch (Throwable t) {
                Log.error("StatContributor 오류", t);
            }
        }
        try {
            if (services.items().heldWeapon(p) == null) {
                double vanilla = VanillaWeapon.damage(p.getInventory().getItemInMainHand());
                if (vanilla > 0) bonus.add("damage", vanilla);
            }
        } catch (Throwable t) {
            Log.error("바닐라 무기 피해 계산 오류", t);
        }
        Settings.Combat cc = services.settings().combat();
        DerivedStats s = StatCalculator.compute(cls, d.level(), d.allocated(), bonus, cc.baseCritChance(), cc.baseCritDamage());
        DerivedStats old = cache.put(p.getUniqueId(), s);
        dirty.remove(p.getUniqueId());
        applyAttributes(p, s, old);
        return s;
    }

    private void applyAttributes(Player p, DerivedStats s, DerivedStats old) {
        double vanillaMax = Math.min(VANILLA_MAX_HEALTH_CAP, s.maxHp());
        AttributeInstance maxHealth = p.getAttribute(Attribute.MAX_HEALTH);
        if (maxHealth != null) {
            double prevMax = maxHealth.getValue();
            double ratio = prevMax > 0 ? p.getHealth() / prevMax : 1.0;
            if (Math.abs(maxHealth.getBaseValue() - vanillaMax) > 1e-6) {
                maxHealth.setBaseValue(vanillaMax);
                double newMax = maxHealth.getValue();
                if (!p.isDead()) p.setHealth(Math.max(0.5, Math.min(newMax, ratio * newMax)));
            }
        }
        if (!p.isHealthScaled() || p.getHealthScale() != 20.0) {
            p.setHealthScaled(true);
            p.setHealthScale(20.0);
        }
        setBase(p, Attribute.MOVEMENT_SPEED, BASE_MOVE_SPEED * (1.0 + s.moveSpeed()));
        ItemDef weapon = services.items().heldWeapon(p);
        boolean vanillaSpeed;
        try {
            vanillaSpeed = weapon == null && VanillaWeapon.hasSpeed(p.getInventory().getItemInMainHand());
        } catch (Throwable t) {
            vanillaSpeed = false;
        }
        double atkSpeed = vanillaSpeed
                ? VanillaWeapon.PLAYER_BASE_SPEED
                : services.settings().weaponAttackSpeed(weapon == null ? null : weapon.weaponType());
        setBase(p, Attribute.ATTACK_SPEED, Math.max(0.2, atkSpeed * (1.0 + s.attackSpeed())));
        setBase(p, Attribute.KNOCKBACK_RESISTANCE, s.knockbackResistance());
    }

    private static void setBase(Player p, Attribute attr, double value) {
        AttributeInstance inst = p.getAttribute(attr);
        if (inst != null && Math.abs(inst.getBaseValue() - value) > 1e-6) inst.setBaseValue(value);
    }

    // ── HP 환산 ───────────────────────────────────────────────────────────

    /** 바닐라 체력 / 커스텀 HP 비율 (최대 HP ≤ 1024 면 1). */
    public double hpRatio(Player p) {
        DerivedStats s = get(p);
        return Math.min(VANILLA_MAX_HEALTH_CAP, s.maxHp()) / s.maxHp();
    }

    public double currentHp(Player p) { return p.getHealth() / hpRatio(p); }

    public double maxHp(Player p) { return get(p).maxHp(); }

    /** 커스텀 HP 단위로 회복. @return 실제 회복량 */
    public double heal(Player p, double amount) {
        if (amount <= 0 || p.isDead()) return 0;
        double r = hpRatio(p);
        AttributeInstance mh = p.getAttribute(Attribute.MAX_HEALTH);
        double max = mh == null ? 20 : mh.getValue();
        double before = p.getHealth();
        double after = Math.min(max, before + amount * r);
        p.setHealth(after);
        return (after - before) / r;
    }

    /** 커스텀 HP 단위로 체력 설정 (부활 등). */
    public void setHp(Player p, double hp) {
        AttributeInstance mh = p.getAttribute(Attribute.MAX_HEALTH);
        double max = mh == null ? 20 : mh.getValue();
        p.setHealth(Math.max(0, Math.min(max, hp * hpRatio(p))));
    }

    // ── 틱: dirty 재계산 + 초당 HP 재생 ───────────────────────────────────

    private void tick() {
        if (!dirty.isEmpty()) {
            for (UUID u : Set.copyOf(dirty)) {
                Player p = Bukkit.getPlayer(u);
                dirty.remove(u);
                if (p != null) recalc(p);
            }
        }
        if (++tickCounter % 20 == 0) {
            for (Player p : Bukkit.getOnlinePlayers()) {
                DerivedStats s = cache.get(p.getUniqueId());
                if (s != null && s.hpRegen() > 0 && !p.isDead()) heal(p, s.hpRegen());
            }
        }
    }

    // ── 자동 감지 ─────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        services.levels().ensureStartPoints(e.getPlayer());
        recalc(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        cache.remove(e.getPlayer().getUniqueId());
        dirty.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) { markDirty(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwap(PlayerSwapHandItemsEvent e) { markDirty(e.getPlayer()); }

    /** 칸을 바꾸지 않고 손(든 칸·보조손 40번)의 아이템이 바뀐 경우 — 삼지창 던지기·줍기·부서짐·명령 지급 등. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onSlot(PlayerInventorySlotChangeEvent e) {
        int slot = e.getSlot();
        if (slot == e.getPlayer().getInventory().getHeldItemSlot() || slot == OFFHAND_SLOT) markDirty(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onArmor(PlayerArmorChangeEvent e) { markDirty(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (e.getPlayer() instanceof Player p) markDirty(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) { markDirty(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerRespawnEvent e) { markDirty(e.getPlayer()); }
}
