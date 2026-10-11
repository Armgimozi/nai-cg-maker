package kr.augsky;

import org.bukkit.NamespacedKey;
import org.bukkit.plugin.Plugin;

/** PersistentDataContainer 에 쓰는 키 모음. 네임스페이스는 플러그인 이름(augmentskyblock)이 아니라 augsky 로 고정한다. */
public final class Keys {
    public static final String NS = "augsky";

    public static NamespacedKey ITEM;      // 커스텀 아이템 id (파편, 결정, 증강권 등)
    public static NamespacedKey WEAPON;    // 무기 id
    public static NamespacedKey MOB;       // 커스텀 몬스터 id
    public static NamespacedKey RIFT_MOB;  // 균열에서 나온 몬스터의 균열 id
    public static NamespacedKey ALTAR;     // 제단 상호작용 엔티티의 등급
    public static NamespacedKey RIFT;      // 균열 마커의 균열 id
    public static NamespacedKey PEDESTAL;  // 보스 소환대의 균열 id
    public static NamespacedKey ALLY;      // 플레이어가 소환한 아군 (주인 UUID)
    public static NamespacedKey MAP_PART;  // 맵 장식용 디스플레이 엔티티
    public static NamespacedKey BEAM;      // 예전 맵의 빛기둥. 보이면 지운다
    public static NamespacedKey USED;      // 힘을 다한(이미 쓴) 제단
    public static NamespacedKey ALTAR_OF;  // 제단 장식이 어느 제단(상호작용 엔티티 UUID)에 속하는지
    public static NamespacedKey LAIR;      // 보스 둥지 마커 / 둥지를 지키는 보스 (둥지 UUID)
    public static NamespacedKey LAIR_TEXT; // 둥지의 부활 시계 글자
    public static NamespacedKey ARMOR;     // 갑옷 세트 id
    public static NamespacedKey ARMOR_SLOT;// 갑옷 부위
    public static NamespacedKey RIG;       // 보스 모델 조각

    private Keys() {}

    static void init(Plugin plugin) {
        ITEM = new NamespacedKey(NS, "item");
        WEAPON = new NamespacedKey(NS, "weapon");
        MOB = new NamespacedKey(NS, "mob");
        RIFT_MOB = new NamespacedKey(NS, "rift_mob");
        ALTAR = new NamespacedKey(NS, "altar");
        RIFT = new NamespacedKey(NS, "rift");
        PEDESTAL = new NamespacedKey(NS, "pedestal");
        ALLY = new NamespacedKey(NS, "ally");
        MAP_PART = new NamespacedKey(NS, "map_part");
        BEAM = new NamespacedKey(NS, "beam");
        USED = new NamespacedKey(NS, "used");
        ALTAR_OF = new NamespacedKey(NS, "altar_of");
        LAIR = new NamespacedKey(NS, "lair");
        LAIR_TEXT = new NamespacedKey(NS, "lair_text");
        ARMOR = new NamespacedKey(NS, "armor");
        ARMOR_SLOT = new NamespacedKey(NS, "armor_slot");
        RIG = new NamespacedKey(NS, "rig");
    }

    public static NamespacedKey of(String path) {
        return new NamespacedKey(NS, path);
    }
}
