package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import org.junit.jupiter.api.Test;

/** 0.3.5 전투 공식 (combat_spec §3): K · 스킬 위력 · 활 세기 · 간격. */
class CombatMathTest {

    private static final double EPS = 1e-9;

    @Test
    void kSlopeByStyleAndInterval() {
        assertEquals(1.47, CombatMath.k(WeaponAttack.Style.MELEE, 0.67), EPS);
        assertEquals(1.47, CombatMath.k(WeaponAttack.Style.MELEE, 1.0), EPS, "느린 근접은 기울기 그대로");
        assertEquals(1.47 - 0.143 * (1 / 0.45 - 1.5), CombatMath.k(WeaponAttack.Style.MELEE, 0.45), EPS);
        assertEquals(1.367, CombatMath.k(WeaponAttack.Style.MELEE, 0.45), 0.001);
        assertEquals(1.413, CombatMath.k(WeaponAttack.Style.RANGED, 1.15), EPS);
        assertEquals(1.22, CombatMath.k(WeaponAttack.Style.CASTER, 0.9), EPS);
    }

    @Test
    void sameTierWeaponsHaveSameSkillPower() {
        // 같은 단계(티어 위력 TP) 무기: 한 방 = TP × K × 간격 (정수 반올림) → 스킬 위력 ±3% 안 (무거운 무기가 스킬을 독차지하지 않음)
        double tp = 36.86; // Lv25 일반 (combat_spec §5.7)
        WeaponAttack[] ws = {
                new WeaponAttack(WeaponAttack.Style.MELEE, 1.0, DamageKind.PHYSICAL, 1.0),   // 대검
                new WeaponAttack(WeaponAttack.Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0),  // 단검
                new WeaponAttack(WeaponAttack.Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0),  // 장검
                new WeaponAttack(WeaponAttack.Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0), // 활
                new WeaponAttack(WeaponAttack.Style.CASTER, 0.9, DamageKind.MAGIC, 1.0)};    // 지팡이 (배율 1 로 비교)
        double lo = Double.MAX_VALUE, hi = 0, perHitLo = Double.MAX_VALUE, perHitHi = 0;
        for (WeaponAttack w : ws) {
            double perHit = Math.round(tp * CombatMath.k(w.style(), w.interval()) * w.interval());
            double sp = CombatMath.skillPower(perHit, w, 0);
            lo = Math.min(lo, sp);
            hi = Math.max(hi, sp);
            perHitLo = Math.min(perHitLo, perHit);
            perHitHi = Math.max(perHitHi, perHit);
        }
        assertTrue(hi / lo <= 1.03 * 1.03, "스킬 위력 최고÷최저 " + hi / lo);
        assertTrue(perHitHi / perHitLo > 2, "한 방 피해는 무게에 따라 크게 벌어짐 " + perHitHi / perHitLo);
    }

    @Test
    void skillPowerAddsHalfOfAttackSpeedAndCasterMult() {
        WeaponAttack staff = new WeaponAttack(WeaponAttack.Style.CASTER, 0.9, DamageKind.MAGIC, 1.05);
        double base = 30 / 0.9 / 1.22 * 1.05;
        assertEquals(base, CombatMath.skillPower(30, staff, 0), EPS);
        assertEquals(base * 1.3, CombatMath.skillPower(30, staff, 0.6), EPS);
        assertEquals(base, CombatMath.skillPower(30, staff, -0.3), EPS, "느려짐은 스킬 위력을 깎지 않음");
    }

    @Test
    void powerByKind() {
        assertEquals(1.5, CombatMath.power(DamageKind.PHYSICAL, 50, 10), EPS);
        assertEquals(1.1, CombatMath.power(DamageKind.MAGIC, 50, 10), EPS);
        assertEquals(1.3, CombatMath.power(DamageKind.HYBRID, 50, 10), EPS);
        assertEquals(1.0, CombatMath.power(DamageKind.FIXED, 50, 10), EPS);
        assertEquals(DamageKind.PHYSICAL, DamageKind.of(DamageType.MELEE));
        assertEquals(DamageKind.PHYSICAL, DamageKind.of(DamageType.RANGED));
        assertEquals(DamageKind.MAGIC, DamageKind.of(DamageType.MAGIC));
        assertEquals(DamageKind.FIXED, DamageKind.of(DamageType.TRUE));
    }

    @Test
    void intervalsAndBowDraw() {
        assertEquals(0.67 / 1.4, CombatMath.meleeInterval(0.67, 0.4, 0.25), EPS);
        assertEquals(0.25, CombatMath.meleeInterval(0.43, 0.75, 0.25), EPS, "하한 0.25초");
        assertEquals((1.25 - 0.15) / 1.5, CombatMath.bowDraw(1.25, 0.5, 0.25), EPS);
        WeaponAttack bow = new WeaponAttack(WeaponAttack.Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0);
        assertEquals(1.0 + 0.15, CombatMath.cycle(bow, 0, 0.25), EPS, "한 발 주기 = 당김 + 0.15");
        // 바닐라 곡선: 끝까지 1, 절반 0.42, 덜 당긴 연사는 손해 (x 0.5 → 시간당 74%)
        assertEquals(1.0, CombatMath.bowForce(2, 1), EPS);
        assertEquals((0.25 + 1.0) / 3, CombatMath.bowForce(0.5, 1), EPS);
        assertEquals(0.0, CombatMath.bowForce(0, 1), EPS);
        double half = CombatMath.bowForce(0.5, 1.0) / (0.5 + 0.15);
        double full = CombatMath.bowForce(1.0, 1.0) / (1.0 + 0.15);
        assertTrue(half / full < 0.8, "덜 당겨 연사해도 이득이 없음 " + half / full);
        // 바닐라 세기 → 당긴 틱 (20틱 = 1)
        assertEquals(20, CombatMath.ticksFromVanillaForce(1.0), 1e-6);
        assertEquals(10, CombatMath.ticksFromVanillaForce((0.25 + 1.0) / 3), 1e-6);
    }

    @Test
    void attackSpeedCaps() {
        assertEquals(0.45, CombatMath.attackSpeed(200, 0), EPS);
        assertEquals(0.75, CombatMath.attackSpeed(200, 0.5), EPS);
        assertEquals(0.30, CombatMath.attackSpeed(0, 0.30), EPS);
        assertEquals(-0.5, CombatMath.attackSpeed(0, -2), EPS);
    }

    @Test
    void weaponAttackFromItemBlockOrLegacyFile() {
        // attack 블록이 있으면 그것 (speed 만 있으면 1/speed)
        ItemDef withBlock = weapon("a", "greatsword", Map.of("attack", Map.of("style", "melee", "interval", 0.85, "kind", "physical")));
        assertEquals(new WeaponAttack(WeaponAttack.Style.MELEE, 0.85, DamageKind.PHYSICAL, 1.0), WeaponAttack.of(withBlock));
        ItemDef speedOnly = weapon("b", "staff", Map.of("attack", Map.of("style", "caster", "speed", 1.25)));
        WeaponAttack sp = WeaponAttack.of(speedOnly);
        assertEquals(0.8, sp.interval(), EPS);
        assertEquals(DamageKind.MAGIC, sp.kind(), "시전 무기 기본 = 마법");
        assertEquals(WeaponAttack.CASTER_SKILL_POWER_MULT, sp.skillPowerMult(), EPS);
        ItemDef magicBow = weapon("c", "bow", Map.of("attack", Map.of("style", "ranged", "interval", 1.1, "kind", "magic")));
        assertEquals(DamageKind.MAGIC, WeaponAttack.of(magicBow).kind(), "지능 활 = 마법");
        assertTrue(WeaponAttack.of(magicBow).ranged());
        // 블록이 없는 예전(0.3.4) 파일: 남은 옛 키의 그때 주기, 옛 키도 없으면 근접 0.67초
        assertEquals(new WeaponAttack(WeaponAttack.Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0), WeaponAttack.of(weapon("d", "bow", Map.of())));
        assertEquals(0.45, WeaponAttack.of(weapon("e", "dagger", Map.of())).interval(), EPS);
        assertEquals(WeaponAttack.Style.CASTER, WeaponAttack.of(weapon("f", "scepter", Map.of())).style());
        assertEquals(WeaponAttack.DEFAULT, WeaponAttack.of(weapon("g", null, Map.of())));
        assertTrue(weapon("d", "bow", Map.of()).isRanged());
        assertNull(new ItemDef("x", "x", ItemType.MATERIAL, WeaponAttack.DEFAULT, null, null, Rarity.COMMON, 1, java.util.List.of(),
                Map.of(), null, null, java.util.List.of(), 1, true, java.util.List.of(), Params.EMPTY, Params.EMPTY, Params.EMPTY, "",
                Params.EMPTY).attack(), "무기가 아니면 attack 없음");
        assertEquals(WeaponAttack.UNARMED, WeaponAttack.of(null));
        assertEquals(0.625, WeaponAttack.UNARMED.interval(), EPS);
        assertEquals(1.6, WeaponAttack.UNARMED.attacksPerSecond(), EPS);
    }

    @Test
    void damageServiceRawAmountAppliesKindPowerOnce() {
        // 원피해 = 기준(한 방 W 또는 스킬 위력) × 종류 배율 × 배율 — 방어·치명 앞단에서 한 번만 (DamageFormula 는 그대로)
        var atk = kr.labyrinth.stats.StatCalculator.compute(null, 10, Map.of(kr.labyrinth.stats.Stat.STR, 30,
                        kr.labyrinth.stats.Stat.INT, 10), new kr.labyrinth.stats.StatBlock().add("damage", 20).add("magic_damage", 0.1),
                0.05, 1.5, new WeaponAttack(WeaponAttack.Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0), 20, 0.25);
        assertEquals(20 * 1.3 * 1.2, DamageService.rawAmount(atk, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 1.2), EPS);
        assertEquals(atk.skillPower() * 1.1 * 2.0 * 1.1, DamageService.rawAmount(atk, DamageContext.Base.SKILL, DamageKind.MAGIC, 2.0), EPS,
                "마법 피해 가산(은총)은 마법에만");
        assertEquals(atk.skillPower() * 1.0 * 0.5, DamageService.rawAmount(atk, DamageContext.Base.SKILL, DamageKind.FIXED, 0.5), EPS);
        assertEquals(3.0, DamageService.rawAmount(null, DamageContext.Base.PER_HIT, DamageKind.PHYSICAL, 3.0), EPS);
    }

    /** @param legacyKey 예전(0.3.4) 파일에 남은 옛 키 값 (null = 없음) — attack 블록이 없을 때만 읽힌다. */
    private static ItemDef weapon(String id, String legacyKey, Map<String, Object> raw) {
        Map<String, Object> r = new java.util.LinkedHashMap<>(raw);
        if (legacyKey != null) r.put("weapon_type", legacyKey);
        return new ItemDef(id, id, ItemType.WEAPON, null, null, null, Rarity.COMMON, 1, java.util.List.of(),
                Map.of("damage", new Range(10, 12)), null, null, java.util.List.of(), 1, true, java.util.List.of(),
                Params.EMPTY, Params.EMPTY, Params.EMPTY, "", Params.of(r));
    }
}
