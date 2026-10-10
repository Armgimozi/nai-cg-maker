package kr.souls.progression;

import kr.souls.Keys;
import kr.souls.data.Profile;
import kr.souls.item.ItemFactory;
import kr.souls.item.MasterKey;
import kr.souls.item.Weapons;
import kr.souls.util.Items;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

/**
 * 출신 (5.1, 5.10, content/origins.yml). 출신마다 시작 능력치 여섯과 시작 아이템. 레벨은 적지 않고 합 − 59 로 셈한다.
 * 시작 아이템은 한 번만: 프로필의 장부 (kit.given) 에 "종류:id" 를 적고, 장부에 없고 지금 만들 수 있는 항목만 준다. 아직 못 만드는 것
 * (방어구 M3, 에스트 M1, 술법 M5) 은 건너뛰고 장부에도 적지 않아, 그 체계가 생긴 뒤 처음 접속할 때 한 번 준다. 궁수의 화살
 * (item: arrows) 은 바닐라 화살 ARROWS 개 (souls 표시 souls:item=arrows 가 붙어 출신 지우기·다시 고르기가 거둔다, 바닐라 활이 쏜다).
 */
public final class Origins {
    /** 시작 아이템 한 줄. kind: weapon | item | armor | spell. to: main | off | hotbar:N | null (가방부터). */
    public record Kit(String kind, String id, String to) {
        /** 장부 열쇠 */
        public String key() {
            return kind + ":" + id;
        }
    }

    public record Origin(String id, int order, StatBlock stats, List<Kit> kit) {
        public int level() {
            return stats.level();
        }
    }

    /** 지금 판 (M1 전) 에 동작이 있는 무기 분류 (14절: M1 의 무기 분류와 방패). 시험이 출신의 주무기가 여기 드는지 본다 */
    public static final Set<String> M1_CLASSES = Set.of("straight_sword", "greatsword", "dagger", "spear", "axe", "hammer", "bow",
            "small_shield", "shield", "parrying_dagger", "catalyst_kiln");

    /** 궁수의 시작 화살 수 */
    public static final int ARROWS = 32;
    public static final String ARROWS_ID = "arrows";

    private final Map<String, Origin> origins = new LinkedHashMap<>();
    private final Logger log;

    public Origins(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml, Weapons weapons) {
        origins.clear();
        List<Origin> list = new ArrayList<>();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            ConfigurationSection st = sec.getConfigurationSection("stats");
            if (st == null) {
                log.warning("출신 " + id + ": stats 가 없어 뺍니다");
                continue;
            }
            int[] v = new int[6];
            boolean bad = false;
            for (int i = 0; i < 6; i++) {
                String k = StatBlock.IDS.get(i);
                v[i] = st.getInt(k, -1);
                if (v[i] < StatBlock.MIN || v[i] > StatBlock.MAX) bad = true;
            }
            StatBlock s = new StatBlock(v[0], v[1], v[2], v[3], v[4], v[5]);
            if (bad || s.sum() < StatBlock.LEVEL_OFFSET + 1) {
                log.warning("출신 " + id + ": 능력치가 1..99 밖이거나 합이 60 보다 작아 뺍니다 (" + s.line() + ")");
                continue;
            }
            List<Kit> kit = new ArrayList<>();
            for (Map<?, ?> m : sec.getMapList("kit")) {
                String kind = null, kid = null;
                for (String k : List.of("weapon", "item", "armor", "spell")) {
                    Object o = m.get(k);
                    if (o != null) {
                        kind = k;
                        kid = String.valueOf(o).trim().toLowerCase(Locale.ROOT);
                        break;
                    }
                }
                if (kind == null) {
                    log.warning("출신 " + id + ": 시작 아이템 줄에 weapon/item/armor/spell 이 없다 (" + m + ")");
                    continue;
                }
                if ("weapon".equals(kind) && weapons.get(kid) == null) log.warning("출신 " + id + ": weapons.yml 에 없는 무기 " + kid);
                Object to = m.get("to");
                // YAML 1.1 은 따옴표 없는 off 를 거짓으로 읽는다 (to: off → false): 왼손으로 되돌린다
                if (to instanceof Boolean bo) to = bo ? "on" : "off";
                kit.add(new Kit(kind, kid, to == null ? null : String.valueOf(to).trim().toLowerCase(Locale.ROOT)));
            }
            list.add(new Origin(id.toLowerCase(Locale.ROOT), sec.getInt("order", 99), s, Collections.unmodifiableList(kit)));
        }
        list.sort(Comparator.comparingInt(Origin::order));
        for (Origin o : list) origins.put(o.id(), o);
        log.info("출신 " + origins.size() + "개 불러옴");
    }

    public Origin get(String id) {
        return id == null ? null : origins.get(id.toLowerCase(Locale.ROOT));
    }

    public List<Origin> all() {
        return List.copyOf(origins.values());
    }

    /** 이 줄을 지금 아이템으로 만들 수 있나. */
    public static boolean creatable(Kit k, Weapons weapons) {
        return switch (k.kind()) {
            case "weapon" -> weapons.get(k.id()) != null;
            case "item" -> MasterKey.ID.equals(k.id()) || ARROWS_ID.equals(k.id());
            default -> false;
        };
    }

    /** 그 줄의 아이템 (만들 수 없으면 null). */
    public static ItemStack make(Kit k, Weapons weapons) {
        return switch (k.kind()) {
            case "weapon" -> weapons.get(k.id()) == null ? null : ItemFactory.weapon(weapons.get(k.id()));
            case "item" -> MasterKey.ID.equals(k.id()) ? MasterKey.make() : ARROWS_ID.equals(k.id()) ? ItemFactory.arrows(ARROWS) : null;
            default -> null;
        };
    }

    /** 아직 받지 않았고 지금 만들 수 없는 줄 (시험 줄 ORIGIN 의 pending). */
    public static List<String> pending(Origin o, Profile pr, Weapons weapons) {
        List<String> out = new ArrayList<>();
        for (Kit k : o.kit()) if (!pr.wasGiven(k.key()) && !creatable(k, weapons)) out.add(k.key());
        return out;
    }

    /**
     * 장부로 준다: 장부에 없고 지금 만들 수 있는 줄만, 정한 자리에 (자리가 없으면 주지 않는다). 준 줄의 장부 열쇠를 돌려준다.
     * 부른 쪽이 프로필을 저장하고 saveData 를 부른다 (아이템과 장부가 한 번에 저장되게).
     */
    public static List<String> grant(Player p, Origin o, Profile pr, Weapons weapons) {
        List<String> given = new ArrayList<>();
        PlayerInventory inv = p.getInventory();
        for (Kit k : o.kit()) {
            if (pr.wasGiven(k.key()) || !creatable(k, weapons)) continue;
            ItemStack it = make(k, weapons);
            if (it == null || !place(inv, it, k.to())) continue;
            pr.markGiven(k.key());
            given.add(k.key());
        }
        return given;
    }

    /** 자리에 놓는다. main: 단축 1 (비었으면, 아니면 첫 빈 단축 칸), off: 왼손 (비었으면), hotbar:N, 없으면 가방 (9..35) 부터. */
    static boolean place(PlayerInventory inv, ItemStack it, String to) {
        if ("off".equals(to)) {
            if (inv.getItemInOffHand().isEmpty()) {
                inv.setItemInOffHand(it);
                return true;
            }
            return Items.putBackpackFirst(inv, it);
        }
        if ("main".equals(to)) {
            if (empty(inv.getItem(0))) {
                inv.setItem(0, it);
                return true;
            }
            for (int i = 0; i < 9; i++) {
                if (empty(inv.getItem(i))) {
                    inv.setItem(i, it);
                    return true;
                }
            }
            return Items.putBackpackFirst(inv, it);
        }
        if (to != null && to.startsWith("hotbar:")) {
            try {
                int n = Integer.parseInt(to.substring(7)) - 1;
                if (n >= 0 && n < 9 && empty(inv.getItem(n))) {
                    inv.setItem(n, it);
                    return true;
                }
            } catch (NumberFormatException ignored) {
                // 잘못 적은 칸이면 가방으로
            }
        }
        return Items.putBackpackFirst(inv, it);
    }

    private static boolean empty(ItemStack it) {
        return it == null || it.isEmpty();
    }

    /** souls 아이템 (무기·우리 아이템·방어구) 을 인벤토리·왼손·방어구 칸에서 모두 거둔다 (관리자의 출신 지우기). 거둔 수. */
    public static int removeSoulsItems(Player p) {
        PlayerInventory inv = p.getInventory();
        int n = 0;
        ItemStack[] all = inv.getContents();
        for (int i = 0; i < all.length; i++) {
            ItemStack it = all[i];
            if (it == null || it.isEmpty()) continue;
            if (Items.tag(it, Keys.WEAPON) != null || Items.tag(it, Keys.ITEM) != null || Items.tag(it, Keys.ARMOR) != null) {
                n += it.getAmount();
                inv.setItem(i, null);
            }
        }
        return n;
    }
}
