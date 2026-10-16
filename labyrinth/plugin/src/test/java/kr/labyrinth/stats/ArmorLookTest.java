package kr.labyrinth.stats;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.MemoryConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 방어구 겉모습 장단점 (look_spec §1.2·§7, 순수): 숨은 효과 합 · 4부위 판정 · 곱하는 키 · 상한 · 설정 읽기. */
class ArmorLookTest {

    static Content content;
    static final double EPS = 1e-9;
    static final ArmorLooks ON = ArmorLooks.DEFAULT;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    /** 부위 수 (body = 머리·몸·다리·발, shield = 방패 판금). */
    static StatBlock wear(Map<ArmorLook, Integer> body, int shield) {
        StatBlock b = new StatBlock();
        body.forEach((l, n) -> {
            if (l.real()) b.add(ArmorLookMath.countKey(l), n);
            b.add(ArmorLookMath.bodyKey(l), n);
        });
        if (shield > 0) b.add(ArmorLookMath.countKey(ArmorLook.HEAVY), shield);
        return b;
    }

    static Map<ArmorLook, Integer> of(Object... kv) {
        Map<ArmorLook, Integer> m = new EnumMap<>(ArmorLook.class);
        for (int i = 0; i + 1 < kv.length; i += 2) m.put((ArmorLook) kv[i], (Integer) kv[i + 1]);
        return m;
    }

    static DerivedStats compute(ClassDef c, StatBlock b, ArmorLooks looks) {
        return StatCalculator.compute(c, 20, Map.of(), b, 0.05, 1.5, kr.labyrinth.combat.WeaponAttack.UNARMED, Double.NaN, 0.25, looks);
    }

    @Test
    void piecesAddTheSameValueEachAndMix() {
        ArmorLookMath.Result r = ArmorLookMath.compute(wear(of(ArmorLook.HEAVY, 2, ArmorLook.LIGHT, 2), 0), ON);
        assertEquals(2, r.count(ArmorLook.HEAVY));
        assertEquals(2, r.count(ArmorLook.LIGHT));
        assertNull(r.full(), "판금 2 + 가죽 2 는 4부위 효과 없음");
        assertEquals(2 * -0.02 + 2 * 0.01, r.additive().get("move_speed"), EPS);
        assertEquals(2 * -0.01 + 2 * 0.015, r.additive().get("evasion"), EPS);
        assertEquals(1 + 2 * 0.04 - 2 * 0.06, r.defenseMult(), EPS);
        assertEquals(1 + 2 * 0.02, r.cooldownMult(), EPS);
        assertEquals(0, r.ccResist(), EPS);
    }

    @Test
    void fullLookNeedsFourBodyPiecesShieldDoesNotCountAnyFills() {
        assertEquals(ArmorLook.HEAVY, ArmorLookMath.compute(wear(of(ArmorLook.HEAVY, 4), 1), ON).full());
        assertNull(ArmorLookMath.compute(wear(of(ArmorLook.HEAVY, 3), 1), ON).full(), "방패는 4부위 수에 안 든다");
        assertEquals(ArmorLook.CLOTH, ArmorLookMath.compute(wear(of(ArmorLook.CLOTH, 3, ArmorLook.ANY, 1), 0), ON).full(),
                "any 는 나머지 세 칸의 겉모습으로");
        assertNull(ArmorLookMath.compute(wear(of(ArmorLook.CLOTH, 2, ArmorLook.LIGHT, 1, ArmorLook.ANY, 1), 0), ON).full());
        assertNull(ArmorLookMath.compute(wear(of(ArmorLook.ANY, 1), 0), ON).full());
        ArmorLookMath.Result any = ArmorLookMath.compute(wear(of(ArmorLook.LIGHT, 3, ArmorLook.ANY, 1), 0), ON);
        assertEquals(3, any.count(ArmorLook.LIGHT), "any 자기 숨은 효과는 없다");
        assertEquals(3 * 0.015, any.additive().get("attack_speed"), EPS);
    }

    @Test
    void heavyFourPlusShield() {
        ClassDef g = content.classDef("guardian");
        StatBlock gear = new StatBlock().add("defense", 40).add("damage_reduction", 0.05).add("move_speed", 0.03);
        DerivedStats off = compute(g, gear, ArmorLooks.OFF);
        StatBlock worn = new StatBlock().addAll(gear).addAll(wear(of(ArmorLook.HEAVY, 4), 1));
        DerivedStats on = compute(g, worn, ON);
        assertEquals(off.defense() * 1.20, on.defense(), EPS, "방어 +20%");
        assertEquals(off.damageReduction() + 0.025, on.damageReduction(), EPS, "받는 피해 감소 +2.5%p");
        assertEquals(off.moveSpeed() - 0.10, on.moveSpeed(), EPS, "이동 −10%");
        assertEquals(1.10, on.cooldownMult(), EPS, "재사용 ×1.10");
        assertEquals(ArmorLook.HEAVY, on.fullLook());
        assertEquals(0.40, on.ccResist(), EPS);
        assertEquals(Math.min(0.85, Math.min(0.5, 0.003 * on.stat(Stat.STR)) + 0.60), on.knockbackResistance(), EPS);
        assertEquals(5, on.lookCount(ArmorLook.HEAVY));
        assertEquals(off.maxHp(), on.maxHp(), EPS);
    }

    @Test
    void multipliedKeysLightAndCloth() {
        ClassDef a = content.classDef("arcanist");
        StatBlock gear = new StatBlock().add("defense", 20).add("mana_regen", 1.0);
        DerivedStats off = compute(a, gear, ArmorLooks.OFF);
        DerivedStats light = compute(a, new StatBlock().addAll(gear).addAll(wear(of(ArmorLook.LIGHT, 4), 0)), ON);
        assertEquals(off.defense() * 0.76, light.defense(), EPS, "가죽 4 = 방어 −24%");
        assertEquals(off.critChance() + 0.04, light.critChance(), EPS);
        assertEquals(off.attackSpeed() + 0.06, light.attackSpeed(), EPS);
        assertEquals(ArmorLook.LIGHT, light.fullLook());
        DerivedStats cloth = compute(a, new StatBlock().addAll(gear).addAll(wear(of(ArmorLook.CLOTH, 4), 0)), ON);
        assertEquals(off.maxHp() * 0.92, cloth.maxHp(), EPS, "천 4 = 최대 HP −8%");
        assertEquals(off.manaRegen() * 1.24, cloth.manaRegen(), EPS, "MP 재생 +24%");
        assertEquals(0.94, cloth.cooldownMult(), EPS);
        assertEquals(off.skillDamage() + 0.08, cloth.skillDamage(), EPS);
        assertEquals(ArmorLook.CLOTH, cloth.fullLook());
        assertEquals(0, cloth.ccResist(), EPS);
    }

    @Test
    void evasionNeverBelowZeroAndKnockbackCapped() {
        ClassDef b = content.classDef("berserker");
        Map<Stat, Integer> alloc = Map.of(Stat.STR, 200);
        StatBlock heavy = wear(of(ArmorLook.HEAVY, 4), 0);
        DerivedStats s = StatCalculator.compute(b, 50, alloc, heavy, 0.05, 1.5, kr.labyrinth.combat.WeaponAttack.UNARMED,
                Double.NaN, 0.25, ON);
        assertTrue(s.evasion() >= 0);
        assertEquals(ArmorLookMath.CAP_KNOCKBACK, s.knockbackResistance(), EPS, "힘 50% + 버팀 60% → 상한 85%");
        assertEquals(0.5, ArmorLookMath.knockbackResistance(400, 0), EPS, "힘만은 예전처럼 50%");
        assertEquals(0.03, ArmorLookMath.knockbackResistance(10, 0), EPS);
        // 재사용 대기 배율은 0.5 아래로 안 내려감
        ArmorLooks fast = new ArmorLooks(true, 4, ArmorLook.HEAVY, Map.of(ArmorLook.CLOTH,
                new ArmorLooks.Look("천", "#fff", Map.of("cooldown_pct", -0.5))), null, null, null, null);
        assertEquals(0.5, ArmorLookMath.compute(wear(of(ArmorLook.CLOTH, 4), 0), fast).cooldownMult(), EPS);
    }

    @Test
    void disabledMeansNoEffectsButCounts() {
        ClassDef g = content.classDef("guardian");
        StatBlock worn = wear(of(ArmorLook.HEAVY, 4), 1);
        DerivedStats off = compute(g, worn, ArmorLooks.OFF);
        DerivedStats plain = compute(g, new StatBlock(), ArmorLooks.OFF);
        assertEquals(plain.defense(), off.defense(), EPS);
        assertEquals(plain.moveSpeed(), off.moveSpeed(), EPS);
        assertEquals(1.0, off.cooldownMult(), EPS);
        assertNull(off.fullLook());
        assertEquals(5, off.lookCount(ArmorLook.HEAVY), "수는 그대로 (화면용)");
    }

    @Test
    void oldSignatureUnchangedWithoutLookPieces() {
        ClassDef h = content.classDef("hunter");
        StatBlock gear = new StatBlock().add("damage", 30).add("defense", 12).add("evasion", 0.05).add("move_speed", 0.04);
        DerivedStats old = StatCalculator.compute(h, 15, Map.of(Stat.DEX, 30), gear, 0.05, 1.5,
                kr.labyrinth.combat.WeaponAttack.UNARMED, Double.NaN, 0.25);
        DerivedStats now = StatCalculator.compute(h, 15, Map.of(Stat.DEX, 30), gear, 0.05, 1.5,
                kr.labyrinth.combat.WeaponAttack.UNARMED, Double.NaN, 0.25, ON);
        assertEquals(old, now, "겉모습 부위가 없으면 옛 계산 그대로");
    }

    // ── 설정 ──────────────────────────────────────────────────────────────

    @Test
    void jarConfigMatchesCodeDefaults() {
        YamlConfiguration cfg = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        ArmorLooks read = ArmorLooks.read(cfg.getConfigurationSection("armor_looks"));
        assertTrue(read.warnings().isEmpty(), read.warnings().toString());
        assertEquals(ArmorLooks.DEFAULT, read, "jar 의 config.yml armor_looks = 코드 기본값");
        assertEquals(5.0, read.tumble().cooldown(), EPS, "주인 결정 D1: 구르기 5초");
        assertEquals(ArmorLooks.DEFAULT, new Settings(new MemoryConfiguration()).armorLooks(), "키가 없으면 기본값");
    }

    @Test
    void configReadsKnobsWarnsUnknownAndClamps() {
        MemoryConfiguration c = new MemoryConfiguration();
        c.set("armor_looks.cloth.full.absorb", 0.15);
        c.set("armor_looks.light.full.cooldown", 8.0);
        c.set("armor_looks.heavy.piece.defense_pct", 0.9);
        c.set("armor_looks.heavy.piece.banana", 0.1);
        c.set("armor_looks.shield_counts_as", "plain");
        ArmorLooks a = new Settings(c).armorLooks();
        assertEquals(0.15, a.manaShield().absorb(), EPS);
        assertEquals(8.0, a.tumble().cooldown(), EPS);
        assertEquals(ArmorLooks.MAX_PIECE, a.look(ArmorLook.HEAVY).get("defense_pct"), EPS);
        assertFalse(a.look(ArmorLook.HEAVY).piece().containsKey("banana"));
        assertEquals(ArmorLook.HEAVY, a.shieldCountsAs());
        assertEquals(3, a.warnings().size(), a.warnings().toString());
        assertEquals(ArmorLooks.DEFAULT_LIGHT, a.look(ArmorLook.LIGHT), "piece 를 안 적은 겉모습은 기본값");

        MemoryConfiguration offc = new MemoryConfiguration();
        offc.set("armor_looks", false);
        assertFalse(new Settings(offc).armorLooks().enabled());
        MemoryConfiguration en = new MemoryConfiguration();
        en.set("armor_looks.enabled", false);
        assertFalse(new Settings(en).armorLooks().enabled());
    }
}
