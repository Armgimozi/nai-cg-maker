package kr.souls.data;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import kr.souls.progression.StatBlock;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * 플레이어 프로필 (5.10, 12.6): 플레이어 PDC souls:profile 의 판 번호가 붙은 JSON.
 * {"v":1,"origin":"knight","originAt":…,"stats":{"vig":15,…},"souls":0,"kit":{"given":["weapon:redin_guard_sword"]},"settingsSeen":1,
 *  "repicked":true,"rings":["test_stamina",null]} (repicked: 휴식 창의 "출신 다시 고르기" 를 썼다. 없으면 거짓. rings: 낀 반지 id,
 *  칸마다 하나 (인벤토리 2×2 자리의 왼쪽 위·왼쪽 아래 칸, 9.4). 끼지 않은 칸은 null, 반지가 하나도 없으면 칸을 쓰지 않는다.
 *  반지 칸의 정본은 이것이다: 칸에 보이는 아이템은 item/RingSlots 가 여기서 다시 만든 사본)
 * 레벨은 적지 않고 능력치로 셈한다. 모르는 칸은 지우지 않고 그대로 둔다 (다음 판이 더한 칸을 옛 플러그인이 지우지 않게).
 * 순수 클래스 (Gson 만, 13.1 의 ProfileJsonTest).
 */
public final class Profile {
    public static final int VERSION = 1;
    /** 소울 지갑의 끝 (5.10) */
    public static final long SOULS_MAX = 999_999_999L;
    /** 반지 칸 수 (9.4, 2026-10-08 사용자 결정 B 안: 인벤토리 2×2 의 왼쪽 세로 두 칸. 셋째 칸은 나중) */
    public static final int RING_SLOTS = 2;
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private final JsonObject raw;
    private String origin;
    private long originAt;
    private StatBlock stats;
    private long souls;
    private final Set<String> given = new LinkedHashSet<>();
    private int settingsSeen;
    private boolean repicked;
    private final String[] rings = new String[RING_SLOTS];

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
        JsonElement rp = o.get("repicked");
        p.repicked = rp != null && rp.isJsonPrimitive() && rp.getAsJsonPrimitive().isBoolean() && rp.getAsBoolean();
        if (o.has("rings") && o.get("rings").isJsonArray()) {
            JsonArray a = o.getAsJsonArray("rings");
            for (int i = 0; i < Math.min(a.size(), RING_SLOTS); i++) {
                JsonElement e = a.get(i);
                p.rings[i] = e != null && e.isJsonPrimitive() && !e.getAsString().isBlank() ? e.getAsString() : null;
            }
        }
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
        if (repicked) o.addProperty("repicked", true);
        else o.remove("repicked");
        // 반지: 이 판의 칸 (RING_SLOTS) 만 고치고, 뒤의 판이 더한 칸 (셋째 칸) 은 그대로 둔다
        JsonArray old = o.has("rings") && o.get("rings").isJsonArray() ? o.getAsJsonArray("rings") : new JsonArray();
        JsonArray ra = new JsonArray();
        boolean any = false;
        for (int i = 0; i < Math.max(RING_SLOTS, old.size()); i++) {
            String r = i < RING_SLOTS ? rings[i] : null;
            JsonElement e = i < RING_SLOTS ? (r == null ? JsonNull.INSTANCE : new com.google.gson.JsonPrimitive(r)) : old.get(i);
            any |= e != null && !e.isJsonNull();
            ra.add(e == null ? JsonNull.INSTANCE : e);
        }
        if (any) o.add("rings", ra);
        else o.remove("rings");
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

    /** 휴식 창의 "출신 다시 고르기" 를 이미 썼나 (한 번만, 검토 repick-not-once). */
    public boolean repicked() {
        return repicked;
    }

    public void setRepicked(boolean v) {
        this.repicked = v;
    }

    /** 반지 칸 i (0 = 왼쪽 위, 1 = 왼쪽 아래) 에 낀 반지 id, 없으면 null. */
    public String ring(int i) {
        return i >= 0 && i < RING_SLOTS ? rings[i] : null;
    }

    public void setRing(int i, String id) {
        if (i >= 0 && i < RING_SLOTS) rings[i] = id == null || id.isBlank() ? null : id;
    }

    /** 낀 반지가 하나라도 있나. */
    public boolean hasRings() {
        for (String r : rings) if (r != null) return true;
        return false;
    }

    /** 모르는 칸 (시험이 보존을 본다). */
    public JsonElement extra(String key) {
        return raw.get(key);
    }
}
