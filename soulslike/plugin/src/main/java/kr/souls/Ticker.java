package kr.souls;

import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;
import org.bukkit.scheduler.BukkitTask;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * 서버 틱마다 한 번 도는 고리 하나 (3.1). 전투, HUD, (나중에) 적·보스 두뇌가 모두 여기서 차례로 돈다.
 * Paper Goal.tick 은 2틱에 한 번만 돌아서 쓰지 않는다. 체계마다 걸린 시간을 재어 /souls perf 로 보인다 (12.10).
 * 틱 번호 now() 는 이 고리가 센다 (서버가 멈춰 있는 동안에도 예약 작업은 돌므로 1씩 늘어난다).
 * M1 (M1_PLAN 0.6): 차례는 load → stamina → input → moves → roll → tap → brains → queue → poise → lock → hud → titles → rings.
 * 아직 없는 체계는 빈 자리 ({@link #slot}) 로 미리 두고, 묶음은 {@link #into} 로 자기 일을 그 자리에 넣는다 (부르는 차례와 상관없이
 * 자리의 차례대로 돈다). 이벤트 처리기는 적기만 하고 input 자리가 정한다. 두뇌 (brains) 는 맞을 틱 C = now 로 한 대를 만들고 대기열
 * (queue) 은 now 까지 온 것을 푼다.
 */
public final class Ticker {
    @FunctionalInterface
    public interface Task {
        void tick(long now);
    }

    private static final int WINDOW = 200;

    private static final class Sys {
        final String name;
        /** 이 체계가 든 자리 (자리의 빈 표시면 이름과 같다, 따로 더한 체계면 null) */
        final String slot;
        final Task task;
        final long[] nanos = new long[WINDOW];
        long max;
        int errors;

        Sys(String name, String slot, Task task) {
            this.name = name;
            this.slot = slot;
            this.task = task;
        }
    }

    private final Plugin plugin;
    private final Logger log;
    private final List<Sys> systems = new ArrayList<>();
    private BukkitTask handle;
    private long now;
    private boolean running;

    public Ticker(Plugin plugin) {
        this.plugin = plugin;
        this.log = plugin.getLogger();
    }

    /** 체계를 더한다. 더한 순서대로 돈다. */
    public void add(String name, Task task) {
        systems.add(new Sys(name, null, task));
    }

    /** 빈 자리를 더한다 (더한 순서의 그 자리에서 {@link #into} 로 넣은 일이 돈다). 같은 이름의 자리가 있으면 아무것도 하지 않는다. */
    public void slot(String name) {
        for (Sys s : systems) if (s.task == null && name.equals(s.slot)) return;
        systems.add(new Sys(name, name, null));
    }

    /**
     * 자리 slot 에 일을 넣는다 (그 자리에 이미 넣은 일들 뒤). 같은 자리·같은 이름이면 바꾼다 (/souls reload 뒤에도 둘이 되지 않는다).
     * @throws IllegalArgumentException 그런 자리가 없을 때
     */
    public void into(String slot, String name, Task task) {
        int at = -1;
        for (int i = 0; i < systems.size(); i++) {
            Sys s = systems.get(i);
            if (!slot.equals(s.slot)) continue;
            if (s.task != null && s.name.equals(name)) {
                systems.set(i, new Sys(name, slot, task));
                return;
            }
            at = i;
        }
        if (at < 0) throw new IllegalArgumentException("ticker slot " + slot);
        systems.add(at + 1, new Sys(name, slot, task));
    }

    /** 도는 차례 (자리는 "자리" 또는 "자리/일", 빈 자리도 보인다): 시험 줄 TICKER order= */
    public List<String> order() {
        List<String> out = new ArrayList<>();
        for (Sys s : systems) {
            if (s.slot == null) out.add(s.name);
            else if (s.task == null) out.add(s.slot);
            else out.add(s.slot + "/" + s.name);
        }
        return out;
    }

    public long now() {
        return now;
    }

    public void start() {
        if (handle != null) return;
        handle = Bukkit.getScheduler().runTaskTimer(plugin, this::run, 1, 1);
    }

    public void stop() {
        if (handle != null) handle.cancel();
        handle = null;
    }

    /** 지금 이 고리가 도는 중인가 (combat/Swings: Ticker 안의 서버 휘두름과 패킷·명령의 휘두름은 서버 쪽 휘두름 시계로 한 틱 다르다). */
    public boolean running() {
        return running;
    }

    private void run() {
        running = true;
        try {
            runSystems();
        } finally {
            running = false;
        }
    }

    private void runSystems() {
        now++;
        int slot = (int) (now % WINDOW);
        // 번호로 돈다: 한 체계가 돌다가 into 로 일을 더해도 (명령·이벤트에서) 목록이 깨지지 않는다
        for (int i = 0; i < systems.size(); i++) {
            Sys s = systems.get(i);
            if (s.task == null) continue;
            long t0 = System.nanoTime();
            try {
                s.task.tick(now);
            } catch (Throwable t) {
                // 한 체계가 터져도 나머지는 돈다. 같은 오류로 기록이 넘치지 않게 처음 몇 번만 남긴다
                if (s.errors++ < 5) log.log(Level.SEVERE, "Ticker 체계 " + s.name + " 오류", t);
            }
            long dt = System.nanoTime() - t0;
            s.nanos[slot] = dt;
            if (dt > s.max) s.max = dt;
        }
    }

    /** 체계별 최근 WINDOW 틱 평균과 최대 (ms). */
    public List<String> report() {
        List<String> out = new ArrayList<>();
        double total = 0;
        for (Sys s : systems) {
            if (s.task == null) continue;
            long sum = 0;
            for (long n : s.nanos) sum += n;
            double avg = sum / (double) WINDOW / 1e6;
            total += avg;
            String name = s.slot == null ? s.name : s.slot + "/" + s.name;
            out.add(String.format(Locale.ROOT, "%-10s avg %.3f ms  max %.3f ms  errors %d", name, avg, s.max / 1e6, s.errors));
        }
        out.add(String.format(Locale.ROOT, "total avg %.3f ms (budget 3.5 ms), tick %d", total, now));
        return out;
    }
}
