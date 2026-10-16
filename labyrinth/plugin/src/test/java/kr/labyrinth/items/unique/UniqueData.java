package kr.labyrinth.items.unique;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.UniqueDef;

/**
 * 시험 데이터: 고유 효과 배정 237개 ({@code tools/data/035/unique_assign.json}, {@code tools/gen_035_unique.py --import} 가
 * 설계 폴더의 unique_assign_all.json 에서 만듦 — A12 bash_stun · B3 강도 0.6 반영). items.yml 에는 P3 가 넣는다.
 */
final class UniqueData {

    static final Path FILE = Path.of("../tools/data/035/unique_assign.json");

    /** 배정 한 줄. */
    record Entry(String weaponId, String effect, String name, String direction, Params params, double strength,
                 double sourceFactor, double g, boolean isNew, String band, int level, String rarity, WeaponAttack attack,
                 List<String> sourceKinds, List<String> tooltip) {

        /** items.yml 에 넣을 unique 블록과 같은 꼴로 읽은 정의. */
        UniqueDef def() {
            Map<String, Object> block = new LinkedHashMap<>();
            block.put("id", effect);
            block.put("name", name);
            block.putAll(params.asMap());
            return UniqueDef.parse(Params.of(Map.of("unique", block)));
        }
    }

    private static Map<String, Entry> cache;

    private UniqueData() {}

    static synchronized Map<String, Entry> all() {
        if (cache != null) return cache;
        JsonObject root;
        try {
            root = JsonParser.parseString(Files.readString(FILE, StandardCharsets.UTF_8)).getAsJsonObject();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Map<String, Entry> out = new LinkedHashMap<>();
        for (Map.Entry<String, JsonElement> e : root.entrySet()) {
            if (e.getKey().startsWith("_")) continue;
            JsonObject o = e.getValue().getAsJsonObject();
            JsonObject w = o.getAsJsonObject("weapon");
            WeaponAttack.Style style = WeaponAttack.Style.byId(w.get("style").getAsString(), WeaponAttack.Style.MELEE);
            DamageKind kind = DamageKind.byId(w.get("attack_kind").getAsString(), DamageKind.PHYSICAL);
            double sp = style == WeaponAttack.Style.CASTER ? WeaponAttack.CASTER_SKILL_POWER_MULT : 1.0;
            WeaponAttack attack = new WeaponAttack(style, w.get("interval").getAsDouble(), kind, sp);
            List<String> kinds = new ArrayList<>();
            w.getAsJsonArray("source_kinds").forEach(x -> kinds.add(x.getAsString()));
            List<String> tooltip = new ArrayList<>();
            if (o.has("tooltip")) o.getAsJsonArray("tooltip").forEach(x -> tooltip.add(x.getAsString()));
            out.put(e.getKey(), new Entry(e.getKey(), o.get("effect").getAsString(), o.get("name").getAsString(),
                    o.get("direction").getAsString(), Params.of(gsonToMap(o.getAsJsonObject("params"))),
                    o.get("strength").getAsDouble(), o.get("source_factor").getAsDouble(), o.get("interval_factor_g").getAsDouble(),
                    w.get("new").getAsBoolean(), w.get("band").getAsString(), w.get("level").getAsInt(),
                    w.get("rarity").getAsString(), attack, List.copyOf(kinds), List.copyOf(tooltip)));
        }
        cache = out;
        return out;
    }

    private static Map<String, Object> gsonToMap(JsonObject o) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (Map.Entry<String, JsonElement> e : o.entrySet()) {
            JsonElement v = e.getValue();
            if (v.isJsonPrimitive() && v.getAsJsonPrimitive().isNumber()) m.put(e.getKey(), v.getAsDouble());
            else if (v.isJsonPrimitive()) m.put(e.getKey(), v.getAsString());
        }
        return m;
    }
}
