package kr.labyrinth.items.enhance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.sell.SellPrices;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비에 층 글자를 붙이지 않는다 (0.3.5 결정 5) — 강화 화면 안내·강화석 설명·판매 가격표. 강화석은 장비의 숨은 단계로 정해지고
 * 단계 풀이 이웃 층과 섞이므로 '지하 1~3층 장비'는 틀린 안내다. 강화석을 얻는 곳(재료)은 층을 적는다.
 */
class EnhanceGuideTextTest {

    /** '장비' 앞에 층 숫자 ("지하 1~3층 장비", "4~7층 상급 … 장비"). */
    static final Pattern FLOOR_GEAR = Pattern.compile("(\\d+\\s*층|지하\\s*\\d)[^.。]*장비");
    static Content content;
    static EnhanceRules.Config config;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        config = EnhanceRules.Config.from(y.getConfigurationSection("enhance"));
    }

    private List<String> stoneNames() {
        List<String> names = new ArrayList<>();
        for (EnhanceRules.Stone s : config.stones()) names.add(content.item(s.item()).name());
        return names;
    }

    @Test
    void stoneGuideSaysEarlyMidLateNotFloors() {
        String line = EnhanceGuide.stoneGuide(stoneNames());
        assertEquals("강화석: 초반 장비 하급 · 중반 상급 · 후반 최상급", line);
        assertFalse(FLOOR_GEAR.matcher(line).find(), line);
        assertFalse(line.contains("층"), line);
        assertEquals("강화석: 초반 장비 하급 · 후반 상급", EnhanceGuide.stoneGuide(List.of("하급 강화석", "상급 강화석")));
        assertTrue(EnhanceGuide.stoneGuide(List.of("강화석")).contains("장비마다"));
    }

    @Test
    void stoneSourceKeepsFloorsButNotForGear() {
        List<EnhanceRules.Stone> stones = config.stones();
        assertEquals("지하 1~3층 몬스터·상자·보스 · 상인", EnhanceGuide.stoneSource(stones, "lesser_enhance_stone", true));
        assertEquals("지하 4~7층 몬스터·상자·보스", EnhanceGuide.stoneSource(stones, "greater_enhance_stone", false));
        assertEquals("지하 8~10층 몬스터·상자·보스", EnhanceGuide.stoneSource(stones, "supreme_enhance_stone", false));
        assertEquals("미궁에서 얻습니다", EnhanceGuide.stoneSource(stones, "nope", false));
        for (EnhanceRules.Stone s : stones) {
            String t = EnhanceGuide.stoneSource(stones, s.item(), true);
            assertFalse(t.contains("장비"), t);
        }
    }

    @Test
    void stoneLoreHasNoFloorGear() {
        for (EnhanceRules.Stone s : config.stones()) {
            ItemDef d = content.item(s.item());
            String lore = d.lore() == null ? "" : d.lore();
            assertFalse(FLOOR_GEAR.matcher(lore).find(), s.item() + ": " + lore);
            assertTrue(lore.contains("장비를 강화한다"), s.item() + ": " + lore);
        }
        // 다른 재료·소모품 설명에도 '…층 장비' 가 없다
        for (ItemDef d : content.items().values()) {
            String lore = d.lore() == null ? "" : d.lore();
            assertFalse(FLOOR_GEAR.matcher(lore).find(), d.id() + ": " + lore);
        }
    }

    @Test
    void sellTableGearLineHasNoFloor() {
        SellPrices prices = new SellPrices(SellPrices.Config.DEFAULT, SellPrices.buyPrices(content.npcs().values()), List.of());
        boolean seen = false;
        for (String raw : prices.tableLore()) {
            String line = Text.strip(raw);
            if (!line.startsWith("장비")) continue;
            seen = true;
            assertFalse(line.contains("층"), line);
            assertTrue(line.contains("장비 단계"), line);
        }
        assertTrue(seen, "가격표 장비 줄");
    }
}
