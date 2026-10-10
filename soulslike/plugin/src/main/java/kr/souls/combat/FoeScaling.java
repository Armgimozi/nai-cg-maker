package kr.souls.combat;

import kr.souls.Keys;
import kr.souls.Souls;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.inventory.EquipmentSlotGroup;

import java.util.Locale;

/**
 * 난이도의 적 체력 (5.7 의 enemy-health, 검토 difficulty-promises-unbuilt). souls 세계의 적 (Enemy: 몬스터·슬라임·팬텀 …) 에
 * MAX_HEALTH 수정자 souls:difficulty (ADD_MULTIPLIED_TOTAL, 배율 − 1) 를 건다.
 * <ul>
 *   <li>생길 때 (CreatureSpawnEvent: 자연·스포너·알·명령 소환 모두): 수정자를 걸고 체력을 새 최대치로 채운다.</li>
 *   <li>세계 설정이 바뀔 때 (StartFlow.apply) 와 다시 읽을 때: 올라와 있는 적 모두에 다시 건다 (체력 비율은 지킨다).</li>
 *   <li>청크가 올라올 때 (EntitiesLoadEvent): 저장된 수정자가 지금 난이도와 다르면 다시 건다 (내려가 있는 동안 바뀌었을 때).</li>
 * </ul>
 * 저장되는 수정자라 적이 저장되어도 그대로 남는다. 보통 (×1.0) 이면 수정자를 떼어 바닐라 값이다. 적의 몸 (가상 체력, 6.1) 이 생기는 M2 에서는
 * 그 체력에 같은 배율을 곱하고 이 클래스는 바닐라 몹에만 남는다. 강인도·패링 창·에스트 횟수는 그 체계 (M1·M2) 가 생길 때 듣는다.
 */
public final class FoeScaling implements Listener {
    public static final NamespacedKey MOD = Keys.of("difficulty");

    private final Souls plugin;

    public FoeScaling(Souls plugin) {
        this.plugin = plugin;
    }

    /** 난이도 체력을 받는 적인가. */
    public static boolean foe(Entity e) {
        return e instanceof Enemy && e instanceof LivingEntity && !(e instanceof Player);
    }

    /**
     * 이 적의 수정자를 지금 난이도에 맞춘다. fill 이면 체력을 새 최대치로 (갓 생긴 적), 아니면 체력 비율을 지킨다. 이미 맞으면 아무것도 하지
     * 않는다. 바꿨으면 true.
     */
    public boolean apply(LivingEntity le, boolean fill) {
        if (le.isDead() || (!le.isValid() && !fill)) return false;
        AttributeInstance a = le.getAttribute(Attribute.MAX_HEALTH);
        if (a == null) return false;
        double want = plugin.difficulty().enemyHealth() - 1;
        AttributeModifier cur = a.getModifier(MOD);
        double have = cur == null ? 0 : cur.getAmount();
        if (!fill && Math.abs(have - want) < 1e-9) return false;
        double before = a.getValue();
        double ratio = before <= 0 ? 1 : le.getHealth() / before;
        a.removeModifier(MOD);
        if (Math.abs(want) > 1e-9) a.addModifier(new AttributeModifier(MOD, want, AttributeModifier.Operation.MULTIPLY_SCALAR_1, EquipmentSlotGroup.ANY));
        double max = a.getValue();
        le.setHealth(fill ? max : Math.max(Math.min(max, 0.5), Math.min(max, ratio * max)));
        return true;
    }

    /** 올라와 있는 souls 세계의 적 모두 (세계 설정이 바뀌었을 때, 다시 읽을 때). 바꾼 수. */
    public int applyAll() {
        World w = plugin.worlds() == null ? null : plugin.worlds().world();
        if (w == null) return 0;
        int n = 0;
        for (LivingEntity le : w.getLivingEntities()) if (foe(le) && apply(le, false)) n++;
        if (n > 0) plugin.test(null, String.format(Locale.ROOT, "FOES rescaled=%d mult=%.2f", n, plugin.difficulty().enemyHealth()));
        return n;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent e) {
        if (!foe(e.getEntity()) || !plugin.worlds().isGameWorld(e.getEntity().getWorld())) return;
        apply(e.getEntity(), true);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onLoad(EntitiesLoadEvent e) {
        if (!plugin.worlds().isGameWorld(e.getWorld())) return;
        for (Entity en : e.getEntities()) if (foe(en)) apply((LivingEntity) en, false);
    }
}
