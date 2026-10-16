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
 * 0.3.6.1 활 손맛 고침 (bowfeel FIX_PLAN · 주인 결정 1): 사냥꾼 당기며 걷기 — 어디서나 ({@link BowDrawMove}) · 화살 피해 = 쏜 활 (B1).
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
    void hunterGetsDrawMoveEverywhereOthersVanilla() {
        // 주인 결정 1 (0.3.6.1): 사냥꾼은 어디서나 (미궁·야생·마을·PvP) — 어디에 있는지는 묻지 않는다
        assertEquals(0.6, BowDrawMove.want("keen_eye", 0.6), EPS);
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("bloodrage", 0.6), EPS, "다른 패시브는 바닐라");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want(null, 0.6), EPS);
        assertEquals(BowDrawMove.DEFAULT_HUNTER, BowDrawMove.want("keen_eye", Double.NaN), EPS, "키가 없는 classes.yml = jar 값");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("keen_eye", 0.2), EPS, "0.2 = 끔");
        assertEquals(1.0, BowDrawMove.want("keen_eye", 1.7), EPS, "위로 1.0 (바닐라 구성요소 범위 0~1)");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want("keen_eye", 0.05), EPS, "바닐라보다 느리게는 안 됨");
        assertEquals(BowDrawMove.VANILLA, BowDrawMove.want((ClassDef) null), EPS, "직업 없음 = 바닐라");
    }

    @Test
    void theBowFollowsWhoeverHoldsIt() {
        // 같은 활 하나가 사냥꾼 → 다른 직업 → 사냥꾼으로 (거래·버림·엔더 상자·전직): 손에 들 때마다 든 사람 값으로 고쳐 쓴다
        ClassDef hunter = content.classDef("hunter");
        boolean present = false;
        double speed = 0;
        String[] holders = {"hunter", "guardian", "hunter", "arcanist", "priest", "hunter", null, "hunter"};
        for (String holder : holders) {
            ClassDef c = holder == null ? null : content.classDef(holder);
            assertTrue(holder == null || c != null, holder);
            double want = BowDrawMove.want(c);
            if (!BowDrawMove.matches(present, speed, false, want)) {
                // EquipmentListener.setBowMove: 사냥꾼 값이면 붙이고, 바닐라면 지운다
                present = BowDrawMove.custom(want);
                speed = present ? (float) want : 0;
            }
            assertTrue(BowDrawMove.matches(present, speed, false, want), holder + " 손에서 맞음 — 한 번 고치면 다시 고치지 않는다");
            assertEquals(c == hunter, present, holder + ": 사냥꾼만 구성요소가 붙어 있다");
        }
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
        assertEquals(HUNTER_DRAW_MOVE, BowDrawMove.want(hunter), EPS);
        assertTrue(hunter.passive().description().contains("60%"), "패시브 설명에 당기며 걷기 값");
        assertFalse(hunter.passive().description().contains("미궁 안"), "어디서나 — '미궁 안에서만' 이라는 말이 없다");
        for (ClassDef c : content.classes().values()) {
            if (c.id().equals("hunter")) continue;
            assertEquals(BowDrawMove.VANILLA, BowDrawMove.want(c), EPS, c.id() + " 은 바닐라 0.2 그대로 — 활이 모든 직업의 정답이 되지 않게");
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
        // 화살: DamageService.deal 은 hasWeaponHit() 이고 기준이 PER_HIT 이면 이 값으로 (c0361 마법탄과 같은 길)
        assertEquals(17 * power, DamageService.rawAmount(dagger, 17.0, DamageKind.PHYSICAL, 1.0), EPS);
        assertEquals(17 * power * 0.5, DamageService.rawAmount(dagger, 17.0, DamageKind.PHYSICAL, 0.5), EPS, "세기 배율은 그대로 곱한다");
        assertEquals(dagger.skillPower() * power * 2.0,
                DamageService.rawAmount(dagger, DamageContext.Base.SKILL, DamageKind.PHYSICAL, 2.0), EPS, "스킬은 스킬 위력 그대로");

        DamageContext ctx = DamageContext.attack(null, null, 1.0, DamageType.RANGED);
        assertTrue(Double.isNaN(ctx.weaponHit()));
        assertFalse(ctx.hasWeaponHit());
        assertEquals(17, ctx.weaponHit(17).weaponHit(), EPS);
        assertTrue(ctx.hasWeaponHit());
        assertTrue(Double.isNaN(ctx.weaponHit(0).weaponHit()), "0 이하는 '없음' (지금 든 무기)");
        assertFalse(ctx.weaponHit(-3).hasWeaponHit());
        assertFalse(ctx.weaponHit(Double.NaN).hasWeaponHit());
        assertEquals(1.0, ctx.attackMultiplier(), EPS, "매의 눈 판정(세기 ≥ 0.999)은 배율로 그대로");
    }
}
