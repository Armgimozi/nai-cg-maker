package kr.labyrinth.pvp;

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
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 스킬 PvP 배율 데이터 (pvp_spec §6). classes.yml {@code skills[].pvp_mult} · items.yml {@code weapon_skills[].pvp_mult} 는
 * {@code tools/gen_035_pvp.py} 가 {@code tools/data/035/pvp_spec.json} 의 {@code skill_mult} 에서 넣는다 —
 * 무기 스킬이 바뀌면(P3) 명세의 skill_mult 를 다시 뽑고 생성기를 다시 돌린다. 어긋나면 이 시험이 잡는다.
 */
class PvpSkillMultDataTest {

    static Content content;
    static JsonObject spec;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        spec = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/pvp_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("skill_mult");
    }

    /** 데이터의 모든 pvp_mult (1 이 아닌 것). 키 = 직업 스킬 id 또는 무기id:입력. */
    static Map<String, Double> dataMults() {
        Map<String, Double> out = new TreeMap<>();
        for (ClassDef c : content.classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) if (s.pvpMult() != 1.0) out.put(s.id(), s.pvpMult());
        }
        for (ItemDef d : content.items().values()) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) if (s.pvpMult() != 1.0) out.put(d.id() + ":" + s.input(), s.pvpMult());
        }
        return out;
    }

    @Test
    void dataEqualsSpec() {
        Map<String, Double> want = new TreeMap<>();
        for (var e : spec.entrySet()) want.put(e.getKey(), e.getValue().getAsDouble());
        assertEquals(38, want.size(), "명세 38개 (직업 7 · 무기 31)");
        assertEquals(want, dataMults(), "tools/gen_035_pvp.py 로 다시 넣기");
    }

    @Test
    void classAndWeaponCounts() {
        long cls = spec.keySet().stream().filter(k -> !k.contains(":")).count();
        assertEquals(7, cls);
        assertEquals(31, spec.size() - cls);
        // 궁극기 넷 (pvp_spec §6)
        assertEquals(0.30, mult("arrow_storm"), 1e-9);
        assertEquals(0.35, mult("meteor_fall"), 1e-9);
        assertEquals(0.40, mult("shadow_execution"), 1e-9);
        assertEquals(0.45, mult("ruinous_leap"), 1e-9);
    }

    private static double mult(String classSkill) {
        for (ClassDef c : content.classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) if (s.id().equals(classSkill)) return s.pvpMult();
        }
        throw new AssertionError("없는 스킬 " + classSkill);
    }

    @Test
    void rangeAndDefaults() {
        List<String> bad = new ArrayList<>();
        int ones = 0;
        for (ClassDef c : content.classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) {
                if (s.pvpMult() < 0.1 || s.pvpMult() > 1.0) bad.add(s.id() + "=" + s.pvpMult());
                if (s.pvpMult() == 1.0) ones++;
            }
        }
        for (ItemDef d : content.items().values()) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                if (s.pvpMult() < 0.1 || s.pvpMult() > 1.0) bad.add(d.id() + ":" + s.input() + "=" + s.pvpMult());
            }
        }
        assertTrue(bad.isEmpty(), "pvp_mult 는 0.1~1.0: " + bad);
        assertTrue(ones > 0, "적지 않은 스킬 = 1.0");
        // 명세 키가 모두 실제 스킬
        for (String k : spec.keySet()) {
            if (!k.contains(":")) continue;
            String[] p = k.split(":");
            ItemDef d = content.item(p[0]);
            assertNotNull(d, k);
            assertNotNull(d.weaponSkill(p[1]), k);
        }
    }

    @Test
    void validatorChecksRange() {
        ContentValidator.Report r = ContentValidator.validate(content);
        assertTrue(r.errors().stream().noneMatch(e -> e.contains("pvp_mult")), r.errors().toString());
    }
}
