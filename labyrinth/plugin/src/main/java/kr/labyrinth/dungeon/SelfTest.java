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
 *   <li>미로 확인: 주 경로 길이, 계단·금 간 벽 블록, 금 간 벽 열기, 탐험 지도 그리기</li>
 *   <li>첫 층에 몹·정예 정의 전부(이후 층은 그 층 몹) 소환 + 정예 변종 1마리, 몇 초 AI 틱</li>
 *   <li>DamageService 로 피해 → 처치 (경험치·골드·루팅·MobKillEvent 경로, 플레이어 없음)</li>
 *   <li>1~5층 보스(+ 구현 없는 6층은 대체 보스 = 층 정예 × 보스 배율)를 차례로 보스방에 소환 → 페이즈가 넘어가게 피해 → 처치</li>
 *   <li>층마다 난이도 층 램프·솔로 보정이 인스턴스 배율에 걸렸는지 확인 (+ 시작 꾸러미 아이템 id)</li>
 *   <li>층마다 시련방을 특별 시련으로 확정 → 조건 4종 판정 · special_trial_fNN 굴림 확인</li>
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

    /** 모든 아이템 ItemStack 생성(툴팁·모델·컴포넌트) + 강화 단계 확인 + 도감 획득처 계산. */
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
        // 강화: 강화할 수 있는 장비 전부 +1~+10 기록·다시 그리기·스탯 배율 (GDD §11.13)
        step("items", () -> count("enhance_checked", kr.labyrinth.items.enhance.EnhanceService.selfCheck(services)));
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
        // 시작 꾸러미: 설정의 아이템 id 가 콘텐츠에 있는지 (없으면 지급할 때 그 줄만 건너뛴다)
        step("content", () -> {
            for (var k : services.settings().starterKit()) {
                boolean vanilla = k.item().startsWith("minecraft:");
                org.bukkit.Material m = vanilla ? org.bukkit.Material.matchMaterial(k.item()) : null;
                if (vanilla ? m != null && m.isItem() : services.content().item(k.item()) != null) {
                    count("starter_kit_items", 1);
                } else {
                    bump(errors, "content");
                    errorSamples.add("content: 시작 꾸러미 아이템 없음 " + k.item());
                }
            }
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
        run.forceSpecialTrial(true);
        long t0 = System.currentTimeMillis();
        step("dungeon", () -> {
            fs = run.createFloor(f);
            if (fs == null) throw new IllegalStateException("createFloor(" + f + ") = null");
            fs.build(() -> {
                if (running != this) return;
                count("floors_built", 1);
                Text.send(sender, "<gray>  지하 " + f + "층 생성 완료 (" + (System.currentTimeMillis() - t0) + "ms, 방 "
                        + fs.rooms().size() + "개)");
                step("hints", this::checkHints);
                step("dungeon", () -> checkScaling(f));
                step("dungeon", () -> checkMaze(f));
                step("dungeon", () -> checkSpecialTrial(f));
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

    /** 점진 힌트: 이 층 기믹방·보스의 단서 3단계가 있고 MiniMessage 로 읽히는지, 단계 계산이 config 와 맞는지. */
    private void checkHints() {
        var cfg = kr.labyrinth.core.Hints.config(services);
        if (kr.labyrinth.core.Hints.level(cfg, 0) > 0 && cfg.mode() == kr.labyrinth.core.Hints.Mode.PROGRESSIVE) {
            throw new IllegalStateException("실패 0회인데 단서 단계 > 0");
        }
        for (Room r : fs.rooms()) {
            if (!(r instanceof kr.labyrinth.dungeon.rooms.GimmickRoom g)) continue;
            var lines = g.hintLines();
            if (lines.size() != 3) throw new IllegalStateException("기믹방 단서가 3단계가 아님: " + fs.def().gimmick() + " (" + lines.size() + ")");
            for (String l : lines) Text.mm(kr.labyrinth.core.Hints.format(l));
            count("hint_gimmicks", 1);
        }
        var boss = services.content().boss(fs.def().boss());
        var clues = kr.labyrinth.core.Hints.bossClues(boss);
        for (String l : clues) Text.mm(kr.labyrinth.core.Hints.format(l));
        if (!clues.isEmpty()) count("hint_bosses", 1);
    }

    /**
     * 특별 시련 (GDD §10.1): 이 층 시련방이 특별 시련으로 확정됐는지, 조건이 그 기믹이 쓸 수 있는 것인지,
     * 조건 4종이 "지킴 → 어김" 으로 판정되는지(방의 판정 재료 그대로), special_trial_fNN 이 사람 없이 굴려도 무언가를 주는지.
     */
    private void checkSpecialTrial(int f) {
        var cfg = manager.config().specialTrial();
        String table = kr.labyrinth.dungeon.rooms.SpecialTrial.table(f);
        if (services.content().lootTable(table) == null) {
            bump(errors, "content");
            errorSamples.add("content: 루팅 표 " + table + " 없음 (특별 시련 상자)");
            return;
        }
        for (Room r : fs.rooms()) {
            if (!(r instanceof kr.labyrinth.dungeon.rooms.GimmickRoom g)) continue;
            String gimmick = fs.def().gimmick();
            var rule = kr.labyrinth.dungeon.rooms.SpecialTrial.rule(gimmick, fs.def().specialTrial(), g.limitSeconds(), cfg);
            var st = g.special();
            if (st == null) {
                if (!rule.isEmpty()) {
                    bump(errors, "dungeon");
                    errorSamples.add("dungeon: 지하 " + f + "층 특별 시련이 확정되지 않음");
                }
                continue;
            }
            if (!kr.labyrinth.dungeon.rooms.SpecialTrial.supports(gimmick, st.condition())) {
                bump(errors, "dungeon");
                errorSamples.add("dungeon: 지하 " + f + "층 기믹 " + gimmick + " 이 못 쓰는 조건 " + st.condition().id());
            }
            Text.mm(st.line(fs.ctx().partySize()));
            count("special_trials", 1);
            for (var c : kr.labyrinth.dungeon.rooms.SpecialTrial.Condition.values()) {
                var t = kr.labyrinth.dungeon.rooms.SpecialTrial.of(c, rule, cfg);
                var k = new kr.labyrinth.dungeon.rooms.SpecialTrial.Counters();
                boolean before = t.kept(k, 1);
                switch (c) {
                    case SWIFT -> k.elapsed(t.seconds() + 1);
                    case UNSCATHED -> { for (int i = 0; i <= t.allowedHits(1); i++) k.hurt(Math.max(t.minDamage(), 0.01), t.minDamage()); }
                    case ABSTAIN -> k.consume(t.potions());
                    case FLAWLESS -> k.mistake();
                }
                var broken = kr.labyrinth.dungeon.rooms.SpecialTrial.reward(f, t, false, k, 1, cfg.xpBonus());
                var keptReward = kr.labyrinth.dungeon.rooms.SpecialTrial.reward(f, t, false, new kr.labyrinth.dungeon.rooms.SpecialTrial.Counters(), 1, cfg.xpBonus());
                if (!before || t.kept(k, 1) || broken.special() || !keptReward.tables().contains(table)
                        || !broken.tables().contains("gimmick_floor_" + f)) {
                    bump(errors, "dungeon");
                    errorSamples.add("dungeon: 특별 시련 조건 판정 이상 " + c.id() + " (지하 " + f + "층)");
                } else {
                    count("special_conditions_checked", 1);
                }
            }
            int items = 0;
            for (var s : services.loot().roll(table, null, fs.ctx())) items += s.getAmount();
            if (items <= 0) {
                bump(errors, "content");
                errorSamples.add("content: " + table + " 을 굴렸는데 아무것도 안 나옴");
            } else {
                count("special_loot_items", items);
            }
        }
    }

    /**
     * 난이도 층 램프·솔로 보정: 이 층 인스턴스 배율이 설정(서버 난이도의 그 층 값 × 인원 배율)과 같은지,
     * 실효 난이도에 램프가 남지 않았는지(이중 적용 방지), 보스 기믹 배율이 램프 진행도를 이어받는지. 걸린 층 수를 센다.
     */
    private void checkScaling(int f) {
        InstanceContext ctx = fs.ctx();
        Difficulty base = services.settings().difficulty();
        var party = services.settings().party();
        int n = ctx.partySize();
        double hp = base.atFloor(f).hp() * party.hp(n), dmg = base.atFloor(f).damage() * party.damage(n);
        if (Math.abs(ctx.hpMultiplier() - hp) > 1e-9 || Math.abs(ctx.damageMultiplier() - dmg) > 1e-9
                || Math.abs(ctx.rampProgress() - base.rampProgress(f)) > 1e-9 || ctx.difficulty().ramp() != null) {
            bump(errors, "dungeon");
            errorSamples.add("dungeon: 지하 " + f + "층 배율 불일치 (HP ×" + ctx.hpMultiplier() + " / 기대 ×" + hp + ")");
        }
        if (base.ramp() != null) count(ctx.rampProgress() < 1 ? "ramp_floors" : "ramp_full_floors", 1);
        if (ctx.solo() && (party.hp(1) != 1.0 || party.damage(1) != 1.0)) count("solo_scaled_floors", 1);
        var ms = new kr.labyrinth.bosses.MechanicScaling(n, ctx.difficulty().id(), 1, false, ctx.rampProgress());
        if (ms.withPhase(3).withEnraged(true).ramp() != ctx.rampProgress()) {
            bump(errors, "bosses");
            errorSamples.add("bosses: 기믹 배율이 램프 진행도를 잃음 (지하 " + f + "층)");
        } else {
            count("boss_ramp_checked", 1);
        }
    }

    /** 미로 구조 확인: 주 경로 길이, 계단·금 간 벽 블록이 실제로 놓였나, 금 간 벽 열기 → 공기, 함정·상자·금고, 탐험 지도 그리기. */
    private void checkMaze(int f) {
        var l = fs.layout();
        var plan = l.plan();
        count("maze_cells", plan.usedCount());
        count("maze_loops", plan.loopCount());
        count("dead_ends", l.deadEnds().size());
        int need = (int) Math.ceil(2.2 * plan.size());
        if (plan.mainPath().size() < need) {
            bump(errors, "dungeon");
            errorSamples.add("dungeon: 지하 " + f + "층 주 경로 " + plan.mainPath().size() + " < " + need);
        }
        // 계단 블록
        boolean stairChecked = false;
        for (int z = 0; z < l.depth() && !stairChecked; z++) {
            for (int x = 0; x < l.width(); x++) {
                if (l.kind(x, z) != kr.labyrinth.dungeon.gen.FloorLayout.STAIR) continue;
                var b = fs.block(x, l.elevation(x, z) + 1, z);
                if (!(b.getBlockData() instanceof org.bukkit.block.data.type.Stairs)) {
                    bump(errors, "dungeon");
                    errorSamples.add("dungeon: 지하 " + f + "층 계단 블록 없음 (" + b.getType() + ")");
                } else {
                    count("stairs_ok", 1);
                }
                stairChecked = true;
                break;
            }
        }
        String dumpDir = System.getProperty("labyrinth.mazeDump");
        if (dumpDir != null) blockDump(f, java.nio.file.Path.of(dumpDir), "before");
        // 금 간 벽 → 열기
        for (var s : l.secretRooms()) {
            int w = s.wall()[s.wall().length / 2];
            int x = kr.labyrinth.dungeon.gen.FloorLayout.unpackX(w), z = kr.labyrinth.dungeon.gen.FloorLayout.unpackZ(w);
            if (fs.block(x, 1, z).getType().isAir()) {
                bump(errors, "dungeon");
                errorSamples.add("dungeon: 지하 " + f + "층 금 간 벽 블록 없음");
                continue;
            }
            fs.secrets().open(s.index(), null);
            if (!fs.block(x, 1, z).getType().isAir() || !fs.secrets().isOpen(s.index())) {
                bump(errors, "dungeon");
                errorSamples.add("dungeon: 지하 " + f + "층 금 간 벽이 열리지 않음");
            } else {
                count("secrets_opened", 1);
            }
        }
        if (dumpDir != null) blockDump(f, java.nio.file.Path.of(dumpDir), "after");
        // 함정·미로 상자·금고·비밀방 (GDD §5.5·§5.6): 개수 + 사람 없이 한 번씩 발동·해제, 상자 블록·금고 문 열기·미믹이 깨어나고 상자가 돌아옴
        count("traps", fs.traps().count());
        count("chests", fs.treasures().chestCount());
        count("vaults", fs.treasures().vaultCount());
        count("secret_rooms", l.secretRooms().size());
        count("mimics", fs.treasures().mimicCount());
        if (fs.traps().count() == 0) {
            bump(errors, "dungeon");
            errorSamples.add("dungeon: 지하 " + f + "층 함정 0개");
        }
        step("dungeon", () -> {
            var kinds = fs.traps().selfTest(1_000_000L + f * 10_000L);
            count("trap_kinds", kinds.size());
            count("traps_disarmed", fs.traps().disarmedCount());
        });
        step("dungeon", () -> {
            int[] r = fs.treasures().selfTest();
            count("chests_ok", r[0]);
            count("vaults_opened", r[1]);
            count("mimic_mobs", r[2]);       // 0.3.5.1: 미믹 상자 하나에 미믹 1마리 (6층부터 + 새끼 미믹 1)
            count("mimic_restored", r[3]);   // 미믹이 사라진 자리에 한 단계 좋은 상자가 돌아옴
            count("mimic_leashed", r[4]);    // 상자 자리에서 아주 멀리 떨어뜨린 미믹이 되돌아옴 (마지막 수단 줄)
            count("mimic_defeated", r[5]);   // 정말로 쓰러뜨린 미믹 = '쓰러뜨림' (칭호 카운터 경로)
            count("mimic_clock_paused", r[6]); // 근처에 아무도 없으면 달아날 시간이 멈춤
        });
        // 보물방 미믹 (방에 미믹이 없으면 첫 상자를 미믹으로): 열기 → 상자 블록 공기 → 미믹 → 시간이 다 돼 달아남(그동안 상자 없음)
        // → 달아나는 몸짓 뒤 미믹이 사라지고 상자가 돌아옴 (쓰러뜨리는 길은 위 미로 상자 쪽)
        for (Room r : fs.rooms()) {
            if (!(r instanceof kr.labyrinth.dungeon.rooms.TreasureRoom tr)) continue;
            step("dungeon", () -> {
                int n = tr.selfTestMimic();
                count("room_mimic_mobs", n);
                if (n > 0) {
                    later(kr.labyrinth.dungeon.treasure.MimicEncounter.FLEE_TICKS + 8, () -> {
                        if (tr.selfTestMimicBack()) {
                            count("room_mimic_restored", 1);
                        } else {
                            bump(errors, "dungeon");
                            errorSamples.add("dungeon: 지하 " + f + "층 보물방 미믹이 달아난 뒤 상자가 돌아오지 않음");
                        }
                    });
                }
            });
            break;
        }
        fs.exploration().revealAll();
        count("map_lines", ExplorationMap.render(fs, null).size());
    }

    /**
     * 개발용 (JVM -Dlabyrinth.mazeDump=폴더 일 때만): 실제로 놓인 블록을 글자로 덤프 — 발 높이 평면도 + 계단·비밀 통로 셀 세로 단면.
     * 평면도: '.' 공기 '/' 계단 '#' 벽 '~' 액체 'X' 금 간 벽 블록 '*' 그 밖(장식·소품). 단면: 위→아래 y0+10 … y0−1.
     */
    private void blockDump(int f, java.nio.file.Path dir, String tag) {
        var l = fs.layout();
        var secretMat = org.bukkit.Material.matchMaterial(fs.def().palette("secret").isEmpty() ? "" : fs.def().palette("secret").get(0));
        StringBuilder sb = new StringBuilder();
        for (int z = 0; z < l.depth(); z++) {
            for (int x = 0; x < l.width(); x++) {
                int e = l.open(x, z) ? l.elevation(x, z) : 0;
                sb.append(blockChar(fs.block(x, e + 1, z), secretMat));
            }
            sb.append('\n');
        }
        StringBuilder sec = new StringBuilder();
        for (int c = 0; c < l.plan().cellCount(); c++) {
            var st = l.plan().style(c);
            if (st != kr.labyrinth.dungeon.gen.HallStyle.STAIRS && st != kr.labyrinth.dungeon.gen.HallStyle.SECRET) continue;
            int bx = l.cellMinX(c), bz = l.cellMinZ(c);
            int ex = l.plan().exits(c);
            boolean alongZ = (ex & 0b0101) != 0;
            sec.append("CELL ").append(c).append(' ').append(st).append(" exits=").append(ex).append('\n');
            for (int dy = 10; dy >= -1; dy--) {
                for (int i = -2; i < 26; i++) {
                    int x = alongZ ? bx + 12 : bx + i, z = alongZ ? bz + i : bz + 12;
                    sec.append(blockChar(fs.block(x, dy, z), secretMat));
                }
                sec.append("  y0").append(dy >= 0 ? "+" : "").append(dy).append('\n');
            }
        }
        try {
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Files.writeString(dir.resolve("floor" + f + "_" + tag + "_plan.txt"), sb.toString());
            java.nio.file.Files.writeString(dir.resolve("floor" + f + "_" + tag + "_slices.txt"), sec.toString());
        } catch (java.io.IOException e) {
            Log.warn("미로 덤프 실패: " + e.getMessage());
        }
    }

    private static char blockChar(org.bukkit.block.Block b, org.bukkit.Material secret) {
        var t = b.getType();
        if (t.isAir()) return '.';
        if (t == secret) return 'X';
        if (b.getBlockData() instanceof org.bukkit.block.data.type.Stairs) return '/';
        if (t == org.bukkit.Material.WATER || t == org.bukkit.Material.LAVA) return '~';
        return t.isOccluding() ? '#' : '*';
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
            if (fs.ctx().rampProgress() < 1) count("bosses_ramped", 1);
        } else {
            // 구현 없는 층 = 대체 보스 (BossRoom 과 같은 규칙: 층 정예 × fallback 배율)
            step("mobs", () -> {
                FloorDef def = services.content().floor(b);
                if (def == null || def.elite() == null) return;
                Difficulty d = fs.ctx().difficulty(); // 이미 층 램프 적용 — 램프 진행도는 원래 ctx 것을 이어받는다
                Difficulty boosted = new Difficulty(d.id(), d.name(), d.hp() * manager.config().fallbackHpMult(),
                        d.damage() * manager.config().fallbackDamageMult(), d.drop(), d.xp(), d.telegraph());
                InstanceContext ctx = fs.ctx();
                InstanceContext bossCtx = new InstanceContext(ctx.id(), ctx.floor(), ctx.members(), boosted, ctx.rampProgress(),
                        ctx.scaling(), c.getWorld().getName(), ctx.startedAt());
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
                double amount = pool.maxHealth() * 0.45;
                DamageContext dc = services.damage().deal(DamageContext.raw(null, pool.entity(), amount, DamageType.TRUE));
                if (dc.dealt() > 0 || forceThroughInvulnerable(pool, amount)) count("boss_hits", 1);
            }));
        }
        later(140, () -> killBoss(b, pool, list, idx, 0));
    }

    /**
     * 처치 피해 → 2초 뒤 확인. 보스가 기믹으로 무적(빙결 껍질 등)이면 아레나의 기믹 오브젝트(인장·알주머니…)부터 깨고 1초 뒤
     * 다시 시도한다 (최대 10회). 그래도 무적(금서 색인 공중 부양·추격 회랑 등 오브젝트로 안 풀리는 기믹)이면
     * {@link #forceThroughInvulnerable} 로 HP 풀에 직접 넣어 처치 경로까지 진단한다.
     */
    private void killBoss(int b, kr.labyrinth.combat.HealthPool pool, List<Integer> list, int idx, int tries) {
        boolean[] retry = {false};
        step("combat", () -> {
            if (!pool.isAlive()) return;
            if (pool.invulnerable() && tries < 10) {
                breakBossObjects(pool);
                retry[0] = true;
                return;
            }
            double amount = pool.health() * 4 + 10_000;
            DamageContext dc = services.damage().deal(DamageContext.raw(null, pool.entity(), amount, DamageType.TRUE));
            if (dc.dealt() <= 0) forceThroughInvulnerable(pool, amount);
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

    /**
     * 보스가 무적 기믹 중(금서 색인 공중 부양·빙결 껍질·추격 등)이라 피해가 막혔으면 HP 풀에 직접 넣어
     * 다음 페이즈·처치 경로까지 진단한다. @return 실제로 깎였는가
     */
    private static boolean forceThroughInvulnerable(kr.labyrinth.combat.HealthPool pool, double amount) {
        if (!pool.isAlive() || !pool.invulnerable()) return false;
        return pool.applyDamage(amount, DamageContext.raw(null, pool.entity(), amount, DamageType.TRUE)) > 0;
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
