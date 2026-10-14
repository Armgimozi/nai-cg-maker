package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.WeaponTypes;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemTooltip;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 직업 장비 제한 없음 (GDD §4.4): 모든 직업이 모든 장비를 쓰고, 아무 미궁 무기로나 직업 스킬 — 추천 무기는 재사용 대기 보너스만. */
class WeaponFreedomTest {

    private static final double EPS = 1e-9;

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static List<String> classIdsAndNone() {
        List<String> ids = new ArrayList<>(content.classes().keySet());
        ids.add(null);
        return ids;
    }

    private static List<ItemDef> weapons() {
        return content.items().values().stream().filter(ItemDef::isWeapon).toList();
    }

    @Test
    void everyItemIsUsableByEveryClass() {
        int checked = 0;
        for (ItemDef def : content.items().values()) {
            for (String cls : classIdsAndNone()) {
                assertTrue(def.usableBy(cls), def.id() + " / " + cls);
                assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, Math.max(50, def.levelReq()), cls), def.id() + " / " + cls);
                checked++;
            }
        }
        assertTrue(checked > 1000, "검사 수 " + checked);
        // 레벨 조건은 그대로
        ItemDef ember = content.item("ember_greatsword");
        assertEquals(EquipRules.Problem.LEVEL, EquipRules.check(ember, ember.levelReq() - 1, "priest"));
    }

    @Test
    void classSkillPassesWithAnyLabyrinthWeapon() {
        assertTrue(weapons().size() >= 66);
        int checked = 0;
        for (ClassDef cls : content.classes().values()) {
            for (ItemDef w : weapons()) {
                assertTrue(WeaponTypes.canCastClassSkill(cls, w), cls.id() + " + " + w.id());
                checked++;
            }
            // 사용자 결정 "언제나": 맨손·방패·장신구·재료·바닐라 무기로도 나간다
            assertTrue(WeaponTypes.canCastClassSkill(cls, null));
            for (ItemDef other : content.items().values()) {
                if (!other.isWeapon()) assertTrue(WeaponTypes.canCastClassSkill(cls, other), cls.id() + " + " + other.id());
            }
        }
        assertEquals(6 * weapons().size(), checked);
        assertFalse(WeaponTypes.canCastClassSkill(null, content.item("ember_greatsword")), "직업이 없으면 직업 스킬 없음");
    }

    @Test
    void recommendedWeaponCutsClassSkillCooldown() {
        ClassDef hunter = content.classDef("hunter");
        ItemDef bow = content.item("corridor_longbow");
        ItemDef dagger = content.item("moss_dirk");
        assertNotNull(bow);
        assertNotNull(dagger);
        assertTrue(WeaponTypes.recommended(hunter, bow));
        assertFalse(WeaponTypes.recommended(hunter, dagger));
        assertEquals(9.0, WeaponTypes.classSkillCooldown(hunter, bow, 10.0), EPS);
        assertEquals(10.0, WeaponTypes.classSkillCooldown(hunter, dagger, 10.0), EPS);
        assertEquals(10.0, WeaponTypes.classSkillCooldown(hunter, null, 10.0), EPS);
        // 레벨이 모자라 능력치가 안 붙는 무기는 '든 무기 없음' 취급 → 보너스 없음
        ItemDef stormEye = weapons().stream().filter(w -> "bow".equals(w.weaponType()) && w.rarity() == Rarity.MYTHIC).findFirst().orElseThrow();
        assertNull(WeaponTypes.effective(stormEye, stormEye.levelReq() - 1));
        assertEquals(stormEye, WeaponTypes.effective(stormEye, stormEye.levelReq()));
    }

    /** 무기 종류별 단계 사다리 (레벨 → 희귀도 순). */
    private static Map<String, List<ItemDef>> ladders() {
        Map<String, List<ItemDef>> by = new HashMap<>();
        for (ItemDef w : weapons()) by.computeIfAbsent(w.weaponType(), k -> new ArrayList<>()).add(w);
        by.values().forEach(l -> l.sort(Comparator.comparingInt(ItemDef::levelReq).thenComparingInt(d -> d.rarity().ordinal())));
        return by;
    }

    private static double avgDamage(ItemDef w) {
        Range r = w.stats().get("damage");
        return (r.min() + r.max()) / 2;
    }

    @Test
    void classSkillPowerDoesNotDependOnWeaponType() {
        ClassDef shadow = content.classDef("shadow");
        assertEquals(0.62 / 1.55, WeaponTypes.classSkillScale(shadow, content.item("ember_greatsword")), EPS);
        assertEquals(1.0, WeaponTypes.classSkillScale(shadow, content.item("moss_dirk")), EPS);
        assertEquals(1.0, WeaponTypes.classSkillScale(shadow, null), EPS);

        // 같은 단계면 어떤 무기를 들든 직업 스킬 기준 피해가 추천 무기와 ±20% 안 (환산이 없으면 최대 2.5배 차이)
        Map<String, List<ItemDef>> ladders = ladders();
        double worstRaw = 1;
        for (ClassDef cls : content.classes().values()) {
            List<ItemDef> own = ladders.get(cls.weaponTypes().get(0));
            for (List<ItemDef> ladder : ladders.values()) {
                assertEquals(own.size(), ladder.size());
                for (int i = 0; i < ladder.size(); i++) {
                    ItemDef w = ladder.get(i);
                    double ref = avgDamage(own.get(i));
                    double scaled = avgDamage(w) * WeaponTypes.classSkillScale(cls, w) / ref;
                    assertTrue(scaled > 0.8 && scaled < 1.2, cls.id() + " + " + w.id() + " → " + scaled);
                    worstRaw = Math.max(worstRaw, Math.max(avgDamage(w) / ref, ref / avgDamage(w)));
                }
            }
        }
        assertTrue(worstRaw > 2.0, "환산 전 최대 차이 " + worstRaw);
        // 지속 피해 비율도 같은 환산, 상태이상 potency 범위(0~1) 안에서 자른다
        assertEquals(0.25, SkillContext.dotRatio(0.10, 2.5), EPS);
        assertEquals(0.95, SkillContext.dotRatio(0.5, 2.5), EPS);
    }

    @Test
    void starterWeaponIsLowestRecommendedWeapon() {
        for (ClassDef cls : content.classes().values()) {
            ItemDef w = WeaponTypes.starterWeapon(content.items().values(), cls);
            assertNotNull(w, cls.id());
            assertTrue(cls.recommendsWeapon(w.weaponType()), cls.id() + " → " + w.id());
            assertEquals(Rarity.COMMON, w.rarity(), w.id());
            assertEquals(1, w.levelReq(), w.id());
        }
    }

    @Test
    void tooltipShowsRecommendationNotRestriction() {
        String weapon = String.join("\n", ItemTooltip.lines(content, content.item("ember_greatsword"), null));
        assertTrue(weapon.contains("추천 직업 <white>광전사"), weapon);
        assertTrue(weapon.contains("모든 직업 사용 가능"), weapon);
        assertFalse(weapon.contains("전용"), weapon);
        for (ItemDef def : content.items().values()) {
            if (!def.isGear()) continue;
            String all = String.join("\n", ItemTooltip.lines(content, def, null));
            assertFalse(all.contains(" 직업 <white>") && !all.contains("추천 직업"), def.id() + ": " + all);
        }
        // 장신구는 추천 직업이 없다
        ItemDef acc = content.items().values().stream().filter(d -> d.type() == kr.labyrinth.content.ItemType.ACCESSORY).findFirst().orElseThrow();
        assertFalse(String.join("\n", ItemTooltip.lines(content, acc, null)).contains("추천 직업"));
        // 추천(드롭 편향·대장간 필터)은 그대로 남는다
        assertTrue(content.item("ember_greatsword").suitedFor("berserker"));
        assertFalse(content.item("ember_greatsword").suitedFor("priest"));
        assertTrue(acc.suitedFor("priest"));
    }
}
