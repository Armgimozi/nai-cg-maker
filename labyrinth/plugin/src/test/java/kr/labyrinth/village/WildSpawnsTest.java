package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.EnumSet;
import java.util.Set;
import kr.labyrinth.core.Settings.Wild.Spawns;
import org.bukkit.entity.SpawnCategory;
import org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason;
import org.bukkit.event.entity.EntityTransformEvent.TransformReason;
import org.junit.jupiter.api.Test;

/** 마을 월드 스폰 규칙 (config wild.spawns, 0.3.5.1) — SpawnReason 전부를 하나씩 정했는지, 모드 범위, 있던 몹 치우기. */
class WildSpawnsTest {

    /** 바닐라 세계가 스스로 만드는 몹 — 막는다. 이 목록이 바뀌면 일부러 바꾼 것이어야 한다. */
    static final Set<SpawnReason> WILD = EnumSet.of(SpawnReason.NATURAL, SpawnReason.CHUNK_GEN, SpawnReason.JOCKEY, SpawnReason.OCELOT_BABY,
            SpawnReason.SPAWNER, SpawnReason.TRIAL_SPAWNER, SpawnReason.OMINOUS_ITEM_SPAWNER, SpawnReason.PATROL, SpawnReason.RAID,
            SpawnReason.VILLAGE_INVASION, SpawnReason.VILLAGE_DEFENSE, SpawnReason.REINFORCEMENTS, SpawnReason.TRAP, SpawnReason.LIGHTNING,
            SpawnReason.SILVERFISH_BLOCK, SpawnReason.ENDER_PEARL, SpawnReason.NETHER_PORTAL, SpawnReason.SPELL,
            SpawnReason.DROWNED, SpawnReason.FROZEN, SpawnReason.INFECTION, SpawnReason.PIGLIN_ZOMBIFIED, SpawnReason.BUILD_WITHER,
            SpawnReason.DEFAULT);

    /** 이미 있는 몹이 바뀜 — 막으면 원래 몹이 사라지므로 허용. */
    static final Set<SpawnReason> KEEP = EnumSet.of(SpawnReason.CURED, SpawnReason.SHEARED, SpawnReason.METAMORPHOSIS, SpawnReason.SLIME_SPLIT);

    @Test
    void everyReasonIsDecidedWithAReason() {
        assertEquals(47, SpawnReason.values().length, "Paper API 의 SpawnReason 수가 바뀜 — WildSpawns.classify 를 다시 볼 것");
        for (SpawnReason r : SpawnReason.values()) {
            WildSpawns.Rule rule = WildSpawns.rule(r);
            assertNotNull(rule, r.name());
            assertFalse(rule.why().isBlank(), r.name());
            WildSpawns.Verdict expect = WILD.contains(r) ? WildSpawns.Verdict.WILD
                    : KEEP.contains(r) ? WildSpawns.Verdict.KEEP_SOURCE : WildSpawns.Verdict.ACTION;
            assertEquals(expect, rule.verdict(), r.name());
        }
    }

    @Test
    void playerAndPluginActionsAreAllowed() {
        for (SpawnReason r : new SpawnReason[] {SpawnReason.CUSTOM, SpawnReason.COMMAND, SpawnReason.SPAWNER_EGG, SpawnReason.DISPENSE_EGG,
                SpawnReason.BREEDING, SpawnReason.EGG, SpawnReason.BUCKET, SpawnReason.BEEHIVE, SpawnReason.SHOULDER_ENTITY, SpawnReason.CURED,
                SpawnReason.DUPLICATION, SpawnReason.BUILD_IRONGOLEM, SpawnReason.BUILD_SNOWMAN, SpawnReason.BUILD_COPPERGOLEM,
                SpawnReason.MOUNT, SpawnReason.REANIMATE, SpawnReason.REHYDRATION, SpawnReason.POTION_EFFECT}) {
            for (Spawns mode : Spawns.values()) {
                assertFalse(WildSpawns.blockSpawn(mode, r, true, true), mode + " " + r + " 적대");
                assertFalse(WildSpawns.blockSpawn(mode, r, true, false), mode + " " + r + " 동물");
            }
        }
    }

    @Test
    void modesScopeTheBlock() {
        // all: 적대 + 동물 · monsters: 적대만 · none: 아무것도
        assertTrue(WildSpawns.blockSpawn(Spawns.ALL, SpawnReason.NATURAL, true, true));
        assertTrue(WildSpawns.blockSpawn(Spawns.ALL, SpawnReason.NATURAL, true, false), "동물·물고기·떠돌이 상인");
        assertTrue(WildSpawns.blockSpawn(Spawns.MONSTERS, SpawnReason.NATURAL, true, true));
        assertFalse(WildSpawns.blockSpawn(Spawns.MONSTERS, SpawnReason.NATURAL, true, false), "monsters 는 동물을 두고");
        assertTrue(WildSpawns.blockSpawn(Spawns.MONSTERS, SpawnReason.CHUNK_GEN, true, true));
        assertFalse(WildSpawns.blockSpawn(Spawns.MONSTERS, SpawnReason.CHUNK_GEN, true, false), "새 청크의 동물");
        for (SpawnReason r : SpawnReason.values()) {
            assertFalse(WildSpawns.blockSpawn(Spawns.NONE, r, true, true), "none " + r);
            // 몹이 아닌 것 (갑옷 거치대 · NPC 마네킹) 은 어떤 모드에서도
            assertFalse(WildSpawns.blockSpawn(Spawns.ALL, r, false, false), "마네킹 " + r);
            assertFalse(WildSpawns.blockSpawn(Spawns.MONSTERS, r, false, false), "마네킹 " + r);
        }
        assertFalse(WildSpawns.blockSpawn(null, SpawnReason.NATURAL, true, true));
        // 이유를 모르면 DEFAULT 로 (바닐라)
        assertEquals(WildSpawns.rule(SpawnReason.DEFAULT), WildSpawns.rule(null));
    }

    @Test
    void naturalTransformsAreBlockedNotPlayerOnes() {
        for (TransformReason r : TransformReason.values()) WildSpawns.naturalTransform(r); // 전부 정해져 있다 (switch 에 default 없음)
        assertTrue(WildSpawns.blockTransform(Spawns.MONSTERS, TransformReason.LIGHTNING, true, true), "돼지 → 좀비 피글린");
        assertTrue(WildSpawns.blockTransform(Spawns.MONSTERS, TransformReason.DROWNED, true, true));
        assertTrue(WildSpawns.blockTransform(Spawns.MONSTERS, TransformReason.FROZEN, true, true));
        assertTrue(WildSpawns.blockTransform(Spawns.MONSTERS, TransformReason.PIGLIN_ZOMBIFIED, true, true));
        assertTrue(WildSpawns.blockTransform(Spawns.MONSTERS, TransformReason.INFECTION, true, true));
        assertFalse(WildSpawns.blockTransform(Spawns.NONE, TransformReason.LIGHTNING, true, true));
        // 플레이어가 하는 변신 · 원래 몹이 사라지지 않게 두는 변신
        for (TransformReason r : new TransformReason[] {TransformReason.CURED, TransformReason.SHEARED, TransformReason.METAMORPHOSIS,
                TransformReason.SPLIT, TransformReason.UNKNOWN}) {
            assertFalse(WildSpawns.blockTransform(Spawns.ALL, r, true, true), r.name());
        }
        assertFalse(WildSpawns.naturalTransform(null));
    }

    static WildSpawns.Existing natural(boolean enemy) {
        return new WildSpawns.Existing(enemy, false, false, false, false, false, false, false, SpawnReason.NATURAL);
    }

    @Test
    void existingVanillaHostilesAreSweptButNotAnimalsOrKeptMobs() {
        assertTrue(WildSpawns.removeExisting(Spawns.ALL, natural(true)));
        assertTrue(WildSpawns.removeExisting(Spawns.MONSTERS, natural(true)));
        assertFalse(WildSpawns.removeExisting(Spawns.NONE, natural(true)));
        assertFalse(WildSpawns.removeExisting(Spawns.ALL, natural(false)), "있던 동물은 그대로");
        assertFalse(WildSpawns.removeExisting(null, natural(true)));
        // 두는 몹: 보스 · 이름표 · 길들임 · 끈 · 사라지지 않음 · 플러그인 · 플레이어가 탄/태운
        WildSpawns.Existing[] keep = {
            new WildSpawns.Existing(true, true, false, false, false, false, false, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, true, false, false, false, false, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, false, true, false, false, false, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, false, false, true, false, false, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, false, false, false, true, false, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, false, false, false, false, true, false, SpawnReason.NATURAL),
            new WildSpawns.Existing(true, false, false, false, false, false, false, true, SpawnReason.NATURAL),
        };
        for (WildSpawns.Existing e : keep) assertFalse(WildSpawns.removeExisting(Spawns.ALL, e), e.toString());
        // 플레이어 쪽 이유로 들어온 적대 몹 (스폰 알 · 명령 · 플러그인) 은 그대로, 이유를 모르는(옛 청크) 몹은 바닐라로 보고 치움
        for (SpawnReason r : new SpawnReason[] {SpawnReason.SPAWNER_EGG, SpawnReason.COMMAND, SpawnReason.CUSTOM, SpawnReason.CURED}) {
            assertFalse(WildSpawns.removeExisting(Spawns.ALL, new WildSpawns.Existing(true, false, false, false, false, false, false, false, r)), r.name());
        }
        assertTrue(WildSpawns.removeExisting(Spawns.ALL, new WildSpawns.Existing(true, false, false, false, false, false, false, false, null)));
        assertTrue(WildSpawns.removeExisting(Spawns.ALL, new WildSpawns.Existing(true, false, false, false, false, false, false, false,
                SpawnReason.SPAWNER)));
    }

    @Test
    void oldVillageBlockStaysAsBefore() {
        // village.block_mob_spawns (0.3.0~): 적대 NATURAL · PATROL · REINFORCEMENTS 만
        for (SpawnReason r : SpawnReason.values()) {
            boolean old = r == SpawnReason.NATURAL || r == SpawnReason.PATROL || r == SpawnReason.REINFORCEMENTS;
            assertEquals(old, WildSpawns.oldVillageBlock(r, true), r.name());
            assertFalse(WildSpawns.oldVillageBlock(r, false), r.name());
            // wild.spawns monsters·all 은 예전 막기를 모두 덮는다
            if (old) assertTrue(WildSpawns.blockSpawn(Spawns.MONSTERS, r, true, true), r.name());
        }
    }

    @Test
    void spawnLimitCategoriesFollowTheMode() {
        // 성능용 상한 0: all = 자연 스폰 분류 전부, monsters = MONSTER 만, none = 없음. MISC 는 바닐라가 상한을 받지 않음
        assertEquals(8, SpawnCategory.values().length, "Paper API 의 SpawnCategory 수가 바뀜 — WildSpawns.limitCategory 를 다시 볼 것");
        for (SpawnCategory c : SpawnCategory.values()) {
            assertFalse(WildSpawns.limitCategory(Spawns.NONE, c), c.name());
            assertFalse(WildSpawns.limitCategory(null, c), c.name());
            assertEquals(c != SpawnCategory.MISC, WildSpawns.limitCategory(Spawns.ALL, c), c.name());
            assertEquals(c == SpawnCategory.MONSTER, WildSpawns.limitCategory(Spawns.MONSTERS, c), c.name());
        }
    }
}
