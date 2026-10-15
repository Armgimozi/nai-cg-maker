package kr.labyrinth.items.sell;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** 접속 종료·서버 종료 때 가방이 꽉 차 맡아 둔 물건 목록 (PlayerData ext): 덧붙이기 · 한 번만 꺼내기 · 망가진 값 무시. */
class SellPendingTest {

    @Test
    void pushAppendsAndTakeEmptiesOnce() {
        Map<String, Object> ext = new LinkedHashMap<>();
        assertTrue(SellService.takePending(ext).isEmpty());
        SellService.pushPending(ext, List.of("a", "b"));
        SellService.pushPending(ext, List.of("c"));
        SellService.pushPending(ext, List.of());
        assertEquals(List.of("a", "b", "c"), ext.get(SellService.PENDING));
        assertEquals(List.of("a", "b", "c"), SellService.takePending(ext));
        assertFalse(ext.containsKey(SellService.PENDING), "꺼낸 뒤에는 지워져 두 번 돌려주지 않는다");
        assertTrue(SellService.takePending(ext).isEmpty());
    }

    @Test
    void loadedYamlListAndJunkAreHandled() {
        Map<String, Object> ext = new LinkedHashMap<>();
        // YAML 에서 읽으면 List<Object> 로 들어온다 — 빈 줄·null 은 건너뜀
        List<Object> raw = new ArrayList<>();
        raw.add("x");
        raw.add("");
        raw.add(null);
        raw.add("y");
        ext.put(SellService.PENDING, raw);
        assertEquals(List.of("x", "y"), SellService.takePending(ext));
        // 목록이 아닌 값은 비어 있는 것으로 보고, 덧붙이면 목록으로 바뀐다
        ext.put(SellService.PENDING, "망가짐");
        SellService.pushPending(ext, List.of("z"));
        assertEquals(List.of("z"), ext.get(SellService.PENDING));
    }
}
