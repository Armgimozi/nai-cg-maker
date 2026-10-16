package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.Test;

/**
 * 번들 items.yml 의 {@code unique:} 블록 (P3 — tools/gen_035_content.py 가 배정 데이터에서 넣음) 을 파서·검사기가 그대로 받는지.
 * 오류 0 · 고유 효과 경고 0 · 무기마다 효과가 읽히고, P3 설계가 덮어쓰지 않은 무기는 배정과 같은 효과·이름·수치.
 */
class UniqueContentLoadTest {

    @Test
    void bundledUniqueBlocksMatchTheAssignments() throws IOException {
        ContentLoader.Result r = ContentLoader.load(Path.of("src/main/resources/content"));
        assertTrue(r.problems().isEmpty(), () -> String.join("\n", r.problems()));
        ContentValidator.Report rep = ContentValidator.validate(r.content());
        assertTrue(rep.ok(), () -> String.join("\n", rep.errors()));
        List<String> uniqueWarnings = rep.warnings().stream().filter(w -> w.contains("unique")).toList();
        assertTrue(uniqueWarnings.isEmpty(), () -> String.join("\n", uniqueWarnings));

        Set<String> p3Weapons = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/content_p3.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("weapons").keySet();
        Map<String, UniqueData.Entry> data = UniqueData.all();
        Content c = r.content();
        int same = 0;
        for (ItemDef d : c.items().values()) {
            if (!d.isWeapon()) continue;
            assertNotNull(d.unique(), d.id());
            UniqueData.Entry e = data.get(d.id());
            if (e == null || p3Weapons.contains(d.id())) continue;
            assertEquals(e.effect(), d.unique().id(), d.id());
            assertEquals(e.name(), d.unique().name(), d.id());
            for (String k : e.params().keys()) {
                Object want = e.params().get(k);
                if (want instanceof Number n) assertEquals(n.doubleValue(), d.unique().num(k), 1e-9, d.id() + "." + k);
                else assertEquals(String.valueOf(want).toLowerCase(Locale.ROOT), d.unique().text(k, ""), d.id() + "." + k);
            }
            same++;
        }
        assertTrue(same >= 200, "배정 그대로인 무기 " + same);
    }
}
