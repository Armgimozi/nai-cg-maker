package kr.souls.progression;

import kr.souls.Keys;
import kr.souls.Souls;
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
 *   <li>든 근접 무기 → ATTACK_SPEED 임시 수정자 souls:weapon_speed (ADD_NUMBER) 로 바닐라 공격 속도를 combat.moves.vanilla-attack-speed
 *       (기본 20) 에 맞춘다 (M1 P1a). 공격 주기는 동작 실행기 (combat/MoveRunner) 가 content/moves.yml 의 틱과 민첩으로 정하고, 바닐라
 *       공격 대기는 쓰지 않는다. 대기를 낮게 두면 서버가 손을 휘두른 뒤 (패링 몸짓·왼손 공격, PS 의 S3) 주무기가 그 대기 동안 화면 밑으로
 *       내려간다. 근접 무기를 들지 않으면 뗀다 (맨손 4.0). 예전 판의 민첩 수정자 souls:lvl_dex (ATTACK_SPEED) 는 늘 뗀다 (민첩은 동작 틱에
 *       듣는다). 든 것이 바뀔 때마다 (Load 의 다시 셈하는 때와 같다) weaponSpeed 로 다시 건다.</li>
 *   <li>민첩 단계 (combat.moves.swing-tiers): 바뀌면 그 사람의 무기를 그 단계의 휘두르는 길이로 새로 만든다 (WeaponRefresh, 시험 줄
 *       SWING_TIER tier= dex= n=).</li>
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
        swingTier(p);
        p.setHealthScale(HEALTH_SCALE);
        plugin.test(p, String.format(Locale.ROOT, "ATTR hp=%.1f/%.0f move=%.4f stats=%s", p.getHealth(), hp == null ? 0 : hp.getValue(),
                c.moveSpeed.at(s.dex()), s.line()));
    }

    /** 사람마다 마지막으로 건 공격 속도 (무기 id 와 배율): 같으면 다시 걸지 않는다 (10틱마다 부른다) */
    private final java.util.Map<java.util.UUID, String> lastSpeed = new java.util.HashMap<>();

    /** 사람마다 마지막으로 본 민첩 단계 (휘두르는 길이) */
    private final java.util.Map<java.util.UUID, Integer> lastTier = new java.util.HashMap<>();

    /** 든 근접 무기에 맞춰 바닐라 공격 속도를 건다 (다르면). M1 P1a: 동작 실행기의 주기와 상관없는 높은 값 하나. */
    public void weaponSpeed(Player p) {
        AttributeInstance as = p.getAttribute(Attribute.ATTACK_SPEED);
        if (as == null) return;
        Weapons.Def w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        boolean melee = Stats.isMelee(w);
        double want = melee ? plugin.cfg().tuning.moves.attackSpeed() : BASE_ATTACK_SPEED;
        String key = (w == null ? "-" : w.id()) + String.format(Locale.ROOT, "/%.5f", want);
        boolean has = as.getModifier(WEAPON_SPEED) != null;
        boolean needs = melee && Math.abs(want - BASE_ATTACK_SPEED) > 1e-9;
        if (key.equals(lastSpeed.get(p.getUniqueId())) && has == needs && as.getModifier(DEX) == null) return;
        lastSpeed.put(p.getUniqueId(), key);
        as.removeModifier(WEAPON_SPEED);
        as.removeModifier(DEX);
        if (needs) {
            as.addTransientModifier(new AttributeModifier(WEAPON_SPEED, want - BASE_ATTACK_SPEED, AttributeModifier.Operation.ADD_NUMBER,
                    EquipmentSlotGroup.ANY));
        }
        plugin.test(p, String.format(Locale.ROOT, "ASPD weapon=%s value=%.3f", w == null ? "-" : w.id(), as.getValue()));
    }

    /** 민첩 단계가 바뀌었으면 무기를 새로 만든다 (능력치를 건 뒤: 접속·출신·레벨 올리기·관리자 변경). */
    private void swingTier(Player p) {
        if (plugin.moves() == null || plugin.weaponRefresh() == null) return;
        int tier = plugin.moves().tier(p);
        Integer was = lastTier.put(p.getUniqueId(), tier);
        // 처음 보는 단계 (접속·다시 읽기 뒤) 는 적어 두기만 한다: 그때의 무기는 접속·다시 읽기의 새로 만들기 (WeaponRefresh, 같은 단계) 가 맡는다
        if (was == null || was == tier) return;
        int n = plugin.weaponRefresh().player(p, "dex");
        plugin.test(p, "SWING_TIER tier=" + tier + " dex=" + plugin.stats().of(p).dex() + " was=" + (was == null ? "-" : was) + " n=" + n);
    }

    public void forget(Player p) {
        lastSpeed.remove(p.getUniqueId());
        lastTier.remove(p.getUniqueId());
    }
}
