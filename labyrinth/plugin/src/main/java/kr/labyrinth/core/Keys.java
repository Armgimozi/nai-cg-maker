package kr.labyrinth.core;

import org.bukkit.NamespacedKey;

/** PDC 키 모음 (네임스페이스 labyrinth). 모든 모듈이 여기 키만 쓴다 — 새 키는 여기에 추가. */
public final class Keys {

    public static final String NS = "labyrinth";

    private Keys() {}

    public static NamespacedKey key(String k) { return new NamespacedKey(NS, k); }

    // 아이템
    /** String: 아이템 정의 id. */
    public static final NamespacedKey ITEM_ID = key("item_id");
    /** Long: 굴림 시드 (스탯 굴림 재현용). */
    public static final NamespacedKey ITEM_SEED = key("item_seed");
    /** String: 굴린 스탯 "key=value;key=value" (ItemService 가 형식 소유). */
    public static final NamespacedKey ITEM_ROLLS = key("item_rolls");
    /** Integer: 아이템 데이터 버전 (1 = 굴림, 2 = 강화 단계 키 추가 — 1 이하는 강화 0 으로 읽는다). */
    public static final NamespacedKey ITEM_VERSION = key("item_version");
    /** Integer: 강화 단계 0~10 (없으면 0, ITEM_VERSION 2 부터). 형식 소유 = items.enhance.Enhancement. */
    public static final NamespacedKey ITEM_ENHANCE = key("item_enhance");
    /** Integer: 0.3.5 굴림 옮기기 깃발 (없으면 0 = 0.3.4 이전 굴림, 35 = 0.3.5 범위). 형식 소유 = items.ItemMigration035. */
    public static final NamespacedKey ITEM_COMBAT_VER = key("item_combat_ver");
    /** String(UUID): 개인 루팅 소유자. */
    public static final NamespacedKey LOOT_OWNER = key("loot_owner");

    // 엔티티
    /** String: 커스텀 몹 id. 서버 재시작 후 남은 엔티티 청소 기준(ARCHITECTURE §7). */
    public static final NamespacedKey MOB = key("mob");
    /** String: 보스 id. */
    public static final NamespacedKey BOSS = key("boss");
    /** String: 모델 리그 파트/이펙트 디스플레이 등 임시 표시 엔티티 (값 = 소유 몹/이펙트 이름). */
    public static final NamespacedKey FX = key("fx");
    /** String: NPC id. */
    public static final NamespacedKey NPC = key("npc");
    /** 피해 숫자 TextDisplay 표시 (값 무관). */
    public static final NamespacedKey DAMAGE_NUMBER = key("damage_number");
    /** String: 인스턴스 id (몹·보스·이펙트가 어느 인스턴스 소속인지). */
    public static final NamespacedKey INSTANCE = key("instance");
    /** Float: 활 당김 세기(0~1) — 화살 엔티티에 기록. */
    public static final NamespacedKey ARROW_FORCE = key("arrow_force");
    /** String: 화살을 쏜 무기 아이템 id. */
    public static final NamespacedKey ARROW_WEAPON = key("arrow_weapon");
    /** Double: 쏜 순간의 무기 한 방 W (0.3.6.1 — 날아가는 동안 무기를 바꿔도 쏜 활로 셈). */
    public static final NamespacedKey ARROW_HIT = key("arrow_hit");

    /** String: 엔티티를 만든 서버 세션 id. 현재 세션이 아닌 임시 엔티티는 청크 로드 시 청소된다. */
    public static final NamespacedKey SESSION = key("session");

    /** 이 키들 중 하나라도 달린 엔티티는 임시 엔티티(재시작 후 청소 대상). */
    public static final NamespacedKey[] TRANSIENT_ENTITY_KEYS = {MOB, BOSS, FX, DAMAGE_NUMBER};

    /** 이번 서버(플러그인) 세션 id — 시작할 때마다 바뀐다. */
    public static final String SESSION_ID = java.util.UUID.randomUUID().toString();

    /**
     * 임시 엔티티 표시: key(=MOB/BOSS/FX/DAMAGE_NUMBER 중 하나)에 value 를 넣고 세션 id 를 단다.
     * 모든 커스텀 몹·모델 파트·이펙트 디스플레이는 반드시 이걸로 태그할 것 (EntityJanitor 가 재시작 후 청소).
     * 엔티티는 setPersistent(false) 권장.
     */
    public static void tagTransient(org.bukkit.entity.Entity e, NamespacedKey key, String value) {
        var pdc = e.getPersistentDataContainer();
        pdc.set(key, org.bukkit.persistence.PersistentDataType.STRING, value == null ? "" : value);
        pdc.set(SESSION, org.bukkit.persistence.PersistentDataType.STRING, SESSION_ID);
    }

    /** 임시 엔티티인데 이번 세션 것이 아니면 true (청소 대상). */
    public static boolean isStaleTransient(org.bukkit.entity.Entity e) {
        var pdc = e.getPersistentDataContainer();
        boolean transientEntity = false;
        for (NamespacedKey k : TRANSIENT_ENTITY_KEYS) {
            if (pdc.getKeys().contains(k)) {
                transientEntity = true;
                break;
            }
        }
        if (!transientEntity) return false;
        return !SESSION_ID.equals(pdc.get(SESSION, org.bukkit.persistence.PersistentDataType.STRING));
    }
}
