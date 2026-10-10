package kr.souls.progression;

import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.combat.DamageCalc;
import kr.souls.item.Weapons;
import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlotGroup;

import java.util.Locale;

/**
 * 능력치를 속성에 건다 (5.2 의 구현, skyblock AugmentService.applyAttributes 를 옮긴 것).
 * <ul>
 *   <li>체력 → MAX_HEALTH 수정자 souls:lvl_vig (ADD_NUMBER, 최대 HP − 기본 20). <b>저장되는</b> 수정자다: 접속할 때 바닐라는 저장된
 *       속성을 걸고 곧바로 저장된 HP 를 그 최대치로 자르므로, 저장되지 않는 수정자면 다시 들어올 때마다 HP 가 20 이 된다 (검토 T2).
 *       바뀌면 늘어난 몫만큼 지금 HP 를 더한다 (줄면 최대치로 자른다).</li>
 *   <li>민첩 → MOVEMENT_SPEED 임시 수정자 souls:lvl_dex (ADD_MULTIPLIED_TOTAL, +n%). 장비 무게의 걷기 배율 souls:load 는 Load 가 따로
 *       걸어 둘이 곱해진다.</li>
 *   <li>든 근접 무기 → ATTACK_SPEED 임시 수정자 둘 (M1 의 동작 실행기 전의 다리, 3.6·3.7): souls:weapon_speed (ADD_NUMBER, 분류의 약공격
 *       한 주기 pve.swing-ticks 로 20 / 주기 − 4: 단검 10틱 → 2.0, 직검 13 → 1.54, 대검 22 → 0.91) 와 민첩의 souls:lvl_dex
 *       (ADD_MULTIPLIED_TOTAL, 공격 속도 배율 − 1 = 민첩 속도 × 무기의 민첩 보정 계수, 필요 민첩 미달이면 깎인다). 바닐라 공격 대기가 이
 *       값으로 차고, 적을 칠 때의 피해 다리 (DamageHook) 가 그 대기를 쓴다. 근접 무기를 들지 않으면 둘 다 뗀다 (맨손 4.0).
 *       든 것이 바뀔 때마다 (Load 의 다시 셈하는 때와 같다) weaponSpeed 로 다시 건다.</li>
 *   <li>하트는 늘 10개 (setHealthScale(20)). 이 값은 저장되지 않아 접속할 때마다 건다.</li>
 * </ul>
 * 같은 열쇠의 수정자가 이미 있으면 Bukkit 이 예외를 던지므로 늘 지운 뒤 건다 (부활은 같은 플레이어 물체를 쓰므로 수정자가 남는다, 검토 T11).
 */
public final class AttributeApplier {
    public static final NamespacedKey VIG = Keys.of("lvl_vig");
    public static final NamespacedKey DEX = Keys.of("lvl_dex");
    /** 든 무기 분류의 기본 공격 속도 (ATTACK_SPEED, ADD_NUMBER) */
    public static final NamespacedKey WEAPON_SPEED = Keys.of("weapon_speed");
    /** 플레이어의 바닐라 기본 공격 속도 */
    private static final double BASE_ATTACK_SPEED = 4.0;
    /** 바닐라 하트 수 × 2 */
    public static final double HEALTH_SCALE = 20;

    private final Souls plugin;

    public AttributeApplier(Souls plugin) {
        this.plugin = plugin;
    }

    /** 프로필의 능력치를 건다 (접속·출신 고르기·레벨업·관리자 변경). */
    public void apply(Player p) {
        StatBlock s = plugin.stats().of(p);
        StatCurves c = plugin.cfg().stats;
        AttributeInstance hp = p.getAttribute(Attribute.MAX_HEALTH);
        if (hp != null) {
            double before = hp.getValue();
            double want = c.maxHealth.at(s.vig());
            hp.removeModifier(VIG);
            // 바탕값 기준 (검토 vig-modifier-uses-total): 회복 강화 같은 다른 최대 HP 수정자는 이 위에 얹힌다
            double add = want - hp.getBaseValue();
            if (Math.abs(add) > 1e-6) {
                hp.addModifier(new AttributeModifier(VIG, add, AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.ANY));
            }
            double after = hp.getValue();
            if (!p.isDead()) {
                double cur = p.getHealth();
                if (after > before + 1e-6) p.setHealth(Math.min(after, cur + (after - before)));
                else if (cur > after) p.setHealth(after);
            }
        }
        AttributeInstance speed = p.getAttribute(Attribute.MOVEMENT_SPEED);
        if (speed != null) {
            speed.removeModifier(DEX);
            double move = c.moveSpeed.at(s.dex());
            if (move > 1e-9) {
                speed.addTransientModifier(new AttributeModifier(DEX, move, AttributeModifier.Operation.MULTIPLY_SCALAR_1, EquipmentSlotGroup.ANY));
            }
        }
        weaponSpeed(p);
        p.setHealthScale(HEALTH_SCALE);
        plugin.test(p, String.format(Locale.ROOT, "ATTR hp=%.1f/%.0f move=%.4f stats=%s", p.getHealth(), hp == null ? 0 : hp.getValue(),
                c.moveSpeed.at(s.dex()), s.line()));
    }

    /** 사람마다 마지막으로 건 공격 속도 (무기 id 와 배율): 같으면 다시 걸지 않는다 (10틱마다 부른다) */
    private final java.util.Map<java.util.UUID, String> lastSpeed = new java.util.HashMap<>();

    /** 든 근접 무기에 맞춰 공격 속도 수정자 둘을 건다 (다르면). */
    public void weaponSpeed(Player p) {
        AttributeInstance as = p.getAttribute(Attribute.ATTACK_SPEED);
        if (as == null) return;
        Weapons.Def w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        Integer cycle = Stats.isMelee(w) ? plugin.cfg().pve.swingTicks(w.cls()) : null;
        double base = cycle == null ? BASE_ATTACK_SPEED : 20.0 / cycle;
        double mult = cycle == null ? 1 : DamageCalc.attackSpeed(plugin.cfg().stats, Stats.arms(w), plugin.stats().of(p).dex());
        String key = (w == null ? "-" : w.id()) + String.format(Locale.ROOT, "/%.5f/%.5f", base, mult);
        if (key.equals(lastSpeed.get(p.getUniqueId())) && (as.getModifier(WEAPON_SPEED) != null) == (cycle != null)) return;
        lastSpeed.put(p.getUniqueId(), key);
        as.removeModifier(WEAPON_SPEED);
        as.removeModifier(DEX);
        if (cycle != null) {
            as.addTransientModifier(new AttributeModifier(WEAPON_SPEED, base - BASE_ATTACK_SPEED, AttributeModifier.Operation.ADD_NUMBER,
                    EquipmentSlotGroup.ANY));
            if (Math.abs(mult - 1) > 1e-9) {
                as.addTransientModifier(new AttributeModifier(DEX, mult - 1, AttributeModifier.Operation.MULTIPLY_SCALAR_1, EquipmentSlotGroup.ANY));
            }
        }
        plugin.test(p, String.format(Locale.ROOT, "ASPD weapon=%s base=%.3f mult=%.4f value=%.3f", w == null ? "-" : w.id(), base, mult,
                as.getValue()));
    }

    public void forget(Player p) {
        lastSpeed.remove(p.getUniqueId());
    }
}
