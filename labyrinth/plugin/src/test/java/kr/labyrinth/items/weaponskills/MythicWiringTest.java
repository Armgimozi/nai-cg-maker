package kr.labyrinth.items.weaponskills;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.AuraDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.UniqueCatalog;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 신화 무기 연결 (0.3.7 myth-037 — 직업마다 둘, 12개): 번들 items.yml 의 신화 무기마다
 * <ul>
 *   <li>고유 효과가 있고 UniqueCatalog.check 오류·경고 0 (방패 강타 n = bashN — 간격에 맞는 타수).</li>
 *   <li>조합형 스킬 MechanicsSpec.parse 문제 0, display 는 fx.yml models 에 있다.</li>
 *   <li>aura 는 fx.yml auras 에 있고 tier mythic.</li>
 *   <li>스킬 pvp_mult 가 명세 값과 같다 (적지 않은 칸 = 1.0). 모르는 신화 무기가 생기면 실패 — 명세에 먼저 적을 것.</li>
 * </ul>
 * 새 6개(D 데이터 · M 모델)가 들어오기 전에는 있는 것만 본다. 들어오지 않은 id 는 출력에 남긴다.
 */
class MythicWiringTest {

    /** 명세 (final_spec §6 · 기존 신화는 지금 값 그대로): 무기 → 입력 → pvp_mult (빠진 입력 = 1.0). */
    static final Map<String, Map<String, Double>> PVP = Map.ofEntries(
            Map.entry("celestial_oathkeeper", Map.of("RIGHT", 0.8, "SNEAK_LEFT", 0.7)),
            Map.entry("mountainheart_maul", Map.of("RIGHT", 0.65, "SNEAK_RIGHT", 0.4)),
            Map.entry("bloodmoon_reaver", Map.of("RIGHT", 0.7, "SNEAK_RIGHT", 0.4)),
            Map.entry("hightide_scythe", Map.of("RIGHT", 0.85, "SNEAK_LEFT", 0.45, "SNEAK_RIGHT", 0.45)),
            Map.entry("tempest_bow", Map.of("SNEAK_LEFT", 0.2, "SNEAK_RIGHT", 0.85)),
            Map.entry("comet_longbow", Map.of()),
            Map.entry("voidheart_staff", Map.of("RIGHT", 0.55, "SNEAK_RIGHT", 0.35)),
            Map.entry("wisp_lantern", Map.of("RIGHT", 0.4, "SNEAK_RIGHT", 0.1)),
            Map.entry("seraph_scepter", Map.of()),
            Map.entry("daybreak_bell", Map.of("SNEAK_RIGHT", 0.45)),
            Map.entry("eclipse_blade", Map.of("SNEAK_RIGHT", 0.85)),
            Map.entry("waning_moon_sickle", Map.of("SNEAK_LEFT", 0.9, "SNEAK_RIGHT", 0.45)));

    static Content content;
    static List<ItemDef> mythics;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        mythics = new ArrayList<>();
        for (ItemDef d : content.items().values()) if (d.isWeapon() && d.rarity() == Rarity.MYTHIC) mythics.add(d);
        List<String> missing = new ArrayList<>();
        for (String id : PVP.keySet()) if (content.item(id) == null) missing.add(id);
        System.out.println("[신화 연결] 번들 신화 무기 " + mythics.size() + "개" + (missing.isEmpty() ? "" : " · 아직 없음 " + missing));
        assertTrue(mythics.size() >= 6, "신화 무기 " + mythics.size());
    }

    @Test
    void everyMythicIsInTheSpec() {
        List<String> unknown = new ArrayList<>();
        for (ItemDef d : mythics) if (!PVP.containsKey(d.id())) unknown.add(d.id());
        assertEquals(List.of(), unknown, "명세에 없는 신화 무기");
        assertTrue(mythics.size() <= PVP.size());
    }

    @Test
    void uniqueChecksClean() {
        List<String> bad = new ArrayList<>();
        for (ItemDef d : mythics) {
            if (d.unique() == null) {
                bad.add(d.id() + ": 고유 효과 없음");
                continue;
            }
            UniqueCatalog.Check ch = UniqueCatalog.check(d.unique(), d.attack());
            for (String e : ch.errors()) bad.add(d.id() + " 오류: " + e);
            for (String w : ch.warnings()) bad.add(d.id() + " 경고: " + w);
            if ("bash_stun".equals(d.unique().id())) {
                int n = (int) d.unique().num("n");
                int n4 = UniqueCatalog.bashN(4, d.attack().interval()), n5 = UniqueCatalog.bashN(5, d.attack().interval());
                if (n != n4 && n != n5) bad.add(d.id() + ": bash_stun n " + n + " ≠ bashN " + n4 + "/" + n5);
            }
        }
        assertEquals(List.of(), bad);
    }

    @Test
    void mechanicsParseAndDisplaysExist() {
        List<String> bad = new ArrayList<>();
        for (ItemDef d : mythics) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                if (!"mechanics".equals(s.id())) continue;
                Object raw = s.params().get("mechanics");
                assertNotNull(raw, d.id() + " " + s.input());
                MechanicsSpec.Result r = MechanicsSpec.parse(raw);
                for (String p : r.problems()) bad.add(d.id() + " " + s.input() + ": " + p);
                for (String fx : r.displays()) if (!content.fxModels().containsKey(fx)) bad.add(d.id() + " " + s.input() + ": fx.yml models 에 없는 display " + fx);
            }
        }
        assertEquals(List.of(), bad);
    }

    @Test
    void auraIsAMythicAura() {
        List<String> bad = new ArrayList<>();
        for (ItemDef d : mythics) {
            AuraDef a = d.aura() == null ? null : content.auras().get(d.aura());
            if (a == null) bad.add(d.id() + ": fx.yml auras 에 없는 aura " + d.aura());
            else if (!"mythic".equals(a.tier())) bad.add(d.id() + ": aura " + a.id() + " tier " + a.tier());
        }
        assertEquals(List.of(), bad);
    }

    @Test
    void noticeLinesUseTheDropBroadcastShape() {
        ItemDef d = mythics.get(0);
        String drop = "미궁 » 홍길동 님이 [신화] " + d.name() + " 을(를) 얻었습니다!";
        String bp = kr.labyrinth.core.Text.plain(kr.labyrinth.core.Text.mm(
                kr.labyrinth.items.loot.LabLootService.mythicBlueprintLine("홍길동", d)));
        String craft = kr.labyrinth.core.Text.plain(kr.labyrinth.core.Text.mm(
                kr.labyrinth.items.crafting.LabCraftingService.mythicCraftLine("홍길동", d)));
        assertEquals(drop.replace("[신화] ", "[신화] 도안: "), bp, "신화 도안 파티 알림");
        assertEquals(drop.replace("님이 ", "님이 대장간에서 ").replace("얻었습니다", "만들었습니다"), craft, "신화 제작 방송");
        // 이름에 MiniMessage 꼬리표가 있어도 글이 깨지지 않는다
        String odd = kr.labyrinth.core.Text.plain(kr.labyrinth.core.Text.mm(
                kr.labyrinth.items.crafting.LabCraftingService.mythicCraftLine("<red>x", d)));
        assertTrue(odd.contains("<red>x 님이"), odd);
    }

    @Test
    void pvpMultMatchesTheSpec() {
        List<String> bad = new ArrayList<>();
        for (ItemDef d : mythics) {
            Map<String, Double> want = PVP.getOrDefault(d.id(), Map.of());
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                double w = want.getOrDefault(s.input(), 1.0);
                if (Math.abs(w - s.pvpMult()) > 1e-9) bad.add(d.id() + ":" + s.input() + " pvp_mult " + s.pvpMult() + " (명세 " + w + ")");
            }
            for (String in : want.keySet()) {
                if (d.weaponSkills().stream().noneMatch(s -> s.input().equals(in))) bad.add(d.id() + ":" + in + " 스킬이 없음");
            }
        }
        assertEquals(List.of(), bad);
    }

    /** 새 신화 6 (0.3.7): 노린 곳(at: aim)은 블록 시선이라 몹을 노리면 그 뒤 바닥에 깔린다 — 장판·낙인은 at: target (적이 없으면 노린 곳). */
    static final List<String> NEW6 = List.of("mountainheart_maul", "hightide_scythe", "comet_longbow", "wisp_lantern", "daybreak_bell",
            "waning_moon_sickle");

    @Test
    void newMythicsDoNotAimAtBlocks() {
        List<String> bad = new ArrayList<>();
        for (String id : NEW6) {
            ItemDef d = content.item(id);
            if (d == null) continue;
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                Object raw = s.params().get("mechanics");
                if (raw != null && String.valueOf(raw).contains("at=aim")) bad.add(id + ":" + s.input() + " " + s.name());
            }
        }
        assertEquals(List.of(), bad);
        ItemDef wisp = content.item("wisp_lantern");
        if (wisp != null) {
            String zone = String.valueOf(wisp.weaponSkills().stream().filter(s -> s.input().equals("SNEAK_LEFT")).findFirst().orElseThrow()
                    .params().get("mechanics"));
            assertTrue(zone.contains("at=target"), "홀림불 at: target — " + zone);
        }
    }
}
