package kr.labyrinth.items.weaponskills;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import kr.labyrinth.classes.LabyrinthStatusEffectService;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 피해 종류 꼬리표 (combat_spec §4) — 직업 스킬 24개(classes.yml kind)와 무기 스킬 전부(데이터에서 {@link SkillKinds} 로 계산)가
 * 명세 JSON {@code skill_kinds} (+ 0.3.5 P3 content_p3.json · 0.3.7 mythic_037.json {@code skill_kinds}) 와 같다. 실제 피해(SkillCast·MechanicsEngine·SkillContext)가 같은 규칙을 쓴다.
 */
class SkillKindTagsTest {

    static Content content;
    static JsonObject kinds;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        kinds = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/combat_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("skill_kinds");
        // 0.3.5 P3 (tools/data/035/content_p3.json skill_kinds): 새 무기·B1 활·B2 무기·영웅 올림 스킬 + gear_spec A8 종류 바뀜이 위에 덮인다
        JsonObject p3 = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/content_p3.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("skill_kinds");
        JsonObject weapon = kinds.getAsJsonObject("weapon_skills");
        for (String k : p3.keySet()) weapon.add(k, p3.get(k));
        // 0.3.7 새 신화 6 (tools/data/037/mythic_037.json skill_kinds)
        JsonObject m37 = JsonParser.parseString(Files.readString(Path.of("../tools/data/037/mythic_037.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("skill_kinds");
        for (String k : m37.keySet()) weapon.add(k, m37.get(k));
    }

    @Test
    void classSkillKindsMatchSpec() {
        JsonObject spec = kinds.getAsJsonObject("class_skills");
        int n = 0;
        for (ClassDef c : content.classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) {
                assertTrue(spec.has(s.id()), s.id());
                assertEquals(spec.get(s.id()).getAsString(), s.kind(), c.id() + ":" + s.id());
                n++;
            }
        }
        assertEquals(24, n);
        assertEquals(spec.size(), n);
    }

    @Test
    void classSkillKindDrivesDamageKind() {
        ClassDef.SkillDef phys = content.classDef("guardian").skillByInput("SWAP");
        ClassDef.SkillDef magic = content.classDef("arcanist").skillByInput("SWAP");
        assertEquals(DamageKind.PHYSICAL, SkillContext.kindOf(phys, DamageType.MELEE));
        assertEquals(DamageKind.MAGIC, SkillContext.kindOf(magic, DamageType.MAGIC));
        // 데이터가 유형과 달라도 데이터가 이긴다, 비우면 유형에서
        assertEquals(DamageKind.MAGIC, SkillContext.kindOf(magic, DamageType.MELEE));
        ClassDef.SkillDef blank = new ClassDef.SkillDef("x", "x", "SWAP", 1, 0, 1, Params.EMPTY, "");
        assertEquals(DamageKind.PHYSICAL, SkillContext.kindOf(blank, DamageType.RANGED));
        assertEquals(DamageKind.MAGIC, SkillContext.kindOf(blank, DamageType.MAGIC));
    }

    @Test
    void weaponSkillKindsMatchSpec() {
        JsonObject spec = kinds.getAsJsonObject("weapon_skills");
        List<String> wrong = new ArrayList<>();
        int n = 0;
        for (ItemDef d : content.items().values()) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                String key = d.id() + ":" + s.input();
                if (!spec.has(key)) {
                    wrong.add(key + " 명세에 없음");
                    continue;
                }
                String got = SkillKinds.tag(d, s);
                if (!spec.get(key).getAsString().equals(got)) wrong.add(key + " " + got + " ≠ " + spec.get(key).getAsString());
                n++;
            }
        }
        assertEquals(List.of(), wrong);
        assertTrue(n >= 137, "무기 스킬 " + n);
    }

    @Test
    void statusDotKindsMatchSpec() {
        JsonObject spec = kinds.getAsJsonObject("status");
        for (String id : spec.keySet()) {
            String want = spec.get(id).getAsString();
            if (want.startsWith("none")) continue; // 서리 = 둔화·빙결만
            assertEquals(want, LabyrinthStatusEffectService.dotKind(id).name().toLowerCase(Locale.ROOT), id);
        }
    }

    @Test
    void hitAndEffectKindRules() {
        // damage_type → 구현 기본 → 무기 attack.kind
        assertEquals(DamageKind.PHYSICAL, SkillKinds.hitKind("missile", Params.EMPTY, DamageKind.PHYSICAL));
        assertEquals(DamageKind.MAGIC, SkillKinds.hitKind("missile", Params.EMPTY, DamageKind.MAGIC), "지능 활의 화살 스킬 = 마법");
        assertEquals(DamageKind.MAGIC, SkillKinds.hitKind("beam", Params.EMPTY, DamageKind.PHYSICAL));
        assertEquals(DamageKind.PHYSICAL, SkillKinds.hitKind("slash_wave", Params.EMPTY, DamageKind.MAGIC));
        assertEquals(DamageKind.MAGIC, SkillKinds.hitKind("slash_wave", Params.of(Map.of("damage_type", "magic")), DamageKind.PHYSICAL));
        assertEquals(DamageKind.HYBRID, SkillKinds.hitKind("missile", Params.of(Map.of("damage_type", "hybrid")), DamageKind.PHYSICAL));
        assertEquals(DamageKind.FIXED, SkillKinds.ofType("true", DamageKind.PHYSICAL));
        // 조합형: magic: true · lightning 마법, percent 고정, 그 밖 무기 종류
        assertEquals(DamageKind.MAGIC, SkillKinds.effectKind(new MechanicsSpec.Effect("damage", Params.of(Map.of("amount", 1.0, "magic", true))), DamageKind.PHYSICAL));
        assertEquals(DamageKind.MAGIC, SkillKinds.effectKind(new MechanicsSpec.Effect("lightning", Params.of(Map.of("amount", 1.0))), DamageKind.PHYSICAL));
        assertEquals(DamageKind.FIXED, SkillKinds.effectKind(new MechanicsSpec.Effect("percent", Params.of(Map.of("amount", 0.1))), DamageKind.PHYSICAL));
        assertEquals(DamageKind.MAGIC, SkillKinds.effectKind(new MechanicsSpec.Effect("damage", Params.of(Map.of("amount", 1.0))), DamageKind.MAGIC));
        assertEquals(DamageKind.PHYSICAL, SkillKinds.effectKind(new MechanicsSpec.Effect("damage",
                Params.of(Map.of("amount", 1.0, "damage_type", "melee"))), DamageKind.MAGIC));
        assertEquals("hybrid", SkillKinds.tag(java.util.Set.of("physical", "magic", "fixed")));
        assertEquals("fixed", SkillKinds.tag(java.util.Set.of("fixed")));
        assertEquals("none", SkillKinds.tag(java.util.Set.of()));
    }

    @Test
    void defaultDamageTypeFollowsAttackStyle() {
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            DamageType t = LabWeaponSkillService.defaultType("mechanics", d);
            DamageType want = switch (d.attack().style()) {
                case RANGED -> DamageType.RANGED;
                case CASTER -> DamageType.MAGIC;
                case MELEE -> DamageType.MELEE;
            };
            assertEquals(want, t, d.id());
        }
    }
}
