package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.DamageResistant;
import io.papermc.paper.datacomponent.item.ItemLore;
import io.papermc.paper.registry.keys.tags.DamageTypeTagKeys;
import kr.souls.Keys;
import kr.souls.Lang;
import kr.souls.util.Items;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/**
 * 반지 등록부 (content/rings.yml, 9.4, 12.5). 반지는 인벤토리 2×2 자리의 왼쪽 세로 두 칸에 끼는 아이템이다 (2026-10-08 사용자 결정
 * B 안, 칸은 {@link RingSlots}). 콘텐츠는 id·모형·효과만 갖고 글은 lang 의 ring.&lt;id&gt;.name (한 줄), ring.&lt;id&gt;.lore (목록),
 * 효과 줄은 ring.effect.&lt;효과&gt; 에 값을 채운다.
 *
 * 효과 (두 반지의 효과는 합친다: 배율은 곱, 나머지는 더한다. 같은 반지 둘은 끼지 않는다)
 *   stamina-regen  스태미나 회복 배율 (1.20 = +20%). 지금 듣는다: combat/Stamina 의 회복과 능력치 창의 회복 값
 *   poise          강인도 덧셈 비율 (0.40 = +40%). 고리만 있다: 강인도 (3.8) 가 생기면 RingSlots.poiseBonus 를 부른다
 *   parry-window   쳐내기 창 덧셈 틱. 고리만 있다: 쳐내기 (3.5) 가 RingSlots.parryWindowBonus 를 부른다
 *   soul-guard     죽어도 소울을 한 번 잃지 않고 반지가 부서진다. 고리만 있다: 소울 잃기 (5.5, M2) 가 RingSlots.consumeSoulGuard 를 부른다
 * 고리만 있는 효과는 설명 칸에 "아직 이 효과를 받는 체계가 없다" 줄이 붙는다 (ring.effect.pending).
 *
 * 아이템: 껍데기는 무기와 같은 부싯돌 (2×2 에 둘이 세로로 놓여도 바닐라 제작법이 없다. 제작은 RingSlots 가 어차피 막는다), 모형
 * souls:&lt;model&gt; (pack/icons.py 의 RING_ART: 모든 반지가 같은 테 꼴이라 반지 칸 바탕의 흐린 반지 그림을 덮는다), 한 칸에 하나,
 * 불에 타지 않는다. PDC souls:ring = id. 반지 칸에 비친 사본에는 souls:ring_worn 이 더 붙는다 (칸 밖에서 보이면 지운다).
 * 무게는 없다 (5.8 은 무기·방어구만 센다). 순수 셈 ({@link #load}, {@link #combine}) 은 13.1 의 RingsTest 가 본다.
 */
@SuppressWarnings("UnstableApiUsage")
public final class Rings {
    public static final String STAMINA_REGEN = "stamina-regen";
    public static final String POISE = "poise";
    public static final String PARRY_WINDOW = "parry-window";
    public static final String SOUL_GUARD = "soul-guard";
    /** 아는 효과 (설명 칸의 차례) */
    public static final List<String> EFFECTS = List.of(STAMINA_REGEN, POISE, PARRY_WINDOW, SOUL_GUARD);
    /** 지금 무엇이 받아 쓰는 효과. 나머지는 고리만 있다 */
    public static final Set<String> LIVE = Set.of(STAMINA_REGEN);
    private static final Pattern ID = Pattern.compile("[a-z0-9_]+");

    /**
     * 반지 하나.
     * @param model        팩의 모형 이름 (souls:&lt;model&gt;)
     * @param test         시험 반지 (/soulstest ring give 로만, 세계에 놓지 않는다)
     * @param staminaRegen 스태미나 회복 배율 (없으면 1)
     * @param poise        강인도 덧셈 비율 (없으면 0)
     * @param parryWindow  쳐내기 창 덧셈 틱 (없으면 0)
     * @param soulGuard    소울 지키기 (한 번, 부서진다)
     */
    public record Def(String id, String model, boolean test, double staminaRegen, double poise, int parryWindow, boolean soulGuard) {
        /** 이 반지에 있는 효과 (EFFECTS 차례). */
        public List<String> effects() {
            List<String> out = new ArrayList<>();
            if (staminaRegen != 1.0) out.add(STAMINA_REGEN);
            if (poise != 0.0) out.add(POISE);
            if (parryWindow != 0) out.add(PARRY_WINDOW);
            if (soulGuard) out.add(SOUL_GUARD);
            return out;
        }
    }

    /** 낀 반지들의 효과를 합친 것. */
    public record Worn(double staminaRegen, double poise, int parryWindow, boolean soulGuard) {
        public static final Worn NONE = new Worn(1.0, 0.0, 0, false);
    }

    private final Map<String, Def> defs = new LinkedHashMap<>();
    private final Logger log;

    public Rings(Logger log) {
        this.log = log;
    }

    /** content/rings.yml 을 읽는다. 잘못된 항목은 서버 기록에 경고하고 뺀다 (모르는 효과는 그 효과만 버린다). */
    public void load(ConfigurationSection yml) {
        defs.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null || !ID.matcher(id).matches()) {
                log.warning("반지 " + id + ": id 는 영어 소문자·숫자·_ 의 묶음이어야 한다 (뺀다)");
                continue;
            }
            String model = sec.getString("model", id);
            if (model == null || !ID.matcher(model).matches()) {
                log.warning("반지 " + id + ": 모형 이름 " + model + " 이 잘못되었다 (" + id + " 로 본다)");
                model = id;
            }
            double regen = 1.0, poise = 0.0;
            int parry = 0;
            boolean guard = false;
            ConfigurationSection fx = sec.getConfigurationSection("effects");
            if (fx != null) {
                for (String k : fx.getKeys(false)) {
                    switch (k.toLowerCase(Locale.ROOT)) {
                        case STAMINA_REGEN -> {
                            double v = fx.getDouble(k, 1.0);
                            if (v > 0 && v <= 10) regen = v;
                            else log.warning("반지 " + id + ": stamina-regen " + v + " 은 0 보다 크고 10 이하라야 한다 (버린다)");
                        }
                        case POISE -> poise = Math.max(-1.0, Math.min(10.0, fx.getDouble(k, 0.0)));
                        case PARRY_WINDOW -> parry = Math.max(-20, Math.min(20, fx.getInt(k, 0)));
                        case SOUL_GUARD -> guard = fx.getBoolean(k, false);
                        default -> log.warning("반지 " + id + ": 모르는 효과 " + k + " (버린다. 아는 것: " + String.join(", ", EFFECTS) + ")");
                    }
                }
            }
            defs.put(id, new Def(id, model, sec.getBoolean("test", false), regen, poise, parry, guard));
        }
    }

    public Def get(String id) {
        return id == null ? null : defs.get(id);
    }

    public Map<String, Def> all() {
        return Collections.unmodifiableMap(defs);
    }

    /** 반지들의 효과를 합친다 (null 은 건너뛴다). */
    public static Worn combine(Collection<Def> worn) {
        double regen = 1.0, poise = 0.0;
        int parry = 0;
        boolean guard = false;
        for (Def d : worn) {
            if (d == null) continue;
            regen *= d.staminaRegen();
            poise += d.poise();
            parry += d.parryWindow();
            guard |= d.soulGuard();
        }
        return new Worn(regen, poise, parry, guard);
    }

    // ------------------------------------------------------------------ 아이템

    /** 반지 아이템 (인벤토리에 넣는 것). */
    public ItemStack make(Def d) {
        ItemStack it = ItemStack.of(ItemFactory.SHELL);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, d.model()));
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("ring." + d.id() + ".name")); // lang-dyn: ring.*.name
        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore(d)));
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.setData(DataComponentTypes.DAMAGE_RESISTANT, DamageResistant.damageResistant(DamageTypeTagKeys.IS_FIRE));
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.RING, PersistentDataType.STRING, d.id()));
        return it;
    }

    /** 반지 칸에 비치는 사본: make 에 표시 souls:ring_worn 을 더한 것. 칸 밖에서 보이면 RingSlots 가 지운다. */
    public ItemStack wornCopy(Def d) {
        ItemStack it = make(d);
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.RING_WORN, PersistentDataType.BYTE, (byte) 1));
        return it;
    }

    /** 설명 칸: 효과 줄 (흐린 옛 금빛), 고리만 있는 효과가 있으면 그 밑에 재빛 한 줄, 그리고 ring.&lt;id&gt;.lore. */
    static List<Component> lore(Def d) {
        List<Component> out = new ArrayList<>();
        boolean pending = false;
        for (String e : d.effects()) {
            out.add(switch (e) {
                case STAMINA_REGEN -> Lang.c("ring.effect.stamina-regen", "pct", signed(Math.round((d.staminaRegen() - 1.0) * 100.0)));
                case POISE -> Lang.c("ring.effect.poise", "pct", signed(Math.round(d.poise() * 100.0)));
                case PARRY_WINDOW -> Lang.c("ring.effect.parry-window", "sec",
                        (d.parryWindow() < 0 ? "-" : "+") + String.format(Locale.ROOT, "%.2f", Math.abs(d.parryWindow()) / 20.0));
                default -> Lang.c("ring.effect.soul-guard");
            });
            pending |= !LIVE.contains(e);
        }
        if (pending) out.add(Lang.c("ring.effect.pending"));
        out.addAll(Lang.lines("ring." + d.id() + ".lore")); // lang-dyn: ring.*.lore
        return out;
    }

    private static String signed(long v) {
        return (v < 0 ? "-" : "+") + Math.abs(v);
    }

    /** 반지 id (souls:ring), 반지가 아니면 null. */
    public static String idOf(ItemStack it) {
        return Items.tag(it, Keys.RING);
    }

    /** 반지 칸의 사본인가 (souls:ring_worn). */
    public static boolean isWornCopy(ItemStack it) {
        if (it == null || it.isEmpty() || !it.hasItemMeta()) return false;
        return it.getItemMeta().getPersistentDataContainer().has(Keys.RING_WORN, PersistentDataType.BYTE);
    }

    /** 이 아이템의 반지 정의 (반지가 아니거나 rings.yml 에 없는 id 면 null). */
    public Def of(ItemStack it) {
        return get(idOf(it));
    }
}
