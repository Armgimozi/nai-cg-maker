package kr.souls.data;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import kr.souls.progression.StatBlock;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * 플레이어 프로필 (5.10, 12.6): 플레이어 PDC souls:profile 의 판 번호가 붙은 JSON.
 * {"v":1,"origin":"knight","originAt":…,"stats":{"vig":15,…},"souls":0,"kit":{"given":["weapon:redin_guard_sword"]},"settingsSeen":1}
 * 레벨은 적지 않고 능력치로 셈한다. 모르는 칸은 지우지 않고 그대로 둔다 (다음 판이 더한 칸을 옛 플러그인이 지우지 않게).
 * 순수 클래스 (Gson 만, 13.1 의 ProfileJsonTest).
 */
public final class Profile {
    public static final int VERSION = 1;
    /** 소울 지갑의 끝 (5.10) */
    public static final long SOULS_MAX = 999_999_999L;
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private final JsonObject raw;
    private String origin;
    private long originAt;
    private StatBlock stats;
    private long souls;
    private final Set<String> given = new LinkedHashSet<>();
    private int settingsSeen;

    private Profile(JsonObject raw) {
        this.raw = raw;
    }

    /** 처음 들어온 사람 (출신 없음, 능력치 모두 10). */
    public static Profile fresh() {
        Profile p = new Profile(new JsonObject());
        p.stats = StatBlock.BASE;
        return p;
    }

    /** JSON 을 읽는다. 깨졌거나 비었으면 새 프로필. */
    public static Profile parse(String json) {
        Profile p = parseStrict(json);
        return p != null ? p : fresh();
    }

    /** JSON 을 읽는다. 비었으면 새 프로필, 깨졌으면 null (부른 쪽이 깨진 것을 백업으로 남긴다). */
    public static Profile parseStrict(String json) {
        if (json == null || json.isBlank()) return fresh();
        JsonObject o;
        try {
            JsonElement e = JsonParser.parseString(json);
            if (!e.isJsonObject()) return null;
            o = e.getAsJsonObject();
        } catch (RuntimeException ex) {
            return null;
        }
        Profile p = new Profile(o);
        p.origin = str(o, "origin");
        p.originAt = num(o, "originAt", 0);
        JsonObject st = o.has("stats") && o.get("stats").isJsonObject() ? o.getAsJsonObject("stats") : new JsonObject();
        p.stats = new StatBlock((int) num(st, "vig", 10), (int) num(st, "mnd", 10), (int) num(st, "end", 10), (int) num(st, "str", 10),
                (int) num(st, "dex", 10), (int) num(st, "int", 10));
        p.souls = Math.max(0, Math.min(SOULS_MAX, num(o, "souls", 0)));
        if (o.has("kit") && o.get("kit").isJsonObject()) {
            JsonObject kit = o.getAsJsonObject("kit");
            if (kit.has("given") && kit.get("given").isJsonArray()) {
                for (JsonElement g : kit.getAsJsonArray("given")) if (g.isJsonPrimitive()) p.given.add(g.getAsString());
            }
        }
        p.settingsSeen = (int) num(o, "settingsSeen", 0);
        return p;
    }

    /** JSON 으로 (모르는 칸은 그대로, 판 번호는 이 판). */
    public String toJson() {
        JsonObject o = raw.deepCopy();
        o.addProperty("v", VERSION);
        if (origin == null) o.remove("origin");
        else o.addProperty("origin", origin);
        if (originAt > 0) o.addProperty("originAt", originAt);
        else o.remove("originAt");
        JsonObject st = o.has("stats") && o.get("stats").isJsonObject() ? o.getAsJsonObject("stats") : new JsonObject();
        st.addProperty("vig", stats.vig());
        st.addProperty("mnd", stats.mnd());
        st.addProperty("end", stats.end());
        st.addProperty("str", stats.str());
        st.addProperty("dex", stats.dex());
        st.addProperty("int", stats.intel());
        o.add("stats", st);
        o.addProperty("souls", souls);
        JsonObject kit = o.has("kit") && o.get("kit").isJsonObject() ? o.getAsJsonObject("kit") : new JsonObject();
        JsonArray arr = new JsonArray();
        for (String g : given) arr.add(g);
        kit.add("given", arr);
        o.add("kit", kit);
        o.addProperty("settingsSeen", settingsSeen);
        return GSON.toJson(o);
    }

    private static String str(JsonObject o, String k) {
        JsonElement e = o.get(k);
        return e != null && e.isJsonPrimitive() && !e.getAsString().isBlank() ? e.getAsString() : null;
    }

    private static long num(JsonObject o, String k, long def) {
        JsonElement e = o.get(k);
        try {
            return e != null && e.isJsonPrimitive() ? e.getAsLong() : def;
        } catch (RuntimeException ex) {
            return def;
        }
    }

    // ------------------------------------------------------------------ 값

    /** 출신 id (아직 고르지 않았으면 null). */
    public String origin() {
        return origin;
    }

    public boolean born() {
        return origin != null;
    }

    public long originAt() {
        return originAt;
    }

    public void setOrigin(String id, long at) {
        this.origin = id;
        this.originAt = id == null ? 0 : at;
    }

    /** 능력치 (출신이 없으면 모두 10). */
    public StatBlock stats() {
        return stats;
    }

    public void setStats(StatBlock s) {
        this.stats = s == null ? StatBlock.BASE : s;
    }

    public long souls() {
        return souls;
    }

    public void setSouls(long n) {
        this.souls = Math.max(0, Math.min(SOULS_MAX, n));
    }

    /** 시작 아이템 장부 (5.10): 준 항목 열쇠 (weapon:redin_guard_sword, item:master_key …). */
    public Set<String> given() {
        return Collections.unmodifiableSet(given);
    }

    public boolean wasGiven(String key) {
        return given.contains(key);
    }

    public void markGiven(String key) {
        given.add(key);
    }

    public void clearGiven() {
        given.clear();
    }

    public int settingsSeen() {
        return settingsSeen;
    }

    public void setSettingsSeen(int rev) {
        this.settingsSeen = rev;
    }

    /** 모르는 칸 (시험이 보존을 본다). */
    public JsonElement extra(String key) {
        return raw.get(key);
    }
}
