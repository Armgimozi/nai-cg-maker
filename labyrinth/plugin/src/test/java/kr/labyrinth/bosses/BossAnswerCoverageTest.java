package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * bs363: 10 보스 모두 자기 대응이 있다 (GDD §8.6) — bosses.yml {@code patterns.answer} 와 구현 클래스의 {@code answer(Answer)},
 * 대응 쿨·최소 간격, 보스끼리 겹치지 않는 대응, 검사기 규칙. 기본 공격 거리는 어떤 보스도 바꾸지 않는다 (reach() 는 final).
 */
class BossAnswerCoverageTest {

    /** 층 → 고른 대응 (명세 bs363 §0). */
    private static final Map<Integer, String> USES = Map.of(1, "rampage_charge", 2, "ceiling_ambush", 3, "spore_brand", 4, "anchor_hurl",
            5, "hammer_toss", 6, "scepter_sweep", 7, "crystal_rain", 8, "quill_barrage", 9, "pendulum_sweep", 10, "tendril_lash");

    private static Content content() {
        return ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void everyBossHasItsOwnAnswerInYaml() {
        Content c = content();
        assertEquals(10, c.bosses().size());
        Set<String> names = new HashSet<>();
        for (BossDef d : c.bosses().values()) {
            assertTrue(d.patterns().containsKey("answer"), d.id() + " 대응 없음");
            Params a = d.pattern("answer");
            String use = a.str("use");
            assertEquals(USES.get(d.floor()), use, d.id());
            assertTrue(d.patterns().containsKey(use), d.id() + " use 패턴 없음");
            if (a.has("fallback")) assertTrue(d.patterns().containsKey(a.str("fallback")), d.id() + " fallback");
            for (String k : a.strings("shares")) assertTrue(d.patterns().containsKey(k), d.id() + " shares " + k);
            assertTrue(a.dbl("cooldown", 0) >= 6, d.id() + " 대응 쿨 6초 이상");
            assertTrue(a.dbl("min_gap", 0) > 0 && a.dbl("min_gap", 0) <= a.dbl("cooldown", 0), d.id() + " 최소 간격");
            for (List<String> rot : d.rotation().values()) assertFalse(rot.contains("answer"), d.id() + " rotation 에 대응");
            assertTrue(names.add(a.str("name", "")), "대응 이름이 겹침: " + a.str("name"));
        }
        // 2층·6층만 대체가 있다 (설 자리가 없을 때)
        assertEquals("venom_spit", c.boss("floor02_silk_queen").pattern("answer").str("fallback"));
        assertEquals("glacial_spikes", c.boss("floor06_frost_empress").pattern("answer").str("fallback"));
        assertEquals(List.of("brand_and_bloom"), c.boss("floor03_mycelium_king").pattern("answer").strings("shares"));
    }

    @Test
    void existingPatternNumbersAreUntouched() {
        // 대응은 빌린 패턴의 yml 값을 그대로 쓴다 — 0.3.6.1 수치 그대로인지 몇 개 확인
        Content c = content();
        Params charge = c.boss("floor01_moss_warden").pattern("rampage_charge");
        assertEquals(2.0, charge.dbl("damage", 0), 1e-9);
        assertEquals(2.0, charge.dbl("mark_time", 0), 1e-9);
        assertEquals(16, charge.dbl("cooldown", 0), 1e-9);
        assertEquals(2.0, c.boss("floor02_silk_queen").pattern("ceiling_ambush").dbl("damage", 0), 1e-9);
        assertEquals(30, c.boss("floor02_silk_queen").pattern("ceiling_ambush").dbl("cooldown", 0), 1e-9);
        assertEquals(0.2, c.boss("floor03_mycelium_king").pattern("spore_brand").dbl("patch_damage", 0), 1e-9);
        assertEquals(1.4, c.boss("floor04_floodwarden").pattern("anchor_hurl").dbl("damage", 0), 1e-9);
        assertEquals(1.5, c.boss("floor05_anvil_king").pattern("hammer_toss").dbl("damage", 0), 1e-9);
        assertEquals(1.3, c.boss("floor06_frost_empress").pattern("scepter_sweep").dbl("damage", 0), 1e-9);
        assertEquals(1.2, c.boss("floor07_dyad").pattern("crystal_rain").dbl("damage", 0), 1e-9);
        assertEquals(0.7, c.boss("floor08_ink_librarian").pattern("quill_barrage").dbl("damage", 0), 1e-9);
        assertEquals(1.8, c.boss("floor09_clock_warden").pattern("pendulum_sweep").dbl("damage", 0), 1e-9);
        assertEquals(1.4, c.boss("floor10_abyss_heart").pattern("tendril_lash").dbl("damage", 0), 1e-9);
    }

    @Test
    void everyFloorBossOverridesAnswerAndNoneChangesReach() throws Exception {
        Method reach = Boss.class.getDeclaredMethod("reach");
        assertTrue(Modifier.isFinal(reach.getModifiers()), "reach() 는 final — 보스마다 2.0 + 0.7 × scale (0.3.6.1)");
        for (int f = 1; f <= 10; f++) {
            String name = String.format("kr.labyrinth.bosses.impl.Floor%02dBoss", f);
            Class<?> cls = Class.forName(name, false, getClass().getClassLoader());
            Method m = cls.getDeclaredMethod("answer", Boss.Answer.class);
            assertEquals(int.class, m.getReturnType(), name);
            for (Method d : cls.getDeclaredMethods()) assertFalse(d.getName().equals("reach") && d.getParameterCount() == 0, name);
        }
        // 기반의 기본값: 대응 없음 (−1) — 층 보스 밖(관리자 시험용 보스 등)은 움직임만
        assertEquals(int.class, Boss.class.getDeclaredMethod("answer", Boss.Answer.class).getReturnType());
    }

    @Test
    void validatorAcceptsBundledAnswersAndRejectsBrokenOnes(@TempDir Path dir) throws IOException {
        Content ok = content();
        ContentValidator.Report r = ContentValidator.validate(ok);
        assertTrue(r.errors().stream().noneMatch(e -> e.contains("answer")), r.errors().toString());

        Path src = Path.of("src/main/resources/content");
        try (Stream<Path> files = Files.walk(src)) {
            for (Path p : (Iterable<Path>) files::iterator) {
                Path to = dir.resolve(src.relativize(p).toString());
                if (Files.isDirectory(p)) Files.createDirectories(to);
                else Files.copy(p, to);
            }
        }
        Path bosses = dir.resolve("bosses.yml");
        List<String> lines = new ArrayList<>(Files.readAllLines(bosses, StandardCharsets.UTF_8));
        int n = 0;
        for (int i = 0; i < lines.size(); i++) {
            String l = lines.get(i);
            if (l.equals("      answer: {use: rampage_charge, name: 돌진, cooldown: 12, min_gap: 8}")) {
                lines.set(i, "      answer: {use: no_such_pattern, name: 돌진, cooldown: 3, min_gap: 0}");
                n++;
            } else if (l.startsWith("      answer: {use: ceiling_ambush")) {
                lines.set(i, "      answer: {use: ceiling_ambush, name: 천장 낙하, cooldown: 14, min_gap: 10, fallback: nope}");
                n++;
            } else if (l.startsWith("      answer: {use: spore_brand")) {
                lines.set(i, "      answer: {use: spore_brand, name: 구석 낙인, cooldown: 14, min_gap: 8, shares: [gone]}");
                n++;
            } else if (l.equals("      1: [key_strike, anchor_hurl, tidal_sweep, rising_flood]")) {
                lines.set(i, "      1: [key_strike, anchor_hurl, tidal_sweep, rising_flood, answer]");
                n++;
            }
        }
        assertEquals(4, n);
        Files.write(bosses, lines, StandardCharsets.UTF_8);
        ContentValidator.Report bad = ContentValidator.validate(ContentLoader.load(dir).content());
        String errs = String.join("\n", bad.errors());
        assertTrue(errs.contains("floor01_moss_warden.patterns.answer") && errs.contains("no_such_pattern"), errs);
        assertTrue(errs.contains("cooldown 은 6초 이상"), errs);
        assertTrue(errs.contains("min_gap 은 0 보다 커야"), errs);
        assertTrue(errs.contains("fallback 패턴이 patterns 에 없음: nope"), errs);
        assertTrue(errs.contains("shares 패턴이 patterns 에 없음: gone"), errs);
        assertTrue(errs.contains("floor04_floodwarden.rotation.1") && errs.contains("answer 는 rotation 에 넣지 않음"), errs);
    }
}
