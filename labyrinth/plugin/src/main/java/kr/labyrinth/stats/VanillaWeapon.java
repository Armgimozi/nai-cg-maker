package kr.labyrinth.stats;

import org.bukkit.Material;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;

/**
 * 미궁 무기가 아닌 바닐라 무기(칼·도끼·삼지창·철퇴·활 등)도 원래 공격력대로 쳐 준다.
 * 다이아 칼 7 · 네더라이트 칼 8 ≈ 미궁 1층 일반 칼(7~8) — 초반엔 쓸 만하고 2층부터는 미궁 무기가 앞선다.
 */
final class VanillaWeapon {

    /** 바닐라 플레이어 기본 공격 속도 (아이템의 공격 속도 수치는 이 값에 더해진다). */
    static final double PLAYER_BASE_SPEED = 4.0;

    private VanillaWeapon() {}

    private static double sum(ItemStack it, Attribute attr) {
        double v = 0;
        for (AttributeModifier m : it.getType().getDefaultAttributeModifiers(EquipmentSlot.HAND).get(attr)) {
            if (m.getOperation() == AttributeModifier.Operation.ADD_NUMBER) v += m.getAmount();
        }
        return v;
    }

    /** 바닐라 무기의 피해 (기본 1 + 아이템 공격력 + 날카로움). 무기가 아니면 0. */
    static double damage(ItemStack it) {
        if (it == null || it.getType().isAir()) return 0;
        Material m = it.getType();
        if (m == Material.BOW || m == Material.CROSSBOW) {
            int power = it.getEnchantmentLevel(Enchantment.POWER);
            return (m == Material.CROSSBOW ? 7.0 : 6.0) * (power > 0 ? 1.0 + 0.25 * (power + 1) : 1.0);
        }
        double add = sum(it, Attribute.ATTACK_DAMAGE);
        if (add <= 0) return 0;
        int sharp = it.getEnchantmentLevel(Enchantment.SHARPNESS);
        return 1.0 + add + (sharp > 0 ? 0.5 * sharp + 0.5 : 0);
    }

    /** 바닐라 무기의 초당 공격 횟수 (플레이어 기본 4 + 아이템 수치). 공격 속도 수치가 없으면 0. */
    static double attacksPerSecond(ItemStack it) {
        if (it == null || it.getType().isAir()) return 0;
        double add = sum(it, Attribute.ATTACK_SPEED);
        return add == 0 ? 0 : Math.max(0.1, PLAYER_BASE_SPEED + add);
    }

    /** 바닐라 활·쇠뇌 (미궁 활 아님). */
    static boolean isBow(ItemStack it) {
        return it != null && (it.getType() == Material.BOW || it.getType() == Material.CROSSBOW);
    }

    /** 아이템 자체에 공격 속도 수치가 있는가 (칼·도끼 등 — 기본 공격 속도를 바닐라 값으로 둬야 원래 속도가 나온다). */
    static boolean hasSpeed(ItemStack it) {
        return it != null && !it.getType().isAir() && sum(it, Attribute.ATTACK_SPEED) != 0;
    }
}
