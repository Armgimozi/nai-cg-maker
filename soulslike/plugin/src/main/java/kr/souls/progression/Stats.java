package kr.souls.progression;

import kr.souls.Souls;
import kr.souls.combat.DamageCalc;
import kr.souls.item.Weapons;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

import java.util.Locale;

/**
 * 플레이어의 능력치와 그 값 (5.2). 능력치는 프로필에 있고 (출신을 고르기 전에는 모두 10), 값은 {@link Derived} 의 셈이다.
 * 공격력·공격 속도는 든 근접 무기 (없으면 단축 슬롯의 첫 souls 근접 무기), 술 세기는 든 촉매 (없으면 단축 슬롯의 첫 촉매) 기준.
 * 양손 잡기는 왼손이 빈 근접 무기다 (근력 ×1.5, 2.1).
 */
public final class Stats {
    private final Souls plugin;

    public Stats(Souls plugin) {
        this.plugin = plugin;
    }

    public StatBlock of(Player p) {
        return plugin.profiles().of(p).stats();
    }

    public int level(Player p) {
        return of(p).level();
    }

    public Derived derived(Player p) {
        return derived(p, of(p));
    }

    /** 능력치를 s 로 가정한 값 (레벨 올리기 창의 미리보기). 무게는 지금 든 것 그대로. */
    public Derived derived(Player p, StatBlock s) {
        Weapons.Def melee = melee(p);
        Weapons.Def cat = catalyst(p);
        return Derived.of(s, plugin.cfg().stats, plugin.cfg().load, arms(melee), melee != null && twoHanded(p, melee), arms(cat),
                plugin.load().weight(p), plugin.cfg().stamina.regenPerTick());
    }

    public static DamageCalc.Arms arms(Weapons.Def d) {
        if (d == null) return null;
        return new DamageCalc.Arms(d.attack(), d.scaling().get("str"), d.scaling().get("dex"), d.scaling().get("int"),
                d.requires().getOrDefault("str", 0), d.requires().getOrDefault("dex", 0), d.requires().getOrDefault("int", 0));
    }

    /** 근접 무기 (공격력이 있고 촉매·방패가 아닌 것). 든 것이 아니면 단축 슬롯의 첫 것. */
    public Weapons.Def melee(Player p) {
        PlayerInventory inv = p.getInventory();
        Weapons.Def held = plugin.weapons().of(inv.getItemInMainHand());
        if (isMelee(held)) return held;
        for (int i = 0; i < 9; i++) {
            Weapons.Def d = plugin.weapons().of(inv.getItem(i));
            if (isMelee(d)) return d;
        }
        return null;
    }

    /** 촉매 (분류가 catalyst_*). 든 것이 아니면 단축 슬롯의 첫 것. */
    public Weapons.Def catalyst(Player p) {
        PlayerInventory inv = p.getInventory();
        Weapons.Def held = plugin.weapons().of(inv.getItemInMainHand());
        if (isCatalyst(held)) return held;
        for (int i = 0; i < 9; i++) {
            Weapons.Def d = plugin.weapons().of(inv.getItem(i));
            if (isCatalyst(d)) return d;
        }
        return null;
    }

    /** 근접 무기: 공격력이 있는 주손 무기 가운데 방패·촉매·활이 아닌 것 (활로 때리는 것은 근접 한 대가 아니다, 검토 bow-counts-as-melee). */
    public static boolean isMelee(Weapons.Def d) {
        return d != null && d.attack() > 0 && !d.shield() && Weapons.MAIN.equals(d.hand()) && !isCatalyst(d) && !Weapons.BOW.equals(d.use());
    }

    public static boolean isCatalyst(Weapons.Def d) {
        return d != null && d.cls().startsWith("catalyst");
    }

    /** 양손 잡기: 활이 아닌 근접 무기를 들고 왼손이 비었다 (2.1). 들지 않은 무기는 왼손이 비었으면 양손으로 본다. */
    public boolean twoHanded(Player p, Weapons.Def d) {
        if (d == null || Weapons.BOW.equals(d.use())) return false;
        ItemStack off = p.getInventory().getItemInOffHand();
        return off == null || off.isEmpty();
    }

    /** 시험 줄 STATS (5.9, 13.2 의 stats.js). */
    public String line(Player p) {
        StatBlock s = of(p);
        Derived d = derived(p);
        var pr = plugin.profiles().of(p);
        Weapons.Def m = melee(p), c = catalyst(p);
        return String.format(Locale.ROOT,
                "STATS level=%d origin=%s souls=%d vig=%d mnd=%d end=%d str=%d dex=%d int=%d hp=%.0f def=%.1f mana=%.0f mres=%.1f slots=%d "
                        + "st=%.0f regen=%.1f atk=%.0f weapon=%s twohand=%s aspd=%.4f load=%.1f/%.1f/%s move=%.4f spell=%.0f catalyst=%s ailment=%.3f",
                s.level(), pr.origin() == null ? "-" : pr.origin(), pr.souls(), s.vig(), s.mnd(), s.end(), s.str(), s.dex(), s.intel(),
                d.maxHp(), d.defense(), d.maxMana(), d.magicRes(), d.slots(), d.maxStamina(), d.regenPerSec(), d.attack(),
                m == null ? "-" : m.id(), d.twoHanded(), d.attackSpeed(), d.weight(), d.cap(), d.tier().id(), d.move(), d.spellPower(),
                c == null ? "-" : c.id(), d.ailment());
    }
}
