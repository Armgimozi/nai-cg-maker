package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 함께 쓰는 광맥의 빈 상태 (계약 §0-3, 주인 늦은 결정 "다른 사람들이랑 공유"). 순수 — 서버 없이 시험.
 * <p>
 * 누가 캐면 그 광맥(또는 보석 노드)이 모두에게 빈 광맥이 된다. 남은 값 = 다시 차기까지 남은 초.
 * 사람 수와 관계 없이 흐른다 (0.3.7 주인 결정 "광맥이 다시 생성되는 시간은 플레이어 유무와 관계 없이") —
 * {@link #tick} 은 흐른 초만큼 그대로 줄인다. 광산에 아무도 없어도 같다.
 * <p>
 * 재시작 때는 기록을 두지 않는다 — 광산을 켤 때 모든 광맥을 다 찬 상태로 되돌린다 (가장 간단하고 막힐 일이 없다).
 * 열쇠는 {@code "L<층>:v<번호>"} (광맥) · {@code "L<층>:g<번호>"} (보석 노드). 번호 = 청사진 (y, z, x) 정렬 순.
 */
public final class VeinState {

    private final Map<String, Double> left = new LinkedHashMap<>();
    private final Map<String, Double> full = new LinkedHashMap<>();
    private final Set<String> rich = new HashSet<>();

    public VeinState() {}

    public static String veinKey(int level, int index) { return "L" + level + ":v" + index; }

    public static String gemKey(int level, int index) { return "L" + level + ":g" + index; }

    /** 열쇠 → 층 번호 (형식이 틀리면 0). */
    public static int levelOf(String key) {
        if (key == null || !key.startsWith("L")) return 0;
        int c = key.indexOf(':');
        try {
            return Integer.parseInt(key.substring(1, c));
        } catch (RuntimeException e) {
            return 0;
        }
    }

    /** 비웠다: 다시 차기까지 seconds 초가 남는다. 이미 비었으면 그대로. */
    public synchronized boolean deplete(String key, double seconds) {
        if (left.containsKey(key)) return false;
        double s = Math.max(1, seconds);
        left.put(key, s);
        full.put(key, s);
        rich.remove(key);
        return true;
    }

    public synchronized boolean isDepleted(String key) { return left.containsKey(key); }

    /** 다시 차기까지 남은 초 (차 있으면 0). */
    public synchronized double remaining(String key) {
        Double v = left.get(key);
        return v == null ? 0 : v;
    }

    /** 다시 차기까지 걸리는 초 (차 있으면 0) — 사람 수와 관계 없음, {@link #remaining} 과 같다. */
    public synchronized double etaSeconds(String key) { return remaining(key); }

    /** dt 초 흐름 (사람 수와 관계 없음). 다 찬 열쇠들을 돌려준다 (차례 = 비운 차례). */
    public synchronized List<String> tick(double dtSeconds) {
        if (left.isEmpty() || !(dtSeconds > 0)) return List.of();
        List<String> done = new ArrayList<>();
        var it = left.entrySet().iterator();
        while (it.hasNext()) {
            var e = it.next();
            double v = e.getValue() - dtSeconds;
            if (v <= 1e-9) {
                done.add(e.getKey());
                it.remove();
                full.remove(e.getKey());
            } else {
                e.setValue(v);
            }
        }
        return done;
    }

    /** 바로 채움 (관리자·시험). */
    public synchronized boolean refill(String key) {
        full.remove(key);
        return left.remove(key) != null;
    }

    /** 그 층 기록을 모두 지움 (층을 다시 지었을 때). @return 지운 수 */
    public synchronized int clearLevel(int level) {
        String p = "L" + level + ":";
        int n = 0;
        var it = left.keySet().iterator();
        while (it.hasNext()) {
            String k = it.next();
            if (k.startsWith(p)) {
                it.remove();
                full.remove(k);
                n++;
            }
        }
        rich.removeIf(k -> k.startsWith(p));
        return n;
    }

    public synchronized void clear() {
        left.clear();
        full.clear();
        rich.clear();
    }

    /** 비어 있는 열쇠들 (사본). */
    public synchronized List<String> depleted() { return List.copyOf(left.keySet()); }

    public synchronized int count() { return left.size(); }

    public synchronized int count(int level) {
        String p = "L" + level + ":";
        int n = 0;
        for (String k : left.keySet()) if (k.startsWith(p)) n++;
        return n;
    }

    // ── 풍부한 광맥 (다시 찰 때 4% 로 반짝, 다음 사람이 ×3) ─────────────────

    public synchronized void markRich(String key) {
        if (!left.containsKey(key)) rich.add(key);
    }

    public synchronized boolean isRich(String key) { return rich.contains(key); }

    /** 캘 때: 풍부했으면 true 를 돌려주고 지움. */
    public synchronized boolean takeRich(String key) { return rich.remove(key); }

    public synchronized Set<String> richKeys() { return Collections.unmodifiableSet(new HashSet<>(rich)); }
}
