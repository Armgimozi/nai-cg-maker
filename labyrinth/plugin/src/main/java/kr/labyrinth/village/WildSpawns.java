package kr.labyrinth.village;

import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.core.Settings;
import org.bukkit.entity.SpawnCategory;
import org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason;
import org.bukkit.event.entity.EntityTransformEvent.TransformReason;

/**
 * 마을 월드 스폰 규칙 (config wild.spawns, 0.3.5.1) — 순수 함수 (테스트: WildSpawnsTest).
 * <p>
 * Paper 26.3 API(build 181) 의 SpawnReason 47가지를 <b>하나씩</b> 정한다 (switch 에 default 가 없어 새 이유가 생기면 컴파일이 깨진다 —
 * 실수로 '그냥 허용'되는 일이 없게). 이유마다 한 줄 설명은 서버 jar 의 실제 호출 자리(javap)를 보고 적었다.
 * <ul>
 *   <li>{@link Verdict#WILD} — 바닐라 세계가 스스로 만드는 몹: 막는다 (모드 범위 안의 몹일 때만).</li>
 *   <li>{@link Verdict#ACTION} — 플레이어·관리자·플러그인이 일부러 만든 것, 이미 있는 동물의 새끼: 막지 않는다.</li>
 *   <li>{@link Verdict#KEEP_SOURCE} — 이미 있는 몹이 바뀌는 것 (치료·털 깎기·올챙이 자람·슬라임 나뉨):
 *       Paper 는 바뀐 몹의 스폰을 막아도 원래 몹을 지우므로(Mob#convertTo) 막지 않는다.
 *       자연이 일으키는 변신(번개·익사·얼음·좀비화·감염)은 {@link #blockTransform} 이 변신 자체를 막아 원래 몹이 그대로 남는다.</li>
 * </ul>
 * 범위: monsters = 적대(Enemy)만, all = 모든 몹(Mob — 동물·물고기·박쥐·떠돌이 상인·라마·팬텀·슬라임 …). 갑옷 거치대·마네킹(NPC)·
 * 디스플레이는 몹이 아니라 범위 밖이고, 플러그인 몹은 CUSTOM 이라 언제나 허용 (그 위에 태그 검사도 따로 한다).
 */
public final class WildSpawns {

    private WildSpawns() {}

    public enum Verdict { WILD, ACTION, KEEP_SOURCE }

    /** 이유 하나의 판정 + 한 줄 설명 (/labadmin wild reasons). */
    public record Rule(Verdict verdict, String why) {
        public boolean wild() { return verdict == Verdict.WILD; }
    }

    private static final Map<SpawnReason, Rule> RULES = new EnumMap<>(SpawnReason.class);

    static {
        for (SpawnReason r : SpawnReason.values()) RULES.put(r, classify(r));
    }

    /** SpawnReason 하나를 정한다. default 없음 — 이유가 늘면 여기서 컴파일 오류. */
    static Rule classify(SpawnReason r) {
        return switch (r) {
            // ── 바닐라 세계가 만드는 것: 막음 ──
            case NATURAL -> wild("자연 스폰 (밤 몹·동물·물고기·박쥐·떠돌이 상인·라마·팬텀·워든)");
            case CHUNK_GEN -> wild("새 청크를 만들 때 함께 생기는 동물·마녀 오두막 마녀");
            case JOCKEY -> wild("자연 몹 위에 함께 붙어 나오는 기수 (거미 기수·스켈레톤 말 함정 기수)");
            case OCELOT_BABY -> wild("자연 스폰 오셀롯의 새끼");
            case SPAWNER -> wild("몬스터 생성기 블록");
            case TRIAL_SPAWNER -> wild("시련의 생성기");
            case OMINOUS_ITEM_SPAWNER -> wild("불길한 시련이 떨구는 생성기");
            case PATROL -> wild("약탈자 순찰대");
            case RAID -> wild("습격");
            case VILLAGE_INVASION -> wild("좀비 공성 (주민 마을 습격)");
            case VILLAGE_DEFENSE -> wild("주민이 부르는 철 골렘");
            case REINFORCEMENTS -> wild("좀비가 부르는 지원군");
            case TRAP -> wild("뇌우 때 스켈레톤 말 함정");
            case LIGHTNING -> wild("번개 (함정 말 · 돼지→좀비 피글린 · 주민→마녀)");
            case SILVERFISH_BLOCK -> wild("벌레 먹은 블록에서 나오는 좀벌레");
            case ENDER_PEARL -> wild("엔더 진주에서 나오는 엔더 진드기");
            case NETHER_PORTAL -> wild("네더 차원문에서 나오는 좀비 피글린");
            case SPELL -> wild("소환사가 부르는 벡스");
            case DROWNED -> wild("물에 빠진 좀비 → 드라운드 (변신은 따로 막아 좀비가 남음)");
            case FROZEN -> wild("가루눈에 언 스켈레톤 → 스트레이 (변신은 따로 막음)");
            case INFECTION -> wild("좀비에게 진 주민 → 좀비 주민 (변신은 따로 막음 — 주민은 그냥 쓰러짐)");
            case PIGLIN_ZOMBIFIED -> wild("오버월드에 온 피글린·호글린 → 좀비화 (변신은 따로 막음)");
            case BUILD_WITHER -> wild("위더 — 바닐라 보스, 폭발로 마을 둘레 지형을 부숨");
            // DEFAULT 는 Entity#spawnAt(Location) 의 기본 이유이기도 하다 — 플러그인 코드가 주 월드에 몹을 넣을 때는
            // spawnAt(loc, CUSTOM) 이나 world.spawn(…, CUSTOM, …) 을 쓸 것 (DEFAULT 로 넣으면 말없이 막힌다. 태그가 먼저 달린 몹은 건너뜀)
            case DEFAULT -> wild("이유 없이 더해지는 바닐라 경로 (삐걱이 심장의 삐걱이·구조물 몹). 플러그인 몹은 CUSTOM");
            // ── 플레이어·관리자·플러그인이 일부러: 허용 ──
            case CUSTOM -> action("플러그인 (이 플러그인의 몬스터·NPC 포함)");
            case COMMAND -> action("관리자 /summon");
            case SPAWNER_EGG -> action("스폰 알을 플레이어가 씀");
            case DISPENSE_EGG -> action("플레이어가 만든 발사기가 쏜 스폰 알");
            case EGG -> action("던진 달걀·개구리알·스니퍼 알·거북 알 — 플레이어 또는 이미 있는 동물의 알");
            case BREEDING -> action("이미 있는 동물·주민의 번식");
            case BEEHIVE -> action("벌집에 들어갔던 벌이 다시 나옴 (막으면 벌이 사라짐)");
            case BUCKET -> action("양동이의 물고기·아홀로틀·올챙이를 풀어 줌");
            case SHOULDER_ENTITY -> action("어깨 위 앵무새가 내려옴");
            case MOUNT -> action("접속할 때 타고 있던 탈것을 다시 놓음 (막으면 말이 사라짐). 닭 기수의 닭은 좀비를 막을 때 함께 치움");
            case BUILD_SNOWMAN -> action("플레이어가 쌓은 눈 골렘");
            case BUILD_IRONGOLEM -> action("플레이어가 쌓은 철 골렘");
            case BUILD_COPPERGOLEM -> action("플레이어가 쌓은 구리 골렘");
            case REANIMATE -> action("구리 골렘 조각상을 플레이어가 되살림");
            case REHYDRATION -> action("플레이어가 물에 놓은 마른 가스트 → 아기 가스트");
            case DUPLICATION -> action("플레이어가 알레이에게 자수정을 줌");
            case ENCHANTMENT -> action("플레이어 장비의 마법 부여 효과");
            case EXPLOSION -> action("크리퍼·드래곤 화염구의 잔류 구름 — 몹이 아님");
            case POTION_EFFECT -> action("플레이어가 빚은 점액·감염 물약이 낳는 슬라임·좀벌레 (불길한 시련 쪽은 시련 생성기를 막아 생기지 않음)");
            // ── 이미 있는 몹이 바뀜: 원래 몹이 지워지지 않게 허용 ──
            case CURED -> keep("플레이어가 좀비 주민을 치료");
            case SHEARED -> keep("플레이어가 무시룸 털을 깎음 → 소");
            case METAMORPHOSIS -> keep("올챙이가 자라 개구리");
            case SLIME_SPLIT -> keep("이미 허용된 슬라임(알·명령)이 죽으며 나뉨");
        };
    }

    private static Rule wild(String why) { return new Rule(Verdict.WILD, why); }

    private static Rule action(String why) { return new Rule(Verdict.ACTION, why); }

    private static Rule keep(String why) { return new Rule(Verdict.KEEP_SOURCE, why); }

    public static Rule rule(SpawnReason r) { return r == null ? RULES.get(SpawnReason.DEFAULT) : RULES.get(r); }

    /** 모드 범위 안의 몹인가 (monsters = 적대만, all = 모든 몹). */
    public static boolean inScope(Settings.Wild.Spawns mode, boolean mob, boolean enemy) {
        if (mode == null) return false;
        return switch (mode) {
            case ALL -> mob || enemy;
            case MONSTERS -> enemy;
            case NONE -> false;
        };
    }

    /**
     * 주 월드 자연 스폰 상한(World#setSpawnLimit)을 0 으로 묶는 분류 — 성능용. 막을지는 언제나 이벤트({@link #blockSpawn})가 정하고,
     * 이것은 NaturalSpawner 가 그 분류를 아예 건너뛰게 할 뿐이다 (막힌 시도마다 이벤트가 오지 않게). 실행 중에만 쓰이고 끄면 되돌린다.
     * all = 자연 스폰 분류 전부 (모두 몹), monsters = MONSTER 만 (기수 없이 남을 탈것 — 낙타 허스크·좀비 앵무조개 — 도 함께 안 나옴),
     * MISC 는 바닐라가 상한을 받지 않는다. default 없음.
     */
    public static boolean limitCategory(Settings.Wild.Spawns mode, SpawnCategory c) {
        if (mode == null || mode == Settings.Wild.Spawns.NONE || c == null) return false;
        return switch (c) {
            case MONSTER -> true;
            case ANIMAL, WATER_ANIMAL, WATER_AMBIENT, WATER_UNDERGROUND_CREATURE, AMBIENT, AXOLOTL -> mode == Settings.Wild.Spawns.ALL;
            case MISC -> false;
        };
    }

    /** 이 스폰을 막는가 (플러그인 태그·월드 검사는 부르는 쪽). */
    public static boolean blockSpawn(Settings.Wild.Spawns mode, SpawnReason r, boolean mob, boolean enemy) {
        return rule(r).wild() && inScope(mode, mob, enemy);
    }

    /**
     * 예전 마을 둘레 적대 막기 (config village.block_mob_spawns, 0.3.0~): 마을 중심 반경 radius+8 안의 적대 NATURAL·PATROL·
     * REINFORCEMENTS. wild.spawns 가 monsters·all 이면 이 경우는 이미 모두 막히고, none 이면 이것만 남는다.
     */
    public static boolean oldVillageBlock(SpawnReason r, boolean enemy) {
        return enemy && (r == SpawnReason.NATURAL || r == SpawnReason.PATROL || r == SpawnReason.REINFORCEMENTS);
    }

    /** 자연이 일으키는 변신인가 (막아도 원래 몹이 그대로 남는다 — EntityTransformEvent 는 새 몹을 넣기 전에 온다). */
    public static boolean naturalTransform(TransformReason r) {
        if (r == null) return false;
        return switch (r) {
            case LIGHTNING, DROWNED, FROZEN, PIGLIN_ZOMBIFIED, INFECTION -> true;
            case CURED, SHEARED, METAMORPHOSIS, SPLIT, UNKNOWN -> false;
        };
    }

    /** 이 변신을 막는가 — 자연 변신이고 바뀔 몹이 모드 범위 안일 때. */
    public static boolean blockTransform(Settings.Wild.Spawns mode, TransformReason r, boolean resultMob, boolean resultEnemy) {
        return naturalTransform(r) && inScope(mode, resultMob, resultEnemy);
    }

    /**
     * 이미 마을 월드에 있던 몹을 치우는가 (켤 때 한 번 + 청크를 불러올 때). 적대 몹만 — 동물은 그대로 둔다.
     * 이름표·길들임·끈·사라지지 않는 몹(persistent)·플러그인 몹·보스·플레이어가 탄/태운 몹은 두고,
     * 스폰 이유가 플레이어 쪽(알·명령·플러그인 …)인 몹도 둔다. 이유를 모르면(DEFAULT) 바닐라로 본다.
     */
    public record Existing(boolean enemy, boolean boss, boolean named, boolean tamed, boolean leashed, boolean persistent,
                           boolean pluginTagged, boolean withPlayer, SpawnReason reason) {}

    public static boolean removeExisting(Settings.Wild.Spawns mode, Existing e) {
        if (mode == null || mode == Settings.Wild.Spawns.NONE || !e.enemy()) return false;
        if (e.boss() || e.named() || e.tamed() || e.leashed() || e.persistent() || e.pluginTagged() || e.withPlayer()) return false;
        return rule(e.reason()).wild();
    }
}
