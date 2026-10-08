package kr.souls.progression;

import kr.souls.Keys;
import kr.souls.Souls;
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
 *   <li>하트는 늘 10개 (setHealthScale(20)). 이 값은 저장되지 않아 접속할 때마다 건다.</li>
 * </ul>
 * 같은 열쇠의 수정자가 이미 있으면 Bukkit 이 예외를 던지므로 늘 지운 뒤 건다 (부활은 같은 플레이어 물체를 쓰므로 수정자가 남는다, 검토 T11).
 */
public final class AttributeApplier {
    public static final NamespacedKey VIG = Keys.of("lvl_vig");
    public static final NamespacedKey DEX = Keys.of("lvl_dex");
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
            double add = want - hp.getValue();
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
        p.setHealthScale(HEALTH_SCALE);
        plugin.test(p, String.format(Locale.ROOT, "ATTR hp=%.1f/%.0f move=%.4f stats=%s", p.getHealth(), hp == null ? 0 : hp.getValue(),
                c.moveSpeed.at(s.dex()), s.line()));
    }
}
