package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.content.WeaponTypes;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.stats.Stat;
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

    /** 모든 능력치가 n 인 판정 능력치. */
    private static Map<Stat, Integer> all(int n) {
        Map<Stat, Integer> m = new EnumMap<>(Stat.class);
        for (Stat s : Stat.values()) m.put(s, n);
        return m;
    }

    @Test
    void everyItemIsUsableByEveryClass() {
        int checked = 0;
        for (ItemDef def : content.items().values()) {
            for (String cls : classIdsAndNone()) {
                assertTrue(def.usableBy(cls), def.id() + " / " + cls);
                // 직업은 판정에 없다 — 능력치만 맞추면 누구든 (레벨 조건도 없음)
                assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, all(999)), def.id() + " / " + cls);
                checked++;
            }
        }
        assertTrue(checked > 1000, "검사 수 " + checked);
        // 능력치 조건은 직업과 상관없이 같다
        ItemDef ember = content.item("ember_greatsword").withRequires(StatRequirement.of(Map.of(Stat.STR, 60), Map.of()));
        assertEquals(EquipRules.Problem.STATS, EquipRules.check(ember, all(59)));
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(ember, all(60)));
    }

    @Test
    void classSkillPassesWithAnyLabyrinthWeapon() {
        // 무기 수는 고정으로 단언하지 않는다 (추가할 때마다 깨지지 않게) — 종류마다 19종 이상, 모든 층에 6종 전부
        Map<String, Integer> byType = new HashMap<>();
        Map<Integer, Set<String>> typesByFloor = new HashMap<>();
        for (ItemDef w : weapons()) {
            byType.merge(w.weaponType(), 1, Integer::sum);
            typesByFloor.computeIfAbsent(w.floor(), k -> new HashSet<>()).add(w.weaponType());
        }
        assertEquals(6, byType.size(), "무기 종류 " + byType);
        byType.forEach((t, n) -> assertTrue(n >= 19, t + " " + n + "종"));
        for (int f = 1; f <= content.maxFloor(); f++) assertEquals(byType.keySet(), typesByFloor.get(f), "지하 " + f + "층 무기 종류");
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
        assertEquals(content.classes().size() * weapons().size(), checked);
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
        // 요구 능력치를 못 맞춰 능력치가 안 붙는 무기는 '든 무기 없음' 취급 → 보너스 없음 (레벨은 보지 않는다)
        ItemDef stormEye = weapons().stream().filter(w -> "bow".equals(w.weaponType()) && w.rarity() == Rarity.MYTHIC).findFirst().orElseThrow()
                .withRequires(StatRequirement.of(Map.of(Stat.DEX, 120), Map.of()));
        assertNull(WeaponTypes.effective(stormEye, all(119)));
        assertEquals(stormEye, WeaponTypes.effective(stormEye, all(120)));
        assertEquals(9.0, WeaponTypes.classSkillCooldown(hunter, WeaponTypes.effective(stormEye, all(120)), 10.0), EPS);
        assertEquals(10.0, WeaponTypes.classSkillCooldown(hunter, WeaponTypes.effective(stormEye, all(119)), 10.0), EPS);
        ItemDef free = stormEye.withRequires(StatRequirement.NONE);
        assertEquals(free, WeaponTypes.effective(free, all(0)));
    }

    /** 같은 단계 = 같은 층·같은 집(몬스터·상자 공용 줄 / 대장간 전용 줄)·같은 요구 레벨에 무기 종류마다 1개씩 있는 묶음. 키 = "층:집:레벨". */
    private static Map<String, Map<String, ItemDef>> ladders() {
        Map<String, Map<String, ItemDef>> tiers = new HashMap<>();
        for (ItemDef w : weapons()) {
            String home = w.sources().contains("drop") ? "common" : w.sources().equals(List.of("craft")) ? "craft" : null;
            if (home == null) continue;
            Map<String, ItemDef> t = tiers.computeIfAbsent(w.floor() + ":" + home + ":" + w.levelReq(), k -> new HashMap<>());
            t.put(w.weaponType(), w);
        }
        tiers.values().removeIf(t -> t.size() < 6);
        return tiers;
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
        Map<String, Map<String, ItemDef>> ladders = ladders();
        assertTrue(ladders.size() >= 12, "6종이 다 있는 단계 수 " + ladders.size());
        double worstRaw = 1;
        for (ClassDef cls : content.classes().values()) {
            for (Map<String, ItemDef> tier : ladders.values()) {
                ItemDef ownW = tier.get(cls.weaponTypes().get(0));
                double ref = avgDamage(ownW);
                for (ItemDef w : tier.values()) {
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
            // Lv.1 에 직업 기본 능력치 + 시작 포인트로 들 수 있다
            int need = w.requirement().pointsNeeded(StatRequirement.playerStats(cls, Map.of(), Map.of()));
            assertTrue(need <= ContentValidator.START_POINTS, cls.id() + " → " + w.id() + " " + w.requirement().text() + " (" + need + " 필요)");
        }
    }

    @Test
    void tooltipShowsRecommendationNotRestriction() {
        // 장비 설명에는 직업을 아예 적지 않는다 (추천 직업 표기 없음 · 전용 표기 없음)
        for (ItemDef def : content.items().values()) {
            String all = String.join("\n", ItemTooltip.lines(content, def, null));
            assertFalse(all.contains("추천 직업"), def.id() + ": " + all);
            assertFalse(all.contains("직업 전용"), def.id() + ": " + all);
        }
        // 드롭 직업 편향(items.yml classes)은 그대로 남는다
        assertTrue(content.item("ember_greatsword").suitedFor("berserker"));
        assertFalse(content.item("ember_greatsword").suitedFor("priest"));
    }
}
