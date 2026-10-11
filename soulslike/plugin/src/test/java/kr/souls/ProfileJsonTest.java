package kr.souls;

import kr.souls.data.Profile;
import kr.souls.progression.StatBlock;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 프로필 JSON (DESIGN 12.6): 돌려 쓰기, 모르는 칸 지키기, 소울 상한, 깨진 글. */
class ProfileJsonTest {
    @Test
    void roundTrip() {
        Profile p = Profile.fresh();
        assertFalse(p.born());
        p.setOrigin("knight", 1234L);
        p.setStats(new StatBlock(15, 9, 11, 13, 11, 9));
        p.setSouls(4321);
        p.markGiven("weapon:redin_guard_sword");
        p.setSettingsSeen(3);
        Profile q = Profile.parse(p.toJson());
        assertTrue(q.born());
        assertEquals("knight", q.origin());
        assertEquals(1234L, q.originAt());
        assertEquals(new StatBlock(15, 9, 11, 13, 11, 9), q.stats());
        assertEquals(4321, q.souls());
        assertTrue(q.wasGiven("weapon:redin_guard_sword"));
        assertFalse(q.wasGiven("weapon:redin_guard_shield"));
        assertEquals(3, q.settingsSeen());
    }

    /** 출신 다시 고르기는 한 번 (검토 repick-not-once): repicked 가 돌아오고, 쓰지 않았으면 JSON 에 칸이 없다. */
    @Test
    void repickedFlag() {
        Profile p = Profile.fresh();
        assertFalse(p.repicked());
        assertFalse(p.toJson().contains("repicked"));
        p.setRepicked(true);
        Profile q = Profile.parse(p.toJson());
        assertTrue(q.repicked());
        q.setRepicked(false);
        assertFalse(Profile.parse(q.toJson()).repicked());
        assertFalse(Profile.parse("{\"v\":1,\"repicked\":\"yes\"}").repicked());
    }

    @Test
    void keepsUnknownFields() {
        String json = "{\"v\":1,\"origin\":\"thief\",\"future\":{\"x\":1},\"stats\":{\"vig\":10,\"mnd\":10,\"end\":12,\"str\":9,\"dex\":16,\"int\":10}}";
        Profile p = Profile.parse(json);
        assertNotNull(p.extra("future"));
        assertTrue(p.toJson().contains("\"future\""));
        assertEquals(16, p.stats().dex());
    }

    @Test
    void soulsAreCapped() {
        Profile p = Profile.fresh();
        p.setSouls(Long.MAX_VALUE);
        assertEquals(Profile.SOULS_MAX, p.souls());
        p.setSouls(-5);
        assertEquals(0, p.souls());
    }

    @Test
    void brokenJson() {
        assertNull(Profile.parseStrict("{not json"));
        assertNotNull(Profile.parse("{not json"), "느슨한 읽기는 새 프로필");
        assertNull(Profile.parse("{not json").origin());
    }

    @Test
    void freshHasBaseStats() {
        assertEquals(StatBlock.BASE, Profile.fresh().stats());
        assertEquals(1, StatBlock.BASE.level());
    }
}
