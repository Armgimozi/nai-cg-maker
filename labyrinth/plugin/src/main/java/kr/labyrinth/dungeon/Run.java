package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import java.util.UUID;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.PartyScaling;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.event.FloorClearEvent;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Stairs;
import org.bukkit.block.BlockFace;
import org.bukkit.entity.Firework;
import org.bukkit.entity.Player;
import org.bukkit.inventory.meta.FireworkMeta;

/**
 * 한 파티(또는 솔로)의 미궁 공략 한 번. 입장 시 서버 난이도·인원으로 배율이 고정되고, 층을 깨면 같은 슬롯의
 * 한 층 아래(실제로 더 낮은 y)에 다음 층을 만들어 계단으로 내려간다.
 */
public final class Run {

    public enum MemberState { ALIVE, DEAD, LEFT }

    private static final String BAR_GEN = "dungeon_gen";

    private final DungeonManager manager;
    private final String id;
    private final int slot;
    private final Difficulty difficulty;
    private final PartyScaling scaling;
    private final List<UUID> members;
    private final Map<UUID, MemberState> states = new LinkedHashMap<>();
    private final Map<UUID, Location> returnTo = new HashMap<>();
    /** 입장 전 게임 모드 — 미궁을 나갈 때만 되돌린다 (안에서는 GameModes 규칙). */
    private final Map<UUID, GameMode> modes = new HashMap<>();
    /** 관리자 테스트 입장 (/labadmin tpfloor): 게임 모드를 바꾸지 않는다. */
    private final boolean adminTest;
    private final Map<UUID, Location> lastSafe = new HashMap<>();
    private final Map<UUID, Long> nextAmbientSound = new HashMap<>();
    private final long seedBase;
    private final long createdAt = System.currentTimeMillis();
    private final SplittableRandom rng;

    private FloorState current;
    private FloorState next;
    private FloorState previous;
    private boolean ending;
    private boolean finished;
    private boolean started;
    private long emptySince = -1;
    private long firstArrival = -1;
    private BossBar genBar;
    private long lastTick;
    /** 자가 진단: 층마다 시련방을 특별 시련으로 확정 (FloorState). */
    private boolean forceSpecialTrial;

    Run(DungeonManager manager, String id, int slot, Difficulty difficulty, PartyScaling scaling, List<UUID> members) {
        this(manager, id, slot, difficulty, scaling, members, false);
    }

    Run(DungeonManager manager, String id, int slot, Difficulty difficulty, PartyScaling scaling, List<UUID> members,
            boolean adminTest) {
        this.manager = manager;
        this.adminTest = adminTest;
        this.id = id;
        this.slot = slot;
        this.difficulty = difficulty;
        this.scaling = scaling;
        this.members = List.copyOf(members);
        for (UUID u : members) states.put(u, MemberState.ALIVE);
        this.seedBase = System.nanoTime() ^ ((long) slot << 40);
        this.rng = new SplittableRandom(seedBase);
    }

    public String id() { return id; }
    public int slot() { return slot; }
    public Difficulty difficulty() { return difficulty; }
    public List<UUID> members() { return members; }
    public FloorState current() { return current; }
    public boolean ending() { return ending; }
    public long createdAt() { return createdAt; }
    public boolean adminTest() { return adminTest; }
    boolean forceSpecialTrial() { return forceSpecialTrial; }
    void forceSpecialTrial(boolean on) { forceSpecialTrial = on; }

    public MemberState state(UUID u) { return states.getOrDefault(u, MemberState.LEFT); }

    public boolean isMember(UUID u) {
        MemberState s = states.get(u);
        return s != null && s != MemberState.LEFT;
    }

    public boolean isAlive(Player p) { return state(p.getUniqueId()) == MemberState.ALIVE; }

    /** 온라인이고 미궁 월드에 있는 (떠나지 않은) 참가자. */
    public List<Player> onlineMembers() {
        List<Player> out = new ArrayList<>();
        for (UUID u : members) {
            if (!isMember(u)) continue;
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.isOnline() && manager.isLabyrinthWorld(p.getWorld())) out.add(p);
        }
        return out;
    }

    public List<Player> aliveOnline() {
        List<Player> out = new ArrayList<>();
        for (Player p : onlineMembers()) if (isAlive(p)) out.add(p);
        return out;
    }

    InstanceContext contextFor(int floor) {
        return new InstanceContext(id + "-b" + floor, floor, members, difficulty, scaling,
                manager.world().getName(), System.currentTimeMillis());
    }

    // ── 시작 ──────────────────────────────────────────────────────────────

    void begin(int floor, List<Player> players) {
        for (Player p : players) {
            // 밖에 남아 있던 금고 열쇠(접속 끊김·재시작으로 새어 나간 것)는 새 공략에 못 들고 들어온다
            kr.labyrinth.dungeon.treasure.VaultKeys.strip(p, "", 0);
            returnTo.put(p.getUniqueId(), p.getLocation().clone());
            modes.put(p.getUniqueId(), GameModes.remembered(p.getGameMode()));
            PlayerData d = manager.services().data().get(p);
            d.ext().put("dungeon.return", DungeonManager.serialize(p.getLocation()));
            d.ext().put("dungeon.gamemode", modes.get(p.getUniqueId()).name());
            d.markDirty();
        }
        genBar = BossBar.bossBar(Text.mm("<gradient:#c9a2ff:#7fd8ff>미궁이 모습을 드러내는 중...</gradient>"), 0f,
                BossBar.Color.PURPLE, BossBar.Overlay.NOTCHED_10);
        for (Player p : players) manager.services().hud().showBossBar(p, BAR_GEN, genBar);
        FloorState fs = createFloor(floor);
        if (fs == null) {
            for (Player p : players) Text.error(p, "층을 만들 수 없습니다 (floors.yml 지하 " + floor + "층 확인).");
            end(false, null);
            return;
        }
        current = fs;
        fs.build(() -> {
            for (UUID u : members) {
                Player p = Bukkit.getPlayer(u);
                if (p == null || !p.isOnline()) continue;
                manager.services().hud().hideBossBar(p, BAR_GEN);
                // 크리에이티브로 들어오면 보스·몹이 공격하지 않는다 → 일반 입장은 서바이벌로 (입장 전 모드는 나갈 때 되돌림)
                GameMode want = GameModes.onEnter(p.getGameMode(), adminTest);
                if (p.getGameMode() != want) p.setGameMode(want);
                Location spawn = fs.spawnPoint();
                kr.labyrinth.core.Teleports.to(p, spawn);
                p.setFallDistance(0);
                lastSafe.put(u, spawn);
                kr.labyrinth.core.DeathPenalty.noticeOnce(manager.services(), p, adminTest); // 첫 입장 때 한 번: 쓰러지면 잃는 것
            }
            started = true;
            firstArrival = System.currentTimeMillis();
            onFloorEntered(fs);
        });
    }

    FloorState createFloor(int floor) {
        FloorDef def = manager.services().content().floor(floor);
        if (def == null) return null;
        var boss = manager.services().content().boss(def.boss());
        var arena = boss == null ? kr.labyrinth.content.Params.EMPTY : boss.arena();
        boolean liquid = def.liquid() != null && !def.liquid().isBlank() && !"null".equalsIgnoreCase(def.liquid());
        FloorGenerator.Params gp = params(def, arena, liquid);
        long seed = seedBase * 1_000_003L + floor * 7919L;
        FloorLayout layout = FloorGenerator.generate(gp, seed);
        int ox = InstanceAllocator.originX(slot), oz = InstanceAllocator.originZ(slot);
        int y0 = manager.config().floorY(floor);
        return new FloorState(manager, this, floor, def, contextFor(floor), layout, seed, ox, y0, oz);
    }

    /** floors.yml 층 + 보스 투기장 → 층 설계 입력 (미로 복잡도 = floors.yml maze). */
    static FloorGenerator.Params params(FloorDef def, kr.labyrinth.content.Params arena, boolean liquid) {
        return new FloorGenerator.Params(def.cells(), def.rooms(), def.roomHeight(), 4, liquid,
                arena.integer("radius", 14), arena.integer("height", 10), arena.integer("corridor_length", 0),
                arena.integer("corridor_width", 7), arena.integer("rim_radius", 0),
                kr.labyrinth.dungeon.gen.MazeGenerator.Settings.of(def.raw().sub("maze")));
    }

    /** 층 첫 도착: 제목 + 카운트다운 후 시작방 문 개방. */
    private void onFloorEntered(FloorState fs) {
        FloorDef def = fs.def();
        fs.title("<gradient:#c9a2ff:#7fd8ff><b>" + Text.escape(def.subtitle() == null ? "지하 " + def.number() + "층" : def.subtitle())
                + "</b></gradient>", def.name(), 10, 60, 20);
        fs.broadcast("<gray>" + def.description());
        fs.broadcast("<gray>서버 난이도 <white>" + difficulty.name() + "</white> · 인원 <white>" + members.size()
                + "</white>명 (몹 HP ×" + String.format("%.2f", fs.ctx().hpMultiplier()) + ", 피해 ×"
                + String.format("%.2f", fs.ctx().damageMultiplier()) + ")");
        for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.AMBIENT_CAVE, 1.0f, 0.6f);
        if (fs.startRoom() instanceof kr.labyrinth.dungeon.rooms.StartRoom sr) sr.beginCountdown(manager.config().startCountdown());
    }

    // ── 틱 ────────────────────────────────────────────────────────────────

    void tick(long t) {
        lastTick = t;
        if (ending) return;
        if (genBar != null && current != null && !current.ready()) {
            genBar.progress((float) Math.max(0, Math.min(1, current.progress())));
        }
        if (!started || current == null) return;
        List<Player> online = onlineMembers();
        if (online.isEmpty()) {
            if (emptySince < 0) emptySince = System.currentTimeMillis();
            else if (System.currentTimeMillis() - emptySince > manager.config().emptyTimeout() * 1000L) {
                Log.info("인스턴스 " + id + " — 접속한 파티원이 없어 정리합니다.");
                end(false, null);
            }
            return;
        }
        emptySince = -1;
        List<Player> alive = aliveOnline();
        if (alive.isEmpty()) {
            wipe();
            return;
        }
        for (Player p : alive) current.updatePresence(p);
        current.tick(t);
        if (next != null && next.ready() && next != current) next.tick(t);

        if (t % 10 == 0) {
            for (Player p : online) {
                if (isAlive(p)) safety(p);
                else leash(p, alive);
            }
            stairsCheck(online);
        }
        if (t % 20 == 0) ambient(online);
    }

    /** 바닥 아래로 떨어짐·도랑 빠짐 → 피해 + 마지막 안전 위치. */
    private void safety(Player p) {
        FloorState fs = floorOf(p);
        if (fs == null) {
            // 층 밖(공허) → 마지막 안전 위치 (그 층이 이미 지워졌으면 현재 층 시작방)
            kr.labyrinth.core.Teleports.to(p, safeSpot(p.getUniqueId()));
            return;
        }
        Location l = p.getLocation();
        Material feet = l.getBlock().getType();
        boolean inLiquid = (feet == Material.WATER || feet == Material.LAVA)
                && fs.layout().kind(fs.tileX(l), fs.tileZ(l)) == FloorLayout.GUTTER;
        boolean inStairs = inStairs(fs, l);
        boolean fell = l.getY() < fs.y0() - 2 && !inStairs;
        if (inLiquid || fell) {
            Location back = lastSafe.getOrDefault(p.getUniqueId(), fs.spawnPoint());
            kr.labyrinth.core.Teleports.to(p, back);
            p.setFireTicks(0);
            p.setFallDistance(0);
            double pct = manager.config().fallDamage();
            if (pct > 0) manager.services().damage().deal(kr.labyrinth.combat.DamageContext.percent(null, p, pct).source("dungeon_fall"));
            Text.send(p, "<gray>발을 헛디뎠습니다! <red>-" + Text.pct(pct) + " HP");
            return;
        }
        int tx = fs.tileX(l), tz = fs.tileZ(l);
        if (p.isOnGround() && fs.layout().walkable(tx, tz) && Math.abs(l.getY() - (fs.y0() + fs.layout().standHeight(tx, tz))) < 1.2) {
            lastSafe.put(p.getUniqueId(), l.clone());
        }
    }

    private void leash(Player p, List<Player> alive) {
        Player nearest = null;
        double best = Double.MAX_VALUE;
        for (Player a : alive) {
            if (!a.getWorld().equals(p.getWorld())) continue;
            double d = a.getLocation().distanceSquared(p.getLocation());
            if (d < best) {
                best = d;
                nearest = a;
            }
        }
        double leash = manager.config().spectatorLeash();
        if (nearest != null && best > leash * leash) {
            kr.labyrinth.core.Teleports.to(p, nearest.getLocation().add(0, 2, 0));
            manager.services().hud().actionBar(p, Text.mm("<gray>관전 중에는 파티원 곁을 떠날 수 없습니다."), 40);
        }
    }

    private void ambient(List<Player> online) {
        FloorState fs = current;
        var amb = fs.def().ambient();
        if (amb == null || amb.isEmpty()) return;
        Particle particle = manager.particle(amb.str("particle", null));
        double density = amb.dbl("density", 1.0);
        String sound = amb.str("sound", null);
        var interval = amb.intRange("sound_interval", new kr.labyrinth.content.IntRange(30, 60));
        float volume = (float) amb.dbl("volume", 0.5);
        float pitch = (float) amb.dbl("pitch", 1.0);
        long now = System.currentTimeMillis();
        for (Player p : online) {
            if (!fs.onThisFloor(p.getLocation())) continue;
            if (particle != null) {
                int count = (int) Math.floor(density) + (rng.nextDouble() < density - Math.floor(density) ? 1 : 0);
                for (int i = 0; i < count; i++) {
                    Location l = p.getLocation().add(rng.nextDouble() * 14 - 7, rng.nextDouble() * 4, rng.nextDouble() * 14 - 7);
                    try {
                        p.spawnParticle(particle, l, 1, 0.2, 0.2, 0.2, 0.0);
                    } catch (Throwable ex) {
                        manager.disableParticle(particle);
                        break;
                    }
                }
            }
            if (sound != null && !sound.isBlank()) {
                long due = nextAmbientSound.getOrDefault(p.getUniqueId(), now + interval.roll(rng) * 1000L);
                if (now >= due) {
                    p.playSound(p.getLocation(), sound, volume, pitch);
                    due = now + interval.roll(rng) * 1000L;
                }
                nextAmbientSound.put(p.getUniqueId(), due);
            }
        }
    }

    /** 플레이어가 서 있는 층 (현재/다음/이전). */
    FloorState floorOf(Player p) { return floorAt(p.getLocation()); }

    /** 이 위치가 속한 아직 남아 있는 층 (현재/다음/지워지지 않은 이전, 없으면 null). */
    private FloorState floorAt(Location l) {
        if (current != null && current.onThisFloor(l)) return current;
        if (next != null && next.onThisFloor(l)) return next;
        if (previous != null && !previous.destroyed() && previous.onThisFloor(l)) return previous;
        return null;
    }

    /** 마지막 안전 위치. 없거나 이미 지워진 층(접속이 끊긴 사이 파티가 내려감)이면 현재 층 시작방으로 바꿔 둔다. */
    private Location safeSpot(UUID u) {
        Location l = lastSafe.get(u);
        if (l == null || floorAt(l) == null) {
            l = current.spawnPoint();
            lastSafe.put(u, l);
        }
        return l;
    }

    // ── 사망·부활·이탈 ────────────────────────────────────────────────────

    void onMemberDeath(Player p) {
        states.put(p.getUniqueId(), MemberState.DEAD);
        manager.forgetCombat(p.getUniqueId());
        // 죽음 페널티 (0.3.6.2): 이번 레벨 경험치 + 가방 2~3칸 + 골드 5~25% (장비·열쇠·곡괭이·손에 든 칸은 안전, 셜커 상자는 손에 있어도 안의 재료만). 쓰러질 때 한 번, 안내는 바로 채팅으로
        kr.labyrinth.core.DeathPenalty.onDungeonDown(manager.services(), p, adminTest);
        FloorState fs = floorOf(p);
        if (fs == null) fs = current;
        if (fs != null) fs.addDeath();
        Location at = p.getLocation().clone();
        manager.services().stats().setHp(p, manager.services().stats().maxHp(p));
        p.setFireTicks(0);
        p.setGameMode(GameMode.SPECTATOR);
        kr.labyrinth.core.Teleports.to(p, at.add(0, 1, 0));
        p.showTitle(net.kyori.adventure.title.Title.title(Text.mm("<red><b>쓰러졌습니다</b></red>"),
                Text.mm("<gray>휴식방에 파티원이 닿거나 보스를 쓰러뜨리면 부활합니다")));
        p.playSound(p.getLocation(), Sound.ENTITY_WITHER_SPAWN, 0.4f, 1.6f);
        for (Player o : onlineMembers()) {
            if (!o.equals(p)) Text.send(o, "<red>" + Text.escape(p.getName()) + "</red><gray> 님이 쓰러졌습니다.");
        }
        if (aliveOnline().isEmpty()) wipe();
    }

    /**
     * 0.3.6.2: 싸우는 중에 접속을 끊음 = 쓰러짐 (판정 DungeonManager.onQuitInCombat — PlayerQuitEvent LOW, 아직 접속 중·저장 전).
     * 쓰러짐과 같은 페널티(경험치·물건·골드, 콘솔 기록 먼저) + DEAD + 층 사망 수. 관전 모드로 바꿔 두어 다시 들어오면 관전
     * ({@link #rejoin} 도 DEAD 면 관전), 그사이 공략이 끝났으면 입구로 ({@code recoverStranded} 가 입장 전 모드로 되돌림).
     * 안내는 다시 접속했을 때 (DeathPenalty.showQuitNotice). 살아 있는 사람이 없으면 쓰러짐처럼 전멸.
     */
    void onCombatQuit(Player p) {
        UUID u = p.getUniqueId();
        states.put(u, MemberState.DEAD);
        manager.forgetCombat(u);
        kr.labyrinth.core.DeathPenalty.onCombatQuit(manager.services(), p, adminTest);
        FloorState fs = floorOf(p);
        if (fs == null) fs = current;
        if (fs != null) fs.addDeath();
        try {
            manager.services().stats().setHp(p, manager.services().stats().maxHp(p));
            p.setFireTicks(0);
            p.setGameMode(GameMode.SPECTATOR);
        } catch (Throwable t) {
            Log.error("접속 끊김 쓰러짐 상태 정리 실패 (" + p.getName() + ")", t);
        }
        for (Player o : onlineMembers()) {
            if (!o.equals(p)) Text.send(o, kr.labyrinth.core.DeathPenaltyRules.quitDownPartyText(Text.escape(p.getName())));
        }
        if (aliveOnline().isEmpty()) wipe();
    }

    /** 쓰러진(관전 중) 파티원 전원 부활. */
    public void reviveAll(Location at, double hpFraction) {
        for (Player p : onlineMembers()) {
            if (state(p.getUniqueId()) != MemberState.DEAD) continue;
            revive(p, at, hpFraction);
        }
    }

    public void revive(Player p, Location at, double hpFraction) {
        states.put(p.getUniqueId(), MemberState.ALIVE);
        p.setGameMode(GameModes.onRevive());
        Location to = at.clone();
        to.setYaw(p.getLocation().getYaw());
        kr.labyrinth.core.Teleports.to(p, to);
        p.setFallDistance(0);
        manager.services().stats().setHp(p, manager.services().stats().maxHp(p) * Math.max(0.1, hpFraction));
        p.showTitle(net.kyori.adventure.title.Title.title(Text.mm("<green><b>부활</b></green>"), Text.mm("<gray>다시 일어섰습니다")));
        p.playSound(p.getLocation(), Sound.ITEM_TOTEM_USE, 0.5f, 1.4f);
        p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.2);
        lastSafe.put(p.getUniqueId(), to);
    }

    /** 자발적 퇴장 (/미궁 퇴장). */
    void leave(Player p, boolean silent) {
        UUID u = p.getUniqueId();
        if (!isMember(u)) return;
        states.put(u, MemberState.LEFT);
        restore(p);
        if (!silent) {
            for (Player o : onlineMembers()) Text.send(o, "<gray>" + Text.escape(p.getName()) + " 님이 미궁을 떠났습니다.");
        }
        manager.unbind(p.getUniqueId());
        if (onlineMembers().isEmpty()) end(false, null);
        else if (aliveOnline().isEmpty()) wipe();
    }

    /** 귀환: 게임 모드 복구 + 원래 자리로. */
    void restore(Player p) {
        UUID u = p.getUniqueId();
        manager.services().hud().hideBossBar(p, BAR_GEN);
        manager.services().hud().hideBossBar(p, "dungeon_boss");
        manager.services().hud().hideBossBar(p, "dungeon_gimmick");
        manager.services().hud().hideBossBar(p, "dungeon_boss_hint");
        manager.services().hud().hideBossBar(p, "dungeon_gimmick_hint");
        p.setGameMode(modes.getOrDefault(u, GameMode.SURVIVAL));
        // 층 전용 금고 열쇠는 미궁 밖으로 못 가져간다
        kr.labyrinth.dungeon.treasure.VaultKeys.strip(p, id, 0);
        p.setFireTicks(0);
        p.setFallDistance(0);
        Location back = returnTo.get(u);
        if (back == null || back.getWorld() == null) back = manager.fallbackReturn(p);
        if (manager.isLabyrinthWorld(p.getWorld())) kr.labyrinth.core.Teleports.to(p, back);
        PlayerData d = manager.services().data().get(p);
        d.ext().remove("dungeon.return");
        d.ext().remove("dungeon.gamemode");
        d.markDirty();
    }

    private void wipe() {
        if (ending) return;
        ending = true;
        FloorState fs = current;
        if (fs != null) {
            for (var room : fs.rooms()) {
                try {
                    room.onWipe();
                } catch (Throwable t) {
                    Log.error("전멸 처리 오류 (방 " + room.info().index() + ")", t);
                }
            }
            fs.title("<dark_red><b>전멸</b></dark_red>", "<gray>미궁이 당신들을 삼켰습니다... 입구로 돌아갑니다", 10, 60, 20);
            for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.ENTITY_ELDER_GUARDIAN_CURSE, 0.8f, 0.6f);
        }
        Bukkit.getScheduler().runTaskLater(manager.services().plugin(), () -> end(false, null),
                manager.config().wipeReturnSeconds() * 20L);
    }

    /** 인스턴스 종료: 귀환 + 정리. */
    void end(boolean success, String message) {
        if (finished) return;
        finished = true;
        ending = true;
        for (UUID u : members) {
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.isOnline() && isMember(u)) {
                restore(p);
                if (message != null) Text.send(p, message);
            }
            manager.unbind(u);
        }
        manager.finish(this, false);
    }

    /** 서버 종료/관리자 종료 시 즉시 정리. */
    void destroyFloors(boolean sync, Runnable done) {
        List<FloorState> floors = new ArrayList<>();
        if (current != null) floors.add(current);
        if (next != null && next != current) floors.add(next);
        if (previous != null && previous != current) floors.add(previous);
        if (floors.isEmpty()) {
            done.run();
            return;
        }
        int[] left = {floors.size()};
        for (FloorState f : floors) {
            if (f.destroyed()) {
                if (--left[0] == 0) done.run();
                continue;
            }
            f.destroy(sync, () -> {
                if (--left[0] == 0) done.run();
            });
        }
    }

    // ── 층 클리어 → 계단 → 다음 층 ────────────────────────────────────────

    void onFloorCleared(FloorState fs, Location center) {
        if (fs != current) return;
        fs.clearedAt = System.currentTimeMillis();
        double seconds = (fs.clearedAt - (fs.startedAt() > 0 ? fs.startedAt() : createdAt)) / 1000.0;
        List<Player> players = onlineMembers();
        reviveAll(center, 0.5);
        int max = manager.services().content().maxFloor();
        // 층 첫 돌파 보너스 (dungeon.yml first_clear_bonus): 그 층 레벨 구간 필요 경험치 합 × 배율, 사람마다 한 번
        long firstXp = manager.config().firstClearXp(manager.services().levels().curve(), fs.def().levelRange());
        for (Player p : players) {
            PlayerData d = manager.services().data().get(p);
            d.unlockUpTo(Math.min(max, fs.floor() + 1));
            d.increment("dungeon.floor_clears", 1);
            boolean first = d.increment("dungeon.clear_floor_" + fs.floor(), 1) == 1;
            if (members.size() == 1) d.increment("dungeon.solo_clears", 1);
            if (first && firstXp > 0) {
                try {
                    manager.services().levels().addXp(p, firstXp);
                    manager.services().hud().refresh(p);
                    Text.send(p, "<#c9a2ff>첫 돌파 보너스</#c9a2ff> <green>+" + Text.num(firstXp) + " XP</green>");
                } catch (Throwable t) {
                    Log.error("첫 돌파 보너스 지급 실패", t);
                }
            }
        }
        try {
            Bukkit.getPluginManager().callEvent(new FloorClearEvent(fs.ctx().id(), fs.floor(), players, members.size(),
                    fs.deaths(), seconds, difficulty.id()));
        } catch (Throwable t) {
            Log.error("FloorClearEvent 처리 오류", t);
        }
        String time = String.format("%d분 %02d초", (int) seconds / 60, (int) seconds % 60);
        fs.title("<gold><b>" + Text.escape(fs.def().subtitle() == null ? "지하 " + fs.floor() + "층" : fs.def().subtitle()) + " 돌파!</b></gold>",
                "<gray>" + time + " · 사망 " + fs.deaths() + "회", 10, 80, 20);
        for (Player p : players) p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1.0f, 1.0f);
        celebrate(center);

        if (fs.floor() >= max || manager.services().content().floor(fs.floor() + 1) == null) {
            fs.broadcast("<gradient:#ffd36b:#ff8a3d><b>미궁 라비린스를 정복했습니다!</b></gradient> <gray>"
                    + manager.config().finalReturnSeconds() + "초 뒤 입구로 돌아갑니다.");
            Bukkit.getScheduler().runTaskLater(manager.services().plugin(),
                    () -> { if (!ending) end(true, "<gold>미궁의 심연에서 무사히 돌아왔습니다.</gold>"); },
                    manager.config().finalReturnSeconds() * 20L);
            return;
        }
        fs.broadcast("<gray>투기장 바닥에 <white>아래로 이어지는 계단</white>이 열렸습니다. 내려가면 <white>지하 "
                + (fs.floor() + 1) + "층</white>입니다. <dark_gray>(/미궁 퇴장 으로 귀환)");
        buildStairs(fs);
        next = createFloor(fs.floor() + 1);
        if (next != null) next.build(null);
    }

    private void celebrate(Location center) {
        if (center == null || center.getWorld() == null) return;
        for (int i = 0; i < 4; i++) {
            final int k = i;
            Bukkit.getScheduler().runTaskLater(manager.services().plugin(), () -> {
                Location l = center.clone().add(rng.nextDouble() * 8 - 4, 1, rng.nextDouble() * 8 - 4);
                Firework fw = l.getWorld().spawn(l, Firework.class, f -> {
                    FireworkMeta meta = f.getFireworkMeta();
                    meta.addEffect(org.bukkit.FireworkEffect.builder().with(org.bukkit.FireworkEffect.Type.BALL_LARGE)
                            .withColor(org.bukkit.Color.fromRGB(0xC9A2FF), org.bukkit.Color.fromRGB(0x7FD8FF))
                            .withFade(org.bukkit.Color.fromRGB(0xFFD36B)).trail(true).build());
                    meta.setPower(1);
                    f.setFireworkMeta(meta);
                    f.getPersistentDataContainer().set(kr.labyrinth.core.Keys.INSTANCE,
                            org.bukkit.persistence.PersistentDataType.STRING, id);
                });
                fw.setPersistent(false);
            }, k * 8L);
        }
    }

    /** 투기장 중앙 남쪽에 아래로 내려가는 3칸 폭 계단 + 착지 구역. */
    private void buildStairs(FloorState fs) {
        FloorLayout.Arena a = fs.layout().arena();
        int cx = a.centerX(), cz = a.centerZ();
        int steps = Math.max(3, Math.min(6, a.radius() - 7));
        Material stairMat = Material.DEEPSLATE_TILE_STAIRS;
        Material wallMat = Material.POLISHED_DEEPSLATE;
        Material glow = Material.CRYING_OBSIDIAN;
        BlockData air = Material.AIR.createBlockData();
        int z0 = cz + 2;
        for (int i = 0; i < steps; i++) {
            int z = z0 + i;
            for (int x = cx - 1; x <= cx + 1; x++) {
                Stairs st = (Stairs) stairMat.createBlockData();
                st.setFacing(BlockFace.NORTH);
                fs.setBlock(x, -i, z, st);
                for (int dy = -i + 1; dy <= 0; dy++) fs.setBlock(x, dy, z, air);
                for (int dy = -i + 1; dy <= 3; dy++) {
                    if (dy > 0) fs.setBlock(x, dy, z, air);
                }
                fs.setBlock(x, -i - 1, z, wallMat);
            }
            for (int dy = -i - 1; dy <= -1; dy++) {
                fs.setBlock(cx - 2, dy, z, wallMat);
                fs.setBlock(cx + 2, dy, z, wallMat);
            }
        }
        int landY = -steps;
        int lz0 = z0 + steps, lz1 = lz0 + 2;
        for (int z = lz0; z <= lz1; z++) {
            for (int x = cx - 1; x <= cx + 1; x++) {
                fs.setBlock(x, landY - 1, z, glow);
                for (int dy = landY; dy <= 0; dy++) fs.setBlock(x, dy, z, air);
            }
            for (int dy = landY - 1; dy <= -1; dy++) {
                fs.setBlock(cx - 2, dy, z, wallMat);
                fs.setBlock(cx + 2, dy, z, wallMat);
            }
        }
        for (int x = cx - 2; x <= cx + 2; x++) for (int dy = landY - 1; dy <= -1; dy++) fs.setBlock(x, dy, lz1 + 1, wallMat);
        fs.stairs = new int[] {cx - 1, cx + 1, lz0, lz1, landY};
        Location mid = fs.tile(cx, lz0 + 1, landY + 0.2);
        fs.text(fs.tile(cx, z0 - 1, 2.6), "<gradient:#c9a2ff:#7fd8ff><b>▼ 지하 " + (fs.floor() + 1) + "층</b></gradient>\n<gray>계단을 따라 내려가세요");
        fs.world().playSound(mid, Sound.BLOCK_END_PORTAL_SPAWN, 0.8f, 0.8f);
    }

    private boolean inStairs(FloorState fs, Location l) {
        int[] st = fs.stairs;
        if (st == null) return false;
        int tx = fs.tileX(l), tz = fs.tileZ(l);
        FloorLayout.Arena a = fs.layout().arena();
        return tx >= st[0] - 1 && tx <= st[1] + 1 && tz >= a.centerZ() + 1 && tz <= st[3] + 1;
    }

    private void stairsCheck(List<Player> online) {
        if (current == null) return;
        for (FloorState f : new FloorState[] {current, previous}) {
            if (f == null || f.stairs == null || f.destroyed()) continue;
            Location mid = f.tile(f.stairs[0] + 1, f.stairs[2] + 1, f.stairs[4] + 0.3);
            f.world().spawnParticle(Particle.REVERSE_PORTAL, mid, 14, 1.0, 0.6, 1.0, 0.02);
        }
        for (Player p : online) {
            FloorState fs = floorOf(p);
            if (fs == null || fs.stairs == null || (fs != current && fs != previous)) continue;
            int[] st = fs.stairs;
            int tx = fs.tileX(p.getLocation()), tz = fs.tileZ(p.getLocation());
            boolean landing = tx >= st[0] && tx <= st[1] && tz >= st[2] && tz <= st[3]
                    && p.getLocation().getY() <= fs.y0() + st[4] + 1.2;
            boolean timeout = fs.clearedAt > 0 && System.currentTimeMillis() - fs.clearedAt > manager.config().stairsWaitSeconds() * 1000L;
            boolean target = fs == previous || (next != null && next.ready());
            if (landing || (timeout && target)) descend(p, fs);
        }
        if (previous != null && !previous.destroyed()) {
            boolean anyone = false;
            for (Player p : online) if (previous.onThisFloor(p.getLocation())) anyone = true;
            if (!anyone) {
                FloorState old = previous;
                previous = null;
                old.destroy(false, null);
            }
        }
        // 새 층 시작방: 전원 도착 또는 15초 경과 시 카운트다운
        if (firstArrival > 0 && current.startRoom() instanceof kr.labyrinth.dungeon.rooms.StartRoom sr && !sr.countdownStarted()) {
            boolean all = true;
            for (Player p : aliveOnline()) if (!current.onThisFloor(p.getLocation())) all = false;
            if (all || System.currentTimeMillis() - firstArrival > 15_000) onFloorEntered(current);
        }
    }

    private void descend(Player p, FloorState from) {
        if (from == previous) {
            Location spawn = current.spawnPoint();
            kr.labyrinth.core.Teleports.to(p, spawn);
            p.setFallDistance(0);
            lastSafe.put(p.getUniqueId(), spawn);
            p.playSound(spawn, Sound.BLOCK_PORTAL_TRAVEL, 0.25f, 1.6f);
            return;
        }
        if (next == null) return;
        if (!next.ready()) {
            manager.services().hud().castBar(p, Text.mm("<gray>아래층이 모습을 드러내는 중... <white>"
                    + (int) Math.round(next.progress() * 100) + "%"), next.progress(), 30);
            return;
        }
        // 첫 도착 → 층 교체
        if (previous != null && !previous.destroyed()) previous.destroy(false, null);
        previous = current;
        current = next;
        next = null;
        firstArrival = System.currentTimeMillis();
        Location spawn = current.spawnPoint();
        kr.labyrinth.core.Teleports.to(p, spawn);
        p.setFallDistance(0);
        lastSafe.put(p.getUniqueId(), spawn);
        p.playSound(spawn, Sound.BLOCK_PORTAL_TRAVEL, 0.25f, 1.6f);
        stripOldKeys();
        manager.services().hud().actionBar(p, Text.mm("<gray>지하 " + current.floor() + "층 도착 — 파티원을 기다리는 중..."), 60);
    }

    /** 지난 층 금고 열쇠는 부서진다 (지금 층 것만 남김). */
    private void stripOldKeys() {
        for (Player o : onlineMembers()) {
            if (kr.labyrinth.dungeon.treasure.VaultKeys.strip(o, id, current.floor()) > 0) {
                Text.send(o, "<gray>지난 층의 금고 열쇠가 바스러져 사라졌습니다.");
            }
        }
    }

    /** 재접속한 파티원을 현재 층으로. 쓰러졌으면 관전, 아니면 서바이벌 (입장 전 크리에이티브로 되돌리지 않음). */
    void rejoin(Player p) {
        GameMode want = GameModes.onRejoin(state(p.getUniqueId()) == MemberState.DEAD, p.getGameMode(), adminTest);
        if (p.getGameMode() != want) p.setGameMode(want);
        if (current == null || !current.ready()) return;
        if (floorOf(p) == null) {
            kr.labyrinth.core.Teleports.to(p, safeSpot(p.getUniqueId()));
            p.setFallDistance(0);
        }
    }

    /** 정보 출력용 요약. */
    String summary() {
        FloorState fs = current;
        int cleared = 0, total = 0;
        if (fs != null) {
            for (var r : fs.rooms()) {
                if (r.type() == kr.labyrinth.dungeon.gen.RoomType.START) continue;
                total++;
                if (r.cleared()) cleared++;
            }
        }
        long sec = fs == null || fs.startedAt() == 0 ? 0 : (System.currentTimeMillis() - fs.startedAt()) / 1000;
        return "<white>" + id + "</white> <gray>· 지하 " + (fs == null ? "?" : fs.floor()) + "층 · 방 " + cleared + "/" + total
                + " · 사망 " + (fs == null ? 0 : fs.deaths()) + " · " + (sec / 60) + "분 " + (sec % 60) + "초 · 인원 "
                + aliveOnline().size() + "/" + members.size() + " · 난이도 " + difficulty.name();
    }

    long lastTick() { return lastTick; }
}
