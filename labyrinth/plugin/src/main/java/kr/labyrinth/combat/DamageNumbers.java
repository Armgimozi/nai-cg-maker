package kr.labyrinth.combat;

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
 */
public final class DamageNumbers {

    private static final int MAX_PER_TICK = 24;

    private final Services services;
    private int spawnedThisTick;
    private int currentTick = -1;

    public DamageNumbers(Services services) { this.services = services; }

    public enum Kind { DAMAGE, CRIT, PLAYER_HURT, HEAL, EVADE, BLOCK, TRUE }

    public void show(LivingEntity target, double amount, Kind kind) {
        if (!services.settings().combat().damageNumbers() || target == null || !target.isValid()) return;
        int tick = Bukkit.getCurrentTick();
        if (tick != currentTick) {
            currentTick = tick;
            spawnedThisTick = 0;
        }
        if (++spawnedThisTick > MAX_PER_TICK) return;

        String text = switch (kind) {
            case DAMAGE -> "<#ffe9a8>" + Text.num(amount);
            case CRIT -> "<gradient:#ffd34f:#ff6b2b><b>" + Text.num(amount) + "!</b></gradient>";
            case PLAYER_HURT -> "<#ff5f6d>-" + Text.num(amount);
            case HEAL -> "<#6dff8f>+" + Text.num(amount);
            case EVADE -> "<#bfbfbf><i>회피</i>";
            case BLOCK -> "<#9ec9ff>막음 <gray>" + Text.num(amount);
            case TRUE -> "<#d59bff>" + Text.num(amount);
        };
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
    }

    /** 서버 재시작 후 남은 숫자 엔티티 정리용 판정. */
    public static boolean isDamageNumber(Entity e) {
        return e.getPersistentDataContainer().has(Keys.DAMAGE_NUMBER);
    }
}
