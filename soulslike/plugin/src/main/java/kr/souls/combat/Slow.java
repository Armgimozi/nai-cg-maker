package kr.souls.combat;

import kr.souls.Keys;
import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlotGroup;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 전투가 거는 느려짐과 뿌리 (M1 P1-0 계약, PS 의 S4 를 받아 바꾼 곳). 공격 중 느려짐 (P1a), 치명타 중 뿌리 (P3), 넘어짐 (P4) 이
 * 모두 여기를 지난다. 이 사람의 걷기 속도를 바꾸는 곳은 여기 하나다.
 * <ul>
 *   <li>S4: MOVEMENT_SPEED 수정자 (와 대안이던 구속 효과) 는 클라이언트의 시야를 좁힌다 (−25% 1.18×, −50% 1.42×, 뿌리 2.22×,
 *       구속 II 1.23×). {@link Player#setWalkSpeed} 는 능력의 걷기 속도와 이동 속도 바탕값을 함께 바꿔 시야가 그대로다 (1.00×).
 *       그래서 느려짐은 setWalkSpeed (바닐라 0.2 × 배율), 뿌리는 setWalkSpeed(0) 에 JUMP_STRENGTH −100% 임시 수정자.</li>
 *   <li>걸어 둔 몫이 여럿이면 가장 느린 것 하나만 듣는다 (곱하지 않는다: 공격 −50% 와 다른 −50% 가 겹쳐 −75% 가 되지 않게).
 *       뿌리 (0) 가 늘 이긴다. 민첩·장비 무게의 수정자 (AttributeApplier·Load) 는 그 위에 그대로 곱해진다.</li>
 *   <li>걷기 속도는 플레이어 파일에 저장된다 (S4): 나가기·죽음·다른 세계·끄기·접속 때 CombatReset 이 {@link #reset} 으로 0.2 로
 *       되돌린다 (Souls 가 "slow" 로 건다). 서버가 갑자기 꺼져 느린 채 저장되어도 다음 접속에 바로잡힌다.</li>
 * </ul>
 * 바꾼 값만 보낸다 (같으면 setWalkSpeed 를 부르지 않는다).
 */
public final class Slow {
    /** 바닐라 걷기 속도 (Player.setWalkSpeed 의 기본) */
    public static final float WALK = 0.2f;
    /** 뿌리의 뛰기 수정자 */
    public static final NamespacedKey ROOT = Keys.of("root");

    private static final Map<UUID, Map<String, Double>> BY = new HashMap<>();

    private Slow() {}

    /**
     * owner 의 몫을 건다: factor 1 이면 떼기, 0 이면 뿌리, 그 사이는 걷기 배율 (0.5 = −50%). 0..1 밖은 자른다.
     * @return 지금 듣는 배율
     */
    public static double set(Player p, String owner, double factor) {
        if (p == null || owner == null) return 1;
        double f = Double.isNaN(factor) ? 1 : Math.max(0, Math.min(1, factor));
        Map<String, Double> m = BY.computeIfAbsent(p.getUniqueId(), k -> new LinkedHashMap<>());
        if (f >= 1) m.remove(owner);
        else m.put(owner, f);
        if (m.isEmpty()) BY.remove(p.getUniqueId());
        return apply(p);
    }

    /** owner 의 몫을 뗀다. */
    public static double clear(Player p, String owner) {
        return set(p, owner, 1);
    }

    /** 뿌리 (걷기 0, 뛰기 0). */
    public static double root(Player p, String owner) {
        return set(p, owner, 0);
    }

    /** 모든 몫을 떼고 바닐라 값으로 (CombatReset). */
    public static void reset(Player p) {
        if (p == null) return;
        BY.remove(p.getUniqueId());
        apply(p);
    }

    /** 지금 듣는 배율 (걸린 것이 없으면 1). */
    public static double factor(Player p) {
        Map<String, Double> m = p == null ? null : BY.get(p.getUniqueId());
        return strongest(m == null ? null : m.values());
    }

    /** 걸린 몫들 가운데 듣는 것 (가장 작은 값, 없으면 1). 순수 함수 (SlowTest). */
    public static double strongest(Iterable<Double> factors) {
        double f = 1;
        if (factors != null) for (Double v : factors) if (v != null && v < f) f = Math.max(0, v);
        return f;
    }

    /** 걸린 몫 (시험 줄). */
    public static Map<String, Double> owners(Player p) {
        Map<String, Double> m = p == null ? null : BY.get(p.getUniqueId());
        return m == null ? Map.of() : Map.copyOf(m);
    }

    private static double apply(Player p) {
        double f = factor(p);
        float want = (float) (WALK * f);
        if (Math.abs(p.getWalkSpeed() - want) > 1e-6) p.setWalkSpeed(want);
        AttributeInstance jump = p.getAttribute(Attribute.JUMP_STRENGTH);
        if (jump != null) {
            boolean rooted = f <= 0;
            boolean has = jump.getModifier(ROOT) != null;
            if (rooted && !has) {
                jump.addTransientModifier(new AttributeModifier(ROOT, -1, AttributeModifier.Operation.MULTIPLY_SCALAR_1, EquipmentSlotGroup.ANY));
            } else if (!rooted && has) {
                jump.removeModifier(ROOT);
            }
        }
        return f;
    }
}
