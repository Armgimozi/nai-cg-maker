package kr.souls.combat;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.event.entity.EntityKnockbackEvent;
import io.papermc.paper.registry.RegistryAccess;
import io.papermc.paper.registry.RegistryKey;
import kr.souls.Keys;
import kr.souls.skill.Combat;
import net.kyori.adventure.key.Key;
import org.bukkit.Location;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.damage.DamageType;
import org.bukkit.entity.Player;
import org.bukkit.entity.Zombie;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.Locale;

/**
 * M0 서버 시험 (13.4 표 첫 줄, 3.4): 막기 성분 + minecraft:generic 피해.
 * 플레이어 앞 2칸에 잠깐 세운 좀비를 원인 물체로 삼아 피해를 넣고, 실제로 깎인 체력, 막는 중이었는지,
 * 바닐라 밀림이 일어났는지, 든 아이템 내구도가 바뀌었는지를 잰다. /soulstest hit 와 rollhit 이 쓴다.
 * 원인 물체가 살아 있는 비플레이어라 난이도 배율 규칙이 걸린다 (normal 이면 배율 없음).
 */
public final class TestHits implements Listener {
    /** 시험용으로 잠깐 세운 몸에 붙이는 태그 (켤 때 쓸어 낸다) */
    public static final String ENT_TAG = "souls_ent";
    private static final Key ARMOR_KEY = Key.key(Keys.NS, "test_armor");

    public record Result(String type, double amount, double dealt, boolean blocking, boolean knockback,
                         boolean cancelled, String durability, double armor, String difficulty) {
        /** 시험 줄 꼬리 ([T] 다음에 붙인다) */
        public String line() {
            return String.format(Locale.ROOT, "type=%s amount=%.2f dealt=%.2f full=%s blocking=%s knockback=%s cancelled=%s dur=%s armor=%.0f diff=%s",
                    type, amount, dealt, Math.abs(dealt - amount) < 1e-3, blocking, knockback, cancelled, durability, armor, difficulty);
        }
    }

    private Player active;
    private boolean sawKnockback, sawCancel;

    /**
     * 시험 피해 하나.
     * @param type generic | hit (데이터팩 souls:hit) | none (원인 없는 generic)
     * @param armor 잠깐 방어력 +20 을 걸고 맞는다 (generic 이 방어구를 지나치는지)
     */
    public Result hit(Player p, double amount, String type, boolean armor) {
        DamageType dt = DamageType.GENERIC;
        if ("hit".equals(type)) {
            dt = RegistryAccess.registryAccess().getRegistry(RegistryKey.DAMAGE_TYPE).get(Key.key(Keys.NS, "hit"));
            if (dt == null) return new Result("hit(없음)", amount, 0, p.isBlocking(), false, true, "-", 0, p.getWorld().getDifficulty().name());
        }
        Zombie cause = null;
        if (!"none".equals(type)) {
            Vector f = p.getLocation().getDirection().setY(0);
            if (f.lengthSquared() < 1e-6) f = new Vector(0, 0, 1);
            Location at = p.getLocation().add(f.normalize().multiply(2));
            at.setDirection(p.getLocation().toVector().subtract(at.toVector()));
            cause = p.getWorld().spawn(at, Zombie.class, z -> {
                z.setAI(false);
                z.setSilent(true);
                z.setPersistent(false);
                z.setShouldBurnInDay(false);
                z.setAdult();
                z.addScoreboardTag(ENT_TAG);
                z.getEquipment().clear();
            });
        }
        AttributeInstance armorAttr = p.getAttribute(Attribute.ARMOR);
        AttributeModifier mod = new AttributeModifier(new org.bukkit.NamespacedKey(ARMOR_KEY.namespace(), ARMOR_KEY.value()), 20,
                AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.ANY);
        if (armor && armorAttr != null) armorAttr.addTransientModifier(mod);
        ItemStack held = p.getActiveItem().isEmpty() ? p.getInventory().getItemInMainHand() : p.getActiveItem();
        Integer durBefore = held.getData(DataComponentTypes.DAMAGE);
        boolean blocking = p.isBlocking();
        double armorValue = armorAttr == null ? 0 : armorAttr.getValue();
        double before = p.getHealth() + p.getAbsorptionAmount();
        p.setNoDamageTicks(0);
        active = p;
        sawKnockback = false;
        sawCancel = false;
        try {
            p.damage(amount, Combat.source(dt, cause));
        } finally {
            active = null;
            if (armor && armorAttr != null) armorAttr.removeModifier(mod);
            if (cause != null) cause.remove();
        }
        double after = p.isDead() ? 0 : p.getHealth() + p.getAbsorptionAmount();
        ItemStack heldAfter = p.getActiveItem().isEmpty() ? p.getInventory().getItemInMainHand() : p.getActiveItem();
        Integer durAfter = heldAfter.getData(DataComponentTypes.DAMAGE);
        String dur = (durBefore == null ? "-" : durBefore) + "->" + (durAfter == null ? "-" : durAfter);
        String name = "none".equals(type) ? "generic(원인 없음)" : "hit".equals(type) ? "souls:hit" : "minecraft:generic";
        return new Result(name, amount, Math.max(0, before - after), blocking, sawKnockback, sawCancel, dur, armorValue,
                p.getWorld().getDifficulty().name());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDamage(EntityDamageEvent e) {
        if (active != null && e.getEntity() == active && e.isCancelled()) sawCancel = true;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onKnockback(EntityKnockbackEvent e) {
        if (active != null && e.getEntity() == active && !e.isCancelled()) sawKnockback = true;
    }
}
