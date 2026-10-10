package kr.souls.combat;

import kr.souls.Config;
import kr.souls.Souls;
import kr.souls.item.Weapons;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.Locale;
import java.util.UUID;

/**
 * 패링 (3.5, DECISIONS 2026-10-10: 다크 소울 방식). F 를 누르면 <b>왼손에 든 것</b> (작은·중형 방패, 패링 단검, 왼손에 든 한손 무기)
 * 으로 쳐낸다. 주무기로 쳐내는 세키로 방식이 아니다. 성공하면 적이 무너지고, 주무기 (좌클릭) 로 치명타 (리포스트) 를 넣는다.
 * 창은 왼손 물건의 <b>분류</b>마다 (combat.parry.windows, weapons.yml 의 class) 이고 설명 칸에는 보이지 않는다 (다크 소울처럼).
 * 대방패·긴 무기 (대검·미늘창·창)·활·촉매, 그리고 빈 왼손 (combat.parry.empty 기본 0) 은 패링하지 못한다: F 는 아무것도 하지 않는다.
 * 창 = 분류의 창 + 반지 (parry-window) + 난이도 (parry-window-bonus, PvE 만), 가장 짧아도 combat.parry.min 틱 (창이 없는 것은 그대로 없다).
 *
 * <p>지금 (M1 전) 하는 것: F 를 누른 틱과 그 패링의 창 몫을 {@link CombatState} 에 적고 시험 줄을 낸다. 적의 공격을 받아 판정하는 것과
 * 성공한 뒤의 무너짐·치명타는 M1 이 아래 고리를 부른다 (지금 부르는 곳은 없다):
 * <ul>
 *   <li>{@link #judge}: 들어오는 공격 대기열 (3.9) 의 판정 2 "쳐냄". 공격이 닿은 틱 C 와 핑 늦춤 d 로, 마지막 F 가 [C − W, C + d] 안이면 true.</li>
 *   <li>{@link #parried}: 성공. 연타 잠금을 짧게 (lock-hit) 하고 치명타 기회 (그 적, 끝 틱) 를 연다. 시험 줄 PARRIED.</li>
 *   <li>{@link #riposte}: 그 적에게 치명타 기회가 열려 있나. M1 의 약·강 공격 입력 (주무기, 좌클릭) 이 부르고, 열려 있으면 그 입력이
 *       치명타 (3.5 "치명타 (리포스트)") 가 된다.</li>
 * </ul>
 * 시험 줄: {@code PARRY item= class= base= ring= diff= window= sneak= t=} (창이 열림), {@code PARRY_NONE item= class= why=cannot|rolling sneak= t=}
 * (패링하지 못하는 왼손: F 는 아무것도 하지 않는다), {@code PARRY_LOCKED since= lock= sneak= t=} (연타 잠금). sneak 은 웅크리기 키를 누른 채였나
 * (roll-key: f·both 면 웅크리기 키 + F 가 패링이다).
 */
public final class Parry {
    /** 왼손이 비었을 때의 분류 이름 (시험 줄) */
    public static final String EMPTY = "empty";
    /** 왼손에 souls 물건이 아닌 것이 있을 때 (패링하지 못한다) */
    public static final String OTHER = "other";

    private final Souls plugin;

    public Parry(Souls plugin) {
        this.plugin = plugin;
    }

    // ------------------------------------------------------------------ 순수 셈 (13.1 의 ParryTest)

    /** 왼손 물건의 분류 이름: souls 물건이면 그 class, 비었으면 EMPTY, 그 밖은 OTHER. */
    public static String source(Weapons.Def off, boolean offEmpty) {
        if (offEmpty) return EMPTY;
        return off == null ? OTHER : off.cls();
    }

    /** 왼손 물건의 바탕 창 (틱). 0 이면 패링하지 못한다. */
    public static int baseWindow(Config.ParryCfg cfg, Weapons.Def off, boolean offEmpty) {
        if (offEmpty) return Math.max(0, cfg.empty());
        return off == null ? 0 : cfg.window(off.cls());
    }

    /** 바탕 창에 덧셈 (반지·난이도) 을 더한 창. 바탕이 0 이면 0 (창이 없는 것은 그대로 없다), 아니면 가장 짧아도 min. */
    public static int window(int base, int bonus, int min) {
        if (base <= 0) return 0;
        return Math.max(min, base + bonus);
    }

    /** 연타 잠금: 지난 F (lastPress) 에서 now 까지가 잠금 틱 (지난 패링이 쳐냈으면 lockHit, 아니면 lockMiss) 보다 짧으면 true. */
    public static boolean locked(long now, long lastPress, boolean lastHit, int lockMiss, int lockHit) {
        return now - lastPress < (lastHit ? lockHit : lockMiss);
    }

    /** 판정 (3.5 의 그림): F 를 누른 틱 raise 가 [contact − window, contact + delay] 안이면 쳐낸다. 창이 0 이면 늘 false. */
    public static boolean inWindow(long raise, long contact, int window, int delay) {
        return window > 0 && raise >= contact - window && raise <= contact + Math.max(0, delay);
    }

    // ------------------------------------------------------------------ F

    /** F (손 바꾸기, Roll.onSwap 이 부른다: 구르지 않을 때). 왼손 물건으로 패링 창을 연다. */
    public void press(Player p) {
        long now = plugin.ticker().now();
        CombatState st = CombatState.of(p);
        ItemStack offItem = p.getInventory().getItemInOffHand();
        boolean offEmpty = offItem == null || offItem.isEmpty();
        Weapons.Def off = offEmpty ? null : plugin.weapons().of(offItem);
        String cls = source(off, offEmpty);
        String item = off == null ? "-" : off.id();
        Config.ParryCfg cfg = plugin.cfg().parry;
        int base = baseWindow(cfg, off, offEmpty);
        String sneak = " sneak=" + p.isSneaking();
        if (base <= 0) {
            plugin.test(p, "PARRY_NONE item=" + item + " class=" + cls + " why=cannot" + sneak + " t=" + now);
            return;
        }
        if (st.rolling(now)) {
            plugin.test(p, "PARRY_NONE item=" + item + " class=" + cls + " why=rolling" + sneak + " t=" + now);
            return;
        }
        if (locked(now, st.parryAt, st.parryHit, cfg.lockMiss(), cfg.lockHit())) {
            plugin.test(p, "PARRY_LOCKED since=" + (now - st.parryAt) + " lock=" + (st.parryHit ? cfg.lockHit() : cfg.lockMiss()) + sneak + " t=" + now);
            return;
        }
        int ring = plugin.ringSlots().parryWindowBonus(p);
        int diff = plugin.difficulty().parryWindowBonus();
        st.parryAt = now;
        st.parryBase = base;
        st.parryRing = ring;
        st.parryHit = false;
        plugin.test(p, String.format(Locale.ROOT, "PARRY item=%s class=%s base=%d ring=%d diff=%d window=%d sneak=%s t=%d", item, cls, base, ring, diff,
                window(base, ring + diff, cfg.min()), p.isSneaking(), now));
    }

    // ------------------------------------------------------------------ M1 의 고리

    /**
     * 판정 고리 (3.9 의 판정 2): 공격이 닿은 틱 contact, 핑 늦춤 delay. pvp 면 난이도 덧셈을 더하지 않는다 (5.7). 마지막 F 가 창 안이면 true.
     * M1 의 들어오는 공격 대기열이 부른다 (그 공격이 쳐낼 수 있는 공격이고 정면 ±60°·거리 4.5칸 안인지는 대기열이 본다).
     */
    public boolean judge(Player p, long contact, int delay, boolean pvp) {
        CombatState st = CombatState.of(p);
        int bonus = st.parryRing + (pvp ? 0 : plugin.difficulty().parryWindowBonus());
        return inWindow(st.parryAt, contact, window(st.parryBase, bonus, plugin.cfg().parry.min()), delay);
    }

    /**
     * 성공 고리: 적 foe 를 쳐냈다. 연타 잠금을 짧게 (lock-hit) 하고, 끝 틱 until 까지 그 적에게 치명타 기회를 연다 (잡몹 30틱, 보스는 자세가
     * 다 찼을 때 40틱, 3.5). 무너짐 (적의 경직·자세) 은 적 두뇌 (M2) 가 한다.
     */
    public void parried(Player p, Entity foe, long until) {
        CombatState st = CombatState.of(p);
        st.parryHit = true;
        st.riposteFoe = foe == null ? null : foe.getUniqueId();
        st.riposteUntil = until;
        plugin.test(p, "PARRIED foe=" + (foe == null ? "-" : foe.getType().key().value()) + " until=" + until + " t=" + plugin.ticker().now());
    }

    /** 치명타 고리: now 에 foe 에게 치명타 기회가 열려 있나 (주무기 좌클릭이 치명타가 되는가). */
    public boolean riposte(Player p, Entity foe, long now) {
        CombatState st = CombatState.of(p);
        UUID id = st.riposteFoe;
        return id != null && foe != null && id.equals(foe.getUniqueId()) && now <= st.riposteUntil;
    }
}
