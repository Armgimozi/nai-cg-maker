package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import kr.labyrinth.classes.LabyrinthClassService;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.ItemTooltip;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.5 P0b — 무기 종류(분류)가 어디에도 없다 (주인 결정 1): 종류 이름·종류 규칙·추천 무기·종류별 피해 환산이 없고,
 * 무기마다 공격 방식(attack: style · interval · kind)만 있다.
 */
class WeaponTypeGoneTest {

    /** 화면에 나오면 안 되는 분류 이름 (아이템 이름·이야기 속 단어가 아니라 '분류'로 쓰인 것). */
    static final List<String> LABELS = List.of("대검", "한손검", "검과 방패", "활", "지팡이", "홀", "단검");

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void weaponTypesClassIsGone() {
        assertThrows(ClassNotFoundException.class, () -> Class.forName("kr.labyrinth.content.WeaponTypes"));
    }

    @Test
    void dataHasNoWeaponTypeKeys() {
        int weapons = 0;
        for (ItemDef d : content.items().values()) {
            assertFalse(d.raw().has("weapon_type"), d.id() + ": weapon_type 이 남음");
            if (!d.isWeapon()) continue;
            weapons++;
            assertFalse(d.raw().sub("attack").isEmpty(), d.id() + ": attack 블록 없음");
        }
        assertTrue(weapons >= 131, "무기 " + weapons);
        for (ClassDef c : content.classes().values()) {
            assertFalse(c.raw().has("weapon_types"), c.id() + ": weapon_types 가 남음");
            assertTrue(c.raw().has("starter_weapon"), c.id() + ": starter_weapon 없음");
        }
        String warnings = String.join("\n", ContentValidator.validate(content).warnings());
        assertFalse(warnings.contains("weapon_type"), warnings);
    }

    @Test
    void classTextsNameNoWeaponCategory() {
        List<String> bad = List.of("대검", "한손검", "검과 방패", "활잡이", "지팡이", "단검", "추천 무기");
        for (ClassDef c : content.classes().values()) {
            List<String> texts = new ArrayList<>(List.of(c.name(), c.description(), LabyrinthClassService.mainStatsText(c)));
            if (c.passive() != null) texts.add(c.passive().description());
            for (ClassDef.SkillDef s : c.skills()) {
                texts.add(s.name());
                texts.add(s.description());
            }
            for (String t : texts) for (String w : bad) assertFalse(t.contains(w), c.id() + ": '" + w + "' — " + t);
            assertFalse(c.mainStats().isEmpty(), c.id());
        }
    }

    @Test
    void tooltipFirstLineSaysJustWeapon() {
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            String first = ItemTooltip.lines(content, d, null).get(0);
            assertTrue(first.contains(d.rarity().displayName() + " 무기"), d.id() + ": " + first);
            for (String w : LABELS) assertFalse(first.contains(w), d.id() + ": '" + w + "' — " + first);
        }
    }

    @Test
    void sourceHasNoWeaponTypeLabelsOrRules() throws IOException {
        // 분류 이름이 문자열로 그대로 들어 있거나(표·지도), 무기 종류를 읽는 코드가 남아 있으면 안 된다
        List<String> problems = new ArrayList<>();
        try (Stream<Path> files = Files.walk(Path.of("src/main/java"))) {
            for (Path f : files.filter(p -> p.toString().endsWith(".java")).toList()) {
                String src = Files.readString(f, StandardCharsets.UTF_8);
                if (src.contains("weaponType(") || src.contains("WeaponTypes") || src.contains("recommendsWeapon")) {
                    problems.add(f + ": 무기 종류 코드");
                }
                for (String w : LABELS) if (src.contains("\"" + w + "\"")) problems.add(f + ": 분류 이름 \"" + w + "\"");
                if (src.contains("추천 무기") && !onlyInComments(src, "추천 무기")) problems.add(f + ": '추천 무기' 글");
            }
        }
        assertEquals(List.of(), problems);
        String config = Files.readString(Path.of("src/main/resources/config.yml"), StandardCharsets.UTF_8);
        assertFalse(config.contains("추천 무기"));
    }

    @Test
    void legacy034FilesStillLoad() {
        // 서버 주인이 손대 jar 의 새 파일로 바뀌지 않은 0.3.4 items.yml · classes.yml: 옛 키를 읽어 그때처럼 움직이고, 검사기가 경고한다
        Map<String, Object> bow = new LinkedHashMap<>();
        bow.put("type", "weapon");
        bow.put("weapon_type", "bow");
        bow.put("stats", Map.of("damage", List.of(9, 10)));
        bow.put("model", Map.of("shape", "longbow"));
        Map<String, Object> blade = new LinkedHashMap<>();
        blade.put("type", "weapon");
        blade.put("weapon_type", "greatsword");
        blade.put("stats", Map.of("damage", List.of(10, 12)));
        Map<String, Object> skill = new LinkedHashMap<>();
        skill.put("id", "piercing_arrow");
        skill.put("input", "SWAP");
        skill.put("cooldown", 10.0);
        Map<String, Object> hunter = new LinkedHashMap<>();
        hunter.put("name", "사냥꾼");
        hunter.put("role", "ranged");
        hunter.put("weapon_types", List.of("bow"));
        hunter.put("skills", List.of(skill));
        Map<String, Map<String, Object>> files = new HashMap<>();
        files.put("items.yml", Map.of("items", Map.of("old_bow", bow, "old_blade", blade)));
        files.put("classes.yml", Map.of("classes", Map.of("hunter", hunter)));
        ContentParser parser = new ContentParser();
        Content c = parser.parse(files);
        assertEquals(List.of(), parser.problems().stream().filter(x -> !x.contains("파일이 없음")).toList());
        assertTrue(c.item("old_bow").isRanged());
        assertEquals(1.15, c.item("old_bow").attack().interval(), 1e-9, "0.3.4 활 주기");
        assertEquals(1.05, c.item("old_blade").attack().interval(), 1e-9);
        assertEquals(9.0, c.classDef("hunter").skills().get(0).cooldown(), 1e-9, "예전 '추천 무기 −10%' 를 재사용 대기에 녹임");
        assertEquals("corridor_longbow", c.classDef("hunter").starterWeapon(), "starter_weapon 이 없으면 직업 기본값");
        assertEquals(List.of(kr.labyrinth.stats.Stat.DEX, kr.labyrinth.stats.Stat.STR), c.classDef("hunter").mainStats());
        String warnings = String.join("\n", ContentValidator.validate(c).warnings());
        assertTrue(warnings.contains("items.old_bow: weapon_type 은 0.3.5 부터 쓰지 않음"), warnings);
        assertTrue(warnings.contains("classes.hunter: weapon_types 는 0.3.5 부터 쓰지 않음"), warnings);
    }

    /** 단어가 주석(// 또는 * 로 시작하는 줄 안)에만 있는가. */
    private static boolean onlyInComments(String src, String word) {
        for (String line : src.split("\n")) {
            if (!line.contains(word)) continue;
            String t = line.trim();
            int code = line.indexOf("//");
            if (t.startsWith("*") || t.startsWith("/*") || t.startsWith("//")) continue;
            if (code >= 0 && line.indexOf(word) > code) continue;
            return false;
        }
        return true;
    }
}
