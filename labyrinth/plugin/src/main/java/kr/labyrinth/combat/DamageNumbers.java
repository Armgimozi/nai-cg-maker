package kr.labyrinth.combat;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

/**
 * 떠오르는 피해 숫자 (TextDisplay, 기본 0.8초). 틱당 생성 수 제한으로 대규모 전투에서도 가볍게.
 * <ul>
 *   <li>기본 공격은 한 대마다 숫자 하나 (방어까지 깎인 최종 피해). 물리 노란색 · 마법 하늘색 · 치명 주황 굵게 · 고정·지속 보라.</li>
 *   <li>같은 틱 안에 같은 대상에게 여러 번 들어간 피해(광역 여러 타격 등)는 숫자 하나로 더한다.</li>
 *   <li>지속 피해 틱(보라)은 대상마다 0.5초 동안 더해서 하나로 띄운다 (빠른 무기·독 중첩에서 숫자 홍수 방지).</li>
 * </ul>
 */
public final class DamageNumbers {

    private static final int MAX_PER_TICK = 24;
    /** 지속 피해 숫자를 모으는 시간 (틱). */
    static final int DOT_WINDOW_TICKS = 10;

    private final Services services;
    private int spawnedThisTick;
    private int currentTick = -1;
    /** 이번 틱에 띄운 숫자 (대상·종류 → [표시, 합계]) — 같은 틱 여러 타격을 하나로. */
    private final Map<String, Object[]> thisTick = new HashMap<>();
    private int mergeTick = -1;
    /** 모으는 중인 지속 피해 (대상 → 합계). */
    private final Map<UUID, double[]> dotPending = new HashMap<>();

    public DamageNumbers(Services services) { this.services = services; }

    public enum Kind { DAMAGE, MAGIC, CRIT, PLAYER_HURT, HEAL, EVADE, BLOCK, TRUE }

    public void show(LivingEntity target, double amount, Kind kind) {
        if (!services.settings().combat().damageNumbers() || target == null || !target.isValid()) return;
        int tick = Bukkit.getCurrentTick();
        if (tick != mergeTick) {
            mergeTick = tick;
            thisTick.clear();
        }
        if (kind == Kind.TRUE) {
            double[] acc = dotPending.get(target.getUniqueId());
            if (acc != null) {
                acc[0] += amount;
                return;
            }
            dotPending.put(target.getUniqueId(), new double[] {amount});
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
                double[] sum = dotPending.remove(target.getUniqueId());
                if (sum != null && sum[0] >= 0.5) spawn(target, sum[0], Kind.TRUE);
            }, DOT_WINDOW_TICKS);
            return;
        }
        if (kind == Kind.DAMAGE || kind == Kind.MAGIC || kind == Kind.CRIT || kind == Kind.PLAYER_HURT) {
            String key = target.getUniqueId() + ":" + kind;
            Object[] prev = thisTick.get(key);
            if (prev != null && prev[0] instanceof TextDisplay td && td.isValid()) {
                double sum = (double) prev[1] + amount;
                prev[1] = sum;
                td.text(Text.mm(text(kind, sum)));
                return;
            }
            TextDisplay td = spawn(target, amount, kind);
            if (td != null) thisTick.put(key, new Object[] {td, amount});
            return;
        }
        spawn(target, amount, kind);
    }

    private static String text(Kind kind, double amount) {
        return switch (kind) {
            case DAMAGE -> "<#ffe9a8>" + Text.num(amount);
            case MAGIC -> "<#9fd3ff>" + Text.num(amount);
            case CRIT -> "<gradient:#ffd34f:#ff6b2b><b>" + Text.num(amount) + "!</b></gradient>";
            case PLAYER_HURT -> "<#ff5f6d>-" + Text.num(amount);
            case HEAL -> "<#6dff8f>+" + Text.num(amount);
            case EVADE -> "<#bfbfbf><i>회피</i>";
            case BLOCK -> "<#9ec9ff>막음 <gray>" + Text.num(amount);
            case TRUE -> "<#d59bff>" + Text.num(amount);
        };
    }

    private TextDisplay spawn(LivingEntity target, double amount, Kind kind) {
        if (target == null || !target.isValid()) return null;
        int tick = Bukkit.getCurrentTick();
        if (tick != currentTick) {
            currentTick = tick;
            spawnedThisTick = 0;
        }
        if (++spawnedThisTick > MAX_PER_TICK) return null;

        String text = text(kind, amount);
        ThreadLocalRandom r = ThreadLocalRandom.current();
        double h = target.getHeight();
        Location loc = target.getLocation().add(r.nextDouble(-0.45, 0.45), h * 0.75 + r.nextDouble(0, 0.3),
                r.nextDouble(-0.45, 0.45));
        float scale = kind == Kind.CRIT ? 1.35f : 1.0f;
        int ticks = services.settings().combat().damageNumberTicks();
        TextDisplay td = target.getWorld().spawn(loc, TextDisplay.class, d -> {
            d.text(Text.mm(text));
            d.setBillboard(Display.Billboard.CENTER);
            d.setShadowed(true);
            d.setSeeThrough(false);
            d.setDefaultBackground(false);
            d.setBackgroundColor(Color.fromARGB(0, 0, 0, 0));
            d.setPersistent(false);
            d.setTeleportDuration(Math.min(59, ticks));
            d.setTransformation(new Transformation(new Vector3f(), new AxisAngle4f(), new Vector3f(scale), new AxisAngle4f()));
            Keys.tagTransient(d, Keys.DAMAGE_NUMBER, "1");
        });
        Location to = loc.clone().add(0, 0.9, 0);
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (td.isValid()) td.teleport(to);
        }, 2L);
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (td.isValid()) td.remove();
        }, ticks + 2L);
        return td;
    }

    /** 서버 재시작 후 남은 숫자 엔티티 정리용 판정. */
    public static boolean isDamageNumber(Entity e) {
        return e.getPersistentDataContainer().has(Keys.DAMAGE_NUMBER);
    }
}
