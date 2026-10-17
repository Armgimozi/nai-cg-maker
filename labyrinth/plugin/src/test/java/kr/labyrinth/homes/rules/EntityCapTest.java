package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.homes.HomesConfig;
import org.junit.jupiter.api.Test;

/** 엔티티 한도 (review R15): 동물 24 · 거치대 + 액자 + 그림 64. */
class EntityCapTest {

    @Test
    void defaults() {
        assertEquals(24, HomesConfig.DEFAULT.entityCaps().animals());
        assertEquals(64, HomesConfig.DEFAULT.entityCaps().decorations());
    }

    @Test
    void kinds() {
        assertEquals(Limits.EntityKind.DECORATION, Limits.entityKind("ARMOR_STAND", false));
        assertEquals(Limits.EntityKind.DECORATION, Limits.entityKind("item_frame", false));
        assertEquals(Limits.EntityKind.DECORATION, Limits.entityKind("GLOW_ITEM_FRAME", false));
        assertEquals(Limits.EntityKind.DECORATION, Limits.entityKind("PAINTING", false));
        assertEquals(Limits.EntityKind.ANIMAL, Limits.entityKind("COW", true));
        assertEquals(Limits.EntityKind.ANIMAL, Limits.entityKind("COPPER_GOLEM", true));
        assertEquals(Limits.EntityKind.OTHER, Limits.entityKind("ZOMBIE", false));
        assertEquals(Limits.EntityKind.OTHER, Limits.entityKind(null, false));
    }

    @Test
    void caps() {
        assertTrue(Limits.underCap(23, 24));
        assertFalse(Limits.underCap(24, 24), "25번째 안 됨");
        assertFalse(Limits.underCap(0, 0), "0 = 하나도 안 됨");
        assertTrue(Limits.capMessage(Limits.EntityKind.ANIMAL, 24).contains("24마리"));
        assertTrue(Limits.capMessage(Limits.EntityKind.DECORATION, 64).contains("64개"));
    }
}
