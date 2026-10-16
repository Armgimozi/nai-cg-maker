package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * 배정 데이터를 items.yml 의 {@code unique:} 블록으로 넣었을 때(P3 가 할 일) 파서·검사기가 그대로 받는지 — 번들 콘텐츠를 임시 폴더에
 * 복사해 기존 무기 131개에 한 줄씩 넣고 읽는다. 오류 0 · 고유 효과 경고 0 · 무기마다 효과가 읽힘.
 */
class UniqueContentLoadTest {

    static final Pattern HEADER = Pattern.compile("^  ([a-z0-9_]+):\\s*(#.*)?$");

    @Test
    void assignmentsLoadAsUniqueBlocks(@TempDir Path dir) throws IOException {
        Path src = Path.of("src/main/resources/content");
        try (Stream<Path> files = Files.walk(src)) {
            for (Path p : (Iterable<Path>) files::iterator) {
                Path to = dir.resolve(src.relativize(p).toString());
                if (Files.isDirectory(p)) Files.createDirectories(to);
                else Files.copy(p, to);
            }
        }
        Map<String, UniqueData.Entry> data = UniqueData.all();
        Path items = dir.resolve("items.yml");
        List<String> out = new ArrayList<>();
        int inserted = 0;
        boolean inItems = false;
        for (String line : Files.readAllLines(items, StandardCharsets.UTF_8)) {
            out.add(line);
            if (!line.startsWith(" ") && !line.isBlank() && !line.startsWith("#")) inItems = line.startsWith("items:");
            Matcher m = HEADER.matcher(line);
            if (inItems && m.matches() && data.containsKey(m.group(1))) {
                out.add("    unique: " + flow(data.get(m.group(1))));
                inserted++;
            }
        }
        Files.write(items, out, StandardCharsets.UTF_8);
        assertEquals(131, inserted);

        ContentLoader.Result r = ContentLoader.load(dir);
        assertTrue(r.problems().isEmpty(), () -> String.join("\n", r.problems()));
        ContentValidator.Report rep = ContentValidator.validate(r.content());
        assertTrue(rep.ok(), () -> String.join("\n", rep.errors()));
        List<String> uniqueWarnings = rep.warnings().stream().filter(w -> w.contains("unique")).toList();
        assertTrue(uniqueWarnings.isEmpty(), () -> String.join("\n", uniqueWarnings));
        Content c = r.content();
        for (ItemDef d : c.items().values()) {
            if (!d.isWeapon()) continue;
            assertNotNull(d.unique(), d.id());
            assertEquals(data.get(d.id()).effect(), d.unique().id(), d.id());
            assertEquals(data.get(d.id()).name(), d.unique().name(), d.id());
        }
    }

    private static String flow(UniqueData.Entry e) {
        StringBuilder sb = new StringBuilder("{id: ").append(e.effect()).append(", name: \"").append(e.name()).append('"');
        e.params().asMap().forEach((k, v) -> {
            sb.append(", ").append(k).append(": ");
            if (v instanceof Number n) {
                double d = n.doubleValue();
                sb.append(d == Math.rint(d) ? String.valueOf((long) d) : String.valueOf(d));
            } else {
                sb.append(v);
            }
        });
        return sb.append('}').toString();
    }
}
