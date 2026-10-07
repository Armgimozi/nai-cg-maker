package kr.souls;

import org.bukkit.NamespacedKey;
import org.bukkit.plugin.Plugin;

/**
 * PersistentDataContainer 에 쓰는 키 모음. 네임스페이스는 플러그인 이름(soulslike)이 아니라 souls 로 고정한다.
 * 리소스팩·데이터팩 이름공간과 같다 (파이썬 NS 와 같은 날 바꾼다).
 */
public final class Keys {
    public static final String NS = "souls";

    public static NamespacedKey ITEM;      // 우리 아이템 id (소모품, 재료, 열쇠, 시험용 막기 도구)
    public static NamespacedKey WEAPON;    // 무기 id
    public static NamespacedKey MOB;       // 적 id
    public static NamespacedKey MAP_PART;  // 지도 장식용 디스플레이 물체
    public static NamespacedKey LAIR;      // 보스 방 표식 / 그 방을 지키는 보스
    public static NamespacedKey LAIR_TEXT; // 보스 방 글자
    public static NamespacedKey ARMOR;     // 방어구 벌 id
    public static NamespacedKey ARMOR_SLOT;// 방어구 부위
    public static NamespacedKey RIG;       // 보스 모형 조각
    public static NamespacedKey BONFIRE;   // 화톳불 물체 (화톳불 id)
    public static NamespacedKey STAIN;     // 혈흔 (주인 UUID)
    public static NamespacedKey FOG;       // 안개문
    public static NamespacedKey ARENA;     // 보스 방 id
    public static NamespacedKey ANCHOR;    // 이름 붙은 자리 (r1.ward.07 처럼)
    public static NamespacedKey PICKUP;    // 줍는 것
    public static NamespacedKey SHORTCUT;  // 지름길 장치
    public static NamespacedKey SPAWN;     // 적 배치 지점
    public static NamespacedKey PROFILE;   // 플레이어 프로필 JSON (M2)
    public static NamespacedKey WORLD;     // 세계 상태 JSON (M2)
    public static NamespacedKey ROOM;      // 시험 방을 지은 판 번호 (souls_world PDC)
    public static NamespacedKey BIOMES;    // souls_world 를 만들 때의 바이옴 경계 판 번호

    private Keys() {}

    static void init(Plugin plugin) {
        ITEM = of("item");
        WEAPON = of("weapon");
        MOB = of("mob");
        MAP_PART = of("map_part");
        LAIR = of("lair");
        LAIR_TEXT = of("lair_text");
        ARMOR = of("armor");
        ARMOR_SLOT = of("armor_slot");
        RIG = of("rig");
        BONFIRE = of("bonfire");
        STAIN = of("stain");
        FOG = of("fog");
        ARENA = of("arena");
        ANCHOR = of("anchor");
        PICKUP = of("pickup");
        SHORTCUT = of("shortcut");
        SPAWN = of("spawn");
        PROFILE = of("profile");
        WORLD = of("world");
        ROOM = of("test_room");
        BIOMES = of("biome_layout");
    }

    public static NamespacedKey of(String path) {
        return new NamespacedKey(NS, path);
    }
}
