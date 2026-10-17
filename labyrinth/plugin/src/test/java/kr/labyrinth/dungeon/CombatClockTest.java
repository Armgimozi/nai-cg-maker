package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.UUID;
import kr.labyrinth.core.DeathPenaltyRules;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.Quit;
import kr.labyrinth.core.DeathPenaltyRules.QuitVerdict;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.2 리뷰: '싸우는 중' 기록 ({@link CombatClock}) — 퇴장 시전과 싸우는 중 접속 끊김이 함께 쓴다.
 * 앞 공략·마을에서 맞은 것이 새 공략의 끊김을 쓰러짐으로 만들면 안 된다 (잘못 잃음).
 */
class CombatClockTest {

    private static final UUID VIC = new UUID(1, 2);

    /** 공략 중 · 미궁 월드 · 살아 있음 · 시전 없음 · 플레이어가 끊음. */
    private static QuitVerdict quit(CombatClock c, long now) {
        return DeathPenaltyRules.combatQuit(Config.DEFAULT, new Quit(true, true, false, true, false, c.since(VIC, now), false, false));
    }

    @Test
    void hitInTheDungeonCountsForTenSeconds() {
        CombatClock c = new CombatClock();
        assertEquals(-1, c.since(VIC, 1_000), "맞은 적 없음");
        c.hurt(VIC, true, true, 1_000);
        assertEquals(1_000, c.last(VIC));
        assertEquals(4_000, c.since(VIC, 5_000));
        assertEquals(QuitVerdict.APPLY, quit(c, 10_999), "9.999초");
        assertEquals(QuitVerdict.NONE, quit(c, 11_000), "10초 지남");
    }

    @Test
    void onlyDungeonHitsCount() {
        CombatClock c = new CombatClock();
        c.hurt(VIC, true, false, 1_000);   // 입장 준비 중 마을 · 야생에서 맞음 (공략은 있음)
        c.hurt(VIC, false, true, 1_000);   // 공략 밖 (미궁 월드에 남은 사람 · 관리자)
        c.hurt(null, true, true, 1_000);
        assertEquals(-1, c.last(VIC));
        assertEquals(QuitVerdict.NONE, quit(c, 3_000), "미궁에 들어와 바로 끊어도 쓰러짐 아님");
    }

    @Test
    void leavingTheRunForgetsTheFight() {
        // 앞 공략: 0초에 맞음 → 6초에 /미궁 퇴장 5초 시전 시작 → 11초에 나감 (공략 떠남 = 지움)
        CombatClock c = new CombatClock();
        c.hurt(VIC, true, true, 0);
        c.forget(VIC);
        // 곧바로 새 공략에 들어와 (8초) 아직 아무에게도 안 맞고 끊음 → 쓰러짐 아님 (지우지 않으면 8초 전 피해로 쓰러짐)
        assertEquals(QuitVerdict.NONE, quit(c, 8_000));
        // 새 공략에서 맞으면 다시 셈
        c.hurt(VIC, true, true, 9_000);
        assertEquals(QuitVerdict.APPLY, quit(c, 9_500));
    }

    @Test
    void knockDownForgetsSoARevivedPlayerIsNotStillFighting() {
        CombatClock c = new CombatClock();
        c.hurt(VIC, true, true, 1_000);
        c.forget(VIC);                       // 쓰러짐 (Run.onMemberDeath · onCombatQuit)
        assertEquals(QuitVerdict.NONE, quit(c, 3_000), "부활 직후 끊음 = 그대로 합류");
    }

    @Test
    void clockGoingBackIsNotCombat() {
        CombatClock c = new CombatClock();
        c.hurt(VIC, true, true, 50_000);
        assertEquals(-10_000, c.since(VIC, 40_000));
        assertEquals(QuitVerdict.NONE, quit(c, 40_000), "시계가 뒤로 가도 한 시간씩 '싸우는 중' 이 되지 않음");
        c.clear();
        assertEquals(-1, c.last(VIC));
    }

    /**
     * 0.3.6.2 마무리: 귀환 주문서 시전 표시는 이 시계로 싸우는 중일 때만 — 주문서 쪽 판정은 마을 피해도 세므로,
     * 입장 직전 마을에서 맞고 미궁에서 바로 쓴 주문서 시전 중에 끊어도 쓰러짐이 아니다.
     */
    @Test
    void scrollCastCountsOnlyWhenTheDungeonClockSaysFighting() {
        ExitCast x = new ExitCast(null);
        x.clock().hurt(VIC, true, false, 1_000);            // 마을에서 맞음 (안 적힘)
        x.scrollCast(VIC, true, 3_000);                     // 미궁에 들어와 2초 뒤 주문서 (주문서 쪽은 5초 시전)
        assertEquals(false, x.combatCasting(VIC), "마을 피해로 시작한 주문서 시전은 끊김 쓰러짐이 아님");
        assertEquals(QuitVerdict.NONE, DeathPenaltyRules.combatQuit(Config.DEFAULT,
                new Quit(true, true, false, true, false, x.clock().since(VIC, 4_000), x.combatCasting(VIC), false)));

        x.clock().hurt(VIC, true, true, 10_000);            // 미궁에서 맞음
        x.scrollCast(VIC, true, 15_000);
        assertEquals(true, x.combatCasting(VIC));
        // 맞은 지 10초가 넘어도 시전 중이면 쓰러짐 (퇴장 시전과 같음)
        assertEquals(QuitVerdict.APPLY, DeathPenaltyRules.combatQuit(Config.DEFAULT,
                new Quit(true, true, false, true, false, x.clock().since(VIC, 21_000), x.combatCasting(VIC), false)));
        x.scrollCast(VIC, false, 21_000);
        assertEquals(false, x.combatCasting(VIC), "시전 끝");
        x.scrollCast(VIC, true, 25_000);                    // 맞은 지 15초 — 싸우는 중 아님
        assertEquals(false, x.combatCasting(VIC));
        x.scrollCast(null, true, 25_000);
    }
}
