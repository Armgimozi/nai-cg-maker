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
 * 누가 캐면 그 광맥(또는 보석 노드)이 모두에게 빈 광맥이 된다. 다시 차기까지 남은 일 = 기본 재생 초 (한 사람 기준).
 * 1초마다 {@link #tick} 이 남은 일을 dt × min(광산 월드 사람 수, cap) 만큼 줄인다 — 넷이 있으면 네 배 빨리 찬다.
 * 그래서 여럿이 같은 층을 캐도 한 사람이 1분에 얻는 몫은 혼자일 때와 비슷하다. 아무도 없어도 한 사람 빠르기로 흐른다.
 * <p>
 * 재시작 때는 기록을 두지 않는다 — 광산을 켤 때 모든 광맥을 다 찬 상태로 되돌린다 (가장 간단하고 막힐 일이 없다).
 * 열쇠는 {@code "L<층>:v<번호>"} (광맥) · {@code "L<층>:g<번호>"} (보석 노드). 번호 = 청사진 (y, z, x) 정렬 순.
 */
public final class VeinState {

    private final Map<String, Double> left = new LinkedHashMap<>();
    private final Map<String, Double> full = new LinkedHashMap<>();
    private final Set<String> rich = new HashSet<>();
    private final int cap;

    public VeinState(int cap) { this.cap = Math.max(1, cap); }

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

    public int cap() { return cap; }

    /** 비웠다: 다시 차기까지 soloSeconds (한 사람 기준) 의 일이 남는다. 이미 비었으면 그대로. */
    public synchronized boolean deplete(String key, double soloSeconds) {
        if (left.containsKey(key)) return false;
        double s = Math.max(1, soloSeconds);
        left.put(key, s);
        full.put(key, s);
        rich.remove(key);
        return true;
    }

    public synchronized boolean isDepleted(String key) { return left.containsKey(key); }

    /** 남은 일 (한 사람 기준 초, 차 있으면 0). */
    public synchronized double remaining(String key) {
        Double v = left.get(key);
        return v == null ? 0 : v;
    }

    /** 지금 사람 수로 다시 차기까지 걸리는 초 (차 있으면 0). */
    public synchronized double etaSeconds(String key, int playersInMine) {
        return remaining(key) / MineMath.regrowFactor(playersInMine, cap);
    }

    /** dt 초 흐름 (사람 수에 따라 빨라짐). 다 찬 열쇠들을 돌려준다 (차례 = 비운 차례). */
    public synchronized List<String> tick(double dtSeconds, int playersInMine) {
        if (left.isEmpty() || !(dtSeconds > 0)) return List.of();
        double work = dtSeconds * MineMath.regrowFactor(playersInMine, cap);
        List<String> done = new ArrayList<>();
        var it = left.entrySet().iterator();
        while (it.hasNext()) {
            var e = it.next();
            double v = e.getValue() - work;
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
