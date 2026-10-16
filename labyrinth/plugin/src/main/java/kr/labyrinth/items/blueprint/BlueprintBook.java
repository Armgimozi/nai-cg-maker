package kr.labyrinth.items.blueprint;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * 배운 도안 기록 — 순수 로직 (0.3.6 Q6). PlayerData ext {@value #KEY} = 레시피 id 목록 (id 순, 겹침 없음).
 * 한 번 배우면 영구 (죽어도·전직해도 남는다). ext {@value #GRANDFATHER_KEY} = 0.3.6 첫 접속 보호를 한 번 했음.
 */
public final class BlueprintBook {

    public static final String KEY = "blueprints.learned";
    public static final String GRANDFATHER_KEY = "blueprints.v036";

    private BlueprintBook() {}

    /** 배운 레시피 id (id 순, 새 목록). */
    public static List<String> learned(Map<String, Object> ext) {
        TreeSet<String> out = new TreeSet<>();
        Object v = ext == null ? null : ext.get(KEY);
        if (v instanceof Collection<?> c) {
            for (Object o : c) if (o != null && !o.toString().isBlank()) out.add(o.toString().trim());
        } else if (v instanceof String s && !s.isBlank()) {
            out.add(s.trim());
        }
        return new ArrayList<>(out);
    }

    public static boolean knows(Map<String, Object> ext, String recipeId) {
        return recipeId != null && learned(ext).contains(recipeId);
    }

    /** @return 새로 배웠으면 true (이미 알면 false — 기록은 그대로) */
    public static boolean learn(Map<String, Object> ext, String recipeId) {
        if (recipeId == null || recipeId.isBlank()) return false;
        List<String> now = learned(ext);
        if (now.contains(recipeId)) return false;
        TreeSet<String> next = new TreeSet<>(now);
        next.add(recipeId);
        ext.put(KEY, new ArrayList<>(next));
        return true;
    }

    /** @return 새로 배운 개수 */
    public static int learnAll(Map<String, Object> ext, Collection<String> recipeIds) {
        TreeSet<String> next = new TreeSet<>(learned(ext));
        int before = next.size();
        if (recipeIds != null) for (String r : recipeIds) if (r != null && !r.isBlank()) next.add(r);
        if (next.size() != before) ext.put(KEY, new ArrayList<>(next));
        return next.size() - before;
    }

    /** @return 잊었으면 true */
    public static boolean forget(Map<String, Object> ext, String recipeId) {
        List<String> now = learned(ext);
        if (!now.remove(recipeId)) return false;
        if (now.isEmpty()) ext.remove(KEY);
        else ext.put(KEY, now);
        return true;
    }

    /** 모두 잊기. @return 잊은 개수 */
    public static int forgetAll(Map<String, Object> ext) {
        int n = learned(ext).size();
        ext.remove(KEY);
        return n;
    }
}
