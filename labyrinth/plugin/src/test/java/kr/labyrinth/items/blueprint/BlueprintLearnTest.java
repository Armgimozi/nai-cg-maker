package kr.labyrinth.items.blueprint;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.data.PlayerData;
import org.junit.jupiter.api.Test;

/** 도안 배우기 (0.3.6 Q6): 영구 기록 · 이미 알면 그대로 · 잊기 · 저장 왕복. */
class BlueprintLearnTest {

    @Test
    void learnOnceKnowForever() {
        Map<String, Object> ext = new LinkedHashMap<>();
        assertFalse(BlueprintBook.knows(ext, "a_sword"));
        assertTrue(BlueprintBook.learn(ext, "a_sword"), "처음 배움");
        assertTrue(BlueprintBook.knows(ext, "a_sword"));
        assertFalse(BlueprintBook.learn(ext, "a_sword"), "이미 알면 false (도안은 소모하지 않는다)");
        assertEquals(List.of("a_sword"), BlueprintBook.learned(ext));
        assertTrue(BlueprintBook.learn(ext, "b_helm"));
        assertEquals(List.of("a_sword", "b_helm"), BlueprintBook.learned(ext), "id 순, 겹침 없음");
        assertFalse(BlueprintBook.learn(ext, null));
        assertFalse(BlueprintBook.learn(ext, " "));
    }

    @Test
    void learnAllAndForget() {
        Map<String, Object> ext = new LinkedHashMap<>();
        assertEquals(3, BlueprintBook.learnAll(ext, List.of("c", "a", "b", "a")));
        assertEquals(0, BlueprintBook.learnAll(ext, List.of("a")));
        assertTrue(BlueprintBook.forget(ext, "b"));
        assertFalse(BlueprintBook.forget(ext, "b"));
        assertEquals(List.of("a", "c"), BlueprintBook.learned(ext));
        assertEquals(2, BlueprintBook.forgetAll(ext));
        assertFalse(ext.containsKey(BlueprintBook.KEY));
    }

    @Test
    void readsWhateverYamlGivesBack() {
        Map<String, Object> ext = new LinkedHashMap<>();
        ext.put(BlueprintBook.KEY, "solo");
        assertTrue(BlueprintBook.knows(ext, "solo"), "한 줄 문자열로 저장돼 있어도 읽는다");
        ext.put(BlueprintBook.KEY, List.of(" x ", "", "y"));
        assertEquals(List.of("x", "y"), BlueprintBook.learned(ext));
    }

    @Test
    void survivesSaveAndLoad() throws Exception {
        PlayerData d = new PlayerData(UUID.randomUUID(), "tester");
        BlueprintBook.learnAll(d.ext(), List.of("ember_blade", "rime_helm"));
        d.ext().put(BlueprintBook.GRANDFATHER_KEY, true);
        PlayerData r = PlayerData.fromYaml(d.uuid(), "tester", d.toYaml());
        assertEquals(List.of("ember_blade", "rime_helm"), BlueprintBook.learned(r.ext()));
        assertEquals(Boolean.TRUE, r.ext().get(BlueprintBook.GRANDFATHER_KEY));
        assertTrue(BlueprintBook.learn(r.ext(), "zz_new"));
        PlayerData r2 = PlayerData.fromYaml(d.uuid(), "tester", r.toYaml());
        assertEquals(3, BlueprintBook.learned(r2.ext()).size());
    }
}
