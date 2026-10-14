package kr.labyrinth.village;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.scheduler.BukkitTask;

/**
 * 틱 분할 작업 (build · survey · selftest · dump · pregen). 한 번에 하나만. 매 틱 {@link #tick} 을 부르고
 * 틱마다 블록 예산(config village.blocks_per_tick)과 시간 예산(35ms)을 넘지 않는다 — 서버가 멈추지 않게.
 * 무거운 계산은 {@link #async} 스레드에서 (스냅샷만 읽기).
 */
abstract class VillageJob {

    private static volatile VillageJob running;
    private static final AtomicInteger THREADS = new AtomicInteger();

    /** 틱당 시간 예산 (ns) — 50ms(1틱) 보다 충분히 작게. */
    static final long TICK_NANOS = 35_000_000L;

    protected final VillageModule module;
    protected final CommandSender sender;
    protected final String title;
    protected final long startedAt = System.currentTimeMillis();
    protected volatile boolean cancelled;
    private BukkitTask task;
    private long lastReport;
    private ExecutorService pool;

    /** 이번 틱 남은 예산. */
    static final class Budget {
        private int blocks;
        private final long deadline;

        Budget(int blocks, long deadline) {
            this.blocks = blocks;
            this.deadline = deadline;
        }

        /** 블록 n 개를 더 써도 되는가 (시간도 확인). */
        boolean more() { return blocks > 0 && System.nanoTime() < deadline; }

        void use(int n) { blocks -= n; }

        boolean timeLeft() { return System.nanoTime() < deadline; }
    }

    VillageJob(VillageModule module, CommandSender sender, String title) {
        this.module = module;
        this.sender = sender;
        this.title = title;
    }

    static VillageJob running() { return running; }

    static boolean cancelRunning() {
        VillageJob j = running;
        if (j == null) return false;
        j.cancelled = true;
        return true;
    }

    /** 플러그인 종료: 다음 틱을 기다리지 않고 바로 정리 (청크 티켓 등). */
    static void abortNow() {
        VillageJob j = running;
        if (j == null) return;
        j.cancelled = true;
        j.finish();
    }

    /** @return 시작했으면 true (다른 작업 중이면 안내 후 false). */
    final boolean start() {
        if (running != null) {
            Text.error(sender, "다른 마을 작업이 진행 중입니다: " + running.title + " <gray>(/labadmin village cancel)");
            return false;
        }
        running = this;
        try {
            begin();
        } catch (Throwable t) {
            running = null;
            throw t;
        }
        task = Bukkit.getScheduler().runTaskTimer(module.plugin(), this::tickSafe, 1L, 1L);
        return true;
    }

    /** 시작 직후 한 번 (메인 스레드). */
    protected void begin() {}

    /** 매 틱. @return 끝났으면 true. */
    protected abstract boolean tick(Budget b) throws Exception;

    /** 진행 상황 한 줄 (몇 초마다 알림). */
    protected abstract String status();

    /** 끝날 때 (성공·실패·취소 모두) — 청크 티켓 정리 등. */
    protected void cleanup() {}

    private void tickSafe() {
        if (running != this) {
            if (task != null) task.cancel();
            return;
        }
        try {
            if (cancelled) {
                say("<#ff6b6b>" + title + " 취소됨");
                finish();
                return;
            }
            Budget b = new Budget(module.blocksPerTick(), System.nanoTime() + TICK_NANOS);
            if (tick(b)) {
                finish();
                return;
            }
            long now = System.currentTimeMillis();
            if (now - lastReport > 4000) {
                lastReport = now;
                String s = status();
                if (s != null) say("<gray>[마을] " + title + " · " + s);
            }
        } catch (Throwable t) {
            Log.error("[마을] " + title + " 오류", t);
            Text.error(sender, title + " 중 오류: " + Text.escape(String.valueOf(t)));
            finish();
        }
    }

    private void finish() {
        if (task != null) task.cancel();
        try {
            cleanup();
        } catch (Throwable t) {
            Log.error("[마을] " + title + " 정리 오류", t);
        }
        if (pool != null) pool.shutdownNow();
        if (running == this) running = null;
    }

    /** 이 작업 전용 비동기 스레드 (작업 끝나면 정리). */
    protected ExecutorService async() {
        if (pool == null) {
            int n = Math.max(1, Math.min(4, Runtime.getRuntime().availableProcessors() / 2));
            ThreadFactory tf = r -> {
                Thread t = new Thread(r, "Labyrinth-Village-" + THREADS.incrementAndGet());
                t.setDaemon(true);
                return t;
            };
            pool = Executors.newFixedThreadPool(n, tf);
        }
        return pool;
    }

    /** 실행자에게 + (실행자가 콘솔이 아니면) 서버 로그에도. */
    protected void say(String mm) {
        Text.send(sender, mm);
        if (!(sender instanceof ConsoleCommandSender)) Log.info(Text.strip(mm));
    }

    protected long elapsedSec() { return (System.currentTimeMillis() - startedAt) / 1000; }

    static String pct(double v) { return Math.round(Math.max(0, Math.min(1, v)) * 100) + "%"; }
}
