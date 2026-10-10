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
 */
public final class Ticker {
    @FunctionalInterface
    public interface Task {
        void tick(long now);
    }

    private static final int WINDOW = 200;

    private static final class Sys {
        final String name;
        final Task task;
        final long[] nanos = new long[WINDOW];
        long max;
        int errors;

        Sys(String name, Task task) {
            this.name = name;
            this.task = task;
        }
    }

    private final Plugin plugin;
    private final Logger log;
    private final List<Sys> systems = new ArrayList<>();
    private BukkitTask handle;
    private long now;

    public Ticker(Plugin plugin) {
        this.plugin = plugin;
        this.log = plugin.getLogger();
    }

    /** 체계를 더한다. 더한 순서대로 돈다. */
    public void add(String name, Task task) {
        systems.add(new Sys(name, task));
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

    private void run() {
        now++;
        int slot = (int) (now % WINDOW);
        for (Sys s : systems) {
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
            long sum = 0;
            for (long n : s.nanos) sum += n;
            double avg = sum / (double) WINDOW / 1e6;
            total += avg;
            out.add(String.format(Locale.ROOT, "%-10s avg %.3f ms  max %.3f ms  errors %d", s.name, avg, s.max / 1e6, s.errors));
        }
        out.add(String.format(Locale.ROOT, "total avg %.3f ms (budget 3.5 ms), tick %d", total, now));
        return out;
    }
}
