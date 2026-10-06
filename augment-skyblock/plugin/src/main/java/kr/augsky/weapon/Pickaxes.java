package kr.augsky.weapon;

import kr.augsky.AugSky;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockDropItemEvent;
import org.bukkit.inventory.ItemStack;

/**
 * 곡괭이 패시브 중 제련. 확률 없이 늘 같다.
 * 같은 효과의 증강(용광로 손·미다스의 손)을 가진 사람도 손해 보지 않게 증강 위에 더해진다.
 * 들고 있는 동안의 성급함은 효과 대신 곡괭이에 붙인 채굴 속도 수식어다 (WeaponRegistry.addStats).
 * 효과로 걸면 계속 다시 걸어야 해서 효과 칸에 '성급함 00:00' 이 남고, 증강의 무한 성급함과 꼬인다.
 */
final class Pickaxes implements Listener {
    private final AugSky plugin;

    Pickaxes(AugSky plugin) {
        this.plugin = plugin;
    }

    /**
     * 캐낸 광석 바로 제련. 증강의 제련(AugmentListener, HIGH)보다 먼저 돌아서 경험치를 직접 주고,
     * 제련 증강도 있으면 경험치를 두 배로 준다 (증강 쪽은 이미 주괴라 아무것도 하지 않는다).
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBlockDrop(BlockDropItemEvent e) {
        Player p = e.getPlayer();
        if (p.getGameMode() != GameMode.SURVIVAL && p.getGameMode() != GameMode.ADVENTURE) return;
        WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        if (w == null || !w.autoSmelt()) return;
        int xp = 0;
        for (Item it : e.getItems()) {
            ItemStack s = it.getItemStack();
            Material to = smelt(s.getType());
            if (to == null) continue;
            it.setItemStack(new ItemStack(to, s.getAmount()));
            xp += s.getAmount();
        }
        if (xp == 0) return;
        if (plugin.augments().stats(p).has("auto_smelt")) xp *= 2;
        Location at = e.getBlock().getLocation().add(0.5, 0.5, 0.5);
        at.getWorld().spawnParticle(Particle.FLAME, at, 8, 0.25, 0.25, 0.25, 0.01);
        // 화로에서 녹였으면 경험치 구슬로 받아 수선이 됐을 것이다. 수선 장비를 먼저 고치고 남는 만큼 준다
        p.giveExp(xp, true);
    }

    /** 증강 '용광로 손'과 같은 표 (AugmentListener.smelt). */
    private static Material smelt(Material m) {
        return switch (m) {
            case RAW_IRON -> Material.IRON_INGOT;
            case RAW_GOLD -> Material.GOLD_INGOT;
            case RAW_COPPER -> Material.COPPER_INGOT;
            case ANCIENT_DEBRIS -> Material.NETHERITE_SCRAP;
            case SAND -> Material.GLASS;
            case CACTUS -> Material.GREEN_DYE;
            default -> null;
        };
    }
}
