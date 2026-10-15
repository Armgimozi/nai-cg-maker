package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 0.3.5 직업 값 (combat_spec §6.3 + review2 G1 · 주인 결정 7): 직업 스킬 배율 · 매의 눈 · 급소 찌르기 · 은총. */
class ClassNumbers035Test {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void skillScalePerClass() {
        Map<String, Double> want = Map.of("guardian", 1.00, "berserker", 1.55, "hunter", 1.55, "arcanist", 1.05,
                "priest", 0.90, "shadow", 0.70);
        assertEquals(want.keySet(), content.classes().keySet());
        want.forEach((id, v) -> assertEquals(v, content.classDef(id).skillScale(), 1e-9, id));
        assertEquals(want, ClassDef.DEFAULT_SKILL_SCALE, "키가 없는 classes.yml 의 기본값 = jar 값");
    }

    @Test
    void hunterShadowPassives() {
        ClassDef hunter = content.classDef("hunter");
        assertEquals("keen_eye", hunter.passive().id());
        assertEquals(0.30, hunter.passive().params().dbl("full_draw_bonus", 0), 1e-9);
        assertTrue(hunter.passive().description().contains("+30%"));
        ClassDef shadow = content.classDef("shadow");
        assertEquals("vital_point", shadow.passive().id());
        assertEquals(0.50, shadow.passive().params().dbl("crit_damage", 0), 1e-9, "그림자 급소 찌르기 치명 피해 +0.50");
        assertTrue(shadow.passive().description().contains("치명타 피해 +50%"));
    }

    @Test
    void priestGraceLowEarlyHighLate() {
        ClassDef priest = content.classDef("priest");
        var pp = priest.passive().params();
        double base = pp.dbl("magic_damage", 0), per = pp.dbl("magic_damage_per_level", 0), max = pp.dbl("magic_damage_max", 0);
        // 초반은 예전(+10%)보다 낮고, 깊은 층은 높다 — 사제 Lv10 +11% · Lv45 −9% 를 ±6% 안으로
        assertEquals(0.02, ClassPassives.graceMagicDamage(1, base, per, max), 1e-9);
        assertEquals(0.02 + 9 * 0.0036, ClassPassives.graceMagicDamage(10, base, per, max), 1e-9);
        assertTrue(ClassPassives.graceMagicDamage(10, base, per, max) < 0.10);
        assertEquals(0.02 + 44 * 0.0036, ClassPassives.graceMagicDamage(45, base, per, max), 1e-9);
        assertTrue(ClassPassives.graceMagicDamage(45, base, per, max) > 0.15);
        assertTrue(ClassPassives.graceMagicDamage(50, base, per, max) <= max + 1e-9);
        assertEquals(0.20, ClassPassives.graceMagicDamage(500, base, per, max), 1e-9, "상한");
        assertTrue(priest.passive().description().contains("마법 피해"));
    }
}
