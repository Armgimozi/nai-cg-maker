package kr.augsky.altar;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.Tier;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.event.world.EntitiesUnloadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.persistence.PersistentDataType;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** 제단(상호작용 엔티티)을 누르면 제단 화면을 연다. 프리즘 제단의 빛기둥은 무지개색으로 돈다. */
public final class AltarService implements Listener {
    private static final Material[] RAINBOW = {
            Material.RED_STAINED_GLASS, Material.ORANGE_STAINED_GLASS, Material.YELLOW_STAINED_GLASS,
            Material.LIME_STAINED_GLASS, Material.LIGHT_BLUE_STAINED_GLASS, Material.BLUE_STAINED_GLASS,
            Material.PURPLE_STAINED_GLASS, Material.MAGENTA_STAINED_GLASS
    };

    private final AugSky plugin;
    private final Set<UUID> beams = new HashSet<>();
    private final Map<UUID, Tier> altars = new HashMap<>();
    /** 블록 보호 범위의 중심 (제단과 보스 소환대) */
    private final Map<UUID, Location> guarded = new HashMap<>();
    private int tick;

    public AltarService(AugSky plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 40, 10);
    }

    public void scanLoaded() {
        for (World w : Bukkit.getWorlds()) for (Entity e : w.getEntities()) track(e);
    }

    private void track(Entity e) {
        var pdc = e.getPersistentDataContainer();
        if (e instanceof BlockDisplay && "prism".equals(pdc.get(Keys.BEAM, PersistentDataType.STRING))) beams.add(e.getUniqueId());
        if (e instanceof Interaction) {
            Tier t = Tier.parse(pdc.get(Keys.ALTAR, PersistentDataType.STRING));
            if (t != null) {
                altars.put(e.getUniqueId(), t);
                guarded.put(e.getUniqueId(), e.getLocation());
            }
            if (pdc.has(Keys.PEDESTAL)) guarded.put(e.getUniqueId(), e.getLocation());
        }
    }

    @EventHandler
    public void onLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) track(en);
    }

    @EventHandler
    public void onUnload(EntitiesUnloadEvent e) {
        for (Entity en : e.getEntities()) {
            beams.remove(en.getUniqueId());
            altars.remove(en.getUniqueId());
            guarded.remove(en.getUniqueId());
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Entity en = e.getRightClicked();
        if (!(en instanceof Interaction)) return;
        var pdc = en.getPersistentDataContainer();
        Player p = e.getPlayer();
        Tier t = Tier.parse(pdc.get(Keys.ALTAR, PersistentDataType.STRING));
        if (t != null) {
            e.setCancelled(true);
            plugin.weaponListener().suppress(p, 6);
            plugin.menus().openAltar(p, t);
            return;
        }
        String rift = pdc.get(Keys.PEDESTAL, PersistentDataType.STRING);
        if (rift != null) {
            e.setCancelled(true);
            plugin.weaponListener().suppress(p, 6);
            plugin.mobs().usePedestal(p, rift, en.getLocation());
        }
    }

    /** 제단을 좌클릭해도 아무 일 없게. */
    @EventHandler(ignoreCancelled = true)
    public void onHit(EntityDamageByEntityEvent e) {
        if (e.getEntity() instanceof Interaction i && (i.getPersistentDataContainer().has(Keys.ALTAR)
                || i.getPersistentDataContainer().has(Keys.PEDESTAL))) {
            e.setCancelled(true);
            if (e.getDamager() instanceof Player p) {
                Tier t = Tier.parse(i.getPersistentDataContainer().get(Keys.ALTAR, PersistentDataType.STRING));
                if (t != null) p.sendActionBar(Text.mm(t.wrap(t.korean + " 제단") + " <gray>— 우클릭해서 사용"));
            }
        }
    }

    public boolean isGuarded(Location l) {
        for (Location c : guarded.values()) {
            if (!c.getWorld().equals(l.getWorld())) continue;
            double dx = l.getBlockX() + 0.5 - c.getX(), dz = l.getBlockZ() + 0.5 - c.getZ();
            double dy = l.getBlockY() - c.getY();
            if (dx * dx + dz * dz <= 5.2 * 5.2 && dy >= -3 && dy <= 7) return true;
        }
        return false;
    }

    private boolean bypass(Player p) {
        return p.getGameMode() == org.bukkit.GameMode.CREATIVE && p.hasPermission("augsky.admin");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(org.bukkit.event.block.BlockBreakEvent e) {
        if (!bypass(e.getPlayer()) && isGuarded(e.getBlock().getLocation())) {
            e.setCancelled(true);
            e.getPlayer().sendActionBar(Text.mm("<#ff7070>제단 주변은 부술 수 없습니다"));
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlace(org.bukkit.event.block.BlockPlaceEvent e) {
        if (!bypass(e.getPlayer()) && isGuarded(e.getBlock().getLocation())) {
            // 제단 바닥 위쪽 공간은 비워 둔다 (기둥/빛기둥 가림 방지). 가장자리 다리 연결은 허용
            Location c = e.getBlock().getLocation();
            for (Location g : guarded.values()) {
                if (!g.getWorld().equals(c.getWorld())) continue;
                double dx = c.getBlockX() + 0.5 - g.getX(), dz = c.getBlockZ() + 0.5 - g.getZ();
                if (dx * dx + dz * dz <= 4.4 * 4.4 && c.getBlockY() >= g.getBlockY() - 1) {
                    e.setCancelled(true);
                    return;
                }
            }
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onExplode(org.bukkit.event.entity.EntityExplodeEvent e) {
        e.blockList().removeIf(b -> isGuarded(b.getLocation()));
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(org.bukkit.event.block.BlockExplodeEvent e) {
        e.blockList().removeIf(b -> isGuarded(b.getLocation()));
    }

    private void tick() {
        tick++;
        Iterator<UUID> it = beams.iterator();
        Material glass = RAINBOW[tick % RAINBOW.length];
        while (it.hasNext()) {
            Entity e = Bukkit.getEntity(it.next());
            if (!(e instanceof BlockDisplay bd) || !e.isValid()) {
                it.remove();
                continue;
            }
            bd.setBlock(glass.createBlockData());
        }
        if (tick % 2 != 0) return;
        for (Map.Entry<UUID, Tier> en : new HashMap<>(altars).entrySet()) {
            Entity e = Bukkit.getEntity(en.getKey());
            if (e == null || !e.isValid()) {
                altars.remove(en.getKey());
                continue;
            }
            Location c = e.getLocation().add(0, 1.2, 0);
            boolean near = false;
            for (Player p : e.getWorld().getPlayers()) {
                if (p.getLocation().distanceSquared(c) < 48 * 48) {
                    near = true;
                    break;
                }
            }
            if (!near) continue;
            Particle part = switch (en.getValue()) {
                case SILVER -> Particle.END_ROD;
                case GOLD -> Particle.WAX_ON;
                case PRISM -> Particle.GLOW;
            };
            e.getWorld().spawnParticle(part, c, 6, 0.8, 0.8, 0.8, 0.01);
            if (en.getValue() == Tier.PRISM) e.getWorld().spawnParticle(Particle.END_ROD, c, 3, 1.2, 1.2, 1.2, 0.02);
        }
    }
}
