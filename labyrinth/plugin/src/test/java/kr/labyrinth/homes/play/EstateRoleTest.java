package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 마을 관리인 모아 (0.3.7): role estate 가 검사기 목록에 있음 · npcs.yml estate_keeper (스킨은 GDD §14.5 닫힌 목록 안) · 안내인 한 줄 ·
 * housing.yml 이 콘텐츠 파일 목록에 (없어도 됨) · 관리인 메뉴는 NPC 정의 없이도 열림 (R20 — 메뉴 코드가 NpcDef 를 보지 않음).
 */
class EstateRoleTest {

    static ContentLoader.Result result;
    static final Set<String> OUTFITS = Set.of("robe", "apron", "coat", "scholar", "traveler", "miner", "uniform", "armor");
    static final Set<String> HAIRS = Set.of("long_braid", "short_beard", "silver_ponytail", "messy_short", "curly_short", "short_bob", "long_straight",
            "twin_buns", "bun", "bald_mustache", "short_messy", "none");
    static final Set<String> ACCESSORIES = Set.of("hood_down", "lantern_belt", "satchel", "soot_marks", "thick_gloves", "goggles_forehead",
            "shoulder_cape", "medal_sash", "monocle", "round_glasses", "scroll_bundle", "quill_ear", "big_backpack", "coin_pouch", "scarf",
            "helmet_lamp", "bandage_arm", "map_case", "key_ring", "rain_cape", "ghostly", "frost_cracks", "broken_crown", "tuning_fork",
            "crystal_pendant", "ink_stains", "tool_belt", "mechanical_arm", "torn_cape", "sculk_scars");

    @BeforeAll
    static void load() {
        result = ContentLoader.load(Path.of("src/main/resources/content"));
    }

    @Test
    void roleIsKnown() {
        assertTrue(ContentValidator.NPC_ROLES.contains(HomesNames.ROLE_ESTATE));
        assertEquals("estate", HomesNames.ROLE_ESTATE);
        assertEquals("estate", HomesNames.INTERACT_ESTATE, "구역 노점 우클릭 = VillageService.openMenu estate 갈래");
        ContentValidator.Report r = ContentValidator.validate(result.content());
        assertTrue(r.ok(), () -> String.join("\n", r.errors()));
    }

    @Test
    void estateKeeperDefinition() {
        NpcDef n = result.content().npcs().get(HomesNames.NPC_ESTATE);
        assertNotNull(n, "npcs.yml estate_keeper");
        assertEquals("마을 관리인 모아", n.name());
        assertEquals("estate", n.role());
        assertEquals("overworld", n.placement());
        assertEquals("estate_keeper", n.skin());
        assertTrue(OUTFITS.contains(n.skinStyle().str("outfit")), "outfit 닫힌 목록");
        assertTrue(HAIRS.contains(n.skinStyle().str("hair")), "hair 닫힌 목록");
        List<String> acc = n.skinStyle().strings("accessories");
        assertFalse(acc.isEmpty());
        for (String a : acc) assertTrue(ACCESSORIES.contains(a), "accessories 닫힌 목록: " + a);
        List<String> pal = n.skinStyle().strings("palette");
        assertEquals(6, pal.size());
        for (String c : pal) assertTrue(c.matches("#[0-9a-fA-F]{6}"), c);
        assertTrue(n.dialogue().size() >= 3);
        for (String line : n.dialogue()) assertTrue(line.length() < 80, "대사는 짧게: " + line);
        assertTrue(n.shop().isEmpty(), "자재는 상인 상점이 아니라 관리인 메뉴 (merchant 를 하나 더 두지 않음)");
    }

    @Test
    void guideMentionsTheAlley() {
        NpcDef guide = result.content().npcs().get("guide");
        assertNotNull(guide);
        assertTrue(guide.dialogue().stream().anyMatch(l -> l.contains("남쪽 골목으로 가면 집을 받을 수 있어요")));
    }

    @Test
    void housingIsAnOptionalContentFile() throws Exception {
        assertTrue(ContentParser.FILES.contains("housing.yml"));
        assertTrue(ContentParser.OPTIONAL_FILES.contains("housing.yml"), "없어도 켜짐 (자재 탭만 빔)");
        assertTrue(result.problems().isEmpty(), () -> String.join("\n", result.problems()));
        assertTrue(Files.exists(Path.of("src/main/resources/content/housing.yml")));
    }

    @Test
    void menusDoNotNeedTheNpcDefinition() throws Exception {
        // 관리인 메뉴 · 지도 · 자재 · 맡긴 짐 · 시작 선물 · 표지판 메뉴는 NpcDef 를 읽지 않는다 (R20)
        for (String f : List.of("EstateMenu", "ClaimMenu", "BuildShopMenu", "ParcelMenu", "StarterMenu", "PlotMenu", "TrustMenu", "ConfirmMenu")) {
            String src = Files.readString(Path.of("src/main/java/kr/labyrinth/homes/play/" + f + ".java"));
            assertFalse(src.contains("npcs()"), f + " 가 npcs.yml 에 기대면 안 됨");
        }
    }
}
