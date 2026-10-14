package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.Test;

class PlayerDataTest {

    @Test
    void roundTripsThroughYaml() throws Exception {
        UUID id = UUID.randomUUID();
        PlayerData d = new PlayerData(id, "모험가");
        d.level(12);
        d.xp(345);
        d.statPoints(10);
        assertTrue(d.allocate(Stat.STR, 4));
        assertFalse(d.allocate(Stat.DEX, 100));
        d.classId("berserker");
        d.gold(1234);
        d.unlockUpTo(3);
        d.grantAchievement("first_clear_floor_1");
        d.equippedTitle("first_clear_floor_1");
        d.increment("kills", 7);
        d.increment("clears.floor_2", 1);
        d.accessory(1, new byte[] {1, 2, 3});
        d.ext().put("pvp.rating", 1032);

        PlayerData r = PlayerData.fromYaml(id, "x", d.toYaml());
        assertEquals("모험가", r.name());
        assertEquals(12, r.level());
        assertEquals(345, r.xp());
        assertEquals(6, r.statPoints());
        assertEquals(4, r.allocated(Stat.STR));
        assertEquals("berserker", r.classId());
        assertEquals(1234, r.gold());
        assertEquals(3, r.unlockedFloor());
        assertTrue(r.hasAchievement("first_clear_floor_1"));
        assertEquals("first_clear_floor_1", r.equippedTitle());
        assertEquals(7, r.counter("kills"));
        assertEquals(1, r.counter("clears.floor_2"));
        assertEquals(3, r.accessory(1).length);
        assertEquals(1032, ((Number) r.ext().get("pvp.rating")).intValue());
        assertFalse(r.isDirty());
    }

    @Test
    void resetReturnsAllPoints() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "a");
        d.statPoints(20);
        d.allocate(Stat.INT, 15);
        assertEquals(15, d.resetAllocation());
        assertEquals(20, d.statPoints());
        assertEquals(0, d.allocated(Stat.INT));
    }
}
