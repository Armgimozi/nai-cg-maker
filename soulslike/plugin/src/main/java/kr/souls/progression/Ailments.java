package kr.souls.progression;

import kr.souls.Souls;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityPotionEffectEvent;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.util.EnumSet;
import java.util.Locale;
import java.util.Set;

/**
 * 상태 이상 저항 (지능, 5.2). 확률이 아니라 셈이다: 해로운 효과 (독·시듦·구속·나약함·실명·멀미·어둠·채굴 피로·공중 부양 …) 와 불붙음의
 * 길이를 × (1 − 저항) 으로 줄인다. 줄어든 길이가 10틱 밑이면 걸리지 않는다 (털어 냈다). 세기 (단계) 는 그대로.
 * 적이 거는 효과 (스킬 엔진, Cause.PLUGIN) 도 이 길을 지난다. 플러그인이 일부러 거는 움직임 잠금 (치명타 굳히기, 공격 중 감속, M1) 만
 * {@link #internal} 안에서 걸어 뺀다.
 * EntityPotionEffectEvent 에는 새 효과를 바꾸는 길이 없어서: 취소하고 줄인 효과를 internal 안에서 다시 건다 (원래 거는 일은 취소로
 * 멈추므로 겹치지 않는다. 효과를 건 물체 (처치 기록) 는 잃는다, 검토 T12).
 * 축적 막대 (독·출혈, 전체판) 의 최대치는 × (1 + 저항) 이다 (3.7).
 */
public final class Ailments implements Listener {
    /** 길이를 줄이지 않는 원인: 명령·죽음·우유·끝남·신호기·전달체 (그 사람이 일부러 받은 것이거나 지우는 일) */
    private static final Set<EntityPotionEffectEvent.Cause> SKIP = EnumSet.of(EntityPotionEffectEvent.Cause.COMMAND,
            EntityPotionEffectEvent.Cause.DEATH, EntityPotionEffectEvent.Cause.MILK, EntityPotionEffectEvent.Cause.EXPIRATION,
            EntityPotionEffectEvent.Cause.BEACON, EntityPotionEffectEvent.Cause.CONDUIT);
    /** 이보다 짧아지면 걸리지 않는다 (틱) */
    public static final int MIN_TICKS = 10;

    private static int internal;
    private final Souls plugin;

    public Ailments(Souls plugin) {
        this.plugin = plugin;
    }

    /** 플러그인이 일부러 거는 효과 (저항으로 줄이지 않는다). 다시 거는 일에도 쓴다. */
    public static void internal(Runnable r) {
        internal++;
        try {
            r.run();
        } finally {
            internal--;
        }
    }

    public double resist(Player p) {
        return plugin.cfg().stats.statusResist.at(plugin.stats().of(p).intel());
    }

    /** 줄인 길이 (틱). MIN_TICKS 밑이면 0. */
    public static int shorten(int ticks, double resist) {
        int t = (int) Math.round(ticks * (1 - Math.max(0, Math.min(0.95, resist))));
        return t < MIN_TICKS ? 0 : t;
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEffect(EntityPotionEffectEvent e) {
        if (internal > 0 || !(e.getEntity() instanceof Player p)) return;
        if (e.getAction() != EntityPotionEffectEvent.Action.ADDED && e.getAction() != EntityPotionEffectEvent.Action.CHANGED) return;
        if (SKIP.contains(e.getCause())) return;
        PotionEffect eff = e.getNewEffect();
        PotionEffectType type = e.getModifiedType();
        if (eff == null || type.getCategory() != PotionEffectType.Category.HARMFUL || type.isInstant() || eff.isInfinite()) return;
        double r = resist(p);
        if (r <= 1e-9) return;
        int from = eff.getDuration();
        int to = shorten(from, r);
        e.setCancelled(true);
        if (to > 0) internal(() -> p.addPotionEffect(eff.withDuration(to)));
        plugin.test(p, String.format(Locale.ROOT, "AILMENT type=%s from=%d to=%d res=%.2f cause=%s", type.key().value(), from, to, r,
                e.getCause().name().toLowerCase(Locale.ROOT)));
    }

    /** 불붙음 (불 위, 불화살, 가마지기 망자의 불씨): 타는 시간을 줄인다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onCombust(EntityCombustEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        double r = resist(p);
        if (r <= 1e-9) return;
        float from = e.getDuration();
        int ticks = shorten(Math.round(from * 20), r);
        if (ticks <= 0) {
            e.setCancelled(true);
        } else {
            e.setDuration(ticks / 20f);
        }
        plugin.test(p, String.format(Locale.ROOT, "AILMENT type=fire from=%d to=%d res=%.2f", Math.round(from * 20), ticks, r));
    }
}
