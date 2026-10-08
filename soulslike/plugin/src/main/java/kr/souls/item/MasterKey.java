package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import kr.souls.Keys;
import kr.souls.Lang;
import kr.souls.util.Items;
import net.kyori.adventure.key.Key;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

import java.util.Map;
import java.util.Set;

/**
 * 만능 열쇠 (9.5, 2026-10-08 사용자 결정): 다크 소울 1 처럼 도적 출신이 들고 시작한다. 맛보기판의 열쇠로 잠긴 문 (탑옥 위층 독방,
 * 병영 지하 감옥) 을 그 문의 열쇠 없이 연다. 이야기로 막힌 문 (서쪽 탑 문, 봉인, 한쪽 문) 은 열지 않는다.
 * 문은 지도가 생기는 M2·M3 에 붙는다. 지금은 아이템과 문 코드가 부를 고리 {@link #opens} (= {@link Keys#opens}) 만 있다.
 * 무게 0 (장비 무게에 들지 않는다, 5.8), 버릴 수 없다 (버리기는 늘 막는다).
 */
@SuppressWarnings("UnstableApiUsage")
public final class MasterKey {
    /** 우리 아이템 id (Keys.ITEM) */
    public static final String ID = "master_key";
    /** 맛보기판의 열쇠 문 (문 id → 그 문의 열쇠 아이템 id). 만능 열쇠는 이 문만 연다 */
    public static final Map<String, String> KEY_DOORS = Map.of(
            "gaol.upper_cell", "gaol_key",          // 탑옥 위층 독방 (탑옥 열쇠)
            "barracks.cells", "barracks_key");      // 병영 지하 감옥 (병영 열쇠)
    /** 이야기로 막힌 문 (어떤 열쇠로도 열지 않는다. 세계 상태가 연다) */
    public static final Set<String> STORY_DOORS = Set.of("redin.west_tower", "shrine.seal_left", "shrine.seal_right", "parish.bell_gate");

    private MasterKey() {}

    public static ItemStack make() {
        ItemStack it = ItemStack.of(ItemFactory.SHELL);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, ID));
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("item.master_key.name"));
        it.setData(DataComponentTypes.LORE, ItemLore.lore(Lang.lines("item.master_key.lore")));
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM, PersistentDataType.STRING, ID));
        return it;
    }

    public static boolean is(ItemStack it) {
        return ID.equals(Items.tag(it, Keys.ITEM));
    }

    /**
     * 이 사람이 이 잠긴 문을 열 수 있나 (문 코드가 부른다, M2·M3). 열쇠 문 (KEY_DOORS) 이면 그 문의 열쇠나 만능 열쇠를 가졌을 때 참.
     * 이야기로 막힌 문과 모르는 문은 늘 거짓 (열쇠로 열리는 문이 아니다).
     */
    public static boolean opens(Player p, String lockId) {
        if (p == null || lockId == null || STORY_DOORS.contains(lockId)) return false;
        String own = KEY_DOORS.get(lockId);
        if (own == null) return false;
        for (ItemStack it : p.getInventory().getContents()) {
            String id = Items.tag(it, Keys.ITEM);
            if (ID.equals(id) || own.equals(id)) return true;
        }
        return false;
    }
}
