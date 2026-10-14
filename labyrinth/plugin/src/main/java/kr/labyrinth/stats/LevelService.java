package kr.labyrinth.stats;

import java.time.Duration;
import kr.labyrinth.Services;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.LevelUpEvent;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;

/**
 * 레벨 1~50, 경험치 곡선(GDD §16.1), 레벨업마다 스탯 포인트 5(config). 레벨업 연출 + {@link LevelUpEvent}.
 */
public final class LevelService implements Module {

    private final Services services;
    private XpCurve curve = XpCurve.DEFAULT;

    public LevelService(Services services) { this.services = services; }

    @Override
    public String name() { return "levels"; }

    @Override
    public void enable() { curve = XpCurve.of(services.settings().level()); }

    @Override
    public void reload() { enable(); }

    public XpCurve curve() { return curve; }

    public int maxLevel() { return curve.maxLevel(); }

    /** 현재 레벨에서 다음 레벨까지 진행도 0~1. */
    public double progress(Player p) {
        PlayerData d = services.data().get(p);
        long need = curve.xpToNext(d.level());
        return need <= 0 ? 1.0 : Math.min(1.0, (double) d.xp() / need);
    }

    /**
     * 보상 경험치: base × (1 + xp_bonus). 몹 처치 등은 이걸 쓴다(난이도 배율은 호출자가 base 에 곱함 — InstanceContext.xpMultiplier).
     * @return 실제 지급량
     */
    public long reward(Player p, double base) {
        double mult = 1.0 + services.stats().get(p).xpBonus();
        long amount = Math.max(0, Math.round(base * mult));
        addXp(p, amount);
        return amount;
    }

    /** 경험치를 그대로 더한다 (보너스 없음). 레벨업 처리 포함. */
    public void addXp(Player p, long amount) {
        if (amount <= 0) return;
        PlayerData d = services.data().get(p);
        int old = d.level();
        long[] r = curve.apply(old, d.xp(), amount);
        d.xp(r[1]);
        if ((int) r[0] != old) applyLevel(p, d, old, (int) r[0]);
    }

    /** 관리자: 레벨 직접 설정. 오르면 포인트 지급, 내리면 분배 초기화 후 포인트 재계산. */
    public void setLevel(Player p, int level) {
        PlayerData d = services.data().get(p);
        int lv = Math.max(1, Math.min(curve.maxLevel(), level));
        int old = d.level();
        d.xp(0);
        if (lv > old) {
            applyLevel(p, d, old, lv);
        } else if (lv < old) {
            d.resetAllocation();
            d.level(lv);
            d.statPoints((lv - 1) * services.settings().level().pointsPerLevel());
            services.stats().recalc(p);
        }
    }

    /** 레벨 lv 에서 받아야 할 총 포인트 (분배 + 미분배). */
    public int totalPointsAt(int lv) {
        return (Math.max(1, lv) - 1) * services.settings().level().pointsPerLevel();
    }

    private void applyLevel(Player p, PlayerData d, int old, int lv) {
        d.level(lv);
        d.statPoints(d.statPoints() + (lv - old) * services.settings().level().pointsPerLevel());
        services.stats().recalc(p);
        services.stats().heal(p, services.stats().maxHp(p));
        p.showTitle(Title.title(Text.mm("<gradient:#ffe27a:#ff9f43><b>LEVEL UP</b></gradient>"),
                Text.mm("<gray>Lv.<white>" + old + "</white> → <yellow><b>" + lv + "</b></yellow>  <gray>스탯 포인트 <green>+"
                        + (lv - old) * services.settings().level().pointsPerLevel()),
                Title.Times.times(Duration.ofMillis(200), Duration.ofMillis(1800), Duration.ofMillis(500))));
        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.2f);
        p.getWorld().spawnParticle(Particle.END_ROD, p.getLocation().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.05);
        p.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, p.getLocation().add(0, 1, 0), 20, 0.5, 0.6, 0.5, 0);
        Text.send(p, "<yellow>레벨 " + lv + " 달성!</yellow> <gray>/스탯</gray> <white>으로 포인트를 분배하세요.");
        Bukkit.getPluginManager().callEvent(new LevelUpEvent(p, old, lv));
    }
}
