package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import kr.labyrinth.Services;
import kr.labyrinth.bosses.BossHandle;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.dungeon.rooms.Room;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.CommandSender;
import org.bukkit.scheduler.BukkitTask;

/**
 * 관리자 자가 진단 {@code /labadmin selftest [층 수]} — 플레이어 없이 런타임 경로 전체를 한 번 돌려 본다.
 * <ol>
 *   <li>임시 인스턴스 슬롯에 지하 1층(… n층)을 실제로 생성 (FloorGenerator → BlockPlacer, 방 준비)</li>
 *   <li>첫 층에 몹·정예 정의 전부(이후 층은 그 층 몹) 소환 + 정예 변종 1마리, 몇 초 AI 틱</li>
 *   <li>DamageService 로 피해 → 처치 (경험치·골드·루팅·MobKillEvent 경로, 플레이어 없음)</li>
 *   <li>1~5층 보스(+ 구현 없는 6층은 대체 보스 = 층 정예 × 보스 배율)를 차례로 보스방에 소환 → 페이즈가 넘어가게 피해 → 처치</li>
 *   <li>층 정리(블록·엔티티)·슬롯 반납 후 요약 출력: 개수 + 하위 시스템별 예외 수 (서버 로그에 남은 SEVERE/스택 포함)</li>
 * </ol>
 * 기존 지형은 건드리지 않는다 — 공허 월드의 빈 슬롯만 쓴다.
 */
final class SelfTest {

    private static volatile SelfTest running;

    private final Services services;
    private final DungeonManager manager;
    private final CommandSender sender;
    private final int floors;
    private final long startedAt = System.currentTimeMillis();
    private final Map<String, Integer> errors = new LinkedHashMap<>();
    private final List<String> errorSamples = new ArrayList<>();
    private final Map<String, Integer> counts = new LinkedHashMap<>();
    private final List<BukkitTask> tasks = new ArrayList<>();
    private Handler handler;
    private final Set<LogRecord> seen = Collections.newSetFromMap(new IdentityHashMap<>());

    private int floorIndex;
    private Run run;
    private FloorState fs;
    private int slot = -1;
    private final List<CustomMob> mobs = new ArrayList<>();

    private SelfTest(Services services, DungeonManager manager, CommandSender sender, int floors) {
        this.services = services;
        this.manager = manager;
        this.sender = sender;
        this.floors = floors;
    }

    static boolean isRunning() { return running != null; }

    static void start(Services services, DungeonManager manager, CommandSender sender, int floors) {
        if (running != null) {
            Text.error(sender, "자가 진단이 이미 진행 중입니다.");
            return;
        }
        if (manager.world() == null) {
            Text.error(sender, "미궁 월드가 없습니다 — 자가 진단을 할 수 없습니다.");
            return;
        }
        int max = Math.max(1, Math.min(floors, services.content().maxFloor()));
        SelfTest t = new SelfTest(services, manager, sender, max);
        running = t;
        t.installLogTap();
        Text.send(sender, "<#c9a2ff>자가 진단 시작</#c9a2ff> <gray>— 지하 1~" + max + "층 생성 · 몹/보스 소환 · 피해/처치 · 정리 (플레이어 불필요)");
        t.checkItemsAndCodex();
        t.nextFloor();
    }

    /** 모든 아이템 ItemStack 생성(툴팁·모델·컴포넌트) + 도감 획득처 계산. */
    private void checkItemsAndCodex() {
        for (String id : services.content().items().keySet()) {
            step("items", () -> {
                var s = services.items().create(id);
                if (s == null || s.getType().isAir()) throw new IllegalStateException("create(" + id + ") 빈 아이템");
                var def = services.items().defOf(s);
                if (def.isEmpty() || !id.equals(def.get().id())) throw new IllegalStateException("defOf(" + id + ") 불일치");
                count("items_created", 1);
            });
        }
        step("ui", () -> {
            var src = kr.labyrinth.ui.menus.CodexMenu.buildSources(services.content());
            int gear = 0, known = 0;
            for (var d : services.content().items().values()) {
                if (!d.isGear()) continue;
                gear++;
                if (!src.getOrDefault(d.id(), List.of()).isEmpty()) known++;
            }
            count("codex_gear_with_source", known);
            count("codex_gear_total", gear);
        });
    }

    /** 플러그인 종료 등으로 중단. */
    static void abort() {
        SelfTest t = running;
        if (t != null) t.finish(true);
    }

    // ── 로그 감시: 진단 중 남는 모든 SEVERE·예외를 하위 시스템별로 센다 ─────────────────────

    private void installLogTap() {
        handler = new Handler() {
            @Override
            public void publish(LogRecord r) {
                if (r == null || !seen.add(r)) return;
                if (r.getLevel().intValue() < Level.WARNING.intValue()) return;
                if (r.getThrown() == null && r.getLevel().intValue() < Level.SEVERE.intValue()) return;
                String sub = subsystem(r.getThrown());
                bump(errors, sub);
                if (errorSamples.size() < 12) {
                    Throwable th = r.getThrown();
                    errorSamples.add(sub + ": " + r.getMessage() + (th == null ? "" : " — " + th));
                }
            }

            @Override
            public void flush() {}

            @Override
            public void close() {}
        };
        Logger.getLogger("").addHandler(handler);
        Log.get().addHandler(handler);
    }

    private static String subsystem(Throwable t) {
        while (t != null) {
            for (StackTraceElement e : t.getStackTrace()) {
                String c = e.getClassName();
                if (c.startsWith("kr.labyrinth.") && !c.startsWith("kr.labyrinth.dungeon.SelfTest")) {
                    String rest = c.substring("kr.labyrinth.".length());
                    int dot = rest.indexOf('.');
                    return dot < 0 ? "core" : rest.substring(0, dot);
                }
            }
            t = t.getCause();
        }
        return "server";
    }

    private static void bump(Map<String, Integer> m, String k) { m.merge(k, 1, Integer::sum); }

    private void count(String k, int n) { counts.merge(k, n, Integer::sum); }

    /** 단계 실행 — 던진 예외는 그 하위 시스템 오류로 센다. */
    private void step(String sub, Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            bump(errors, sub);
            if (errorSamples.size() < 12) errorSamples.add(sub + ": " + t);
            Log.error("[자가 진단] " + sub + " 단계 예외", t);
        }
    }

    private void later(long ticks, Runnable r) {
        tasks.add(Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (running != this) return;
            step("selftest", r);
        }, Math.max(1, ticks)));
    }

    // ── 층 ────────────────────────────────────────────────────────────────

    private void nextFloor() {
        floorIndex++;
        if (floorIndex > floors) {
            finish(false);
            return;
        }
        int f = floorIndex;
        FloorDef def = services.content().floor(f);
        if (def == null) {
            bump(errors, "content");
            errorSamples.add("content: floors.yml 에 지하 " + f + "층 없음");
            nextFloor();
            return;
        }
        slot = manager.allocateTestSlot();
        if (slot < 0) {
            bump(errors, "dungeon");
            errorSamples.add("dungeon: 빈 인스턴스 슬롯 없음");
            finish(false);
            return;
        }
        Difficulty d = services.settings().difficulty();
        String id = "selftest" + manager.nextRunSeq() + "s" + slot;
        run = new Run(manager, id, slot, d, services.settings().party(), List.of(new UUID(0x5E1F7E57L, f)));
        long t0 = System.currentTimeMillis();
        step("dungeon", () -> {
            fs = run.createFloor(f);
            if (fs == null) throw new IllegalStateException("createFloor(" + f + ") = null");
            fs.build(() -> {
                if (running != this) return;
                count("floors_built", 1);
                Text.send(sender, "<gray>  지하 " + f + "층 생성 완료 (" + (System.currentTimeMillis() - t0) + "ms, 방 "
                        + fs.rooms().size() + "개)");
                step("selftest", this::spawnMobs);
            });
        });
        if (fs == null) {
            releaseFloor(this::nextFloor);
            return;
        }
        // 생성이 2분 넘게 안 끝나면 실패로 보고 다음 단계
        later(20L * 120, () -> {
            if (fs != null && !fs.ready()) {
                bump(errors, "dungeon");
                errorSamples.add("dungeon: 지하 " + f + "층 생성 시간 초과 (진행 " + Math.round(fs.progress() * 100) + "%)");
                releaseFloor(this::nextFloor);
            }
        });
    }

    private List<Location> spots() {
        List<Location> out = new ArrayList<>();
        for (Room r : fs.rooms()) {
            if (r.type() == RoomType.BOSS) continue;
            out.add(r.center());
        }
        if (out.isEmpty()) out.add(fs.spawnPoint());
        return out;
    }

    private void spawnMobs() {
        List<Location> spots = spots();
        List<String> ids = new ArrayList<>();
        for (MobDef m : services.content().mobs().values()) {
            if (floorIndex == 1 || m.floor() == floorIndex) ids.add(m.id());
        }
        int i = 0;
        for (String id : ids) {
            Location base = spots.get(i % spots.size()).clone().add((i / spots.size()) % 3 - 1, 0, (i / spots.size() / 3) % 3 - 1);
            i++;
            step("mobs", () -> {
                CustomMob m = fs.spawnMob(id, base);
                if (m == null) {
                    bump(errors, "mobs");
                    errorSamples.add("mobs: 소환 실패 " + id);
                } else {
                    mobs.add(m);
                    count("mobs_spawned", 1);
                }
            });
        }
        // 정예 변종 경로 (일반 몹 하나)
        String normal = fs.def().mobs().isEmpty() ? null : fs.def().mobs().get(0);
        if (normal != null) {
            step("mobs", () -> {
                CustomMob m = services.mobs().spawn(normal, spots.get(0).clone().add(2, 0, 2), fs.ctx(), true);
                if (m != null) {
                    m.entity().getPersistentDataContainer().set(kr.labyrinth.core.Keys.INSTANCE,
                            org.bukkit.persistence.PersistentDataType.STRING, fs.ctx().id());
                    mobs.add(m);
                    count("elite_variants", 1);
                }
            });
        }
        Text.send(sender, "<gray>  몹 " + mobs.size() + "/" + (ids.size() + (normal != null ? 1 : 0)) + " 소환 — AI 5초 틱");
        later(100, this::damageMobs);
    }

    private void damageMobs() {
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m)) continue;
            step("combat", () -> {
                DamageContext c = services.damage().deal(DamageContext.raw(null, m.entity(), Math.max(1, m.maxHealth() * 0.3), DamageType.TRUE));
                if (c.dealt() > 0) count("hits", 1);
            });
        }
        later(60, this::killMobs);
    }

    private void killMobs() {
        int alive = 0;
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m)) continue;
            alive++;
            step("combat", () -> {
                DamageContext c = services.damage().deal(DamageContext.raw(null, m.entity(), m.health() * 4 + 1000, DamageType.TRUE));
                if (c.killed() || !m.isAlive()) count("mobs_killed", 1);
            });
        }
        count("mobs_alive_before_kill", alive);
        later(40, () -> {
            int left = 0;
            for (CustomMob m : mobs) if (FloorState.alive(m)) left++;
            if (left > 0) {
                bump(errors, "mobs");
                errorSamples.add("mobs: 처치 후에도 살아 있는 몹 " + left + "마리");
            }
            mobs.clear();
            List<Integer> bossFloors = new ArrayList<>();
            if (floorIndex == 1) {
                for (int b = 1; b <= Math.min(6, services.content().maxFloor()); b++) bossFloors.add(b);
            } else {
                bossFloors.add(floorIndex);
            }
            Text.send(sender, "<gray>  몹 처치 확인 — 보스 " + bossFloors + " 차례로 소환");
            bossChain(bossFloors, 0);
        });
    }

    // ── 보스 ──────────────────────────────────────────────────────────────

    private Location arenaCenter() {
        List<Room> br = fs.rooms(RoomType.BOSS);
        return br.isEmpty() ? fs.spawnPoint() : br.get(0).center();
    }

    private void bossChain(List<Integer> list, int idx) {
        if (idx >= list.size()) {
            releaseFloor(this::nextFloor);
            return;
        }
        int b = list.get(idx);
        Location c = arenaCenter();
        final BossHandle[] boss = new BossHandle[1];
        final CustomMob[] standIn = new CustomMob[1];
        step("bosses", () -> boss[0] = services.bosses().spawnBoss(b, c, fs.ctx()));
        if (boss[0] != null) {
            count("bosses_spawned", 1);
        } else {
            // 구현 없는 층 = 대체 보스 (BossRoom 과 같은 규칙: 층 정예 × fallback 배율)
            step("mobs", () -> {
                FloorDef def = services.content().floor(b);
                if (def == null || def.elite() == null) return;
                Difficulty d = fs.ctx().difficulty();
                Difficulty boosted = new Difficulty(d.id(), d.name(), d.hp() * manager.config().fallbackHpMult(),
                        d.damage() * manager.config().fallbackDamageMult(), d.drop(), d.xp(), d.telegraph());
                InstanceContext ctx = fs.ctx();
                InstanceContext bossCtx = new InstanceContext(ctx.id(), ctx.floor(), ctx.members(), boosted, ctx.scaling(),
                        c.getWorld().getName(), ctx.startedAt());
                standIn[0] = fs.spawnMob(def.elite(), c, bossCtx);
            });
            if (standIn[0] != null) count("fallback_bosses", 1);
            else {
                bump(errors, "bosses");
                errorSamples.add("bosses: 지하 " + b + "층 보스·대체 보스 모두 소환 실패");
            }
        }
        var pool = boss[0] != null ? (kr.labyrinth.combat.HealthPool) boss[0] : standIn[0];
        if (pool == null) {
            bossChain(list, idx + 1);
            return;
        }
        // 2초 틱(패턴 시작) → 45% 피해 ×2 (페이즈 전환) → 처치 → 정리
        for (int k = 1; k <= 2; k++) {
            later(40L * k, () -> step("combat", () -> {
                if (!pool.isAlive()) return;
                DamageContext dc = services.damage().deal(DamageContext.raw(null, pool.entity(), pool.maxHealth() * 0.45, DamageType.TRUE));
                if (dc.dealt() > 0) count("boss_hits", 1);
            }));
        }
        later(140, () -> killBoss(b, pool, list, idx, 0));
    }

    /**
     * 처치 피해 → 2초 뒤 확인. 보스가 기믹으로 무적(빙결 껍질 등)이면 아레나의 기믹 오브젝트(인장·알주머니…)부터 깨고 1초 뒤
     * 다시 시도한다 (최대 40회 — 오브젝트로 안 풀리는 기믹은 제한 시간이 끝나 풀릴 때까지 기다린다).
     */
    private void killBoss(int b, kr.labyrinth.combat.HealthPool pool, List<Integer> list, int idx, int tries) {
        boolean[] retry = {false};
        step("combat", () -> {
            if (!pool.isAlive()) return;
            if (pool.invulnerable() && tries < 40) {
                breakBossObjects(pool);
                retry[0] = true;
                return;
            }
            services.damage().deal(DamageContext.raw(null, pool.entity(), pool.health() * 4 + 10_000, DamageType.TRUE));
        });
        if (retry[0]) {
            later(20, () -> killBoss(b, pool, list, idx, tries + 1));
            return;
        }
        later(40, () -> {
            if (pool.isAlive()) {
                bump(errors, "bosses");
                errorSamples.add("bosses: 지하 " + b + "층 보스가 처치 피해 뒤에도 살아 있음");
            } else {
                count("bosses_killed", 1);
            }
            step("bosses", () -> services.bosses().endAll(fs.ctx().id()));
            step("mobs", () -> services.mobs().removeAll(fs.ctx().id()));
            later(10, () -> bossChain(list, idx + 1));
        });
    }

    /** 보스 주변의 부술 수 있는 기믹 오브젝트(BossHandle 이지만 보스 자신은 아닌 것)에 큰 피해. */
    private void breakBossObjects(kr.labyrinth.combat.HealthPool pool) {
        org.bukkit.entity.LivingEntity e = pool.entity();
        if (e == null || !e.isValid()) return;
        for (org.bukkit.entity.Entity near : e.getWorld().getNearbyEntities(e.getLocation(), 24, 12, 24)) {
            if (!(near instanceof org.bukkit.entity.LivingEntity le)) continue;
            BossHandle h = services.bosses().byEntity(le).orElse(null);
            if (h == null || h == pool || !h.isAlive() || h.invulnerable()) continue;
            DamageContext dc = services.damage().deal(DamageContext.raw(null, le, h.maxHealth() * 2 + 1000, DamageType.TRUE));
            if (dc.dealt() > 0) count("boss_objects_broken", 1);
        }
    }

    // ── 정리·요약 ─────────────────────────────────────────────────────────

    private void releaseFloor(Runnable then) {
        FloorState f = fs;
        int s = slot;
        fs = null;
        slot = -1;
        if (f == null) {
            if (s >= 0) manager.releaseTestSlot(s);
            then.run();
            return;
        }
        step("dungeon", () -> f.destroy(false, () -> {
            manager.releaseTestSlot(s);
            count("floors_cleaned", 1);
            if (running == this) step("selftest", then);
        }));
    }

    private void finish(boolean aborted) {
        if (running != this) return;
        if (aborted && fs != null) {
            FloorState f = fs;
            int s = slot;
            try {
                f.destroy(true, () -> manager.releaseTestSlot(s));
            } catch (Throwable t) {
                Log.error("[자가 진단] 중단 정리 실패", t);
            }
        }
        for (BukkitTask t : tasks) t.cancel();
        tasks.clear();
        running = null;
        if (handler != null) {
            Logger.getLogger("").removeHandler(handler);
            Log.get().removeHandler(handler);
        }
        int totalErr = errors.values().stream().mapToInt(Integer::intValue).sum();
        long secs = (System.currentTimeMillis() - startedAt) / 1000;
        String head = totalErr == 0 ? "<#7fe07f><b>자가 진단 통과</b></#7fe07f>" : "<#ff6b6b><b>자가 진단: 예외 " + totalErr + "건</b></#ff6b6b>";
        Text.send(sender, head + " <gray>(" + secs + "초" + (aborted ? ", 중단됨" : "") + ")");
        StringBuilder sb = new StringBuilder();
        counts.forEach((k, v) -> sb.append(k).append('=').append(v).append(' '));
        Text.send(sender, "<gray>  " + Text.escape(sb.toString().trim()));
        if (!errors.isEmpty()) {
            StringBuilder eb = new StringBuilder();
            errors.forEach((k, v) -> eb.append(k).append('=').append(v).append(' '));
            Text.send(sender, "<#ff6b6b>  하위 시스템별 예외: " + Text.escape(eb.toString().trim()));
            for (String e : errorSamples) Text.send(sender, "<dark_gray>   - " + Text.escape(e.length() > 220 ? e.substring(0, 220) + "…" : e));
        }
        Log.info("[자가 진단] 결과: 예외 " + totalErr + " · " + sb.toString().trim() + (errors.isEmpty() ? "" : " · " + errors));
    }
}
