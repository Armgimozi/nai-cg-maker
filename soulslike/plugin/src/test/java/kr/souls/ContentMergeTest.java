package kr.souls;

import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * M1 P1-0 계약 (R20): moves.yml·enemies.yml 은 열쇠마다 jar 사본 위에 사용자 파일을 겹쳐 읽는다. 사용자가 맞춘 값은 남고, 새 판이 더한
 * 열쇠는 jar 값으로 들어온다. 판을 올리지 않는다.
 */
class ContentMergeTest {
    private static YamlConfiguration y(String text) {
        YamlConfiguration c = new YamlConfiguration();
        try {
            c.loadFromString(text);
        } catch (InvalidConfigurationException e) {
            throw new AssertionError(e);
        }
        return c;
    }

    @Test
    void userWinsPerKeyJarFillsTheRest() {
        YamlConfiguration jar = y("""
                dummy: {body: zombie, hp: 1000, def: 20, poise: 0}
                post: {body: husk, hp: 500, moves: {jab: {windup: 12, raw: 40}}}
                """);
        YamlConfiguration user = y("""
                dummy: {hp: 2500}
                post: {moves: {jab: {windup: 16}}}
                """);
        Content.Merge m = Content.merge(jar, user);
        YamlConfiguration out = m.yml();
        assertEquals(2500, out.getInt("dummy.hp"), "사용자가 맞춘 값");
        assertEquals("zombie", out.getString("dummy.body"), "사용자 파일에 없는 열쇠는 jar 값");
        assertEquals(20, out.getInt("dummy.def"));
        assertEquals(16, out.getInt("post.moves.jab.windup"));
        assertEquals(40, out.getInt("post.moves.jab.raw"), "새 판이 더한 깊은 열쇠도 jar 값");
        assertTrue(m.filled().contains("dummy.body") && m.filled().contains("post.moves.jab.raw"));
        assertFalse(m.filled().contains("dummy.hp"));
    }

    @Test
    void userOnlyIdsStayAndListsReplaceWhole() {
        YamlConfiguration jar = y("""
                straight_sword: {light: [[4, 2, 7], [4, 2, 7], [5, 2, 8]], cost: 14}
                """);
        YamlConfiguration user = y("""
                straight_sword: {light: [[3, 2, 6]]}
                my_test: {cost: 9}
                """);
        YamlConfiguration out = Content.merge(jar, user).yml();
        assertEquals(1, out.getList("straight_sword.light").size(), "목록은 통째로 사용자 값");
        assertEquals(14, out.getInt("straight_sword.cost"));
        assertEquals(9, out.getInt("my_test.cost"), "사용자만 쓴 id 도 남는다");
    }

    @Test
    void emptyOrMissingUserFileIsJar() {
        YamlConfiguration jar = y("dummy: {hp: 1000}\n");
        assertEquals(1000, Content.merge(jar, new YamlConfiguration()).yml().getInt("dummy.hp"));
        assertEquals(1000, Content.merge(jar, null).yml().getInt("dummy.hp"));
        assertEquals(1000, Content.merge(jar, y("dummy: {}\n")).yml().getInt("dummy.hp"), "빈 절은 자리를 비우지 않는다");
        assertTrue(Content.merge(null, y("a: 1\n")).filled().isEmpty());
    }

    @Test
    void scalarOverSectionAndBack() {
        // 사용자가 절 자리에 값 하나를 쓰면 그 값이 이긴다 (읽는 쪽이 기본값으로 읽는다), 값 자리에 절을 쓰면 절이 이긴다
        YamlConfiguration out = Content.merge(y("a: {b: 1}\nc: 5\n"), y("a: 3\nc: {d: 2}\n")).yml();
        assertEquals(3, out.getInt("a"));
        assertEquals(2, out.getInt("c.d"));
    }

    @Test
    void stubFilesAreListedAndValid() {
        assertTrue(Content.FILES.containsAll(Content.MERGED));
        assertEquals(List.of("moves.yml", "enemies.yml"), Content.MERGED);
        for (String f : Content.MERGED) {
            YamlConfiguration c = TestFiles.yaml("content/" + f);
            // P1-0 의 틀은 비어 있다 (P1a 가 moves, P1b·P2b·P5a 가 enemies 를 채운다). 채운 뒤에도 맨 위는 id → 절이다
            for (String id : c.getKeys(false)) assertTrue(c.isConfigurationSection(id), f + ": " + id + " 는 절이어야 한다");
        }
    }
}
