package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.random.RandomGenerator;
import kr.labyrinth.combat.DamageFormula;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * PvP 피해 훅의 결정 (pvp_spec §3·§5·§6) — {@link PvpDamage} 순수 부분 + 피해 공식. 실제 훅(PvpModule.PvpHook.before)은
 * 대상이 다른 파티 플레이어일 때만 이것을 곱하고 defenseScale(0)·critDamageScale(0.6) 을 넣는다.
 */
class PvpDamageHookTest {

    static final PvpConfig C = PvpConfig.DEFAULT;
    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static RandomGenerator fixed(double v) {
        return new RandomGenerator() {
            @Override
            public long nextLong() { return 0; }

            @Override
            public double nextDouble() { return v; }
        };
    }

    /** 같은 레벨 유리 → 유리 기본 공격 한 대 = 원피해 × m × (1 − R) × HP비, 방어 0. */
    @Test
    void basicHitFollowsFormula() {
        PvpMath.Target glass = new PvpMath.Target(20, 662, 20, 37);
        double f = PvpDamage.factor(C, new PvpDamage.Hit(20, "berserker", glass, 1.0, false));
        double expect = 2.0 * (1 - 0.4 * 57 / (57 + 160.0)) * 662 / (662 + 840.0);
        assertEquals(expect, f, 1e-9);
        // DamageService: 원피해 100 × f, 방어 × defenseScale 0 → 방어가 있어도 그대로
        var out = DamageFormula.compute(new DamageFormula.Input(100 * f, false, 0, 0, 0, 1.5, true, 0, true,
                37 * C.defenseWeight(), false, 0, 0, 0, true), fixed(0.99));
        assertEquals(100 * expect, out.damage(), 1e-9);
    }

    @Test
    void classCorrectionAndSkillMult() {
        PvpMath.Target t = new PvpMath.Target(35, 1500, 50, 100);
        double base = PvpDamage.factor(C, new PvpDamage.Hit(35, "berserker", t, 1.0, false));
        assertEquals(base * 0.9, PvpDamage.factor(C, new PvpDamage.Hit(35, "hunter", t, 1.0, false)), 1e-9);
        assertEquals(base * 1.2, PvpDamage.factor(C, new PvpDamage.Hit(35, "arcanist", t, 1.0, false)), 1e-9);
        assertEquals(base * 0.3, PvpDamage.factor(C, new PvpDamage.Hit(35, "berserker", t, 0.3, false)), 1e-9);
    }

    @Test
    void critScaledForPlayers() {
        var crit = DamageFormula.compute(new DamageFormula.Input(100, false, 0, 0, 1.0,
                DamageFormula.scaledCritDamage(2.5, C.critDamageScale()), true, 0, true, 0, false, 0, 0, 0, true), fixed(0));
        assertEquals(190, crit.damage(), 1e-9);
    }

    /** 수호의 맹세가 옮겨 받는 피해는 이미 PvP 공식을 거쳤다 — 두 번 줄이지 않는다. */
    @Test
    void relayedDamageIsNotReducedTwice() {
        assertTrue(PvpDamage.relayed("guardian_oath"));
        assertFalse(PvpDamage.relayed("spin_slash"));
        assertFalse(PvpDamage.relayed(null));
    }

    /** 스킬 pvp_mult: 직업 스킬 id · ws:/mech: 무기 스킬 · 지속 피해(effect:) 1 · 기본 공격 1. */
    @Test
    void skillMultBySource() {
        ClassDef hunter = content.classDef("hunter");
        assertEquals(0.3, PvpDamage.skillMult(content, hunter, null, "arrow_storm", true), 1e-9);
        assertEquals(0.35, PvpDamage.skillMult(content, hunter, null, "meteor_fall", true), 1e-9, "다른 직업 스킬 id 도");
        assertEquals(1.0, PvpDamage.skillMult(content, hunter, null, "hunters_mark", true), 1e-9, "적지 않은 스킬 = 1");
        assertEquals(0.2, PvpDamage.skillMult(content, null, null, "ws:tempest_bow:SNEAK_LEFT", true), 1e-9);
        assertEquals(0.2, PvpDamage.skillMult(content, null, null, "mech:tempest_bow:SNEAK_LEFT", true), 1e-9);
        assertEquals(0.85, PvpDamage.skillMult(content, null, null, "mech:tempest_bow:SNEAK_RIGHT", true), 1e-9);
        assertEquals(1.0, PvpDamage.skillMult(content, null, null, "ws:tempest_bow:LEFT", true), 1e-9);
        assertEquals(1.0, PvpDamage.skillMult(content, null, null, "effect:bleed", false), 1e-9, "지속 피해는 1");
        assertEquals(1.0, PvpDamage.skillMult(content, null, null, null, false), 1e-9, "기본 공격 1");
        assertEquals(1.0, PvpDamage.skillMult(content, null, null, "ws:nope:RIGHT", true), 1e-9);
        ItemDef held = content.item("emberforge_warhammer");
        String id = held.weaponSkill("RIGHT").id();
        assertEquals(0.85, PvpDamage.skillMult(content, null, held, id, true), 1e-9, "옛 출처(구현 id)는 손에 든 무기에서");
    }

    /** 최대 HP 비율 피해는 레벨 곡선·완충 없이 (이미 상대 HP 기준). */
    @Test
    void percentDamage() {
        PvpMath.Target t = new PvpMath.Target(50, 3000, 0, 0);
        assertEquals(1.0, PvpDamage.factor(C, new PvpDamage.Hit(50, null, t, 1.0, true)), 1e-9);
    }

    /** 높은 레벨이 낮은 레벨을 칠 때 기준 배율은 높은 레벨 것 (§10.8). */
    @Test
    void levelGap() {
        PvpMath.Target low = new PvpMath.Target(20, 662, 20, 37);
        double fromHigh = PvpDamage.factor(C, new PvpDamage.Hit(50, null, low, 1.0, false));
        double fromSame = PvpDamage.factor(C, new PvpDamage.Hit(20, null, low, 1.0, false));
        assertTrue(fromHigh < fromSame);
    }
}
