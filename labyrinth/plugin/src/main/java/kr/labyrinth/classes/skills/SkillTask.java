package kr.labyrinth.classes.skills;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.IntPredicate;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.scheduler.BukkitTask;

/** 지속 스킬(장판·채널링·연속 공격)용 반복 작업. 예외는 로그 후 중단, 모듈 종료 시 {@link #cancelAll}. */
public final class SkillTask {

    private static final Set<BukkitTask> TASKS = ConcurrentHashMap.newKeySet();

    private SkillTask() {}

    /**
     * delay 틱 후부터 period 틱마다 body(step) 호출 (step 0,1,2…). body 가 false 를 돌려주거나 maxSteps 번 돌면 끝.
     * @param onEnd 끝날 때 한 번 (null 가능)
     */
    public static BukkitTask repeat(long delay, long period, int maxSteps, IntPredicate body, Runnable onEnd) {
        BukkitRunnable r = new BukkitRunnable() {
            int step;

            @Override
            public void run() {
                boolean go;
                try {
                    go = step < maxSteps && body.test(step);
                } catch (Throwable t) {
                    Log.error("직업 스킬 반복 작업 오류", t);
                    go = false;
                }
                step++;
                if (!go || step >= maxSteps) {
                    cancel();
                    TASKS.removeIf(BukkitTask::isCancelled);
                    if (onEnd != null) {
                        try {
                            onEnd.run();
                        } catch (Throwable t) {
                            Log.error("직업 스킬 종료 처리 오류", t);
                        }
                    }
                }
            }
        };
        BukkitTask task = r.runTaskTimer(Services.get().plugin(), Math.max(0, delay), Math.max(1, period));
        TASKS.add(task);
        return task;
    }

    public static void cancelAll() {
        for (BukkitTask t : TASKS) t.cancel();
        TASKS.clear();
    }
}
