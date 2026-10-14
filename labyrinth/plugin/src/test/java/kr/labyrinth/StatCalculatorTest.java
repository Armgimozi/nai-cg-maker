package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;
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
        // 맨손: 무기 피해 3 × (1 + 0.02 × (0.6 STR + 0.4 VIT))
        double mix = 0.6 * g.baseStat(Stat.STR) + 0.4 * vit;
        assertEquals(StatCalculator.UNARMED_DAMAGE * (1 + 0.02 * mix), s.attackPower(), EPS);
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
        assertEquals(40 * (1 + 0.02 * str), s.attackPower(), EPS);
        assertEquals(b.baseHp() + b.hpPerLevel() * 9 + vit * 8.0 + 50, s.maxHp(), EPS);
        double crit = 0.05 + b.baseStat(Stat.DEX) * 0.0015 + b.baseStat(Stat.LUK) * 0.0025 + 0.1;
        assertEquals(crit, s.critChance(), EPS);
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
