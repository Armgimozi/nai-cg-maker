package kr.labyrinth.homes.rules;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 집터 권한·지형 잠금 규칙표 (0.3.7, plan §9 · review R4·R21) — 순수 (서버 없이 시험). 소유: 묶음 B.
 * <p>
 * 리스너는 "어디서 (Where) 무엇을 (Act)" 만 정해 {@link #decide} 에 묻는다.
 * <ul>
 *   <li>{@link Verdict#ALLOW}: 막지 않음</li>
 *   <li>{@link Verdict#DENY}: 우리가 막고 글 한 번</li>
 *   <li>{@link Verdict#PASS}: 우리 일이 아님 — 그대로 둔다 (보호 상자 칸은 마을 핸들러(HIGH)가 막고 마을 글을 보냄, 잠금 꺼진 들판은 바닐라)</li>
 * </ul>
 */
public final class PlotRules {

    private PlotRules() {}

    /** 그 사람에게 그 칸은 어디인가. */
    public enum Where {
        /** 내 집 (주인·초대) 높이 창 안. */
        OWN,
        /** 남의 집, 손님 허용 켜짐. */
        GUEST,
        /** 남의 집 (손님 허용 꺼짐) · 빈 집. */
        STRANGER,
        /** 보호 상자 (마을·광산·집 구역 공용 칸). */
        PROTECTED,
        /** 그 밖 (주 월드, 지형 잠금 켜짐) — 높이 창 밖의 내 집 열도 여기. */
        WILD_LOCKED,
        /** 그 밖 (지형 잠금 꺼짐). */
        WILD_OPEN;

        public boolean inPlot() { return this == OWN || this == GUEST || this == STRANGER; }
    }

    /** 무엇을. */
    public enum Act {
        BREAK, PLACE,
        /** deny_place 블록·엔티티 놓기 (TNT·TNT 수레·리스폰 정박기·엔드 수정·발사기). */
        PLACE_BANNED,
        /** 물 양동이 붓기·뜨기 (가루눈·물고기 양동이 포함). */
        BUCKET,
        /** deny_use 쓰기 (용암 양동이·화염구, R21). */
        USE_BANNED,
        /** TNT 점화 · 리스폰 정박기 우클릭 (주 월드 어디서나 막음). */
        PRIME,
        /** 상자류 열기 (BlockState instanceof InventoryHolder — 선반·구리 상자·제작기·발사기 포함). */
        CONTAINER,
        ENDER_CHEST,
        /** 문·다락문·울타리 문. */
        DOOR,
        /** 작업대류·종. */
        WORKSTATION,
        /** 그 밖 블록 우클릭 (버튼·레버·화분·가마솥·퇴비통·모닥불·케이크·초·소리 블록·중계기·비교기·벌통·조각상 …). */
        OTHER_USE,
        /** 블록 좌클릭 (소리 블록 치기 등 — 부수기는 BREAK). */
        LEFT_CLICK,
        /** 압력판·실 밟기. */
        PRESSURE,
        BED,
        /** 밭·거북알 밟기. */
        TRAMPLE,
        /** 걸개 (액자·그림·끈 매듭) 놓기·부수기·쏘기. */
        HANGING,
        /** 거치대 놓기·때리기·부수기. */
        ARMOR_STAND,
        /** 액자 돌리기·꺼내기·넣기 · 거치대 장비 바꾸기 (0.3.7 fix — 잠긴 들판의 옛 것은 상자처럼 늘 됨). */
        DECO_USE,
        /** 보트·수레 놓기·부수기. */
        VEHICLE,
        /** 동물·엔티티 손대기 (때리기·끈·털 깎기·이름표·염색·타기·말/상자 보트 열기·낚싯대 끌기·먹이). */
        ANIMAL,
        /** 엔티티 양동이 담기·끈 (보호 상자 칸에서는 마을 핸들러가 없어 우리가 막음 — R4). */
        ENTITY_GRAB,
        /** 블록 바꾸는 손 도구 (괭이·삽·도끼 벗기기·붓·가위·뼛가루·밀랍·염료 …). */
        TOOL,
        /** 부싯돌로 모닥불·초·차원문 붙이기. */
        IGNITE,
        /** 부싯돌로 아무 데나 불 놓기. */
        FIRE,
        /** 표지판 글 (SignChange · 편집 창). */
        SIGN
    }

    public enum Verdict { ALLOW, DENY, PASS }

    /**
     * @param bypass         크리에이티브 관리자 (labyrinth.admin + CREATIVE)
     * @param graceBreakable 이사 기간이고 그 블록이 사람이 놓은 것 (Nature UNNATURAL · 지속 잎) — 그 밖에서 BREAK 를 풂.
     *                       걸개·거치대·탈것 부수기도 이사 기간이면 이 값을 참으로 넘긴다 (옛 건물의 거치대·액자·수레를 옮기게, 0.3.7 fix)
     */
    public static Verdict decide(Act act, Where where, boolean bypass, boolean graceBreakable) {
        if (act == Act.TRAMPLE) return where == Where.WILD_OPEN ? Verdict.PASS : Verdict.DENY; // 관리자도 (밭은 늘 지킴)
        if (bypass) return Verdict.ALLOW;
        if (act == Act.PRIME) return Verdict.DENY; // 주 월드 어디서나
        return switch (where) {
            case OWN -> switch (act) {
                case PLACE_BANNED, USE_BANNED, FIRE -> Verdict.DENY;
                default -> Verdict.ALLOW;
            };
            case GUEST -> switch (act) {
                case DOOR, WORKSTATION, PRESSURE, ENDER_CHEST -> Verdict.ALLOW;
                default -> Verdict.DENY;
            };
            case STRANGER -> switch (act) {
                case PRESSURE, ENDER_CHEST -> Verdict.ALLOW;
                default -> Verdict.DENY;
            };
            case PROTECTED -> switch (act) {
                // 마을 핸들러가 없는 것만 우리가 막는다 (R4) — 나머지는 마을 HIGH 가 그대로
                case ARMOR_STAND, DECO_USE, VEHICLE, SIGN, ENTITY_GRAB, PLACE_BANNED, USE_BANNED -> Verdict.DENY;
                case PRESSURE -> Verdict.ALLOW;
                default -> Verdict.PASS;
            };
            case WILD_LOCKED -> switch (act) {
                case BREAK, HANGING, ARMOR_STAND, VEHICLE -> graceBreakable ? Verdict.ALLOW : Verdict.DENY; // 놓기는 grace 를 넘기지 않음
                case PLACE, PLACE_BANNED, BUCKET, USE_BANNED, TOOL, IGNITE, FIRE, SIGN -> Verdict.DENY;
                case CONTAINER, ENDER_CHEST, DOOR, WORKSTATION, OTHER_USE, LEFT_CLICK, PRESSURE, BED, DECO_USE -> Verdict.ALLOW; // 옛 건물은 그대로 씀
                default -> Verdict.PASS; // 들판 동물
            };
            case WILD_OPEN -> Verdict.PASS;
        };
    }

    public static boolean denied(Act act, Where where, boolean bypass, boolean graceBreakable) {
        return decide(act, where, bypass, graceBreakable) == Verdict.DENY;
    }

    // ── 블록·아이템 분류 (블록 id 문자열만 — 서버 없이 시험) ───────────────

    private static final Set<String> WORKSTATIONS = Set.of("crafting_table", "stonecutter", "loom", "cartography_table", "smithing_table",
            "grindstone", "fletching_table", "bell");

    /** 우클릭한 블록 → 행동. container = 그 칸의 BlockState 가 InventoryHolder 인가 (엔더 상자는 아님). */
    public static Act blockUse(String block, boolean container) {
        String k = key(block);
        if (k.equals("ender_chest")) return Act.ENDER_CHEST;
        if (k.equals("respawn_anchor")) return Act.PRIME;
        if (container) return Act.CONTAINER;
        if (k.endsWith("_door") || k.endsWith("_trapdoor") || k.endsWith("_fence_gate")) return Act.DOOR;
        if (k.endsWith("_bed")) return Act.BED;
        if (WORKSTATIONS.contains(k)) return Act.WORKSTATION;
        return Act.OTHER_USE;
    }

    /** 밟은 블록 → 행동. */
    public static Act physical(String block) {
        String k = key(block);
        return k.equals("farmland") || k.equals("turtle_egg") || k.equals("sniffer_egg") ? Act.TRAMPLE : Act.PRESSURE;
    }

    /** 부싯돌이 붙일 수 있는 블록 (모닥불·초·차원문 틀) — 내 집에서 이것만 IGNITE, 나머지는 FIRE. */
    public static boolean ignitable(String block) {
        String k = key(block);
        return k.equals("campfire") || k.equals("soul_campfire") || k.equals("candle") || k.endsWith("_candle") || k.endsWith("candle_cake")
                || k.equals("obsidian");
    }

    /**
     * 손에 든 아이템으로 블록을 우클릭 → 행동 (없으면 null = 아이템 쓰기는 상관없음).
     *
     * @param changesBlocks VillageService.changesBlocks(아이템) (괭이·삽·도끼·양동이·염료·뼛가루·밀랍·부싯돌 …)
     */
    public static Act itemUse(String item, String clicked, boolean changesBlocks, List<String> denyUse, List<String> denyPlace) {
        String i = key(item);
        if (i.isEmpty() || i.equals("air")) return null;
        if (denyUse != null && denyUse.contains(i)) return Act.USE_BANNED;
        if (denyPlace != null && denyPlace.contains(i) && ENTITY_ITEMS.contains(i)) return Act.PLACE_BANNED; // 블록은 BlockPlaceEvent 가 봄
        if (i.equals("flint_and_steel") || i.equals("fire_charge")) return ignitable(clicked) ? Act.IGNITE : Act.FIRE;
        if (i.equals("lead") && key(clicked).endsWith("_fence")) return Act.HANGING; // 끈 매듭
        if (i.equals("milk_bucket")) return null; // 마시기
        if (i.equals("potion")) return isDirt(clicked) ? Act.TOOL : null; // 물병 → 진흙만 (마시기는 그대로)
        if (i.equals("armor_stand")) return Act.ARMOR_STAND;
        if (changesBlocks) return Act.TOOL;
        return null;
    }

    /** 엔티티를 만드는 아이템 (deny_place 에 있으면 우클릭 단계에서 막음). */
    private static final Set<String> ENTITY_ITEMS = Set.of("tnt_minecart", "end_crystal", "minecart", "chest_minecart", "hopper_minecart",
            "furnace_minecart", "armor_stand");

    /**
     * 손에 든 것이 블록·엔티티를 놓거나 블록을 바꾸는 아이템인가 — 남의 집에서 블록 쓰기를 막으면 Paper 가 손에 든 것 쓰기도 함께 막아
     * 놓기·양동이 이벤트가 오지 않으므로, 그때 글을 보낼지 (verify 찾은 것 1). 먹기·마시기·던지기는 아님.
     *
     * @param isBlock Material#isBlock (블록 아이템)
     */
    public static boolean worldItem(String item, boolean isBlock, boolean changesBlocks) {
        String i = key(item);
        if (i.isEmpty() || i.equals("air") || i.equals("milk_bucket")) return false;
        if (isBlock || changesBlocks) return true;
        return i.endsWith("_bucket") || i.equals("bucket") || i.endsWith("_boat") || i.endsWith("_raft") || i.endsWith("minecart")
                || i.equals("armor_stand") || i.endsWith("item_frame") || i.equals("painting") || i.endsWith("_spawn_egg") || i.equals("lead")
                || i.endsWith("_seeds") || i.equals("carrot") || i.equals("potato") || i.equals("sweet_berries") || i.equals("glow_berries")
                || i.equals("cocoa_beans") || i.equals("pitcher_pod") || i.equals("redstone") || i.equals("string") || i.equals("end_crystal");
    }

    private static boolean isDirt(String b) {
        String k = key(b);
        return k.equals("dirt") || k.equals("coarse_dirt") || k.equals("rooted_dirt");
    }

    /** "minecraft:OAK_DOOR[half=upper]" → "oak_door". */
    public static String key(String s) {
        if (s == null) return "";
        String k = s.trim().toLowerCase(Locale.ROOT);
        int b = k.indexOf('[');
        if (b >= 0) k = k.substring(0, b);
        int c = k.indexOf(':');
        if (c >= 0) k = k.substring(c + 1);
        return k;
    }

    // ── 자가 진단용 표 (plan §9 그대로 — PlotRulesTest 와 [집터 자가 진단] rules= 가 같이 씀) ─────

    /** 한 줄: 행동 · 어디 · 관리자 · 이사 기간 사람 블록 → 기대. */
    public record Case(Act act, Where where, boolean bypass, boolean grace, Verdict expect) {}

    public static List<Case> table() {
        List<Case> t = new ArrayList<>();
        Verdict A = Verdict.ALLOW, D = Verdict.DENY, P = Verdict.PASS;
        // 부수기·놓기
        t.add(new Case(Act.BREAK, Where.OWN, false, false, A));
        t.add(new Case(Act.PLACE, Where.OWN, false, false, A));
        t.add(new Case(Act.BREAK, Where.GUEST, false, false, D));
        t.add(new Case(Act.PLACE, Where.STRANGER, false, false, D));
        t.add(new Case(Act.BREAK, Where.PROTECTED, false, false, P));
        t.add(new Case(Act.BREAK, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.BREAK, Where.WILD_LOCKED, false, true, A));
        t.add(new Case(Act.PLACE, Where.WILD_LOCKED, false, true, D));
        t.add(new Case(Act.BREAK, Where.WILD_OPEN, false, false, P));
        t.add(new Case(Act.PLACE, Where.WILD_LOCKED, true, false, A));
        // 금지 블록·쓰기
        t.add(new Case(Act.PLACE_BANNED, Where.OWN, false, false, D));
        t.add(new Case(Act.USE_BANNED, Where.OWN, false, false, D));
        t.add(new Case(Act.USE_BANNED, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.USE_BANNED, Where.WILD_OPEN, false, false, P));
        t.add(new Case(Act.PLACE_BANNED, Where.OWN, true, false, A));
        t.add(new Case(Act.PRIME, Where.OWN, false, false, D));
        t.add(new Case(Act.PRIME, Where.WILD_OPEN, false, false, D));
        t.add(new Case(Act.PRIME, Where.WILD_OPEN, true, false, A));
        // 양동이
        t.add(new Case(Act.BUCKET, Where.OWN, false, false, A));
        t.add(new Case(Act.BUCKET, Where.GUEST, false, false, D));
        t.add(new Case(Act.BUCKET, Where.WILD_LOCKED, false, false, D));
        // 상자류
        t.add(new Case(Act.CONTAINER, Where.OWN, false, false, A));
        t.add(new Case(Act.CONTAINER, Where.GUEST, false, false, D));
        t.add(new Case(Act.CONTAINER, Where.PROTECTED, false, false, P));
        t.add(new Case(Act.CONTAINER, Where.WILD_LOCKED, false, false, A));
        t.add(new Case(Act.ENDER_CHEST, Where.STRANGER, false, false, A));
        // 문·작업대·그 밖 우클릭
        t.add(new Case(Act.DOOR, Where.GUEST, false, false, A));
        t.add(new Case(Act.DOOR, Where.STRANGER, false, false, D));
        t.add(new Case(Act.WORKSTATION, Where.GUEST, false, false, A));
        t.add(new Case(Act.WORKSTATION, Where.STRANGER, false, false, D));
        t.add(new Case(Act.OTHER_USE, Where.GUEST, false, false, D));
        t.add(new Case(Act.OTHER_USE, Where.WILD_LOCKED, false, false, A));
        t.add(new Case(Act.LEFT_CLICK, Where.GUEST, false, false, D));
        t.add(new Case(Act.PRESSURE, Where.STRANGER, false, false, A));
        t.add(new Case(Act.BED, Where.GUEST, false, false, D));
        t.add(new Case(Act.BED, Where.WILD_LOCKED, false, false, A));
        // 밟기
        t.add(new Case(Act.TRAMPLE, Where.OWN, false, false, D));
        t.add(new Case(Act.TRAMPLE, Where.OWN, true, false, D));
        t.add(new Case(Act.TRAMPLE, Where.WILD_OPEN, false, false, P));
        // 걸개·거치대·탈것·동물
        t.add(new Case(Act.HANGING, Where.OWN, false, false, A));
        t.add(new Case(Act.HANGING, Where.GUEST, false, false, D));
        t.add(new Case(Act.HANGING, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.HANGING, Where.WILD_LOCKED, false, true, A));
        t.add(new Case(Act.ARMOR_STAND, Where.WILD_LOCKED, false, true, A));
        t.add(new Case(Act.VEHICLE, Where.WILD_LOCKED, false, true, A));
        t.add(new Case(Act.DECO_USE, Where.WILD_LOCKED, false, false, A));
        t.add(new Case(Act.DECO_USE, Where.GUEST, false, false, D));
        t.add(new Case(Act.DECO_USE, Where.OWN, false, false, A));
        t.add(new Case(Act.DECO_USE, Where.PROTECTED, false, false, D));
        t.add(new Case(Act.ARMOR_STAND, Where.PROTECTED, false, false, D));
        t.add(new Case(Act.VEHICLE, Where.PROTECTED, false, false, D));
        t.add(new Case(Act.VEHICLE, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.ANIMAL, Where.STRANGER, false, false, D));
        t.add(new Case(Act.ANIMAL, Where.OWN, false, false, A));
        t.add(new Case(Act.ANIMAL, Where.WILD_LOCKED, false, false, P));
        t.add(new Case(Act.ENTITY_GRAB, Where.PROTECTED, false, false, D));
        // 도구·불·표지판
        t.add(new Case(Act.TOOL, Where.OWN, false, false, A));
        t.add(new Case(Act.TOOL, Where.GUEST, false, false, D));
        t.add(new Case(Act.TOOL, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.IGNITE, Where.OWN, false, false, A));
        t.add(new Case(Act.FIRE, Where.OWN, false, false, D));
        t.add(new Case(Act.SIGN, Where.OWN, false, false, A));
        t.add(new Case(Act.SIGN, Where.PROTECTED, false, false, D));
        t.add(new Case(Act.SIGN, Where.WILD_LOCKED, false, false, D));
        t.add(new Case(Act.SIGN, Where.WILD_OPEN, false, false, P));
        return t;
    }

    /** 표를 돌려 [맞은 수, 전체]. */
    public static int[] selfCheck() {
        int ok = 0;
        List<Case> t = table();
        for (Case c : t) if (decide(c.act(), c.where(), c.bypass(), c.grace()) == c.expect()) ok++;
        return new int[] {ok, t.size()};
    }
}
