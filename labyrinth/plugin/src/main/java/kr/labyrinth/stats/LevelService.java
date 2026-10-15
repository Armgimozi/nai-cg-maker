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
 * 레벨 1~50, 경험치 곡선(GDD §16.1), Lv.1 시작 포인트 5 + 레벨업마다 스탯 포인트 5(config). 레벨업 연출 + {@link LevelUpEvent}.
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
            d.statPoints(totalPointsAt(lv));
            services.stats().recalc(p);
        }
    }

    /** 레벨 lv 에서 받아야 할 총 포인트 (분배 + 미분배). */
    public int totalPointsAt(int lv) {
        return services.settings().level().totalPointsAt(lv);
    }

    /** PlayerData ext: 지금까지 받은 Lv.1 시작 포인트 수. */
    static final String START_POINTS_FLAG = "level.start_points";

    /**
     * Lv.1 시작 포인트를 아직 다 받지 않았으면 남은 몫을 미분배 포인트로 준다 (접속할 때 — 새 플레이어와,
     * 시작 포인트가 없던 판에서 넘어온 플레이어 모두 한 번). 받은 양은 ext 에 남겨 다시 주지 않는다.
     */
    public void ensureStartPoints(Player p) {
        PlayerData d = services.data().get(p);
        Object v = d.ext().get(START_POINTS_FLAG);
        int granted = v instanceof Number n ? n.intValue() : 0;
        int owed = services.settings().level().startPointsOwed(granted);
        if (owed <= 0) return;
        d.statPoints(d.statPoints() + owed);
        d.ext().put(START_POINTS_FLAG, granted + owed);
        d.markDirty();
        Text.send(p, "<gray>스탯 포인트 <green>+" + owed + "</green> 를 받았습니다. <white>/스탯</white> <gray>으로 분배하세요.");
    }

    /** PlayerData ext: 0.3.4 착용 조건 변경(레벨 → 능력치) 무료 초기화를 이미 받았는지. */
    static final String REQ_RESET_FLAG = "stats.req_reset_034";

    /**
     * 0.3.4 에서 장비 착용 조건이 레벨에서 요구 능력치로 바뀌었다. 예전 판에서 포인트를 이미 나눈 플레이어는
     * 새 조건에 맞게 다시 나눌 수 있도록 무료 초기화를 한 번 되돌려 준다 (접속할 때 한 번만).
     */
    public void ensureRequirementReset(Player p) {
        if (grantRequirementReset(services.data().get(p))) {
            Text.send(p, "<#c79bff>장비 착용 조건이 레벨에서 능력치로 바뀌었습니다.</#c79bff> <gray>/스탯</gray> <white>에서 스탯 초기화를 한 번 무료로 할 수 있습니다.");
        }
    }

    /** 순수 판정: 아직 안 받았으면 표시하고, 나눈 포인트가 있으면 무료 초기화를 되돌려 true. */
    static boolean grantRequirementReset(PlayerData d) {
        if (Boolean.TRUE.equals(d.ext().get(REQ_RESET_FLAG))) return false;
        d.ext().put(REQ_RESET_FLAG, true);
        d.markDirty();
        int spent = 0;
        for (int v : d.allocated().values()) spent += v;
        if (spent <= 0) return false;
        d.counter(kr.labyrinth.ui.menus.StatsMenu.FREE_RESET_KEY, 0);
        return true;
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
