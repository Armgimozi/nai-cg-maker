package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.stats.DerivedStats;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatCalculator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 직업 장비 제한 없음 (GDD §4.4) + 무기 종류 없음 (0.3.5): 모든 직업이 모든 장비를 쓰고, 아무 미궁 무기로나 직업 스킬.
 * 직업 스킬 피해 = 스킬 위력 × skill_scale × 스킬 배율 — 든 무기가 무엇이든 같은 식, 같은 단계면 무거운 무기와 가벼운 무기가 비슷하다.
 */
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
        ItemDef ember = content.item("ember_greatsword").withRequires(StatRequirement.of(Map.of(Stat.STR, 60)));
        assertEquals(EquipRules.Problem.STATS, EquipRules.check(ember, all(59)));
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(ember, all(60)));
    }

    @Test
    void everyFloorHasEveryAttackStyle() {
        // 무기 종류는 없고 무기마다 공격 방식 — 층마다 근접·원거리·시전이 다 나온다
        Map<Integer, Set<WeaponAttack.Style>> byFloor = new HashMap<>();
        for (ItemDef w : weapons()) {
            assertNotNull(w.attack(), w.id());
            byFloor.computeIfAbsent(w.floor(), k -> EnumSet.noneOf(WeaponAttack.Style.class)).add(w.attack().style());
        }
        for (int f = 1; f <= content.maxFloor(); f++) {
            assertEquals(EnumSet.allOf(WeaponAttack.Style.class), byFloor.get(f), "지하 " + f + "층 공격 방식");
        }
    }

    @Test
    void effectiveWeaponNeedsItsRequirement() {
        // 요구 능력치를 못 맞춰 능력치가 안 붙는 무기는 '든 무기 없음' (레벨은 보지 않는다)
        ItemDef stormEye = weapons().stream().filter(w -> w.isRanged() && w.rarity() == Rarity.MYTHIC).findFirst().orElseThrow()
                .withRequires(StatRequirement.of(Map.of(Stat.DEX, 120)));
        assertNull(EquipRules.effective(stormEye, all(119)));
        assertEquals(stormEye, EquipRules.effective(stormEye, all(120)));
        ItemDef free = stormEye.withRequires(StatRequirement.NONE);
        assertEquals(free, EquipRules.effective(free, all(0)));
        assertNull(EquipRules.effective(content.item("novice_cap"), all(999)), "무기가 아니면 null");
        assertNull(EquipRules.effective(null, all(999)));
    }

    /** 그 무기를 든 Lv.lv 시전자 (모든 분배 n) 의 파생 능력치 — 무기 피해 = 범위 가운데값. */
    private static DerivedStats holding(ClassDef cls, ItemDef w, int lv, int n) {
        Range r = w.stats().get("damage");
        double mid = (r.min() + r.max()) / 2;
        return StatCalculator.compute(cls, lv, all(n), new StatBlock().add("damage", mid), 0.05, 1.5, w.attack(), mid,
                CombatMath.MIN_INTERVAL);
    }

    @Test
    void classSkillIsSkillPowerTimesSkillScaleWithAnyWeapon() {
        int checked = 0;
        for (ClassDef cls : content.classes().values()) {
            double scale = SkillContext.skillScale(cls);
            assertEquals(cls.skillScale(), scale, EPS);
            for (ClassDef.SkillDef sk : cls.skills()) {
                if ("none".equals(sk.kind())) continue;
                double mult = sk.params().dbl("damage", 1.0);
                DamageType type = "magic".equals(sk.kind()) ? DamageType.MAGIC : DamageType.MELEE;
                DamageKind kind = SkillContext.kindOf(sk, type);
                for (ItemDef w : weapons()) {
                    DerivedStats atk = holding(cls, w, 20, 10);
                    // SkillContext.damage = DamageContext.skill(mult × skill_scale) → DamageService 원피해
                    double raw = DamageService.rawAmount(atk, DamageContext.Base.SKILL, kind, mult * scale);
                    double magic = kind == DamageKind.MAGIC ? atk.magicDamage() : 0;
                    assertEquals(atk.skillPower() * atk.power(kind) * mult * scale * (1 + magic), raw, 1e-6,
                            cls.id() + ":" + sk.id() + " + " + w.id());
                    checked++;
                }
            }
        }
        assertTrue(checked > 1000, "검사 수 " + checked);
        assertEquals(1.0, SkillContext.skillScale(null), EPS, "직업이 없으면 1");
        // 지속 피해 비율도 같은 배율, 상태이상 potency 범위(0~1) 안에서 자른다
        assertEquals(0.25, SkillContext.dotRatio(0.10, 2.5), EPS);
        assertEquals(0.95, SkillContext.dotRatio(0.5, 2.5), EPS);
    }

    /** 같은 단계 = 같은 층·같은 집(몬스터·상자 / 대장간)·같은 내부 레벨에 6개 이상 있는 묶음. 키 = "층:집:레벨". */
    private static Map<String, List<ItemDef>> ladders() {
        Map<String, List<ItemDef>> tiers = new HashMap<>();
        for (ItemDef w : weapons()) {
            String home = w.sources().contains("drop") ? "common" : w.sources().equals(List.of("craft")) ? "craft" : null;
            if (home == null) continue;
            tiers.computeIfAbsent(w.floor() + ":" + home + ":" + w.levelReq(), k -> new ArrayList<>()).add(w);
        }
        tiers.values().removeIf(t -> t.size() < 6);
        return tiers;
    }

    @Test
    void sameTierWeaponsGiveSimilarSkillPower() {
        // 한 방 피해는 무게에 따라 2~3배 벌어지지만(손맛), 스킬 위력은 같은 단계면 ±20% 안 — 무거운 무기가 스킬을 독차지하지 않는다
        Map<String, List<ItemDef>> ladders = ladders();
        assertTrue(ladders.size() >= 12, "6개 이상인 단계 수 " + ladders.size());
        ClassDef shadow = content.classDef("shadow");
        double worstSp = 1, worstRaw = 1;
        for (Map.Entry<String, List<ItemDef>> e : ladders.entrySet()) {
            double spMin = Double.MAX_VALUE, spMax = 0, hitMin = Double.MAX_VALUE, hitMax = 0;
            for (ItemDef w : e.getValue()) {
                DerivedStats atk = holding(shadow, w, 20, 10);
                spMin = Math.min(spMin, atk.skillPower());
                spMax = Math.max(spMax, atk.skillPower());
                hitMin = Math.min(hitMin, atk.weaponDamage());
                hitMax = Math.max(hitMax, atk.weaponDamage());
            }
            assertTrue(spMax / spMin <= 1.2, e.getKey() + " 스킬 위력 " + spMin + " ~ " + spMax);
            worstSp = Math.max(worstSp, spMax / spMin);
            worstRaw = Math.max(worstRaw, hitMax / hitMin);
        }
        assertTrue(worstRaw > 2.0, "한 방 피해 최대 차이 " + worstRaw + " (스킬 위력 " + worstSp + ")");
    }

    @Test
    void starterWeaponIsCommonLevelOneAndUsable() {
        for (ClassDef cls : content.classes().values()) {
            ItemDef w = content.item(cls.starterWeapon());
            assertNotNull(w, cls.id() + " starter_weapon " + cls.starterWeapon());
            assertTrue(w.isWeapon(), w.id());
            assertEquals(cls.starterWeapon(), ClassDef.DEFAULT_STARTER_WEAPON.get(cls.id()), "jar 기본값 = classes.yml");
            assertEquals(Rarity.COMMON, w.rarity(), w.id());
            assertEquals(1, w.levelReq(), w.id());
            // Lv.1 에 직업 기본 능력치 + 시작 포인트로 들 수 있다
            int need = w.requirement().pointsNeeded(StatRequirement.playerStats(cls, Map.of(), Map.of()));
            assertTrue(need <= ContentValidator.START_POINTS, cls.id() + " → " + w.id() + " " + w.requirement().text() + " (" + need + " 필요)");
        }
    }

    @Test
    void tooltipShowsNoClassOrWeaponCategory() {
        // 장비 설명에는 직업을 아예 적지 않는다 (추천 직업 표기 없음 · 전용 표기 없음), 무기 첫 줄 분류는 '무기'
        for (ItemDef def : content.items().values()) {
            String all = String.join("\n", ItemTooltip.lines(content, def, null));
            assertFalse(all.contains("추천 직업"), def.id() + ": " + all);
            assertFalse(all.contains("직업 전용"), def.id() + ": " + all);
            if (def.isWeapon()) assertEquals("무기", ItemTooltip.category(def), def.id());
        }
        // 0.3.5 P3: 장비에는 classes 가 없다 — 드롭 편향은 요구 능력치(loot.yml own_build_bias)로
        for (ItemDef def : content.items().values()) {
            if (def.isGear()) assertTrue(def.classes().isEmpty(), def.id() + " classes " + def.classes());
        }
        assertTrue(content.item("ember_greatsword").suitedFor("berserker"));
        assertTrue(content.item("ember_greatsword").suitedFor("priest"));
    }
}
