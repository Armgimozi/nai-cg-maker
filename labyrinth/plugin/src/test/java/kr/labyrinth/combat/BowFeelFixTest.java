package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatCalculator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 활 손맛 고침 (bowfeel FIX_PLAN): 사냥꾼 당기며 걷기 ({@link BowDrawMove}) · 화살 피해 = 쏜 활 (B1).
 * 가방이 가득 찰 때 화살 넣기(B3)는 Bukkit 가방이 있어야 해서 여기서는 못 본다.
 */
class BowFeelFixTest {

    private static final double EPS = 1e-9;
    /** 사냥꾼 매의 눈 draw_move (classes.yml) — 고친 안의 값. */
    private static final double HUNTER_DRAW_MOVE = 0.60;

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void hunterInLabyrinthGetsDrawMoveOthersVanilla() {
        assertEquals(0.6, BowDrawMove.want("keen_eye", 0.6, true), EPS);
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("keen_eye", 0.6, false), EPS, "미궁 밖(야생·마을 = PvP 있는 곳)은 바닐라");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("bloodrage", 0.6, true), EPS, "다른 패시브는 바닐라");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want(null, 0.6, true), EPS);
        assertEquals(BowDrawMove.DEFAULT_HUNTER, BowDrawMove.want("keen_eye", Double.NaN, true), EPS, "키가 없는 classes.yml = jar 값");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("keen_eye", 0.2, true), EPS, "0.2 = 끔");
        assertEquals(1.0, BowDrawMove.want("keen_eye", 1.7, true), EPS, "위로 1.0 (바닐라 구성요소 범위 0~1)");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("keen_eye", 0.05, true), EPS, "바닐라보다 느리게는 안 됨");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want((ClassDef) null, true), EPS);
    }

    @Test
    void matchesDecidesWhenTheBowMustBeRewritten() {
        // 바닐라를 원하면 구성요소가 없어야 맞다
        assertTrue(BowDrawMove.matches(false, 0, false, BowDrawMove.VANILLA));
        assertFalse(BowDrawMove.matches(true, 0.6, false, BowDrawMove.VANILLA), "사냥꾼 활을 다른 직업이 들면 지운다");
        assertTrue(BowDrawMove.matches(true, 0.2f, false, BowDrawMove.VANILLA), "바닐라 값 그대로 붙어 있으면 다시 쓰지 않는다 (무한 고쳐 쓰기 방지)");
        // 사냥꾼 값이면 그 배율 + 달리기 꺼짐
        assertTrue(BowDrawMove.matches(true, 0.6f, false, 0.6), "float 로 저장된 값도 같다고 본다");
        assertFalse(BowDrawMove.matches(false, 0, false, 0.6), "새 활 = 구성요소 없음 → 붙인다");
        assertFalse(BowDrawMove.matches(true, 0.5, false, 0.6));
        assertFalse(BowDrawMove.matches(true, 0.6, true, 0.6), "달리기는 켜지 않는다");
        assertFalse(BowDrawMove.custom(BowDrawMove.VANILLA));
        assertTrue(BowDrawMove.custom(0.6));
    }

    @Test
    void onlyTheHunterPassiveCarriesDrawMove() {
        ClassDef hunter = content.classDef("hunter");
        assertEquals(BowDrawMove.PASSIVE, hunter.passive().id());
        assertEquals(HUNTER_DRAW_MOVE, hunter.passive().params().dbl(BowDrawMove.PARAM, Double.NaN), EPS);
        assertEquals(HUNTER_DRAW_MOVE, BowDrawMove.DEFAULT_HUNTER, EPS, "jar 기본값 = classes.yml 값");
        assertEquals(HUNTER_DRAW_MOVE, BowDrawMove.want(hunter, true), EPS);
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want(hunter, false), EPS);
        assertTrue(hunter.passive().description().contains("60%"), "패시브 설명에 당기며 걷기 값");
        assertTrue(hunter.passive().description().contains("미궁 안"), "미궁 안에서만이라는 말");
        for (ClassDef c : content.classes().values()) {
            if (c.id().equals("hunter")) continue;
            assertEquals(BowDrawMove.VANILLA, BowDrawMove.want(c, true), EPS, c.id() + " 은 바닐라 0.2 그대로 — 활이 모든 직업의 정답이 되지 않게");
        }
    }

    @Test
    void arrowUsesTheBowItWasShotFrom() {
        // B1: 화살 피해 W = 쏜 순간의 활 (지금 든 무기 = 단도 W 6 이어도 활 W 17)
        var dagger = StatCalculator.compute(null, 5, Map.of(Stat.STR, 7), new StatBlock().add("damage", 6), 0.05, 1.5,
                new WeaponAttack(WeaponAttack.Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0), 6, 0.25);
        double power = dagger.power(DamageKind.PHYSICAL);
        assertEquals(6 * power, DamageService.rawAmount(dagger, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 1.0), EPS,
                "바꿔 넣지 않으면 지금 든 무기");
        assertEquals(17 * power, DamageService.rawAmount(dagger, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 1.0, 17), EPS);
        assertEquals(17 * power * 0.5, DamageService.rawAmount(dagger, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 0.5, 17), EPS,
                "세기 배율은 그대로 곱한다");
        assertEquals(6 * power, DamageService.rawAmount(dagger, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 1.0, Double.NaN), EPS);
        assertEquals(dagger.skillPower() * power * 2.0,
                DamageService.rawAmount(dagger, DamageContext.Base.SKILL, DamageKind.PHYSICAL, 2.0, 17), EPS, "스킬은 스킬 위력 그대로");

        DamageContext ctx = DamageContext.attack(null, null, 1.0, DamageType.RANGED);
        assertTrue(Double.isNaN(ctx.weaponHit()));
        assertEquals(17, ctx.weaponHit(17).weaponHit(), EPS);
        assertTrue(Double.isNaN(ctx.weaponHit(0).weaponHit()), "0 이하는 무시");
        assertEquals(1.0, ctx.attackMultiplier(), EPS, "매의 눈 판정(세기 ≥ 0.999)은 배율로 그대로");
    }
}
