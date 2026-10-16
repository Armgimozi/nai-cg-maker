package kr.labyrinth.combat;

import org.bukkit.configuration.ConfigurationSection;

/**
 * 시전 무기 마법탄 설정 (0.3.6.1, config.yml {@code combat.caster_bolt}). 키가 없으면 {@link #DEFAULT} — 예전 config.yml 에는 이 블록이 없다.
 * {@code caster_bolt: false} 한 줄도 받는다 (= 끔, 예전처럼 근접 휘두르기).
 *
 * @param enabled      켜짐 (끄면 시전 무기도 근접 휘두르기)
 * @param range        날아가는 거리 (블록, 4~32)
 * @param speed        한 틱(0.05초)에 나아가는 거리 (블록, 0.5~6) — 기본 2.5 = 초당 50칸, 16칸에 약 0.33초
 * @param radius       맞는 판정 굵기 (블록, 0~1) — 대상 히트박스를 이만큼 키워서 본다
 * @param pvpKnockback 플레이어를 맞히면 밀어내는 세기 (DamageService 단위, 0~3 — 화살 0.6 과 같음). 몹은 밀지 않는다 (예전 휘두르기와 같음)
 * @param pvpDamage    다른 플레이어를 맞힐 때 한 방 배율 (0.1~2, 기본 0.65). 예전 휘두르기는 활을 든 상대에게 붙기 어려워 1:1 에서 덜 맞았다 —
 *                     마법탄은 활처럼 멀리서 맞히므로 그만큼 줄여 1:1 승률을 0.3.6 근처로 (1:1 모의 실험, GDD §11.2.1). 몹에게는 1
 * @param trail        날아가는 입자 (무기 색)
 * @param sound        쏘는·맞는 작은 소리
 */
public record CasterBoltConfig(boolean enabled, double range, double speed, double radius, double pvpKnockback,
                               double pvpDamage, boolean trail, boolean sound) {

    public static final CasterBoltConfig DEFAULT = new CasterBoltConfig(true, 16, 2.5, 0.3, 0.6, 0.65, true, true);

    public CasterBoltConfig {
        range = clamp(range, 4, 32, 16);
        speed = clamp(speed, 0.5, 6, 2.5);
        radius = clamp(radius, 0, 1, 0.3);
        pvpKnockback = clamp(pvpKnockback, 0, 3, 0.6);
        pvpDamage = clamp(pvpDamage, 0.1, 2, 0.65);
    }

    /** 끔 (나머지는 기본값). */
    public CasterBoltConfig off() { return new CasterBoltConfig(false, range, speed, radius, pvpKnockback, pvpDamage, trail, sound); }

    /** 날아가는 동안 걸리는 최대 틱 (한 번 쏜 마법탄이 아무리 늦어도 이 안에 사라진다). */
    public int maxTicks() { return (int) Math.ceil(range / speed) + 1; }

    /**
     * config.yml 의 combat 블록에서 읽기 (null = 기본값). {@code caster_bolt} 가 없으면 기본값, false/true 한 줄이면 켬·끔만.
     */
    public static CasterBoltConfig from(ConfigurationSection combat) {
        if (combat == null) return DEFAULT;
        Object raw = combat.get("caster_bolt"); // 파일에 없으면 jar 기본값 (getConfigurationSection 처럼 빈 블록을 만들지 않음)
        if (raw instanceof Boolean b) return b ? DEFAULT : DEFAULT.off();
        if (!(raw instanceof ConfigurationSection s)) return DEFAULT;
        CasterBoltConfig d = DEFAULT;
        return new CasterBoltConfig(s.getBoolean("enabled", d.enabled()), s.getDouble("range", d.range()),
                s.getDouble("speed", d.speed()), s.getDouble("radius", d.radius()),
                s.getDouble("pvp_knockback", d.pvpKnockback()), s.getDouble("pvp_damage", d.pvpDamage()),
                s.getBoolean("trail", d.trail()), s.getBoolean("sound", d.sound()));
    }

    private static double clamp(double v, double lo, double hi, double def) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return def;
        return Math.max(lo, Math.min(hi, v));
    }
}
