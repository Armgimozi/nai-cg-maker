package kr.labyrinth.mobs;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.ArmorStand;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 몹 스킬 훈련 {@code /labadmin mobdrill <몹 id…|all|f<층>>} — 플레이어 없이도 몹의 스킬·애니메이션이 예외 없이 도는지 본다
 * (자가 진단은 몹을 소환·처치만 하고, 플레이어가 없으면 스킬은 한 번도 안 쓴다).
 * <p>
 * 명령을 친 자리(플레이어는 바라보는 블록 위, 콘솔은 {@code execute positioned … run labadmin mobdrill …}) 에 몹 하나와
 * 6칸 앞에 허수아비(무적 갑옷 거치대)를 세우고, 몹의 능동 스킬을 하나씩 허수아비에게 강제로 시전한다(거리·시야 조건 무시,
 * 경고 시간·판정은 그대로). 그다음 피해(분노 임계)·처치(사망 스킬) → 소환물·분열체·허수아비 정리 → 다음 몹.
 * 진행 중 서버 로그의 SEVERE/예외를 센다. 블록은 바꾸지 않는다.
 */
final class MobDrill {

    private static volatile MobDrill running;

    /** 스킬 하나에 주는 시간(틱): 몸을 움직이는 스킬(dive·burrow·charge·leap)은 길게. */
    private static int gapFor(String type) {
        return switch (type) {
            case "dive", "burrow" -> 120;
            case "charge", "leap", "beam", "breath", "life_drain" -> 70;
            default -> 50;
        };
    }

    private final Services services;
    private final MobServiceImpl mobs;
    private final CommandSender sender;
    private final Location base;
    private final Deque<String> queue;
    private final int total;
    private final List<BukkitTask> tasks = new ArrayList<>();
    private final Map<String, Integer> errors = new LinkedHashMap<>();
    private final List<String> samples = new ArrayList<>();
    private final Set<LogRecord> seen = Collections.newSetFromMap(new IdentityHashMap<>());
    private Handler handler;
    private int casts, failed, thrown, hits, deaths, mobsDone;

    private MobDrill(Services services, MobServiceImpl mobs, CommandSender sender, Location base, List<String> ids) {
        this.services = services;
        this.mobs = mobs;
        this.sender = sender;
        this.base = base;
        this.queue = new ArrayDeque<>(ids);
        this.total = ids.size();
    }

    static boolean isRunning() { return running != null; }

    static void start(Services services, MobServiceImpl mobs, CommandSender sender, Location at, List<String> ids) {
        if (running != null) {
            Text.error(sender, "몹 훈련이 이미 진행 중입니다.");
            return;
        }
        if (ids.isEmpty()) {
            Text.error(sender, "훈련할 몹이 없습니다.");
            return;
        }
        MobDrill d = new MobDrill(services, mobs, sender, at.clone(), ids);
        running = d;
        d.installLogTap();
        Text.send(sender, "<#c9a2ff>몹 훈련 시작</#c9a2ff> <gray>— " + ids.size() + "종, 몹마다 능동 스킬을 허수아비에게 차례로 시전 → 처치 → 정리");
        d.next();
    }

    /** 플러그인 종료·리로드 등으로 중단. */
    static void abort() {
        MobDrill d = running;
        if (d != null) d.finish(true);
    }

    // ── 몹 하나 ───────────────────────────────────────────────────────────

    private void next() {
        if (running != this) return;
        String id = queue.poll();
        if (id == null) {
            finish(false);
            return;
        }
        MobDef def = services.content().mob(id);
        if (def == null) {
            bump("content", "없는 몹 " + id);
            next();
            return;
        }
        Vector dir = base.getDirection().setY(0);
        if (dir.lengthSquared() < 1e-4) dir = new Vector(0, 0, 1);
        dir.normalize();
        Location at = base.clone();
        Location dummyAt = base.clone().add(dir.clone().multiply(6));
        dummyAt.setYaw(Geometry.yawOf(-dir.getX(), -dir.getZ()));
        List<LabMob> before = mobs.mobsNear(at, 40);
        InstanceContext ictx = InstanceContext.adhoc(Math.max(1, def.floor()), 1, services.settings().difficulty(), services.settings().party());
        ArmorStand dummy;
        LabMob m;
        try {
            dummy = at.getWorld().spawn(dummyAt, ArmorStand.class, a -> {
                a.setPersistent(false);
                a.setInvulnerable(true);
                a.setBasePlate(false);
                a.setArms(true);
                a.customName(Component.text("훈련용 허수아비"));
                a.setCustomNameVisible(true);
                Keys.tagTransient(a, Keys.FX, "mob_drill");
            });
            CustomMob cm = mobs.spawn(id, at, ictx, false);
            if (!(cm instanceof LabMob lm)) {
                dummy.remove();
                bump("mobs", "소환 실패 " + id);
                later(5, this::next);
                return;
            }
            m = lm;
        } catch (Throwable t) {
            bump("mobs", "소환 예외 " + id + " — " + t);
            Log.error("[몹 훈련] 소환 예외 (" + id + ")", t);
            later(5, this::next);
            return;
        }
        m.drill = true;
        m.drillDummy = dummy;
        if (m.ambushing) MobSkills.revealAmbush(m);
        List<Integer> active = new ArrayList<>();
        for (int i = 0; i < m.skills.size(); i++) {
            String type = m.skills.get(i).type() == null ? "" : m.skills.get(i).type().toLowerCase(Locale.ROOT);
            if (!MobSkills.PASSIVE.contains(type)) active.add(i);
        }
        Text.send(sender, "<gray>  [" + (mobsDone + 1) + "/" + total + "] <white>" + def.name() + "</white> <dark_gray>(" + id
                + ")</dark_gray> 능동 스킬 " + active.size() + "개");
        long t = 30;
        for (int idx : active) {
            String type = m.skills.get(idx).type();
            later(t, () -> castOne(m, idx, type));
            t += gapFor(type == null ? "" : type.toLowerCase(Locale.ROOT));
        }
        later(t, () -> hurt(m));
        later(t + 25, () -> kill(m, dummy, before, 0));
    }

    private void castOne(LabMob m, int idx, String type) {
        if (!m.isAlive() || m.drillDummy == null || !m.drillDummy.isValid()) return;
        try {
            // 앞 스킬이 몸을 묶어 둔 상태는 풀고 시작 (훈련은 순서대로 강제 시전)
            m.busyUntil = 0;
            m.staggerUntil = 0;
            if (MobSkills.forceCast(m, idx, m.drillDummy)) casts++;
            else {
                failed++;
                samples(type + " 시전 안 됨 (" + m.def().id() + ")");
            }
        } catch (Throwable ex) {
            thrown++;
            bump("mobs", m.def().id() + "/" + type + " — " + ex);
            Log.error("[몹 훈련] 스킬 예외 (" + m.def().id() + "/" + type + ")", ex);
        }
    }

    private void hurt(LabMob m) {
        if (!alive(m)) return;
        try {
            // 분노 임계(30~40%) 아래로
            services.damage().deal(DamageContext.raw(null, m.entity(), m.maxHealth() * 0.65, DamageType.TRUE));
        } catch (Throwable ex) {
            thrown++;
            bump("combat", m.def().id() + " 피해 — " + ex);
            Log.error("[몹 훈련] 피해 예외 (" + m.def().id() + ")", ex);
        }
    }

    private void kill(LabMob m, ArmorStand dummy, List<LabMob> before, int tries) {
        if ((m.burrowed || m.motionLocked) && tries < 8) {
            // 땅속·급강하 중이면 끝날 때까지 조금 더 기다린다 (무적)
            later(20, () -> kill(m, dummy, before, tries + 1));
            return;
        }
        if (m.burrowed || m.motionLocked) bump("mobs", m.def().id() + " 땅속·급강하 상태가 풀리지 않음");
        hits += m.drillHits;
        m.drillHits = 0;
        if (alive(m)) {
            try {
                DamageContext c = services.damage().deal(DamageContext.raw(null, m.entity(), m.health() * 4 + 1000, DamageType.TRUE));
                if (c.killed() || !m.isAlive()) deaths++;
            } catch (Throwable ex) {
                thrown++;
                bump("combat", m.def().id() + " 처치 — " + ex);
                Log.error("[몹 훈련] 처치 예외 (" + m.def().id() + ")", ex);
            }
        }
        later(60, () -> cleanup(m, dummy, before));
    }

    private void cleanup(LabMob m, ArmorStand dummy, List<LabMob> before) {
        try {
            if (m.isAlive()) {
                bump("mobs", m.def().id() + " 처치 후에도 살아 있음");
                m.remove();
            }
            // 이 훈련이 만든 소환물·분열체 정리
            Set<LabMob> keep = Collections.newSetFromMap(new IdentityHashMap<>());
            keep.addAll(before);
            for (LabMob x : mobs.mobsNear(base, 40)) if (!keep.contains(x)) x.remove();
            if (dummy.isValid()) dummy.remove();
        } catch (Throwable ex) {
            bump("mobs", "정리 예외 — " + ex);
            Log.error("[몹 훈련] 정리 예외", ex);
        }
        mobsDone++;
        later(10, this::next);
    }

    // ── 공용 ─────────────────────────────────────────────────────────────

    private static boolean alive(CustomMob m) {
        try {
            return m != null && m.isAlive() && m.entity() != null && m.entity().isValid();
        } catch (Throwable t) {
            return false;
        }
    }

    private void later(long ticks, Runnable r) {
        tasks.add(Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (running != this) return;
            try {
                r.run();
            } catch (Throwable t) {
                bump("mobs", "훈련 단계 예외 — " + t);
                Log.error("[몹 훈련] 단계 예외", t);
            }
        }, Math.max(1, ticks)));
    }

    private void bump(String sub, String sample) {
        errors.merge(sub, 1, Integer::sum);
        samples(sample);
    }

    private void samples(String s) {
        if (samples.size() < 12) samples.add(s);
    }

    private void installLogTap() {
        handler = new Handler() {
            @Override
            public void publish(LogRecord r) {
                if (r == null || !seen.add(r)) return;
                if (r.getLevel().intValue() < Level.SEVERE.intValue() && r.getThrown() == null) return;
                if (r.getMessage() != null && r.getMessage().startsWith("[몹 훈련]")) return; // 직접 센 예외
                errors.merge("log", 1, Integer::sum);
                Throwable th = r.getThrown();
                samples("로그: " + r.getMessage() + (th == null ? "" : " — " + th));
            }

            @Override
            public void flush() {}

            @Override
            public void close() {}
        };
        Logger.getLogger("").addHandler(handler);
        Log.get().addHandler(handler);
    }

    private void finish(boolean aborted) {
        if (running != this) return;
        for (BukkitTask t : tasks) t.cancel();
        tasks.clear();
        running = null;
        if (handler != null) {
            Logger.getLogger("").removeHandler(handler);
            Log.get().removeHandler(handler);
        }
        int err = errors.values().stream().mapToInt(Integer::intValue).sum();
        String head = err == 0 ? "<#7fe07f><b>몹 훈련 통과</b></#7fe07f>" : "<#ff6b6b><b>몹 훈련: 예외 " + err + "건</b></#ff6b6b>";
        String body = "몹 " + mobsDone + "/" + total + " · 시전 " + casts + " (안 됨 " + failed + ") · 허수아비 적중 " + hits
                + " · 처치 " + deaths + " · 스킬 예외 " + thrown;
        Text.send(sender, head + " <gray>" + body + (aborted ? " (중단됨)" : ""));
        for (String s : samples) Text.send(sender, "<dark_gray>   - " + Text.escape(s.length() > 220 ? s.substring(0, 220) + "…" : s));
        Log.info("[몹 훈련] 결과: 예외 " + err + " · " + body + (errors.isEmpty() ? "" : " · " + errors));
    }
}
