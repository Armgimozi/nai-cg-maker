package kr.souls.combat;

import org.bukkit.entity.Entity;
import org.bukkit.util.Vector;

import java.util.Locale;

/**
 * 한 대 (3.7 의 "한 번 맞힐 때"). 플레이어의 동작 (P1a MoveRunner), 활 (P7), 치명타 (P3), 낙하 (P6) 가 만들어 Foes.hit 에 넘긴다.
 * 바뀌지 않는 값이고 늘 {@link #builder()} 로 만든다: 나중 묶음이 칸을 더해도 부르는 쪽이 깨지지 않게 (M1_PLAN 1절의 P1-0 계약).
 * <ul>
 *   <li>moveId: 동작 id (light1, heavy, running, riposte, arrow …). 시험 줄과 기록에만 쓴다.</li>
 *   <li>cls: 무기 분류 (weapons.yml class). 치명 배율·강인도 표를 고른다.</li>
 *   <li>raw: 원피해 = {@link DamageCalc#hit} (AR × 동작 배율/100 × 맞받아치기 × 치명). 방어 전 값.</li>
 *   <li>poise: 강인도 피해 (3.8, P4 가 쓴다).</li>
 *   <li>type: 피해 종류. 적의 흡수·약점표 (enemies.yml) 를 고른다.</li>
 *   <li>counter: 맞받아치기 (적의 준비·판정 틱에 맞혔다, 3.6). raw 에는 이미 들어 있고, 강인도 배율 (P4) 과 시험 줄이 본다.</li>
 *   <li>crit: 치명 배율 (combat.crit, 1 이면 보통). raw 에는 이미 들어 있다.</li>
 *   <li>dir: 맞는 쪽으로 미는 수평 방향 (길이 1, 없으면 null): 아파하는 몸짓의 방향과 밀림.</li>
 *   <li>attacker: 때린 것 (플레이어, 화살을 쏜 사람). 없을 수 있다.</li>
 * </ul>
 */
public final class Hit {
    /** 피해 종류 (3.7 의 약점표: 참격·타격·찌르기·불. 술은 magic). standard 는 종류를 따지지 않는 보통 물리. */
    public enum Type {
        STANDARD, SLASH, STRIKE, THRUST, FIRE, MAGIC;

        /** "slash" 같은 이름 (모르면 def). */
        public static Type parse(String s, Type def) {
            if (s == null) return def;
            try {
                return valueOf(s.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return def;
            }
        }

        /** 물리 피해인가 (막기의 non-physical, 방어력과 마법 방어력 고르기). */
        public boolean physical() {
            return this != FIRE && this != MAGIC;
        }
    }

    private final String moveId;
    private final String cls;
    private final double raw;
    private final double poise;
    private final Type type;
    private final boolean counter;
    private final double crit;
    private final Vector dir;
    private final Entity attacker;

    private Hit(Builder b) {
        this.moveId = b.moveId;
        this.cls = b.cls;
        this.raw = b.raw;
        this.poise = b.poise;
        this.type = b.type;
        this.counter = b.counter;
        this.crit = b.crit;
        this.dir = b.dir == null ? null : b.dir.clone();
        this.attacker = b.attacker;
    }

    public static Builder builder() {
        return new Builder();
    }

    /** 이 한 대를 바탕으로 몇 칸만 바꾼 새 한 대를 만든다. */
    public Builder toBuilder() {
        Builder b = new Builder();
        b.moveId = moveId;
        b.cls = cls;
        b.raw = raw;
        b.poise = poise;
        b.type = type;
        b.counter = counter;
        b.crit = crit;
        b.dir = dir;
        b.attacker = attacker;
        return b;
    }

    public String moveId() { return moveId; }
    public String cls() { return cls; }
    public double raw() { return raw; }
    public double poise() { return poise; }
    public Type type() { return type; }
    public boolean counter() { return counter; }
    public double crit() { return crit; }
    /** 사본 (바꿔도 이 한 대는 그대로). null 일 수 있다. */
    public Vector dir() { return dir == null ? null : dir.clone(); }
    public Entity attacker() { return attacker; }

    @Override
    public String toString() {
        return String.format(Locale.ROOT, "Hit[move=%s cls=%s raw=%.2f poise=%.1f type=%s counter=%s crit=%.2f]", moveId, cls, raw, poise,
                type, counter, crit);
    }

    /** 칸마다 기본값이 있다 (raw 0, poise 0, STANDARD, counter 거짓, crit 1). build 가 값의 범위를 본다. */
    public static final class Builder {
        private String moveId = "-";
        private String cls = "-";
        private double raw;
        private double poise;
        private Type type = Type.STANDARD;
        private boolean counter;
        private double crit = 1.0;
        private Vector dir;
        private Entity attacker;

        private Builder() {}

        public Builder moveId(String v) { moveId = v == null ? "-" : v; return this; }
        public Builder cls(String v) { cls = v == null ? "-" : v; return this; }
        public Builder raw(double v) { raw = v; return this; }
        public Builder poise(double v) { poise = v; return this; }
        public Builder type(Type v) { type = v == null ? Type.STANDARD : v; return this; }
        public Builder counter(boolean v) { counter = v; return this; }
        public Builder crit(double v) { crit = v; return this; }
        /** 수평으로 눕혀 길이 1 로 맞춘다 (0 이면 null). */
        public Builder dir(Vector v) {
            if (v == null) {
                dir = null;
                return this;
            }
            Vector h = v.clone().setY(0);
            dir = h.lengthSquared() < 1e-9 ? null : h.normalize();
            return this;
        }
        public Builder attacker(Entity v) { attacker = v; return this; }

        /** @throws IllegalArgumentException raw·poise 가 음수이거나 수가 아닐 때, crit 이 0 이하일 때 */
        public Hit build() {
            if (!(raw >= 0) || Double.isInfinite(raw)) throw new IllegalArgumentException("raw " + raw);
            if (!(poise >= 0) || Double.isInfinite(poise)) throw new IllegalArgumentException("poise " + poise);
            if (!(crit > 0) || Double.isInfinite(crit)) throw new IllegalArgumentException("crit " + crit);
            return new Hit(this);
        }
    }
}
