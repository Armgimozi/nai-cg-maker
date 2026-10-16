package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.lang.reflect.Field;
import kr.labyrinth.core.DeathPenalty;
import org.bukkit.NamespacedKey;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 통합 (p0361 죽음 페널티 + bow-fix-0361 활): 활이 넣어 주는 미궁 화살(무한, 가방이 가득 차면 보조손)은 죽음 페널티가
 * 같은 표시로 알아보고 지우지 않는다 — 두 곳의 표시 이름이 어긋나면 화살이 '가방 2~3칸' 하나를 차지해 진짜 물건 대신 사라진다.
 */
class LabArrowPenaltyKeyTest {

    @Test
    void deathPenaltyKnowsTheBowArrow() throws Exception {
        Field f = DeathPenalty.class.getDeclaredField("LAB_ARROW");
        f.setAccessible(true);
        assertEquals(EquipmentListener.LAB_ARROW, (NamespacedKey) f.get(null));
    }
}
