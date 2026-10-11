package kr.souls.item;

import kr.souls.Keys;
import kr.souls.util.Items;
import kr.souls.util.P;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.logging.Logger;

/**
 * 무기·방패·활·촉매 등록부 (content/weapons.yml, 9.1, 9.2, 3.12.4, 12.5). 아이템은 ItemFactory.weapon 이 만든다.
 * 글은 콘텐츠에 없다: 이름 weapon.&lt;id&gt;.name, 설명 weapon.&lt;id&gt;.lore, 분류 줄 weapon.class.&lt;class&gt;, 수치 이름 weapon.stat.* (값은 item/StatTable 이 한 줄로).
 * 장비에는 능력치 보정도 요구 능력치도 없다 (DECISIONS 2026-10-10): 보이는 값은 제 값 하나 (공격력·막기·술법 위력) 와 무게뿐이다.
 */
public final class Weapons {
    /** 손 */
    public static final String MAIN = "main";
    public static final String OFF = "off";
    /** 쓰는 몸짓: 막기 (무기), 방패 막기, 활 당기기, 없음 (촉매, 패링 단검) */
    public static final String GUARD = "guard";
    public static final String BLOCK = "block";
    public static final String BOW = "bow";
    public static final String NONE = "none";
    /** 예전 판 (보정·요구 능력치·방패 넷) 의 열쇠. 남아 있으면 읽지 않고 서버 기록에 한 번 알린다 */
    static final List<String> LEGACY = List.of("scaling", "requires", "absorb", "stability", "parry", "fire");
    /** 술법 위력이 적히지 않은 예전 판 촉매의 값 (지금 판의 두 촉매와 같다) */
    static final int LEGACY_SPELL = 100;

    /**
     * 한 아이템.
     * @param cls 분류 (lang weapon.class.&lt;cls&gt;. 패링 창 combat.parry.windows 와 양손 막기 combat.guard.two-handed 의 열쇠)
     * @param hand MAIN 또는 OFF
     * @param use GUARD, BLOCK, BOW, NONE
     * @param walk 막거나 당기는 동안 걸음 배율 (2.3.9)
     * @param attack 기본 물리 공격력 (+0, 3.7). 방패·촉매는 0
     * @param guard 막기: 막는 동안 막는 물리 피해 % (방패만, 0..100)
     * @param spell 술법 위력 (촉매만, 3.12.4)
     */
    public record Def(String id, String cls, String hand, String use, double walk, int attack, int guard, int spell, double weight) {
        /** 방패 (막기 값이 있다). */
        public boolean shield() {
            return guard > 0;
        }

        /** 촉매 (분류가 catalyst_*). */
        public boolean catalyst() {
            return cls.startsWith("catalyst");
        }
    }

    private final Map<String, Def> defs = new LinkedHashMap<>();
    private final Logger log;

    public Weapons(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml) {
        defs.clear();
        List<String> legacy = new ArrayList<>();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            String use = p.s("use", GUARD).toLowerCase(Locale.ROOT);
            if (!List.of(GUARD, BLOCK, BOW, NONE).contains(use)) {
                log.warning("무기 " + id + ": 모르는 use " + use + " (guard 로 본다)");
                use = GUARD;
            }
            for (String k : LEGACY) if (sec.contains(k)) legacy.add(id + "." + k);
            // YAML 1.1 은 따옴표 없는 off 를 거짓으로 읽는다 (hand: off → "false")
            String hand = p.s("hand", MAIN).toLowerCase(Locale.ROOT);
            if ("false".equals(hand)) hand = OFF;
            String cls = p.s("class", "straight_sword");
            // 예전 판 (v4) 의 중형 방패 분류 이름. 지금은 medium_shield (패링 창·설명 칸 분류 줄의 열쇠)
            if ("shield".equals(cls)) cls = "medium_shield";
            int guard = Math.max(0, Math.min(100, p.i("guard", 0)));
            // 예전 판의 방패 (absorb·stability·fire) 를 되살려 쓴 파일: 막기 값이 없으면 물리 흡수를 막기로 본다 (검토 legacy-weapons-yml-no-fallback.
            // 그러지 않으면 막기 0 이라 방패로 보지 않는다)
            if (!sec.contains("guard") && BLOCK.equals(use) && sec.contains("absorb")) guard = Math.max(0, Math.min(100, p.i("absorb", 0)));
            int spell = Math.max(0, p.i("spell", 0));
            // 예전 판의 촉매에는 술법 위력이 없었다: 지금 판의 바탕 값 100 (3.12.4)
            if (!sec.contains("spell") && cls.startsWith("catalyst")) spell = LEGACY_SPELL;
            defs.put(id, new Def(id, cls, hand, use, p.d("walk", 0.55), Math.max(0, p.i("attack", 0)), guard, spell, p.d("weight", 1.0)));
        }
        if (!legacy.isEmpty()) {
            log.warning("weapons.yml 의 예전 열쇠는 읽지 않는다 (장비에는 보정·요구 능력치가 없고 방패는 guard 하나다. guard 가 없는 방패는 "
                    + "absorb 를 막기로, spell 이 없는 촉매는 술법 위력 " + LEGACY_SPELL + " 으로 본다): " + String.join(", ", legacy));
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
