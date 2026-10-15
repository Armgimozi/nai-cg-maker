package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.DerivedStats;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatCalculator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

class StatCalculatorTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static final double EPS = 1e-9;

    @Test
    void guardianLevelOneFromClassBase() {
        ClassDef g = content.classDef("guardian");
        DerivedStats s = StatCalculator.compute(g, 1, Map.of(), new StatBlock(), 0.05, 1.5);
        int vit = g.baseStat(Stat.VIT);
        int intel = g.baseStat(Stat.INT), wis = g.baseStat(Stat.WIS);
        assertEquals(g.baseHp() + vit * 8.0, s.maxHp(), EPS);
        assertEquals(g.baseMp() + intel * 3.0 + wis * 2.0, s.maxMp(), EPS);
        assertEquals(vit * 0.5, s.defense(), EPS);
        // 맨손: 무기 피해 3 × (1 + 0.01 × STR) — 물리 (0.3.5: 직업 주스탯 혼합 없음)
        assertEquals(StatCalculator.UNARMED_DAMAGE * (1 + 0.01 * g.baseStat(Stat.STR)), s.attackPower(), EPS);
        assertEquals(WeaponAttack.UNARMED, s.weapon());
    }

    @Test
    void levelAllocationAndGearAdd() {
        ClassDef b = content.classDef("berserker");
        Map<Stat, Integer> alloc = new EnumMap<>(Stat.class);
        alloc.put(Stat.STR, 20);
        alloc.put(Stat.VIT, 10);
        StatBlock gear = new StatBlock().add("damage", 40).add("hp", 50).add("STR", 5).add("crit_chance", 0.1);
        DerivedStats s = StatCalculator.compute(b, 10, alloc, gear, 0.05, 1.5);
        int str = b.baseStat(Stat.STR) + 25;
        int vit = b.baseStat(Stat.VIT) + 10;
        assertEquals(str, s.stat(Stat.STR));
        assertEquals(40 * (1 + 0.01 * str), s.attackPower(), EPS);
        assertEquals(b.baseHp() + b.hpPerLevel() * 9 + vit * 8.0 + 50, s.maxHp(), EPS);
        double crit = 0.05 + b.baseStat(Stat.DEX) * 0.0025 + b.baseStat(Stat.LUK) * 0.0025 + 0.1;
        assertEquals(crit, s.critChance(), EPS);
        assertEquals(b.baseStat(Stat.DEX) * 0.001, s.evasion(), EPS);
    }

    @Test
    void strengthIsPhysicalIntelligenceIsMagicDexterityAddsNoPower() {
        StatBlock gear = new StatBlock().add("damage", 50);
        WeaponAttack sword = new WeaponAttack(WeaponAttack.Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0);
        WeaponAttack staff = new WeaponAttack(WeaponAttack.Style.CASTER, 0.9, DamageKind.MAGIC, 1.05);
        Map<Stat, Integer> strBuild = Map.of(Stat.STR, 40, Stat.INT, 10);
        DerivedStats phys = StatCalculator.compute(null, 20, strBuild, gear, 0.05, 1.5, sword, 50, 0.25);
        assertEquals(50 * 1.40, phys.attackPower(), EPS);
        assertEquals(1.40, phys.power(DamageKind.PHYSICAL), EPS);
        assertEquals(1.10, phys.power(DamageKind.MAGIC), EPS);
        assertEquals(1.25, phys.power(DamageKind.HYBRID), EPS);
        assertEquals(1.0, phys.power(DamageKind.FIXED), EPS);
        DerivedStats mag = StatCalculator.compute(null, 20, strBuild, gear, 0.05, 1.5, staff, 50, 0.25);
        assertEquals(50 * 1.10, mag.attackPower(), EPS, "시전 무기 = 마법 = 지능");
        assertEquals(DamageKind.MAGIC, mag.weaponKind());
        // 민첩은 공격력을 올리지 않는다 (치명·공속·회피만)
        DerivedStats dex0 = StatCalculator.compute(null, 20, Map.of(Stat.DEX, 0), gear, 0.05, 1.5, sword, 50, 0.25);
        DerivedStats dex80 = StatCalculator.compute(null, 20, Map.of(Stat.DEX, 80), gear, 0.05, 1.5, sword, 50, 0.25);
        assertEquals(dex0.attackPower(), dex80.attackPower(), EPS);
        assertEquals(0.05 + 80 * 0.0025, dex80.critChance(), EPS);
        assertEquals(80 * 0.001, dex80.evasion(), EPS);
        assertEquals(80 * 0.005, dex80.attackSpeed(), EPS);
    }

    @Test
    void attackSpeedDexShareCappedAt45TotalAt75() {
        WeaponAttack dagger = new WeaponAttack(WeaponAttack.Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0);
        // 민첩만: 0.5%/점, 민첩 몫은 +45% 까지 (Lv45 사냥꾼·그림자 민첩 134 → +45%, 예전이면 +67%)
        DerivedStats d134 = StatCalculator.compute(null, 45, Map.of(Stat.DEX, 134), new StatBlock(), 0.05, 1.5, dagger, 10, 0.25);
        assertEquals(StatCalculator.CAP_DEX_ATTACK_SPEED, d134.attackSpeed(), EPS);
        assertEquals(0.45, StatCalculator.CAP_DEX_ATTACK_SPEED, EPS);
        // 장비·버프는 그 위에 더해 합계 +75% 까지 — 가죽·가속 효과가 죽지 않는다
        DerivedStats withGear = StatCalculator.compute(null, 45, Map.of(Stat.DEX, 134), new StatBlock().add("attack_speed", 0.15),
                0.05, 1.5, dagger, 10, 0.25);
        assertEquals(0.60, withGear.attackSpeed(), EPS);
        DerivedStats capped = StatCalculator.compute(null, 45, Map.of(Stat.DEX, 300), new StatBlock().add("attack_speed", 0.9),
                0.05, 1.5, dagger, 10, 0.25);
        assertEquals(0.75, capped.attackSpeed(), EPS);
        assertEquals(0.75, StatCalculator.CAP_ATTACK_SPEED, EPS);
        // Lv25 이하는 바뀌지 않음 (민첩 76 → +38%)
        DerivedStats d76 = StatCalculator.compute(null, 25, Map.of(Stat.DEX, 76), new StatBlock(), 0.05, 1.5, dagger, 10, 0.25);
        assertEquals(0.38, d76.attackSpeed(), EPS);
        // 실제 간격 = 간격 ÷ (1 + 공속), 하한 0.25초
        assertEquals(0.45 / 1.75, capped.attackInterval(), EPS);
        assertEquals(0.25, StatCalculator.compute(null, 45, Map.of(Stat.DEX, 300), new StatBlock().add("attack_speed", 0.9),
                0.05, 1.5, new WeaponAttack(WeaponAttack.Style.MELEE, 0.42, DamageKind.PHYSICAL, 1.0), 10, 0.25).attackInterval(), EPS);
        assertEquals(1.0 / capped.attackInterval(), capped.attacksPerSecond(), EPS);
        // 활: 당김 = (한 발 주기 − 0.15) ÷ (1 + 공속), 실제 주기 = 당김 + 0.15
        WeaponAttack bow = new WeaponAttack(WeaponAttack.Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0);
        DerivedStats archer = StatCalculator.compute(null, 25, Map.of(Stat.DEX, 76), new StatBlock(), 0.05, 1.5, bow, 20, 0.25);
        assertEquals(1.0 / 1.38 + 0.15, archer.attackInterval(), EPS);
    }

    @Test
    void skillPowerFollowsFormula() {
        WeaponAttack sword = new WeaponAttack(WeaponAttack.Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0);
        StatBlock gear = new StatBlock().add("damage", 22);
        DerivedStats s = StatCalculator.compute(null, 10, Map.of(Stat.DEX, 40), gear, 0.05, 1.5, sword, 21.5, 0.25);
        double k = 1.47 - 0.143 * Math.max(0, 1 / 0.67 - 1.5);
        assertEquals(21.5 / 0.67 / k * (1 + 0.5 * 0.20), s.skillPower(), EPS);
        assertEquals(21.5, s.weaponMidDamage(), EPS);
        assertEquals(22, s.weaponDamage(), EPS);
        // 가운데값이 없으면 굴린 피해 W 를 쓴다
        DerivedStats noMid = StatCalculator.compute(null, 10, Map.of(), gear, 0.05, 1.5, sword, Double.NaN, 0.25);
        assertEquals(22 / 0.67 / k, noMid.skillPower(), EPS);
    }

    @Test
    void capsAreApplied() {
        StatBlock huge = new StatBlock().add("crit_chance", 5).add("evasion", 5).add("damage_reduction", 5)
                .add("cooldown_reduction", 5).add("lifesteal", 5).add("move_speed", 5).add("attack_speed", 5)
                .add("block_chance", 5).add("craft_discount", 5);
        DerivedStats s = StatCalculator.compute(null, 1, Map.of(), huge, 0.05, 1.5);
        assertEquals(StatCalculator.CAP_CRIT, s.critChance(), EPS);
        assertEquals(StatCalculator.CAP_EVASION, s.evasion(), EPS);
        assertEquals(StatCalculator.CAP_DR, s.damageReduction(), EPS);
        assertEquals(StatCalculator.CAP_CDR, s.cooldownReduction(), EPS);
        assertEquals(StatCalculator.CAP_LIFESTEAL, s.lifesteal(), EPS);
        assertEquals(StatCalculator.CAP_MOVE_SPEED, s.moveSpeed(), EPS);
        assertEquals(StatCalculator.CAP_ATTACK_SPEED, s.attackSpeed(), EPS);
        assertEquals(StatCalculator.CAP_BLOCK, s.blockChance(), EPS);
        assertEquals(StatCalculator.CAP_CRAFT, s.craftDiscount(), EPS);
    }

    @Test
    void intCooldownReductionCappedAtTwentyPercent() {
        Map<Stat, Integer> alloc = Map.of(Stat.INT, 500);
        DerivedStats s = StatCalculator.compute(null, 50, alloc, new StatBlock(), 0.05, 1.5);
        assertEquals(StatCalculator.CAP_CDR_INT, s.cooldownReduction(), EPS);
        assertTrue(s.maxMp() > 1500);
    }

    @Test
    void everyClassHasPositiveDerivedStats() {
        for (ClassDef c : content.classes().values()) {
            DerivedStats s = StatCalculator.compute(c, 1, Map.of(), new StatBlock(), 0.05, 1.5);
            assertTrue(s.maxHp() > 0 && s.maxMp() > 0 && s.attackPower() > 0, c.id());
        }
    }
}
