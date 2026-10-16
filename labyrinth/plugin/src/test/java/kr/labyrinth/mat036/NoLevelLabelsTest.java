package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import org.junit.jupiter.api.Test;

/** 광석·주괴·보석·곡괭이의 이름·설명에 Lv·층 번호·단계·띠·티어 글자가 없다 (주인 결정 2·4). */
class NoLevelLabelsTest {

    static final Pattern LABEL = Pattern.compile("(Lv\\s*\\d|레벨|\\d+\\s*층|층\\s*\\d|단계|구간|티어|tier\\s*\\d|띠)", Pattern.CASE_INSENSITIVE);

    @Test
    void mineItemTextHasNoLevelLabels() {
        Content c = Mat036.content();
        List<String> bad = new ArrayList<>();
        int n = 0;
        for (ItemDef d : c.items().values()) {
            if (!d.isMineMaterial() && !d.isTool()) continue;
            n++;
            for (String s : List.of(d.name(), d.lore() == null ? "" : d.lore())) {
                if (LABEL.matcher(s).find()) bad.add(d.id() + ": " + s);
            }
        }
        assertEquals(List.of(), bad);
        assertEquals(24, n, "광석 6 · 주괴 6 · 보석 6 · 곡괭이 6");
    }

    @Test
    void smelterNpcTextHasNoLevelLabels() {
        Content c = Mat036.content();
        for (String id : List.of("miner", "smelter")) {
            var npc = c.npcs().get(id);
            for (String line : npc.dialogue()) assertEquals(false, LABEL.matcher(line).find(), id + ": " + line);
        }
    }
}
