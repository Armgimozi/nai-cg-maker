package kr.labyrinth.items.enhance;

import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * +10(최대 강화) 장비의 특별한 빛 (GDD §11.13) — 성능을 생각해 은은하게:
 * <ul>
 *   <li>config {@code enhance.glow_interval} 틱(기본 10)마다 한 번, 32칸 안의 사람에게만 입자를 보낸다.</li>
 *   <li>주손 무기: 손 근처 금빛 반짝임 1~2개. 아우라 무기는 AuraService 가 링을 더 밝게 하고 여기서 반짝임을 하나 더.</li>
 *   <li>+10 방어구·방패: 몸 둘레 금빛 가루 1개(부위 여러 개여도 최대 2개).</li>
 *   <li>관전·투명(그림자 잠행)·죽음 상태에서는 안 보낸다.</li>
 * </ul>
 */
final class EnhanceGlow {

    private static final Particle.DustOptions GOLD = new Particle.DustOptions(Color.fromRGB(0xFFD36B), 0.8f);
    private static final Particle.DustOptions PALE = new Particle.DustOptions(Color.fromRGB(0xFFF4D6), 0.6f);
    private static final EquipmentSlot[] ARMOR = {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS,
            EquipmentSlot.FEET, EquipmentSlot.OFF_HAND};

    private final Services services;
    private BukkitTask task;
    private long tick;

    EnhanceGlow(Services services) { this.services = services; }

    void start() {
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 20L, 1L);
    }

    void stop() {
        if (task != null) task.cancel();
        task = null;
    }

    private void tickAll() {
        int interval = Enhancement.rules().config().glowInterval();
        if (interval <= 0 || ++tick % interval != 0) return;
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                glow(p);
            } catch (Throwable t) {
                Log.warnOnce("enhance-glow", "[강화] 빛 입자 오류: " + t);
            }
        }
    }

    private boolean radiant(ItemStack s) {
        return s != null && !s.isEmpty() && Enhancement.rules().radiant(Enhancement.level(s));
    }

    private void glow(Player p) {
        if (p.getGameMode() == GameMode.SPECTATOR || p.isDead() || p.isInvisible()
                || p.hasPotionEffect(PotionEffectType.INVISIBILITY)) return;
        ItemStack main = p.getInventory().getItemInMainHand();
        boolean weapon = radiant(main);
        int armor = 0;
        for (EquipmentSlot slot : ARMOR) if (radiant(p.getInventory().getItem(slot))) armor++;
        if (!weapon && armor == 0) return;
        Location base = p.getLocation();
        if (weapon) {
            ItemDef def = services.items().defOf(main).orElse(null);
            boolean aura = def != null && def.aura() != null;
            double yaw = Math.toRadians(p.getBodyYaw());
            Vector fwd = new Vector(-Math.sin(yaw), 0, Math.cos(yaw));
            Vector right = new Vector(-fwd.getZ(), 0, fwd.getX());
            Location hand = base.clone().add(0, 0.95, 0).add(fwd.multiply(0.35)).add(right.multiply(0.38));
            Particle.WAX_ON.builder().location(hand).count(1).offset(0.12, 0.25, 0.12).speed(0).receivers(32, true).spawn();
            Particle.DUST.builder().location(hand).count(aura ? 2 : 1).offset(0.15, 0.3, 0.15).data(GOLD).receivers(32, true).spawn();
            if (aura) Particle.END_ROD.builder().location(hand).count(1).offset(0.1, 0.2, 0.1).speed(0.005).receivers(32, true).spawn();
        }
        if (armor > 0) {
            double a = (tick / 10.0) * 0.9;
            for (int i = 0; i < Math.min(2, armor); i++) {
                double ang = a + i * Math.PI;
                Location at = base.clone().add(Math.cos(ang) * 0.45, 0.4 + (tick / 10 % 4) * 0.35, Math.sin(ang) * 0.45);
                Particle.DUST.builder().location(at).count(1).offset(0.03, 0.03, 0.03).data(i == 0 ? GOLD : PALE)
                        .receivers(32, true).spawn();
            }
        }
    }
}
