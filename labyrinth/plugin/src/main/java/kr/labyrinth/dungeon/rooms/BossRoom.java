package kr.labyrinth.dungeon.rooms;

import java.util.List;
import kr.labyrinth.bosses.BossHandle;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Hints;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.mobs.CustomMob;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;

/**
 * 보스방: 원형 투기장. 진입 → 3초 뒤 문 봉인 → BossService.spawnBoss. 보스 구현이 없는 층(null)은 그 층 정예 몹을
 * 보스 배율(HP ×hp_mult, 보스바)로 세워 모든 층이 끝까지 공략 가능하게 한다. 둘 다 실패하면 바로 클리어.
 * 봉인 뒤 안에 살아 있는 파티원이 10초 동안 없으면 전투를 거두고 문을 연다 (밖의 생존자가 다시 도전할 수 있게).
 */
public final class BossRoom extends Room {

    private static final String BAR = "dungeon_boss";
    /** 점진 힌트 — 보스바 아래 단서 한 줄. */
    private static final String HINT_BAR = "dungeon_boss_hint";
    private static final long HINT_DELAY_MS = 2500;
    private static final long HINT_SHOW_MS = 20_000;

    private long sealAt = -1;
    private BossHandle boss;
    private CustomMob standIn;
    private BossBar bar;
    private boolean defeated;
    private boolean fightStarted;
    private boolean failureRecorded;
    private long hintAt = -1;
    private long hintUntil = -1;
    private BossBar hintBar;

    public BossRoom(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
    }

    @Override
    public boolean wantsDecor() { return true; }

    @Override
    public void onReady() {
        BossDef def = fs.services().content().boss(fs.def().boss());
        String name = def == null ? "층의 수호자" : def.name();
        String title = def == null || def.title() == null ? "" : def.title();
        // 문 앞 표지
        int[] d = info.doors();
        if (d.length > 0) {
            int x = FloorLayout.unpackX(d[d.length / 2]), z = FloorLayout.unpackZ(d[d.length / 2]);
            fs.text(fs.tile(x, z - 2, 3.2), "<dark_red><b>⚔ " + name + "</b></dark_red>\n<gray>" + title + "\n<dark_gray>들어서면 문이 봉인됩니다");
        }
    }

    @Override
    public Location center() {
        FloorLayout.Arena a = fs.layout().arena();
        return fs.tile(a.centerX(), a.centerZ(), 1);
    }

    @Override
    public void onEnter(Player p) {
        if (state != State.IDLE) return;
        state = State.ACTIVE;
        emptyTicks = 0;
        sealAt = System.currentTimeMillis() + 3000;
        BossDef def = fs.services().content().boss(fs.def().boss());
        fs.title("<dark_red><b>" + (def == null ? "수호자" : def.name()) + "</b></dark_red>",
                "<gray>" + (def == null || def.title() == null ? "" : def.title()), 10, 50, 10);
        fs.sound(center(), Sound.ENTITY_WARDEN_EMERGE, 0.9f, 0.7f);
    }

    @Override
    public void tick(long t) {
        if (state != State.ACTIVE) return;
        if (sealAt > 0) {
            if (System.currentTimeMillis() < sealAt) return;
            sealAt = -1;
            lock();
            summon();
            // 봉인(문 위 사람을 안으로 민 뒤) 시점에 안에 아무도 없으면 도전이 아니다 — 들여다보고 물러난 경우 실패로 세지 않는다
            fightStarted = !alivePlayersInside().isEmpty();
            hintAt = System.currentTimeMillis() + HINT_DELAY_MS;
            return;
        }
        if (defeated) return;
        tickHint();
        if (boss != null) {
            if (!safeAlive(boss)) {
                // onDeath 콜백이 오지 않은 경우 대비 (보상은 보스 구현이 이미 지급)
                defeat();
                return;
            }
            if (t % 10 == 0 && abandoned(40)) resetFight(); // 약 10초
            return;
        }
        if (standIn != null) {
            if (bar != null) {
                float prog = (float) Math.max(0, Math.min(1, standIn.health() / Math.max(1, standIn.maxHealth())));
                bar.progress(prog);
            }
            if (!FloorState.alive(standIn)) {
                standInRewards();
                defeat();
                return;
            }
            if (t % 10 == 0 && abandoned(40)) resetFight(); // 약 10초
            return;
        }
        // 소환 실패 → 그대로 진행
        defeat();
    }

    private static boolean safeAlive(BossHandle b) {
        try {
            return b.isAlive();
        } catch (Throwable t) {
            return false;
        }
    }

    private void summon() {
        Location c = center();
        try {
            boss = fs.services().bosses().spawnBoss(fs.floor(), c, fs.ctx());
        } catch (Throwable e) {
            Log.error("보스 소환 실패 (지하 " + fs.floor() + "층)", e);
            boss = null;
        }
        if (boss != null) {
            try {
                boss.onDeath(h -> defeat());
            } catch (Throwable e) {
                Log.error("보스 사망 콜백 등록 실패", e);
            }
            return;
        }
        // 대체 보스: 층 정예를 보스 배율로 (d 는 이미 층 램프가 적용된 값 — 램프 진행도는 원래 ctx 것을 이어받는다)
        String eliteId = fs.def().elite();
        Difficulty d = fs.ctx().difficulty();
        Difficulty boosted = new Difficulty(d.id(), d.name(), d.hp() * fs.config().fallbackHpMult(),
                d.damage() * fs.config().fallbackDamageMult(), d.drop(), d.xp(), d.telegraph());
        InstanceContext ctx = fs.ctx();
        InstanceContext bossCtx = new InstanceContext(ctx.id(), ctx.floor(), ctx.members(), boosted, ctx.rampProgress(),
                ctx.scaling(), c.getWorld().getName(), ctx.startedAt());
        standIn = fs.spawnMob(eliteId, c, bossCtx);
        if (standIn == null) {
            Log.warn("지하 " + fs.floor() + "층 보스·정예 모두 소환 실패 — 층을 바로 클리어 처리합니다.");
            return;
        }
        mobs.add(standIn);
        BossDef def = fs.services().content().boss(fs.def().boss());
        String color = def == null || def.bossbar() == null ? "RED" : def.bossbar().toUpperCase();
        BossBar.Color bc;
        try {
            bc = BossBar.Color.valueOf(color);
        } catch (IllegalArgumentException e) {
            bc = BossBar.Color.RED;
        }
        bar = BossBar.bossBar(Text.mm("<b>" + standIn.displayName() + "</b> <gray>— 층의 수호자"), 1f, bc, BossBar.Overlay.NOTCHED_12);
        for (Player p : fs.allPlayers()) fs.services().hud().showBossBar(p, BAR, bar);
        fs.sound(c, Sound.ENTITY_ENDER_DRAGON_GROWL, 0.7f, 1.2f);
        c.getWorld().spawnParticle(Particle.SONIC_BOOM, c.clone().add(0, 1, 0), 1);
    }

    /** 대체 보스 처치 보상: 층 보스 루팅·경험치·골드 (진짜 보스는 BossService 가 지급). */
    private void standInRewards() {
        BossDef def = fs.services().content().boss(fs.def().boss());
        List<Player> players = fs.alivePlayers();
        if (def == null) return;
        Location at = center().add(0, 0.5, 0);
        if (def.drops() != null) fs.loot(def.drops(), players, at, "boss");
        fs.rewardXp(def.xp());
        for (Player p : players) {
            long gold = Math.round(def.gold().roll(rng) * fs.ctx().goldMultiplier());
            if (gold > 0) {
                fs.services().data().get(p).addGold(gold);
                Text.send(p, "<gold>+" + Text.num(gold) + " 골드");
                fs.services().hud().refresh(p);
            }
        }
    }

    // ── 점진 힌트 ─────────────────────────────────────────────────────────

    private String bossId() {
        BossDef def = fs.services().content().boss(fs.def().boss());
        return def == null ? fs.def().boss() : def.id();
    }

    /** 보스가 등장하고 2.5초 뒤(보스바가 먼저 뜬 다음) 파티 기준 단서를 보스바 아래에 20초 띄운다. */
    private void tickHint() {
        long now = System.currentTimeMillis();
        if (hintAt > 0 && now >= hintAt) {
            hintAt = -1;
            BossDef def = fs.services().content().boss(fs.def().boss());
            String id = bossId();
            if (id == null) return;
            List<Player> party = fs.run().onlineMembers();
            String clue = Hints.partyClue(fs.services(), party, Hints.bossKey(id), Hints.bossClues(def));
            if (clue == null) return;
            hintBar = BossBar.bossBar(Text.mm(Hints.format(clue)), 0f, BossBar.Color.WHITE, BossBar.Overlay.PROGRESS);
            for (Player p : fs.allPlayers()) {
                fs.services().hud().showBossBar(p, HINT_BAR, hintBar);
                Text.send(p, "<dark_gray>쓰러졌던 기억이 속삭인다…</dark_gray> " + Hints.format(clue));
            }
            hintUntil = now + HINT_SHOW_MS;
        }
        if (hintUntil > 0 && now >= hintUntil) hideHint();
    }

    private void hideHint() {
        hintUntil = -1;
        hintBar = null;
        for (Player p : fs.run().onlineMembers()) fs.services().hud().hideBossBar(p, HINT_BAR);
    }

    /** 보스전 도중 전멸 = 이 보스에서 실패 1회 (파티원 전원). */
    @Override
    public void onWipe() {
        recordFailure();
    }

    /** 이 도전에서 실패 1회 기록 (파티원 전원, 도전마다 한 번). */
    private void recordFailure() {
        if (!fightStarted || defeated || failureRecorded) return;
        String id = bossId();
        if (id == null) return;
        failureRecorded = true;
        Hints.recordFailure(fs.services(), fs.run().onlineMembers(), Hints.bossKey(id));
    }

    /**
     * 고착 방지: 봉인된 보스방 안에 살아 있는 파티원이 없으면(안에서 모두 쓰러지고 밖에만 생존자) 보상 없이 보스를 거두고
     * 문을 열어 다음 진입 때 처음부터 시작. 보스가 바꾼 투기장 블록은 {@link BossHandle#end()} 가 되돌린다.
     */
    private void resetFight() {
        recordFailure(); // 안의 파티원이 모두 쓰러져 비었음 = 실패
        BossHandle b = boss;
        boss = null;
        if (b != null) {
            try {
                b.end(); // 사망 콜백을 부르지 않으므로 defeat() 로 새지 않는다
            } catch (Throwable e) {
                Log.error("보스전 초기화 오류 (지하 " + fs.floor() + "층)", e);
            }
        }
        removeMobs();
        standIn = null;
        for (Player p : fs.run().onlineMembers()) fs.services().hud().hideBossBar(p, BAR);
        bar = null;
        hintAt = -1;
        hideHint();
        unlock();
        state = State.IDLE;
        fightStarted = false;
        sealAt = -1;
        emptyTicks = 0;
        failureRecorded = false;
        for (Player p : fs.allPlayers()) Text.send(p, "<gray>수호자가 어둠 속으로 물러나고 봉인이 풀렸습니다. 다시 들어가면 처음부터 시작합니다.");
    }

    private void defeat() {
        if (defeated) return;
        defeated = true;
        state = State.CLEARED;
        hideHint();
        for (Player p : fs.run().onlineMembers()) fs.services().hud().hideBossBar(p, BAR);
        unlock();
        Location c = center();
        fs.world().spawnParticle(Particle.END_ROD, c.clone().add(0, 1, 0), 80, 3, 2, 3, 0.05);
        fs.onBossDefeated(c);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (boss != null && !defeated) {
            try {
                boss.end();
            } catch (Throwable ignored) {
                // 이미 끝남
            }
        }
        for (Player p : fs.run().onlineMembers()) fs.services().hud().hideBossBar(p, BAR);
        hideHint();
    }
}
