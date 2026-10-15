package kr.labyrinth.dungeon.treasure;

import kr.labyrinth.Services;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 층 전용 금고 열쇠 (items.yml {@code vault_key}, type key). PDC 에 "인스턴스#층" 을 새겨 그 층 금고만 연다.
 * 미궁을 나가거나({@code Run.restore}) 다음 층으로 내려가면 인벤토리에서 사라진다 — 미궁 밖으로 못 가져간다.
 */
public final class VaultKeys {

    public static final String ITEM_ID = "vault_key";
    static final NamespacedKey TAG = Keys.key("vault_key");

    private VaultKeys() {}

    /** 새김 문자열. */
    public static String tag(String instanceId, int floor) { return instanceId + "#" + floor; }

    public static boolean matches(String tag, String instanceId, int floor) {
        return tag != null && tag.equals(tag(instanceId, floor));
    }

    /** 층 번호 (새김이 없거나 잘못되면 -1). */
    public static int floorOf(String tag) {
        if (tag == null) return -1;
        int i = tag.lastIndexOf('#');
        if (i < 0) return -1;
        try {
            return Integer.parseInt(tag.substring(i + 1));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    /** 열쇠 아이템 (아이템 정의가 없으면 null). */
    public static ItemStack create(Services services, String instanceId, int floor) {
        ItemStack s = services.items().create(ITEM_ID, 1);
        if (s == null) return null;
        String t = tag(instanceId, floor);
        s.editMeta(m -> {
            m.getPersistentDataContainer().set(TAG, PersistentDataType.STRING, t);
            m.customName(Text.mm("<!i><gold>지하 " + floor + "층 금고 열쇠"));
        });
        return s;
    }

    public static String tagOf(ItemStack s) {
        if (s == null || !s.hasItemMeta()) return null;
        return s.getItemMeta().getPersistentDataContainer().get(TAG, PersistentDataType.STRING);
    }

    /** 이 층 금고 열쇠 하나를 쓴다 (주 손 먼저, 없으면 인벤토리). @return 썼으면 true */
    public static boolean consume(Player p, String instanceId, int floor) {
        PlayerInventory inv = p.getInventory();
        ItemStack hand = inv.getItemInMainHand();
        if (matches(tagOf(hand), instanceId, floor)) {
            hand.setAmount(hand.getAmount() - 1);
            return true;
        }
        ItemStack[] all = inv.getContents();
        for (int i = 0; i < all.length; i++) {
            if (!matches(tagOf(all[i]), instanceId, floor)) continue;
            all[i].setAmount(all[i].getAmount() - 1);
            inv.setItem(i, all[i].getAmount() <= 0 ? null : all[i]);
            return true;
        }
        return false;
    }

    /** 금고 열쇠를 지운다. keepFloor &gt; 0 이면 그 층 열쇠는 남긴다. @return 지운 개수 */
    public static int strip(Player p, String instanceId, int keepFloor) {
        PlayerInventory inv = p.getInventory();
        ItemStack[] all = inv.getContents();
        int n = 0;
        for (int i = 0; i < all.length; i++) {
            String t = tagOf(all[i]);
            if (t == null) continue;
            if (keepFloor > 0 && matches(t, instanceId, keepFloor)) continue;
            n += all[i].getAmount();
            inv.setItem(i, null);
        }
        ItemStack cursor = p.getItemOnCursor();
        if (tagOf(cursor) != null && !(keepFloor > 0 && matches(tagOf(cursor), instanceId, keepFloor))) {
            n += cursor.getAmount();
            p.setItemOnCursor(null);
        }
        return n;
    }
}
