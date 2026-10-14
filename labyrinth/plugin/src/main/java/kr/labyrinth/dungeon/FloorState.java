package kr.labyrinth.dungeon;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import kr.labyrinth.Services;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.BlockPlacer;
import kr.labyrinth.dungeon.gen.FloorBuilder;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.dungeon.rooms.BattleRoom;
import kr.labyrinth.dungeon.rooms.BossRoom;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import kr.labyrinth.dungeon.rooms.RestRoom;
import kr.labyrinth.dungeon.rooms.Room;
import kr.labyrinth.dungeon.rooms.StartRoom;
import kr.labyrinth.dungeon.rooms.TreasureRoom;
import kr.labyrinth.mobs.CustomMob;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.persistence.PersistentDataType;

/**
 * 한 층의 런타임 (블록·방·몹·표시 엔티티). Run 이 층마다 하나씩 만든다. 원점 (ox, y0, oz) = 타일 (0,0) 의 바닥 블록.
 */
public final class FloorState {

    private final DungeonManager manager;
    private final Run run;
    private final int floor;
    private final FloorDef def;
    private final InstanceContext ctx;
    private final FloorLayout layout;
    private final long seed;
    private final int ox, y0, oz;
    private final List<Room> rooms = new ArrayList<>();
    private final Set<Long> extras = new LinkedHashSet<>();
    private final Set<Long> chunkTickets = new HashSet<>();
    private final List<Entity> entities = new ArrayList<>();
    private long[] shell = new long[0];
    private volatile double progress;
    private boolean ready;
    private boolean destroyed;
    private boolean cleared;
    private long startedAt;
    private int deaths;
    private int maxTop;
    /** 보스 처치 후 계단 착지 구역 {minX, maxX, minZ, maxZ, landY} (없으면 null). */
    int[] stairs;
    long clearedAt = -1;
    private Runnable cancelBuild;
    private final SecretPassages secrets;
    private final Exploration exploration;

    FloorState(DungeonManager manager, Run run, int floor, FloorDef def, InstanceContext ctx, FloorLayout layout,
               long seed, int ox, int y0, int oz) {
        this.manager = manager;
        this.run = run;
        this.floor = floor;
        this.def = def;
        this.ctx = ctx;
        this.layout = layout;
        this.seed = seed;
        this.ox = ox;
        this.y0 = y0;
        this.oz = oz;
        this.maxTop = layout.maxTop(); // 가장 높은 천장 (계단 복도 단상 포함)
        for (FloorLayout.RoomInfo r : layout.rooms()) rooms.add(createRoom(r));
        this.secrets = new SecretPassages(this);
        this.exploration = new Exploration(this);
    }

    private Room createRoom(FloorLayout.RoomInfo r) {
        return switch (r.type()) {
            case START -> new StartRoom(this, r);
            case COMBAT -> new BattleRoom(this, r, false);
            case ELITE -> new BattleRoom(this, r, true);
            case TREASURE -> new TreasureRoom(this, r);
            case REST -> new RestRoom(this, r);
            case GIMMICK -> GimmickRoom.create(this, r, def.gimmick());
            case BOSS -> new BossRoom(this, r);
            case HALL -> throw new IllegalStateException("복도는 방이 아님");
        };
    }

    // ── 생성 ──────────────────────────────────────────────────────────────

    void build(Runnable onReady) {
        Set<Integer> noDecor = new HashSet<>(), noLight = new HashSet<>();
        for (Room r : rooms) {
            if (!r.wantsDecor()) noDecor.add(r.info().index());
            if (!r.wantsLights()) noLight.add(r.info().index());
        }
        Params arena = bossArena();
        FloorBuilder builder = new FloorBuilder(layout, def, ox, y0, oz, seed, noDecor, noLight, arena);
        BlockList list = builder.build();
        for (Room r : rooms) {
            try {
                r.prepare(list);
            } catch (Throwable t) {
                Log.error("방 소품 준비 실패: " + r.type(), t);
            }
        }
        shell = list.positions();
        cancelBuild = manager.placer().place(world(), list, chunkTickets, p -> progress = p, () -> {
            if (destroyed) return;
            ready = true;
            progress = 1.0;
            for (Room r : rooms) {
                try {
                    r.onReady();
                } catch (Throwable t) {
                    Log.error("방 준비 실패: " + r.type(), t);
                }
            }
            if (onReady != null) onReady.run();
        });
    }

    Params bossArena() {
        var boss = services().content().boss(def.boss());
        return boss == null ? Params.EMPTY : boss.arena();
    }

    /** 블록·엔티티·몹 정리 (예산 나눠서). sync = 서버 종료 시 즉시. */
    void destroy(boolean sync, Runnable done) {
        if (destroyed) return;
        destroyed = true;
        if (cancelBuild != null) cancelBuild.run();
        for (Room r : rooms) {
            try {
                r.onDestroy();
            } catch (Throwable t) {
                Log.error("방 정리 실패", t);
            }
        }
        try {
            services().mobs().removeAll(ctx.id());
        } catch (Throwable t) {
            Log.error("몹 정리 실패", t);
        }
        try {
            services().bosses().endAll(ctx.id());
        } catch (Throwable t) {
            Log.error("보스 정리 실패", t);
        }
        for (Entity e : entities) if (e.isValid()) e.remove();
        entities.clear();
        World w = world();
        if (w == null) {
            if (done != null) done.run();
            return;
        }
        // 이 인스턴스 태그가 달린 남은 엔티티 (이펙트 등)
        for (Entity e : w.getEntities()) {
            String inst = e.getPersistentDataContainer().get(Keys.INSTANCE, PersistentDataType.STRING);
            if (ctx.id().equals(inst) && !(e instanceof Player)) e.remove();
        }
        // 보스 구현이 투기장에 놓았을 수 있는 블록(기둥·해자 등)까지 비우기: 투기장 원기둥 내부 + 바닥 아래 2칸
        FloorLayout.Arena a = layout.arena();
        int bossIdx = layout.bossRoom().index();
        for (int z = a.centerZ() - a.radius() - 1; z <= a.centerZ() + a.radius() + a.corridorLength() + 1; z++) {
            for (int x = a.centerX() - a.radius() - 1; x <= a.centerX() + a.radius() + 1; x++) {
                if (layout.region(x, z) != bossIdx) continue;
                int h = layout.height(x, z);
                for (int dy = -2; dy <= h; dy++) {
                    if (dy == 0) continue;
                    extras.add(BlockList.pack(ox + x, y0 + dy, oz + z));
                }
            }
        }
        long[] all = new long[shell.length + extras.size()];
        System.arraycopy(shell, 0, all, 0, shell.length);
        int i = shell.length;
        for (long p : extras) all[i++] = p;
        if (sync) {
            BlockPlacer.clearNow(w, all);
            manager.placer().releaseChunks(w, chunkTickets);
            if (done != null) done.run();
        } else {
            manager.placer().clear(w, all, () -> {
                manager.placer().releaseChunks(w, chunkTickets);
                if (done != null) done.run();
            });
        }
    }

    // ── 진행 ──────────────────────────────────────────────────────────────

    void tick(long t) {
        if (!ready || destroyed) return;
        try {
            secrets.tick(t);
        } catch (Throwable e) {
            Log.error("비밀 통로 틱 오류", e);
        }
        for (Room r : rooms) {
            try {
                r.tick(t);
            } catch (Throwable e) {
                Log.error("방 틱 오류 (" + r.type() + ")", e);
            }
        }
    }

    /** 살아 있는 파티원 위치 → 방 진입 알림. */
    void updatePresence(Player p) {
        Location l = p.getLocation();
        if (!onThisFloor(l)) return;
        exploration.visit(l);
        int region = layout.region(tileX(l), tileZ(l));
        if (region < 0) return;
        if (layout.kind(tileX(l), tileZ(l)) != FloorLayout.FLOOR) return;
        Room r = rooms.get(region);
        try {
            r.onEnter(p);
        } catch (Throwable e) {
            Log.error("방 진입 처리 오류", e);
        }
    }

    public void markStarted() { startedAt = System.currentTimeMillis(); }

    /** 보스 처치 → Run 에 알림. */
    public void onBossDefeated(Location center) {
        if (cleared) return;
        cleared = true;
        run.onFloorCleared(this, center);
    }

    // ── 공용 헬퍼 (방 구현용) ─────────────────────────────────────────────

    public Services services() { return manager.services(); }
    public DungeonManager manager() { return manager; }
    public DungeonConfig config() { return manager.config(); }
    public Run run() { return run; }
    public int floor() { return floor; }
    public FloorDef def() { return def; }
    public InstanceContext ctx() { return ctx; }
    public FloorLayout layout() { return layout; }
    public long seed() { return seed; }
    public int ox() { return ox; }
    public int y0() { return y0; }
    public int oz() { return oz; }
    public List<Room> rooms() { return rooms; }
    /** 금 간 벽 비밀 통로 (열기·열림 알림). */
    public SecretPassages secrets() { return secrets; }
    /** 파티가 함께 쓰는 탐험 기록 (지나간 셀·보스 문·비밀 통로). */
    public Exploration exploration() { return exploration; }
    public Room startRoom() { return rooms.get(layout.startRoom().index()); }
    public Room bossRoom() { return rooms.get(layout.bossRoom().index()); }
    public boolean ready() { return ready; }
    public boolean destroyed() { return destroyed; }
    public boolean cleared() { return cleared; }
    public double progress() { return progress; }
    public long startedAt() { return startedAt; }
    public int deaths() { return deaths; }
    void addDeath() { deaths++; }
    public World world() { return manager.world(); }

    /** 이 층의 높이 띠 안인가 (같은 슬롯의 다른 층과 구분). */
    public boolean onThisFloor(Location l) {
        if (l == null || l.getWorld() == null || !l.getWorld().equals(world())) return false;
        double y = l.getY();
        // 계단 착지(y0-7)까지 포함, 아래층 천장(y0 - 간격 + 높이 + 1)과 겹치지 않게 (간격 ≥ 30)
        if (y < y0 - 9 || y > y0 + maxTop + 2) return false;
        int tx = tileX(l), tz = tileZ(l);
        return tx >= -4 && tz >= -4 && tx < layout.width() + 4 && tz < layout.depth() + 4;
    }

    public int tileX(Location l) { return l.getBlockX() - ox; }
    public int tileZ(Location l) { return l.getBlockZ() - oz; }

    /** 타일 중심 위치 (dy = 바닥 기준 높이; 1 = 바닥 위). */
    public Location tile(double tx, double tz, double dy) {
        return new Location(world(), ox + tx + 0.5, y0 + dy, oz + tz + 0.5);
    }

    public Block block(int tx, int dy, int tz) { return world().getBlockAt(ox + tx, y0 + dy, oz + tz); }

    /** 런타임 블록 변경 (정리 목록에 기록). */
    public void setBlock(int tx, int dy, int tz, BlockData d) {
        int x = ox + tx, y = y0 + dy, z = oz + tz;
        world().getBlockAt(x, y, z).setBlockData(d, false);
        extras.add(BlockList.pack(x, y, z));
    }

    public void setBlock(int tx, int dy, int tz, Material m) { setBlock(tx, dy, tz, m.createBlockData()); }

    /** 이 층에 있는 온라인 파티원 (관전 포함). */
    public List<Player> allPlayers() {
        List<Player> out = new ArrayList<>();
        for (Player p : run.onlineMembers()) if (onThisFloor(p.getLocation())) out.add(p);
        return out;
    }

    /** 이 층에 있는 살아 있는 파티원. */
    public List<Player> alivePlayers() {
        List<Player> out = new ArrayList<>();
        for (Player p : run.onlineMembers()) if (run.isAlive(p) && onThisFloor(p.getLocation())) out.add(p);
        return out;
    }

    /** 몹 소환 (인스턴스 배율). 실패하면 null. */
    public CustomMob spawnMob(String mobId, Location at) {
        return spawnMob(mobId, at, ctx);
    }

    public CustomMob spawnMob(String mobId, Location at, InstanceContext c) {
        if (mobId == null) return null;
        try {
            CustomMob m = services().mobs().spawn(mobId, at, c);
            if (m != null && m.entity() != null) {
                m.entity().getPersistentDataContainer().set(Keys.INSTANCE, PersistentDataType.STRING, ctx.id());
                at.getWorld().spawnParticle(Particle.LARGE_SMOKE, at.clone().add(0, 0.6, 0), 12, 0.3, 0.5, 0.3, 0.02);
            }
            return m;
        } catch (Throwable t) {
            Log.error("몹 소환 실패: " + mobId, t);
            return null;
        }
    }

    /** 층 일반 몹 중 무작위. */
    public String randomFloorMob(java.util.SplittableRandom rng) {
        List<String> list = def.mobs();
        if (list.isEmpty()) return null;
        return list.get(rng.nextInt(list.size()));
    }

    /** 층 일반 몹 평균 경험치 (기믹 보상 = ×10). */
    public double averageMobXp() {
        double sum = 0;
        int n = 0;
        for (String id : def.mobs()) {
            MobDef m = services().content().mob(id);
            if (m != null) {
                sum += m.xp();
                n++;
            }
        }
        return n == 0 ? 10 : sum / n;
    }

    public static boolean alive(CustomMob m) {
        try {
            return m != null && m.isAlive() && m.entity() != null && m.entity().isValid();
        } catch (Throwable t) {
            return false;
        }
    }

    /** 표시 엔티티 등록 (정리 대상 태그 + 비영속). */
    public <T extends Entity> T track(T e) {
        Keys.tagTransient(e, Keys.FX, "dungeon");
        e.getPersistentDataContainer().set(Keys.INSTANCE, PersistentDataType.STRING, ctx.id());
        e.setPersistent(false);
        entities.add(e);
        return e;
    }

    /** 타일 위 떠 있는 글자. */
    public TextDisplay text(Location at, String mm) {
        return track(at.getWorld().spawn(at, TextDisplay.class, d -> {
            d.text(Text.mm(mm));
            d.setBillboard(Display.Billboard.CENTER);
            d.setShadowed(true);
            d.setSeeThrough(false);
            d.setBackgroundColor(Color.fromARGB(110, 10, 8, 20));
            d.setLineWidth(220);
            d.setViewRange(0.6f);
            d.setBrightness(new Display.Brightness(15, 15));
        }));
    }

    public void untrack(Entity e) {
        entities.remove(e);
        if (e != null && e.isValid()) e.remove();
    }

    public void broadcast(String mm) {
        for (Player p : allPlayers()) Text.send(p, mm);
    }

    public void title(String title, String subtitle, int fadeIn, int stay, int fadeOut) {
        Title t = Title.title(Text.mm(title), Text.mm(subtitle), Title.Times.times(Duration.ofMillis(fadeIn * 50L),
                Duration.ofMillis(stay * 50L), Duration.ofMillis(fadeOut * 50L)));
        for (Player p : allPlayers()) p.showTitle(t);
    }

    public void actionBar(List<Player> to, String mm, int ticks) {
        Component c = Text.mm(mm);
        for (Player p : to) services().hud().actionBar(p, c, ticks);
    }

    public void sound(Location at, org.bukkit.Sound s, float vol, float pitch) {
        at.getWorld().playSound(at, s, vol, pitch);
    }

    /** 이 층 살아 있는 파티원 전원에게 경험치 (난이도 배율 포함). */
    public void rewardXp(double base) {
        for (Player p : alivePlayers()) {
            try {
                services().levels().reward(p, base * ctx.xpMultiplier());
            } catch (Throwable t) {
                Log.error("경험치 지급 실패", t);
            }
        }
    }

    /** 개인 루팅 상자 보상. */
    public void loot(String table, List<Player> looters, Location at, String source) {
        if (looters.isEmpty()) return;
        try {
            services().loot().drop(table, looters, at, ctx, source);
        } catch (Throwable t) {
            Log.error("루팅 실패: " + table, t);
        }
    }

    /** 휴식방 타일 등 RoomType 으로 방 찾기. */
    public List<Room> rooms(RoomType type) {
        List<Room> out = new ArrayList<>();
        for (Room r : rooms) if (r.type() == type) out.add(r);
        return out;
    }

    /** 이 층 스폰 지점 (시작방 중앙). */
    public Location spawnPoint() {
        Location l = startRoom().center();
        l.setYaw(0); // 남쪽(+z, 보스 방향)을 바라봄
        return l;
    }
}
