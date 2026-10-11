package kr.souls.item;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import kr.souls.TestFiles;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.logging.Logger;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 팩의 손 자세와 플러그인의 껍데기 아이템이 같은 무기를 같게 보는가 (검토 P0-2, pack/weapons/gripcheck.py check_plugin 과 같은 것을
 * 지은 pack.zip 으로 본다). 3인칭 팔 자세는 아이템 종류가 정한다: 창 자세 (바닐라 창 display 합성) 는 돌창 껍데기 (#minecraft:spears) 위에서만
 * 맞고, 방패 막기 모형 (shield_blocking) 은 방패 껍데기 위에서만 바닐라 방패와 같다 (부싯돌이면 칼 막기 몸짓이 더 걸린다). 그래서
 * weapons.yml 의 class·use 나 ItemFactory.SPEAR_CLASSES 를 고치고 팩을 그대로 두면 (또는 거꾸로) 여기서 걸린다.
 * 무기 모형 &lt;id&gt;_3d 의 3인칭 오른손 display 를 시험 모형 test_grip_{sword,mace,spear,bow,shield} 의 것과 견주어 그 무기의 바닐라
 * 모형을 정한다 (둘 다 같은 합성에서 나온다).
 */
class GripParityTest {
    private static final List<String> PROBES = List.of("sword", "mace", "spear", "bow", "shield");

    private static JsonObject json(ZipFile zip, String path) throws IOException {
        ZipEntry e = zip.getEntry(path);
        assertNotNull(e, "pack.zip 에 없다: " + path);
        try (var r = new InputStreamReader(zip.getInputStream(e), StandardCharsets.UTF_8)) {
            return JsonParser.parseReader(r).getAsJsonObject();
        }
    }

    private static JsonElement tpRight(ZipFile zip, String model) throws IOException {
        JsonObject m = json(zip, "assets/souls/models/item/" + model + ".json");
        assertTrue(m.has("display"), model + ": display 가 없다");
        return m.getAsJsonObject("display").get("thirdperson_righthand");
    }

    @Test
    void packGripMatchesPluginShell() throws IOException {
        Weapons weapons = new Weapons(Logger.getLogger("test"));
        weapons.load(TestFiles.yaml("content/weapons.yml"));
        try (ZipFile zip = new ZipFile(TestFiles.resource("pack.zip"))) {
            Map<String, JsonElement> probe = new LinkedHashMap<>();
            for (String p : PROBES) probe.put(p, tpRight(zip, "test_grip_" + p));
            // 팩의 무기 모형 id 와 weapons.yml 의 id 가 같다
            Set<String> packIds = new TreeSet<>();
            zip.stream().map(ZipEntry::getName)
                    .filter(n -> n.startsWith("assets/souls/models/item/") && n.endsWith("_3d.json"))
                    .forEach(n -> packIds.add(n.substring("assets/souls/models/item/".length(), n.length() - "_3d.json".length())));
            assertEquals(new TreeSet<>(weapons.all().keySet()), packIds, "팩의 무기 모형과 weapons.yml 의 id");
            List<String> bad = new ArrayList<>();
            for (Weapons.Def d : weapons.all().values()) {
                JsonElement mine = tpRight(zip, d.id() + "_3d");
                List<String> sets = PROBES.stream().filter(p -> probe.get(p).equals(mine)).toList();
                if (sets.size() != 1) {
                    bad.add(d.id() + ": 3인칭 display 가 시험 모형 하나와 같지 않다 " + sets);
                    continue;
                }
                String set = sets.get(0);
                String def = json(zip, "assets/souls/items/" + d.id() + ".json").toString();
                boolean spear = ItemFactory.SPEAR_CLASSES.contains(d.cls());
                if (set.equals("spear") != spear) bad.add(d.id() + ": 팩 " + set + ", 돌창 껍데기 " + spear + " (class " + d.cls() + ")");
                if (set.equals("shield") != Weapons.BLOCK.equals(d.use())) bad.add(d.id() + ": 팩 " + set + ", use " + d.use() + " (방패 껍데기는 use: block)");
                if (set.equals("bow") != Weapons.BOW.equals(d.use())) bad.add(d.id() + ": 팩 " + set + ", use " + d.use() + " (활 껍데기는 use: bow)");
                // 정의 길: 방패만 막기 모형, 활만 당김 (use_duration)
                if (set.equals("shield") != def.contains("souls:item/" + d.id() + "_block")) bad.add(d.id() + ": 막기 모형 길 (" + set + ")");
                if (set.equals("bow") != def.contains("minecraft:use_duration")) bad.add(d.id() + ": 당김 길 (" + set + ")");
            }
            assertTrue(bad.isEmpty(), String.join("\n", bad));
        }
    }
}
