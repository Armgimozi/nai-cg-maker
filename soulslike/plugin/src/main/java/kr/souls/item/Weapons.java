package kr.souls.item;

import kr.souls.Keys;
import kr.souls.util.Items;
import kr.souls.util.P;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.ItemStack;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.logging.Logger;

/**
 * 무기·방패·활·촉매 등록부 (content/weapons.yml, 9.1, 9.2, 3.12.4, 12.5). 아이템은 ItemFactory.weapon 이 만든다.
 * 글은 콘텐츠에 없다: 이름 weapon.&lt;id&gt;.name, 설명 weapon.&lt;id&gt;.lore, 분류 줄 weapon.class.&lt;class&gt;, 수치 이름 weapon.stat.* (값은 item/StatTable 이 두 열 표로).
 */
public final class Weapons {
    /** 손 */
    public static final String MAIN = "main";
    public static final String OFF = "off";
    /** 쓰는 몸짓: 막기 (무기), 방패 막기, 활 당기기, 없음 (촉매) */
    public static final String GUARD = "guard";
    public static final String BLOCK = "block";
    public static final String BOW = "bow";
    public static final String NONE = "none";
    /**
     * 보정·필요 능력치를 보이는 차례 (근력, 민첩, 지능, 1.3판 5.2). 근력 보정은 공격력 (3.7), 민첩 보정은 그 무기의 공격 속도 몫 (3.6),
     * 지능 보정은 촉매의 술 세기 (3.12.4). 1.2판의 att (기억) 는 int 로 바뀌었다.
     */
    public static final List<String> STATS = List.of("str", "dex", "int");

    /**
     * 한 아이템.
     * @param cls 분류 (lang weapon.class.&lt;cls&gt;)
     * @param hand MAIN 또는 OFF
     * @param use GUARD, BLOCK, BOW, NONE
     * @param walk 막거나 당기는 동안 걸음 배율 (2.3.9)
     * @param attack 기본 물리 공격력 (+0, 3.7). 방패·촉매는 0
     * @param scaling 보정 등급 (str 근력 → 공격력, dex 민첩 → 공격 속도, int 지능 → 술 세기: E..S)
     * @param requires 필요 능력치
     * @param absorb 물리 흡수 % (방패), stability 안정성, parry 쳐내기 창 틱, fire 불 흡수 %
     */
    public record Def(String id, String cls, String hand, String use, double walk, int attack, Map<String, String> scaling,
                      Map<String, Integer> requires, double weight, int absorb, int stability, int parry, int fire) {
        public boolean shield() {
            return absorb > 0;
        }
    }

    private final Map<String, Def> defs = new LinkedHashMap<>();
    private final Logger log;

    public Weapons(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml) {
        defs.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            String use = p.s("use", GUARD).toLowerCase(Locale.ROOT);
            if (!List.of(GUARD, BLOCK, BOW, NONE).contains(use)) {
                log.warning("무기 " + id + ": 모르는 use " + use + " (guard 로 본다)");
                use = GUARD;
            }
            Map<String, String> scaling = new LinkedHashMap<>();
            Map<String, Integer> requires = new LinkedHashMap<>();
            ConfigurationSection sc = sec.getConfigurationSection("scaling");
            ConfigurationSection rq = sec.getConfigurationSection("requires");
            for (String s : STATS) {
                if (sc != null && sc.isString(s)) scaling.put(s, sc.getString(s, "E").toUpperCase(Locale.ROOT));
                if (rq != null && rq.isInt(s)) requires.put(s, rq.getInt(s));
            }
            defs.put(id, new Def(id, p.s("class", "straight_sword"), p.s("hand", MAIN), use, p.d("walk", 0.55), p.i("attack", 0),
                    Collections.unmodifiableMap(scaling), Collections.unmodifiableMap(requires), p.d("weight", 1.0),
                    p.i("absorb", 0), p.i("stability", 0), p.i("parry", 0), p.i("fire", 0)));
        }
        log.info("무기·방패·촉매 " + defs.size() + "개 불러옴");
    }

    public Def get(String id) {
        return id == null ? null : defs.get(id);
    }

    /** 이 아이템이 우리 무기면 그 정의, 아니면 null. */
    public Def of(ItemStack it) {
        return get(Items.tag(it, Keys.WEAPON));
    }

    public Map<String, Def> all() {
        return Collections.unmodifiableMap(defs);
    }
}
