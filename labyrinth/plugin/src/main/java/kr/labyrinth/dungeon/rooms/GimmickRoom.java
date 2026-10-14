package kr.labyrinth.dungeon.rooms;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Hints;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.gimmicks.BookCipher;
import kr.labyrinth.dungeon.rooms.gimmicks.ForgeBellows;
import kr.labyrinth.dungeon.rooms.gimmicks.GearTiming;
import kr.labyrinth.dungeon.rooms.gimmicks.LeverSequence;
import kr.labyrinth.dungeon.rooms.gimmicks.LightsOut;
import kr.labyrinth.dungeon.rooms.gimmicks.ResonanceTune;
import kr.labyrinth.dungeon.rooms.gimmicks.SporePurge;
import kr.labyrinth.dungeon.rooms.gimmicks.TorchRelay;
import kr.labyrinth.dungeon.rooms.gimmicks.ValveFlow;
import kr.labyrinth.dungeon.rooms.gimmicks.VoidTrial;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * 기믹방 공통 (GDD §10): 입장 시 문이 닫히고 분위기 문구(가운데 글자 — 정답은 알려 주지 않음) → 2초 뒤 시작.
 * 실패(시간 초과·기회 소진·안에서 전멸)가 쌓이면 다음 도전 때 {@link #hints()} 단서가 한 단계씩 또렷해진다 (core/Hints).
 * 성공: 보상 상자(gimmick_floor_N, 개인 루팅) + 경험치(층 일반 몹 평균 ×10) + 문 개방. 실패: 페널티 후 문 개방(보상 없음).
 * 안에 살아 있는 파티원이 없으면 초기화되어 다시 도전할 수 있다. 구현 키 = floors.yml gimmick.
 */
public abstract class GimmickRoom extends Room {

    private static final String BAR = "dungeon_gimmick";
    private static final String HINT_BAR = "dungeon_gimmick_hint";

    protected final Params params;
    private long startAt = -1;
    private long startedMs;
    protected boolean running;
    private BossBar bar;
    private BossBar hintBar;
    private String clue;
    private boolean failureRecorded;
    private final List<Entity> displays = new ArrayList<>();

    protected GimmickRoom(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        this.params = fs.def().gimmickParams() == null ? Params.EMPTY : fs.def().gimmickParams();
    }

    /** 구현 키 → 기믹방. 알 수 없으면 전투방으로 대체 (진행 막힘 방지). */
    public static Room create(FloorState fs, FloorLayout.RoomInfo info, String key) {
        String k = key == null ? "" : key;
        return switch (k) {
            case "lever_sequence" -> new LeverSequence(fs, info);
            case "torch_relay" -> new TorchRelay(fs, info);
            case "spore_purge" -> new SporePurge(fs, info);
            case "valve_flow" -> new ValveFlow(fs, info);
            case "forge_bellows" -> new ForgeBellows(fs, info);
            case "lights_out" -> new LightsOut(fs, info);
            case "resonance_tune" -> new ResonanceTune(fs, info);
            case "book_cipher" -> new BookCipher(fs, info);
            case "gear_timing" -> new GearTiming(fs, info);
            case "void_trial" -> new VoidTrial(fs, info);
            default -> {
                Log.warn("[미궁] 알 수 없는 기믹방 키 '" + k + "' (지하 " + fs.floor() + "층) — 전투방으로 대체");
                yield new BattleRoom(fs, info, false);
            }
        };
    }

    /** 기믹 이름 (한국어). */
    protected abstract String title();

    /**
     * 가운데 안내문 1~2줄 (MiniMessage, 줄바꿈 \n). 조작법·정답을 적지 않고 분위기·관찰 단서만 (GDD "보스 문구 규칙").
     */
    protected abstract String rules();

    /** 점진 힌트 단서 3단계 (흐릿 → 조금 분명 → 거의 정답). 실패가 쌓이면 다음 도전 때 보여 준다. */
    protected List<String> hints() { return List.of(); }

    /** 단서 목록 (자가 진단·도구용). */
    public final List<String> hintLines() { return hints(); }

    /** 점진 힌트 기록 키 (floors.yml gimmick 구현 키). */
    protected String hintKey() {
        String k = fs.def().gimmick();
        return Hints.gimmickKey(k == null || k.isBlank() ? getClass().getSimpleName().toLowerCase(java.util.Locale.ROOT) : k);
    }

    /** 시작 (재도전 시에도 호출 — 상태를 처음부터). */
    protected abstract void begin();

    /** 2틱마다 (진행 중일 때만). */
    protected abstract void update(long t);

    /** 보스바에 붙일 진행 상태 ("3/4" 등). */
    protected String status() { return ""; }

    /** 진행률 0~1 (보스바). 기본 = 남은 시간. */
    protected float progress() {
        int limit = timeLimit();
        if (limit <= 0) return 1f;
        return (float) Math.max(0, 1.0 - elapsed() / limit);
    }

    /** 제한 시간(초). 0 = 없음. 시간 초과 = 실패. */
    protected int timeLimit() { return 0; }

    /** 초기화·종료 시 기믹이 바꾼 블록/엔티티 되돌리기. */
    protected void cleanup() {}

    @Override
    public boolean wantsDecor() { return false; }

    protected double elapsed() { return (System.currentTimeMillis() - startedMs) / 1000.0; }

    @Override
    public void onReady() {
        displays.add(fs.text(fs.tile(info.centerX(), info.centerZ(), 4.2), "<light_purple><b>✦ 시련: " + title() + " ✦</b></light_purple>\n" + rules()));
    }

    @Override
    public void onEnter(Player p) {
        if (state != State.IDLE) return;
        state = State.ACTIVE;
        emptyTicks = 0;
        lock();
        startAt = System.currentTimeMillis() + 2500;
        failureRecorded = false;
        fs.title("<light_purple><b>" + title() + "</b></light_purple>", "<gray>시련이 시작됩니다", 5, 40, 10);
        fs.actionBar(fs.allPlayers(), "<light_purple>시련의 방</light_purple> <gray>— 문이 닫혔다", 60);
        for (Player o : fs.allPlayers()) o.sendMessage(Text.mm(Text.PREFIX + "<light_purple><b>" + title() + "</b></light_purple><gray> — "
                + rules().replace("\n", " ")));
        clue = Hints.partyClue(fs.services(), fs.run().onlineMembers(), hintKey(), hints());
        if (clue != null) {
            for (Player o : fs.allPlayers()) Text.send(o, "<dark_gray>실패의 기억이 속삭인다…</dark_gray> " + Hints.format(clue));
        }
    }

    @Override
    public final void tick(long t) {
        if (state != State.ACTIVE) return;
        if (startAt > 0) {
            if (System.currentTimeMillis() < startAt) return;
            startAt = -1;
            startedMs = System.currentTimeMillis();
            running = true;
            bar = BossBar.bossBar(Text.mm("<light_purple>" + title()), 1f, BossBar.Color.PURPLE, BossBar.Overlay.PROGRESS);
            for (Player p : fs.allPlayers()) fs.services().hud().showBossBar(p, BAR, bar);
            if (clue != null) {
                hintBar = BossBar.bossBar(Text.mm(Hints.format(clue)), 0f, BossBar.Color.WHITE, BossBar.Overlay.PROGRESS);
                for (Player p : fs.allPlayers()) fs.services().hud().showBossBar(p, HINT_BAR, hintBar);
            }
            try {
                begin();
            } catch (Throwable e) {
                Log.error("기믹 시작 오류: " + title(), e);
                succeed();
            }
            return;
        }
        if (!running) return;
        try {
            update(t);
        } catch (Throwable e) {
            Log.error("기믹 진행 오류: " + title(), e);
        }
        if (!running) return;
        if (t % 4 == 0 && bar != null) {
            int limit = timeLimit();
            String time = limit > 0 ? " <gray>· 남은 시간 <white>" + Math.max(0, (int) Math.ceil(limit - elapsed())) + "초" : "";
            String st = status();
            bar.name(Text.mm("<light_purple><b>" + title() + "</b></light_purple>" + (st.isEmpty() ? "" : " <gray>· <white>" + st) + time));
            bar.progress(Math.max(0f, Math.min(1f, progress())));
        }
        if (timeLimit() > 0 && elapsed() >= timeLimit()) {
            fail("시간이 다 되었습니다");
            return;
        }
        if (t % 10 == 0 && abandoned(40)) reset(); // 약 10초
    }

    protected void succeed() {
        if (state != State.ACTIVE) return;
        running = false;
        state = State.CLEARED;
        hideBar();
        cleanup();
        removeMobs();
        unlock();
        Location c = center();
        List<Player> winners = fs.alivePlayers();
        fs.loot("gimmick_floor_" + fs.floor(), winners, c.clone().add(0, 0.5, 0), "chest");
        fs.rewardXp(fs.averageMobXp() * 10);
        fs.title("<gold><b>시련 성공!</b></gold>", "<gray>" + title() + " — 보상을 받았습니다", 5, 50, 10);
        for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.8f, 1.3f);
        fs.world().spawnParticle(Particle.TOTEM_OF_UNDYING, c.clone().add(0, 1, 0), 60, 2, 1, 2, 0.3);
        for (Entity e : displays) fs.untrack(e);
        displays.clear();
    }

    protected void fail(String reason) {
        if (state != State.ACTIVE) return;
        recordFailure();
        running = false;
        state = State.CLEARED;
        hideBar();
        cleanup();
        unlock();
        fs.title("<red><b>시련 실패</b></red>", "<gray>" + reason, 5, 50, 10);
        for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.8f, 0.7f);
        for (Entity e : displays) fs.untrack(e);
        displays.clear();
    }

    private void reset() {
        if (running) recordFailure(); // 안의 파티원이 모두 쓰러져 비었음 = 실패
        running = false;
        startAt = -1;
        hideBar();
        cleanup();
        removeMobs();
        unlock();
        state = State.IDLE;
        emptyTicks = 0;
        for (Player p : fs.allPlayers()) Text.send(p, "<gray>시련의 방이 고요해졌습니다. 다시 들어가면 처음부터 시작합니다.");
    }

    private void hideBar() {
        for (Player p : fs.run().onlineMembers()) {
            fs.services().hud().hideBossBar(p, BAR);
            fs.services().hud().hideBossBar(p, HINT_BAR);
        }
        bar = null;
        hintBar = null;
    }

    /** 이 도전에서 실패 1회 기록 (파티원 전원, 도전마다 한 번). */
    private void recordFailure() {
        if (failureRecorded) return;
        failureRecorded = true;
        try {
            Hints.recordFailure(fs.services(), fs.run().onlineMembers(), hintKey());
        } catch (Throwable t) {
            Log.error("기믹 실패 기록 오류: " + title(), t);
        }
    }

    /** 시련 도중 전멸 = 실패. */
    @Override
    public void onWipe() {
        if (state == State.ACTIVE && (running || startAt > 0)) recordFailure();
    }

    @Override
    public void onDestroy() {
        hideBar();
        super.onDestroy();
    }

    // ── 하위 구현용 헬퍼 ─────────────────────────────────────────────────

    /** 방 중심 기준 상대 타일 → 절대 타일 x. */
    protected int rx(int dx) { return info.centerX() + dx; }

    protected int rz(int dz) { return info.centerZ() + dz; }

    protected Material accent() {
        List<String> a = fs.def().palette("accent");
        Material m = a.isEmpty() ? null : Material.matchMaterial(a.get(0));
        return m == null || !m.isBlock() ? Material.CHISELED_STONE_BRICKS : m;
    }

    /** 방 안 살아 있는 파티원에게 최대 HP 비율 피해. */
    protected void hurt(Player p, double pct, String source) {
        if (pct <= 0) return;
        fs.services().damage().deal(kr.labyrinth.combat.DamageContext.percent(null, p, pct).source(source));
    }

    /** 실패 소환 (fail_spawn × fail_spawn_count). */
    protected void failSpawn() {
        String id = params.str("fail_spawn", null);
        int n = params.integer("fail_spawn_count", 2);
        if (id == null || fs.services().content().mob(id) == null) id = fs.randomFloorMob(rng);
        for (int i = 0; i < n; i++) spawn(id, randomSpot(3));
    }

    protected int partySize() { return fs.ctx().partySize(); }
}
