package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.ItemMigration035;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 무기 공격 간격 데이터 (combat_spec §5·§12, P0b). 기존 무기 131개의 attack 블록·새 한 방 피해는
 * {@code tools/gen_035_attack.py} 가 {@code tools/data/035/combat_spec.json} 에서 만든다 — 손으로 고치면 이 시험이 잡는다.
 */
class WeaponIntervalDataTest {

    static final Path SPEC = Path.of("../tools/data/035/combat_spec.json");
    static final Map<Rarity, Double> RARITY = Map.of(Rarity.COMMON, 1.00, Rarity.UNCOMMON, 1.06, Rarity.RARE, 1.13,
            Rarity.EPIC, 1.21, Rarity.LEGENDARY, 1.31, Rarity.MYTHIC, 1.45);

    static Content content;
    static JsonObject weapons;
    static JsonObject changes;
    static final Path GEAR_SPEC = Path.of("../tools/data/035/gear_spec.json");

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        weapons = JsonParser.parseString(Files.readString(SPEC, StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("weapons");
        changes = JsonParser.parseString(Files.readString(GEAR_SPEC, StandardCharsets.UTF_8)).getAsJsonObject()
                .getAsJsonObject("existing_changes");
    }

    private static List<ItemDef> all() {
        return content.items().values().stream().filter(ItemDef::isWeapon).toList();
    }

    private static double mid(ItemDef d) {
        Range r = d.stats().get("damage");
        return (r.min() + r.max()) / 2;
    }

    @Test
    void everyWeaponHasAnAttackBlockInRange() {
        for (ItemDef d : all()) {
            Params a = d.raw().sub("attack");
            assertTrue(a.has("style") && a.has("interval") && a.has("kind"), d.id() + " attack " + a.asMap());
            double iv = d.attack().interval();
            assertTrue(iv >= ContentValidator.MIN_WEAPON_INTERVAL && iv <= ContentValidator.MAX_WEAPON_INTERVAL, d.id() + " 간격 " + iv);
            assertTrue(iv >= 0.42 - 1e-9, d.id() + " 간격 " + iv + " (지금 데이터 0.42 ~ 1.30)");
            // 활 모양 ⇔ 당겨 쏘기, 시전 = 기본 마법
            String shape = d.model().str("shape");
            assertEquals(shape.endsWith("bow"), d.isRanged(), d.id() + " 모양 " + shape + " / " + d.attack().style());
            if (d.attack().style() == WeaponAttack.Style.CASTER) assertEquals(DamageKind.MAGIC, d.attack().kind(), d.id());
            assertTrue(d.attack().kind() == DamageKind.PHYSICAL || d.attack().kind() == DamageKind.MAGIC, d.id());
        }
        List<String> errors = ContentValidator.validate(content).errors().stream().filter(e -> e.contains(".attack")).toList();
        assertEquals(List.of(), errors);
    }

    @Test
    void existingWeaponsMatchTheCombatSpec() {
        int n = 0;
        for (String id : weapons.keySet()) {
            JsonObject w = weapons.getAsJsonObject(id);
            if (!"existing".equals(w.get("src").getAsString())) continue;
            ItemDef d = content.item(id);
            assertNotNull(d, id);
            JsonObject a = w.getAsJsonObject("items_yml").getAsJsonObject("attack");
            assertEquals(a.get("style").getAsString(), d.raw().sub("attack").str("style"), id);
            assertEquals(a.get("interval").getAsDouble(), d.attack().interval(), 1e-9, id);
            // 0.3.5 A8: gear_spec existing_changes 가 피해 종류를 바꾼 무기(지능·정신 요구로 마법이 된 활 등)는 그 값
            JsonObject change = changes.has(id) ? changes.getAsJsonObject(id).getAsJsonObject("attack") : null;
            String kind = change != null ? change.get("kind").getAsString() : a.get("kind").getAsString();
            assertEquals(kind, d.raw().sub("attack").str("kind"), id);
            var ph = w.getAsJsonArray("per_hit");
            assertEquals(new Range(ph.get(0).getAsDouble(), ph.get(1).getAsDouble()), d.stats().get("damage"), id + " 새 한 방 피해");
            // 가진 무기 굴림 옮기기(ItemMigration035)의 옛 범위 = 명세의 옛 범위
            var old = w.getAsJsonArray("old_damage");
            assertEquals(new Range(old.get(0).getAsDouble(), old.get(1).getAsDouble()), ItemMigration035.OLD_DAMAGE.get(id), id + " 옛 범위");
            n++;
        }
        assertEquals(131, n);
    }

    /** 새 티어 위력 TP′ = P(L) × 희귀도 × c(L) (combat_spec §5.7). */
    static double tierPower(ItemDef d) {
        int l = d.levelReq();
        double p = 7 + 0.25 * (l - 1) + 0.0195 * (l - 1) * (l - 1);
        double s = 8 + 3.6 * (l + 3);
        double c = (1 + 0.02 * s) / (1 + 0.01 * s);
        return p * RARITY.get(d.rarity()) * c;
    }

    @Test
    void dpsFollowsTierPowerTimesK() {
        // 초당 피해 등가(한 방 가운데값 ÷ 간격) = TP′ × K(방식, 간격) ±5% — 작은 숫자는 정수 반올림 몫(±1)까지
        List<String> off = new ArrayList<>();
        for (ItemDef d : all()) {
            WeaponAttack a = d.attack();
            double want = tierPower(d) * CombatMath.k(a.style(), a.interval()) * a.interval();
            double got = mid(d);
            if (Math.abs(got - want) > Math.max(0.05 * want, 1.0)) off.add(d.id() + " 한 방 " + got + " (식 " + String.format("%.1f", want) + ")");
        }
        assertEquals(List.of(), off);
    }

    @Test
    void skillPowerSpreadPerBandStaysSmall() {
        // 같은 5레벨 구간(신화 제외)에서 스킬 위력 최고 ÷ 최저 ≤ 1.65 — 한 방 피해는 무게에 따라 훨씬 더 벌어진다
        Map<Integer, double[]> band = new TreeMap<>();
        Map<Integer, double[]> hits = new TreeMap<>();
        for (ItemDef d : all()) {
            if (d.rarity() == Rarity.MYTHIC) continue;
            int b = (d.levelReq() - 1) / 5;
            double sp = CombatMath.skillPower(mid(d), d.attack(), 0);
            double[] x = band.computeIfAbsent(b, k -> new double[] {Double.MAX_VALUE, 0});
            x[0] = Math.min(x[0], sp);
            x[1] = Math.max(x[1], sp);
            double[] h = hits.computeIfAbsent(b, k -> new double[] {Double.MAX_VALUE, 0});
            h[0] = Math.min(h[0], mid(d));
            h[1] = Math.max(h[1], mid(d));
        }
        assertEquals(10, band.size(), "구간 " + band.keySet());
        band.forEach((b, x) -> assertTrue(x[1] / x[0] <= 1.65, "Lv" + (b * 5 + 1) + "~ 스킬 위력 " + x[0] + " ~ " + x[1]));
        assertTrue(hits.values().stream().anyMatch(h -> h[1] / h[0] > 2.5), "한 방 피해 퍼짐");
    }
}
