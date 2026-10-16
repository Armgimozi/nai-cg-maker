package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 5레벨 띠마다 무기 고르는 폭 (gear_spec §12 BandDiversity) — 신화 제외. 방향(고유 효과 묶음 12개 중)은 gear_spec 무기의
 * {@code direction} (기존 131 · 새 106 — B2 새 무기 8은 방향 표가 없어 뺀다).
 */
class BandDiversityTest {

    static Content content;
    static Map<String, String> direction = new HashMap<>();

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        JsonObject gs = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/gear_spec.json"), StandardCharsets.UTF_8)).getAsJsonObject();
        for (String key : List.of("existing_changes", "weapons")) {
            for (Map.Entry<String, JsonElement> e : gs.getAsJsonObject(key).entrySet()) {
                JsonElement d = e.getValue().getAsJsonObject().get("direction");
                if (d != null && !d.isJsonNull()) direction.put(e.getKey(), d.getAsString());
            }
        }
    }

    static List<ItemDef> band(int b) {
        List<ItemDef> out = new ArrayList<>();
        for (ItemDef w : content.items().values()) {
            if (w.isWeapon() && w.rarity() != Rarity.MYTHIC && GearModel.band(w.levelReq()) == b) out.add(w);
        }
        return out;
    }

    static String kind(String source) {
        return source.equals("drop") || source.equals("chest") ? "common" : source;
    }

    @Test
    void everyBandOffersAWideChoice() {
        List<String> off = new ArrayList<>();
        for (int b = 1; b <= 10; b++) {
            List<ItemDef> ws = band(b);
            if (ws.size() < 14) off.add("띠 " + b + " 무기 " + ws.size());
            Map<WeaponAttack.Style, Integer> styles = new EnumMap<>(WeaponAttack.Style.class);
            int magicNonCaster = 0;
            Map<Stat, Integer> stats = new EnumMap<>(Stat.class);
            Set<String> dirs = new HashSet<>(), kinds = new HashSet<>();
            Map<String, Set<List<Stat>>> shapeOrders = new HashMap<>();
            for (ItemDef w : ws) {
                styles.merge(w.attack().style(), 1, Integer::sum);
                if (w.attack().kind() == DamageKind.MAGIC && w.attack().style() != WeaponAttack.Style.CASTER) magicNonCaster++;
                for (Stat s : w.requirement().all().keySet()) stats.merge(s, 1, Integer::sum);
                if (direction.containsKey(w.id())) dirs.add(direction.get(w.id()));
                for (String s : w.sources()) kinds.add(kind(s));
                if (!w.requirement().isEmpty()) {
                    List<Stat> order = new ArrayList<>();
                    for (var e : w.requirement().ordered()) order.add(e.getKey());
                    String shape = w.model().str("shape", "?");
                    if (!shapeOrders.computeIfAbsent(shape, k -> new HashSet<>()).add(order)) {
                        off.add("띠 " + b + " 같은 모양 " + shape + " 에 같은 요구 순서 " + order + " (" + w.id() + ")");
                    }
                }
            }
            if (styles.getOrDefault(WeaponAttack.Style.MELEE, 0) < 5) off.add("띠 " + b + " 근접 " + styles);
            if (styles.getOrDefault(WeaponAttack.Style.RANGED, 0) < 3) off.add("띠 " + b + " 원거리 " + styles);
            if (styles.getOrDefault(WeaponAttack.Style.CASTER, 0) < 3) off.add("띠 " + b + " 시전 " + styles);
            // 마법 피해 근접·원거리 무기 — 띠 3~10 (9 띠는 빼도 됨)
            if (b >= 3 && b != 9 && magicNonCaster < 1) off.add("띠 " + b + " 마법 근접·원거리 없음");
            for (Stat s : Stat.values()) {
                int need = s == Stat.LUK && b == 1 ? 1 : 2;
                if (stats.getOrDefault(s, 0) < need) off.add("띠 " + b + " 요구 " + s + " " + stats.getOrDefault(s, 0) + "번");
            }
            if (dirs.size() < 10) off.add("띠 " + b + " 방향 " + dirs.size());
            if (kinds.size() < 5) off.add("띠 " + b + " 획득처 종류 " + kinds);
        }
        assertEquals(List.of(), off);
        assertEquals(12, new HashSet<>(direction.values()).size(), "방향 12개");
    }
}
