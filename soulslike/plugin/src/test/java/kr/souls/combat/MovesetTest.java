package kr.souls.combat;

import kr.souls.Content;
import kr.souls.TestFiles;
import kr.souls.progression.Origins;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1a: content/moves.yml (3.6 의 분류표) 과 열쇠마다 jar 로 채워 읽기 (R20). */
class MovesetTest {
    private static final YamlConfiguration JAR = TestFiles.yaml("content/moves.yml");
    private static final Moveset M = Moveset.parse(JAR, 1.2);

    private static YamlConfiguration y(String text) {
        YamlConfiguration c = new YamlConfiguration();
        try {
            c.loadFromString(text);
        } catch (InvalidConfigurationException e) {
            throw new AssertionError(e);
        }
        return c;
    }

    @Test
    void jarFileReadsCleanly() {
        assertTrue(M.problems().isEmpty(), "jar 의 moves.yml 에 틀린 값이 없다: " + M.problems());
    }

    @Test
    void everyMeleeClassHasMoves() {
        for (String cls : Origins.M1_CLASSES) {
            // 활 (combat.bow, P7)·방패·촉매는 공격 동작이 아니다
            if (cls.equals("bow") || cls.endsWith("shield") || cls.startsWith("catalyst")) continue;
            assertNotNull(M.of(cls), "시작 무기의 분류 " + cls);
        }
        for (String cls : new String[] {"curved_sword", "ultra_greatsword", "halberd"}) assertNotNull(M.of(cls), cls);
        assertSame(M.of("dagger"), M.of("parrying_dagger"), "패링 단검은 단검의 동작 (as)");
    }

    /** 약공격 1단의 한 주기 = M1 전의 pve.swing-ticks (바닐라 공격 대기의 한 주기였던 값). */
    @Test
    void lightOneCycleEqualsOldSwingTicks() {
        Map<String, Integer> old = Map.of("dagger", 10, "straight_sword", 13, "curved_sword", 12, "greatsword", 22, "ultra_greatsword", 30,
                "axe", 18, "hammer", 18, "spear", 13, "halberd", 20);
        for (Map.Entry<String, Integer> e : old.entrySet()) assertEquals(e.getValue(), M.of(e.getKey()).lightCycle(), e.getKey());
    }

    @Test
    void designTableValues() {
        Moveset.Cls ss = M.of("straight_sword");
        assertEquals(3, ss.combo());
        assertEquals(5, ss.light(2).s());
        assertEquals(8, ss.light(2).r());
        assertEquals(new MoveTiming.Base(8, 2, 12), ss.heavy().base());
        assertSame(ss.light(0), ss.running(), "달리기 공격 틱이 없으면 약공격 1단");
        assertEquals(HitQuery.Shape.CONE, ss.spec().shape());
        assertEquals(100, ss.spec().angle());
        assertEquals(3.0, ss.spec().range());
        assertEquals(1.2, ss.spec().vertical(), "위아래는 combat.moves.vertical");
        assertEquals(14, ss.staminaLight());
        assertEquals(22, ss.staminaHeavy());
        assertEquals(12, ss.poiseLight());
        assertEquals(Hit.Type.SLASH, ss.type());
        assertFalse(ss.stab());
        Moveset.Cls sp = M.of("spear");
        assertEquals(HitQuery.Shape.LINE, sp.spec().shape());
        assertEquals(4.2, sp.spec().range());
        assertTrue(sp.stab(), "창은 찌르기 (Q6)");
        assertEquals(Hit.Type.THRUST, sp.type());
        assertEquals(Hit.Type.STRIKE, M.of("hammer").type());
        Moveset.Cls hb = M.of("halberd");
        assertEquals(2, hb.combo(), "미늘창은 2단");
        assertEquals(HitQuery.Shape.CONE, hb.light(0).spec().shape(), "1단 휩쓸기");
        assertEquals(HitQuery.Shape.LINE, hb.light(1).spec().shape(), "2단 찌르기");
        assertEquals(Hit.Type.THRUST, hb.light(1).type());
        assertEquals(4.2, hb.light(1).spec().range(), "단의 모양은 분류의 사거리를 이어받는다");
        assertSame(hb.light(0), hb.light(2), "단은 돌아간다");
        assertEquals(2, M.of("ultra_greatsword").combo());
    }

    /** 열쇠마다 jar 로 채운다: 사용자가 맞춘 값은 남고, 지운 열쇠는 jar 값, 틀린 값은 그 열쇠만 기본값. */
    @Test
    void perKeyFallback() {
        YamlConfiguration user = y("""
                straight_sword:
                  light: [[3, 2, 6]]
                  stamina: {light: 9}
                  range: abc
                dagger:
                  heavy: [6, x, 10]
                my_test: {light: [[2, 1, 8]], shape: line}
                """);
        Moveset m = Moveset.parse(Content.merge(JAR, user).yml(), 1.2);
        Moveset.Cls ss = m.of("straight_sword");
        assertEquals(1, ss.combo(), "목록은 통째로 사용자 값");
        assertEquals(new MoveTiming.Base(3, 2, 6), ss.light(0).base());
        assertEquals(9, ss.staminaLight(), "사용자 값");
        assertEquals(22, ss.staminaHeavy(), "지운 열쇠는 jar 값");
        assertEquals(new MoveTiming.Base(8, 2, 12), ss.heavy().base(), "jar 값");
        assertEquals(Moveset.DEFAULT_SPEC.range(), ss.spec().range(), "틀린 값은 기본값");
        assertTrue(m.problems().stream().anyMatch(x -> x.startsWith("straight_sword.range")), m.problems().toString());
        assertEquals(new MoveTiming.Base(6, 1, 10), M.of("dagger").heavy().base());
        assertEquals(new MoveTiming.Base(8, 2, 12), m.of("dagger").heavy().base(), "틀린 강공격은 기본값 (3.6 의 직검)");
        assertTrue(m.problems().stream().anyMatch(x -> x.startsWith("dagger.heavy")), m.problems().toString());
        assertNotNull(m.of("hammer"), "사용자 파일에 없는 분류는 jar 값");
        assertEquals(HitQuery.Shape.LINE, m.of("my_test").spec().shape(), "사용자가 더한 분류");
        assertEquals(14, m.of("my_test").staminaLight(), "빠진 열쇠는 코드 기본값");
    }

    @Test
    void emptyOrMissing() {
        Moveset m = Moveset.parse(y("broken: {light: oops}\n"), 1.2);
        assertEquals(1, m.of("broken").combo(), "약공격이 없으면 기본 한 단");
        assertFalse(m.problems().isEmpty());
        assertTrue(Moveset.parse(null, 1.2).all().isEmpty());
        assertTrue(Moveset.parse(y("x: {as: nothing}\n"), 1.2).problems().get(0).startsWith("x.as"));
    }
}
