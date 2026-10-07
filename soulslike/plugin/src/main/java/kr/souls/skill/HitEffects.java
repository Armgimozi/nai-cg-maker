package kr.souls.skill;

import kr.souls.util.Fx;
import kr.souls.util.P;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Registry;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

public final class HitEffects {
    private static Logger log = Logger.getLogger("AugmentSkyblock");
    public static final String STUN_TAG = "augsky_stunned";

    private static final Set<String> NEGATIVE = Set.of("slowness", "mining_fatigue", "instant_damage", "nausea",
            "blindness", "hunger", "weakness", "poison", "wither", "levitation", "unluck", "darkness",
            "bad_omen", "infested", "oozing", "weaving", "wind_charged");

    private HitEffects() {}

    public static void setLogger(Logger l) { log = l; }

    public static List<HitEffect> parseList(List<Map<?, ?>> raw) {
        List<HitEffect> out = new ArrayList<>();
        for (Map<?, ?> m : raw) {
            HitEffect e = parse(normalize(m));
            if (e != null) out.add(e);
        }
        return out;
    }

    /**
     * 축약형을 풀어 쓴다. 첫 키가 효과 이름이다.
     * {damage: 8} → {type: damage, value: 8}
     * {damage: 6, magic: true} → {type: damage, value: 6, magic: true}
     * {potion: {effect: speed, seconds: 3}} → {type: potion, effect: speed, seconds: 3}
     */
    public static P normalize(Map<?, ?> m) {
        P p = new P(m);
        if (p.has("type") || p.m.isEmpty()) return p;
        var it = p.m.entrySet().iterator();
        Map.Entry<String, Object> e = it.next();
        P q = new P(Map.of("type", e.getKey()));
        if (e.getValue() instanceof Map<?, ?> inner) {
            for (Map.Entry<?, ?> ie : inner.entrySet()) q.m.put(String.valueOf(ie.getKey()), ie.getValue());
        } else if (e.getValue() instanceof org.bukkit.configuration.ConfigurationSection cs) {
            q.m.putAll(cs.getValues(false));
        } else {
            q.m.put("value", e.getValue());
        }
        while (it.hasNext()) {
            Map.Entry<String, Object> rest = it.next();
            q.m.put(rest.getKey(), rest.getValue());
        }
        return q;
    }

    public static PotionEffectType potion(String name) {
        if (name == null) return null;
        String k = name.toLowerCase(Locale.ROOT).replace("minecraft:", "");
        PotionEffectType t = Registry.EFFECT.get(NamespacedKey.minecraft(k));
        if (t == null) log.warning("알 수 없는 포션 효과: " + name);
        return t;
    }

    public static void apply(List<HitEffect> list, SkillContext ctx, LivingEntity target, Location origin) {
        if (list == null) return;
        for (HitEffect e : list) {
            if (target.isDead() || !target.isValid()) {
                // 죽은 뒤에도 회복/사운드 같은 효과는 의미가 없으니 멈춘다
                break;
            }
            e.apply(ctx, target, origin);
        }
    }

    static HitEffect parse(P p) {
        String type = p.s("type", "").toLowerCase(Locale.ROOT);
        double value = p.d("value", Double.NaN);
        switch (type) {
            case "damage": {
                double amt = p.d("amount", Double.isNaN(value) ? 4 : value);
                boolean magic = p.b("magic", false) || "magic".equals(p.s("kind", ""));
                return (ctx, t, o) -> Combat.damage(ctx, t, amt * ctx.power, magic);
            }
            case "percent": {
                double ratio = p.d("ratio", Double.isNaN(value) ? 0.05 : value);
                double max = p.d("max", 30);
                return (ctx, t, o) -> {
                    double amt = Math.min(max, Combat.maxHealth(t) * ratio);
                    Combat.damage(ctx, t, amt * ctx.power, true);
                };
            }
            case "ignite": {
                int ticks = (int) (p.d("seconds", Double.isNaN(value) ? 3 : value) * 20);
                return (ctx, t, o) -> t.setFireTicks(Math.max(t.getFireTicks(), ticks));
            }
            case "potion": {
                PotionEffectType pt = potion(p.s("effect", "slowness"));
                int ticks = (int) (p.d("seconds", 3) * 20);
                int amp = p.i("amplifier", 0);
                if (pt == null) return null;
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(pt, ticks, amp, false, true, true));
            }
            case "slow": {
                int ticks = (int) (p.d("seconds", Double.isNaN(value) ? 2 : value) * 20);
                int amp = p.i("amplifier", 1);
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, ticks, amp, false, true, true));
            }
            case "poison": {
                int ticks = (int) (p.d("seconds", Double.isNaN(value) ? 4 : value) * 20);
                int amp = p.i("amplifier", 0);
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(PotionEffectType.POISON, ticks, amp, false, true, true));
            }
            case "wither": {
                int ticks = (int) (p.d("seconds", Double.isNaN(value) ? 4 : value) * 20);
                int amp = p.i("amplifier", 0);
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(PotionEffectType.WITHER, ticks, amp, false, true, true));
            }
            case "knockback": {
                double power = p.d("power", Double.isNaN(value) ? 0.8 : value);
                double up = p.d("upward", 0.3);
                return (ctx, t, o) -> push(t, o, power, up);
            }
            case "pull": {
                double power = p.d("power", Double.isNaN(value) ? 0.8 : value);
                return (ctx, t, o) -> push(t, o, -power, 0.15);
            }
            case "launch": {
                double power = p.d("power", Double.isNaN(value) ? 0.9 : value);
                return (ctx, t, o) -> {
                    double kb = kbResist(t);
                    Vector v = t.getVelocity();
                    v.setY(Math.max(v.getY(), power * (1 - kb * 0.8)));
                    t.setVelocity(v);
                };
            }
            case "freeze": {
                double sec = p.d("seconds", Double.isNaN(value) ? 2 : value);
                return (ctx, t, o) -> {
                    t.setFreezeTicks(Math.min(t.getMaxFreezeTicks() + 60, t.getFreezeTicks() + (int) (sec * 30)));
                    t.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, (int) (sec * 20), 2, false, true, true));
                    Fx.Spec s = new Fx.Spec(Particle.SNOWFLAKE, null);
                    s.spawn(t.getLocation().add(0, t.getHeight() / 2, 0), 12, 0.3, 0.02);
                };
            }
            case "stun": {
                double sec = p.d("seconds", Double.isNaN(value) ? 1 : value);
                return (ctx, t, o) -> stun(ctx, t, sec);
            }
            case "heal": {
                double amt = p.d("amount", Double.isNaN(value) ? 4 : value);
                return (ctx, t, o) -> {
                    Combat.heal(t, amt * ctx.power);
                    new Fx.Spec(Particle.HEART, null).spawn(t.getLocation().add(0, t.getHeight() + 0.3, 0), 2, 0.3, 0);
                };
            }
            case "heal_caster": {
                double amt = p.d("amount", Double.isNaN(value) ? 2 : value);
                return (ctx, t, o) -> Combat.heal(ctx.caster, amt);
            }
            case "lifesteal": {
                double ratio = p.d("ratio", Double.isNaN(value) ? 0.2 : value);
                return (ctx, t, o) -> Combat.heal(ctx.caster, ctx.lastDamage * ratio);
            }
            case "absorption": {
                double amt = p.d("amount", Double.isNaN(value) ? 4 : value);
                int ticks = (int) (p.d("seconds", 10) * 20);
                int amp = Math.max(0, (int) Math.ceil(amt / 4.0) - 1);
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(PotionEffectType.ABSORPTION, ticks, amp, false, true, true));
            }
            case "cleanse": {
                return (ctx, t, o) -> {
                    for (PotionEffect pe : t.getActivePotionEffects()) {
                        if (NEGATIVE.contains(pe.getType().getKey().getKey())) t.removePotionEffect(pe.getType());
                    }
                    t.setFireTicks(0);
                    t.setFreezeTicks(0);
                };
            }
            case "extinguish":
                return (ctx, t, o) -> t.setFireTicks(0);
            case "lightning": {
                return (ctx, t, o) -> {
                    t.getWorld().strikeLightningEffect(t.getLocation());
                    Fx.bolt(t.getLocation(), null);
                };
            }
            case "explosion": {
                return (ctx, t, o) -> {
                    new Fx.Spec(Particle.EXPLOSION, null).spawn(t.getLocation().add(0, 0.5, 0), 1, 0.1, 0);
                    Fx.sound(t.getLocation(), "entity.generic.explode", 0.8f, 1.2f);
                };
            }
            case "particle": {
                Fx.Spec spec = Fx.parse(p.s("particle", p.s("value", "CRIT")));
                int count = p.i("count", 10);
                double spread = p.d("spread", 0.3);
                return (ctx, t, o) -> {
                    if (spec != null) spec.spawn(t.getLocation().add(0, t.getHeight() / 2, 0), count, spread, 0.02);
                };
            }
            case "sound": {
                String snd = p.s("sound", p.s("value", "entity.player.attack.crit"));
                float vol = (float) p.d("volume", 1);
                float pitch = (float) p.d("pitch", 1);
                return (ctx, t, o) -> Fx.sound(t.getLocation(), snd, vol, pitch);
            }
            case "execute": {
                double th = p.d("threshold", Double.isNaN(value) ? 0.15 : value);
                return (ctx, t, o) -> {
                    if (Targets.isBoss(t) || t instanceof Player) return;
                    if (t.getHealth() / Combat.maxHealth(t) <= th) {
                        new Fx.Spec(Particle.DAMAGE_INDICATOR, null).spawn(t.getLocation().add(0, 1, 0), 15, 0.3, 0.1);
                        Combat.damage(ctx, t, t.getHealth() + t.getAbsorptionAmount() + 100, true);
                    }
                };
            }
            case "glow": {
                int ticks = (int) (p.d("seconds", Double.isNaN(value) ? 5 : value) * 20);
                return (ctx, t, o) -> t.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, ticks, 0, false, false, true));
            }
            default:
                log.warning("알 수 없는 효과 type: " + type);
                return null;
        }
    }

    static double kbResist(LivingEntity t) {
        AttributeInstance a = t.getAttribute(Attribute.KNOCKBACK_RESISTANCE);
        return a == null ? 0 : Math.min(1, a.getValue());
    }

    static void push(LivingEntity t, Location origin, double power, double up) {
        if (origin == null) return;
        Vector d = t.getLocation().toVector().subtract(origin.toVector()).setY(0);
        if (d.lengthSquared() < 1e-6) d = new Vector(0, 0, 0);
        else d.normalize();
        double kb = kbResist(t);
        double scale = 1 - kb * 0.8;
        Vector v = d.multiply(power * scale);
        v.setY(Math.max(t.getVelocity().getY(), up * scale));
        t.setVelocity(v);
    }

    static void stun(SkillContext ctx, LivingEntity t, double sec) {
        int ticks = (int) (sec * 20);
        new Fx.Spec(Particle.CRIT, null).spawn(t.getLocation().add(0, t.getHeight() + 0.2, 0), 8, 0.3, 0.05);
        if (t instanceof Player) {
            t.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, ticks, 5, false, true, true));
            return;
        }
        if (Targets.isBoss(t)) {
            t.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, ticks / 2, 3, false, true, true));
            return;
        }
        if (t instanceof Mob m && m.hasAI()) {
            m.setAI(false);
            // 기절 중에 서버가 꺼지면 AI 가 꺼진 채 저장되므로, 다시 불러올 때 풀 수 있게 표시해 둔다
            m.addScoreboardTag(STUN_TAG);
            ctx.plugin.getServer().getScheduler().runTaskLater(ctx.plugin, () -> {
                if (m.isValid()) {
                    m.setAI(true);
                    m.removeScoreboardTag(STUN_TAG);
                }
            }, ticks);
        }
    }
}
