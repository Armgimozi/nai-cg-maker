package kr.souls.world;

import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.enemy.Foe;
import kr.souls.enemy.Foes;
import org.bukkit.Chunk;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.Bisected;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.MultipleFacing;
import org.bukkit.block.data.type.Lantern;
import org.bukkit.block.data.type.Slab;
import org.bukkit.block.data.type.Stairs;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.logging.Logger;

/**
 * 전투 도장 (M1_PLAN 3절, M1 P1b 의 판 1). 코드로 짓는 고딕 석조 홀과 시험 방 북쪽 문에서 오는 복도. 시험 방과 같은 팔레트 (심층암
 * 타일·벽돌, 위치 해시로 섞기) 와 같은 빛 (랜턴만). 몸이 바닐라인 이름 없는 허수아비 셋이 선다. 화톳불은 시험 방의 것을 쓴다.
 * <pre>
 *   도장 가운데 = 시험 방 가운데 + dojo.offset (기본 dx 0, dz -44). 아래 좌표는 가운데 기준 (x 동쪽, z 남쪽, y 0 = 바닥 블록 줄)
 *   홀       안쪽 x -11..11 (23칸), z -14..14 (29칸), 높이 y 1..9. 벽 x ±12, z ±15, 지붕 y 10 위에 1:2 박공.
 *            벽기둥 x ±11, z 12·8·4·0·-4·-8·-12 (그 줄마다 천장 늑재와 매단 랜턴 둘), 그 사이 좁은 창 (쇠창살),
 *            북쪽 벽 가운데 큰 창. 가운데 길 x -1..1 (남쪽 문에서 북쪽 벽까지), 동쪽 달리기 길 x 6..8, z -6..13 (2칸마다 눈금).
 *   문       남쪽 벽 z 15 의 x -1..1, y 1..3, 위가 뾰족한 아치 (시험 방 북쪽 문과 같은 꼴)
 *   복도     z 16 .. (시험 방 문턱 바로 북쪽, 기본 29), 안쪽 x -1..1 · y 1..3, 두 겹 벽 x ±2·±3 (벽감에 랜턴), 지붕 y 4, 4칸마다 아치 늑재
 *   허수아비  toward  ( 0.5, 2.5)  문 쪽 (남쪽) 을 본다: 들어오면 바로 앞
 *            away    (-6.5, 2.5)  북쪽을 본다 (등을 돌렸다: 뒤에서 치기)
 *            lane    ( 7.5,-7.5)  달리기 길 북쪽 끝에서 남쪽을 본다 (길을 따라 달려와 친다)
 *            발밑은 조각 심층암. 북쪽 (z -14..-5) 은 비워 둔다 (판 2 의 시험 말뚝, 판 3 의 투기장은 P2b·P5b)
 * </pre>
 * 판 번호 {@link #VERSION} 와 지은 자리 (offset) 를 souls_world PDC (Keys.DOJO, Keys.DOJO_AT) 에 적는다. 켤 때 판이 낮거나 자리가
 * 바뀌었으면 WorldService 가 (옛 자리를 지우고) 다시 짓는다.
 * <p>
 * 허수아비는 저장하지 않는 몸이라 청크가 내려가면 사라진다 (R7). 이 틱 (Ticker brains 자리, check-every 틱마다) 이 플레이어가 도장
 * (복도와 홀) 에서 near 칸 안에 있는 동안 빈 자리를 다시 세운다: 청크가 내려가 사라진 것은 곧바로, 쓰러졌거나 지운 것은 enemies.yml 의
 * respawn 틱 뒤에. 세울 자리의 청크가 올라와 있지 않으면 기다린다 (세우려고 청크를 올리지 않는다). 밀리거나 돈 허수아비는 제자리로 돌려
 * 놓는다 (Foes.teleport).
 */
public final class Dojo {
    /** 도장 모양을 바꾸면 올린다 (1: 홀과 복도, 허수아비 셋) */
    public static final int VERSION = 1;
    /** 홀 안쪽 반폭 (x), 반길이 (z), 높이 */
    static final int HX = 11, HZ = 14, H = 9;
    /** 복도가 시작하는 z (홀 남쪽 벽 바로 밖) */
    static final int CORR0 = HZ + 2;
    /** 허수아비 id (enemies.yml) */
    public static final String DUMMY = "dummy";

    /** dojo.* (config.yml, M1_PLAN 0.4: 한 곳에서만 읽는다) */
    public record Cfg(int dx, int dz, double near, int every) {
        /** 복도가 시험 방 문턱 (z = -(HALF+2)) 까지 1칸 이상 남는 가장 남쪽의 dz */
        static final int MAX_DZ = TestRoom.SILL - 1 - CORR0;

        public static Cfg read(ConfigurationSection c, Logger log) {
            int dx = c == null ? 0 : c.getInt("dojo.offset.dx", 0);
            int dz = c == null ? -44 : c.getInt("dojo.offset.dz", -44);
            if (dz > MAX_DZ) {
                if (log != null) log.warning("dojo.offset.dz " + dz + " 는 시험 방과 겹쳐 " + MAX_DZ + " 로 읽습니다.");
                dz = MAX_DZ;
            }
            if (dx != 0 && log != null) log.warning("dojo.offset.dx 가 0 이 아니라 도장 복도가 시험 방 북쪽 문 (x = 0) 과 만나지 않습니다.");
            double near = c == null ? 32 : Math.max(4, Math.min(160, c.getDouble("dojo.near", 32)));
            int every = c == null ? 10 : Math.max(1, Math.min(200, c.getInt("dojo.check-every", 10)));
            return new Cfg(dx, dz, near, every);
        }

        /** 복도 북쪽 끝에서 시험 방 문턱 바로 앞까지 (가운데 기준 z) */
        int corridorEnd() {
            return TestRoom.SILL - 1 - dz;
        }
    }

    /** 허수아비 자리 하나 (가운데 기준 블록 가운데, 보는 쪽) */
    public record Spot(String name, double x, double z, float yaw) {}

    /** 판 1 의 셋 (yaw 0 = 남쪽, 180 = 북쪽) */
    public static final List<Spot> SPOTS = List.of(
            new Spot("toward", 0.5, 2.5, 0f),
            new Spot("away", -6.5, 2.5, 180f),
            new Spot("lane", 7.5, -7.5, 0f));

    private static final class Slot {
        final Spot spot;
        Foe foe;
        long respawnAt;

        Slot(Spot spot) {
            this.spot = spot;
        }
    }

    private final Souls plugin;
    private Cfg cfg;
    private final List<Slot> slots = new ArrayList<>();
    /** souls_world 에 지금 판의 도장이 지어져 있다 (PDC 를 매 틱 읽지 않게) */
    private volatile boolean built;
    private boolean nearNow;

    public Dojo(Souls plugin) {
        this.plugin = plugin;
        this.cfg = Cfg.read(plugin.getConfig(), plugin.getLogger());
        for (Spot s : SPOTS) slots.add(new Slot(s));
        plugin.foes().onGone(this::gone);
        World w = plugin.worlds().world();
        built = w != null && isBuilt(w, cfg);
    }

    /** /souls reload: dojo.* 를 다시 읽는다 (자리가 바뀌면 다음 켤 때 또는 /soulstest dojo build 로 옮겨 짓는다). */
    public void reload() {
        cfg = Cfg.read(plugin.getConfig(), plugin.getLogger());
        World w = plugin.worlds().world();
        built = w != null && isBuilt(w, cfg);
    }

    public Cfg cfg() {
        return cfg;
    }

    public boolean built() {
        return built;
    }

    /** 지금 판의 도장이 cfg 의 자리에 지어져 있나 (souls_world PDC). */
    public static boolean isBuilt(World w, Cfg c) {
        Integer v = w.getPersistentDataContainer().get(Keys.DOJO, PersistentDataType.INTEGER);
        String at = w.getPersistentDataContainer().get(Keys.DOJO_AT, PersistentDataType.STRING);
        return v != null && v >= VERSION && at(c).equals(at);
    }

    static String at(Cfg c) {
        return c.dx() + "," + c.dz();
    }

    /** 도장 가운데 (월드 블록 좌표). */
    public int[] center() {
        int[] r = plugin.worlds().roomCenter();
        return new int[]{r[0] + cfg.dx(), r[1], r[2] + cfg.dz()};
    }

    // ── 자리 ──

    /** 복도 남쪽 끝 = 시험 방 북쪽 문 앞 (방 안, 북쪽을 본다). */
    public Location entry(World w) {
        int[] r = plugin.worlds().roomCenter();
        return TestRoom.northDoor(w, r[0], r[1], r[2]);
    }

    /** 홀 문 안쪽 (북쪽을 본다). */
    public Location hall(World w) {
        int[] c = center();
        return new Location(w, c[0] + 0.5, c[1] + 1, c[2] + HZ - 0.5, 180f, 0f);
    }

    /** 허수아비 자리 (월드). */
    public Location spot(World w, Spot s) {
        int[] c = center();
        return new Location(w, c[0] + s.x(), c[1] + 1, c[2] + s.z(), s.yaw(), 0f);
    }

    /** 플레이어가 도장 (복도와 홀) 의 수평 상자에서 r 칸 안에 있나. */
    public boolean near(Location l, double r) {
        World w = plugin.worlds().world();
        if (l == null || w == null || l.getWorld() != w) return false;
        int[] c = center();
        double x0 = c[0] - HX - 1, x1 = c[0] + HX + 2, z0 = c[2] - HZ - 1, z1 = c[2] + cfg.corridorEnd() + 1;
        double dx = Math.max(Math.max(x0 - l.getX(), 0), l.getX() - x1);
        double dz = Math.max(Math.max(z0 - l.getZ(), 0), l.getZ() - z1);
        return dx * dx + dz * dz <= r * r;
    }

    // ── 틱 (Ticker brains 자리) ──

    public void tick(long now) {
        if (now % cfg.every() != 0 || !built || plugin.worlds().building()) return;
        World w = plugin.worlds().world();
        if (w == null) return;
        boolean any = false;
        for (Player p : w.getPlayers()) {
            if (near(p.getLocation(), cfg.near())) {
                any = true;
                break;
            }
        }
        nearNow = any;
        if (!any) return;
        for (Slot s : slots) ensure(w, s, now);
    }

    private void ensure(World w, Slot s, long now) {
        Location at = spot(w, s.spot);
        Foe f = s.foe;
        if (f != null && f.alive() && plugin.foes().of(f.entity()) != null) {
            settle(f, at);
            return;
        }
        s.foe = null;
        if (now < s.respawnAt) return;
        int cx = at.getBlockX() >> 4, cz = at.getBlockZ() >> 4;
        if (!w.isChunkLoaded(cx, cz)) return;
        Chunk ch = w.getChunkAt(cx, cz);
        if (!ch.isEntitiesLoaded()) return;
        s.foe = plugin.foes().spawn(DUMMY, at, "dojo_" + s.spot.name());
        // 정의가 없거나 몸이 몹이 아니면 Foes 가 한 번 알렸다. 틱마다 다시 하지 않게 조금 쉰다
        if (s.foe == null) s.respawnAt = now + 200;
    }

    /** 밀렸거나 돌았으면 제자리로 (Foes.teleport). */
    private void settle(Foe f, Location at) {
        Mob m = f.entity();
        Location l = m.getLocation();
        double dx = l.getX() - at.getX(), dz = l.getZ() - at.getZ(), dy = l.getY() - at.getY();
        if (dx * dx + dz * dz > 0.04 || Math.abs(dy) > 0.6) {
            Foes.teleport(m, at);
            return;
        }
        float dyaw = Math.abs(((m.getBodyYaw() - at.getYaw()) % 360 + 540) % 360 - 180);
        if (dyaw > 3) {
            m.setRotation(at.getYaw(), 0f);
            m.setBodyYaw(at.getYaw());
        }
    }

    /** 등록부에서 빠진 허수아비: 청크가 내려가 사라졌으면 곧바로, 쓰러졌거나 지웠으면 respawn 틱 뒤에 다시 세운다. */
    private void gone(Foe f, String why) {
        for (Slot s : slots) {
            if (s.foe != f) continue;
            s.foe = null;
            long now = plugin.ticker().now();
            int wait = f instanceof Foes.Live l ? l.definition().respawn() : 0;
            s.respawnAt = "unload".equals(why) ? now : now + wait;
        }
    }

    /** 도장의 허수아비를 지운다 (다시 지을 때). 바로 다시 세울 수 있게 기다림도 지운다. */
    public void clearDummies() {
        for (Slot s : slots) {
            Foe f = s.foe;
            s.foe = null;
            s.respawnAt = 0;
            if (f != null) plugin.foes().clear(x -> x == f);
        }
        for (Slot s : slots) s.respawnAt = 0;
    }

    /**
     * 시험 줄 DOJO: v= built= near= alive= slots=이름:상태:체력:eid:어긋남:yaw,… (상태 alive, waitN (N 틱 뒤 다시 세운다), empty. 어긋남은 제자리에서
     * 수평 거리, yaw 는 몸이 보는 쪽)
     */
    public String dump() {
        List<String> parts = new ArrayList<>();
        int alive = 0;
        long now = plugin.ticker().now();
        World w = plugin.worlds().world();
        for (Slot s : slots) {
            Foe f = s.foe;
            boolean ok = f != null && f.alive() && plugin.foes().of(f.entity()) != null;
            if (ok) alive++;
            String where = "-:-";
            if (ok && w != null) {
                Location at = spot(w, s.spot), l = f.entity().getLocation();
                where = String.format(Locale.ROOT, "%.2f:%.0f", Math.hypot(l.getX() - at.getX(), l.getZ() - at.getZ()), f.entity().getBodyYaw());
            }
            parts.add(s.spot.name() + ":" + (ok ? "alive" : now < s.respawnAt ? "wait" + (s.respawnAt - now) : "empty") + ":"
                    + (ok ? String.format(Locale.ROOT, "%.1f", f.hp()) : "-") + ":" + (ok ? f.entity().getEntityId() : -1) + ":" + where);
        }
        int[] c = center();
        return String.format(Locale.ROOT, "DOJO v=%d built=%s near=%s alive=%d slots=%s center=%d,%d,%d", VERSION, built, nearNow, alive,
                String.join(",", parts), c[0], c[1], c[2]);
    }

    // ── 짓기 ──

    /**
     * 지운 뒤 짓는다 (WorldService.buildDojo). 놓은 블록 수. old 가 있으면 (자리가 바뀌었을 때) 옛 자리를 먼저 비운다.
     */
    public int build(World w, int[] oldAt) {
        clearDummies();
        int[] r = plugin.worlds().roomCenter();
        if (oldAt != null) {
            Cfg prev = new Cfg(oldAt[0], oldAt[1], cfg.near(), cfg.every());
            clearArea(w, r[0] + prev.dx(), r[1], r[2] + prev.dz(), prev.corridorEnd());
        }
        int[] c = center();
        int n = build(w, c[0], c[1], c[2], cfg.corridorEnd());
        w.getPersistentDataContainer().set(Keys.DOJO, PersistentDataType.INTEGER, VERSION);
        w.getPersistentDataContainer().set(Keys.DOJO_AT, PersistentDataType.STRING, at(cfg));
        built = true;
        return n;
    }

    /** 지은 자리 (dx, dz) 를 PDC 에서 (없으면 null). */
    public static int[] builtAt(World w) {
        String at = w.getPersistentDataContainer().get(Keys.DOJO_AT, PersistentDataType.STRING);
        if (at == null) return null;
        try {
            String[] p = at.split(",");
            return new int[]{Integer.parseInt(p[0].trim()), Integer.parseInt(p[1].trim())};
        } catch (RuntimeException ex) {
            return null;
        }
    }

    private static void clearArea(World w, int cx, int cy, int cz, int corrEnd) {
        TestRoom.Builder b = new TestRoom.Builder(w, cx, cy, cz);
        b.fill(-HX - 3, -2, -HZ - 3, HX + 3, H + 12, corrEnd, Material.AIR);
    }

    /** 가운데 (cx, cy, cz) 에 홀과 복도를 짓는다 (복도는 z = CORR0..corrEnd). 놓은 블록 수. 물리 갱신 없이 놓는다 (8.10). */
    static int build(World w, int cx, int cy, int cz, int corrEnd) {
        TestRoom.Builder b = new TestRoom.Builder(w, cx, cy, cz);
        clearArea(w, cx, cy, cz, corrEnd);
        hall(b);
        corridor(b, corrEnd);
        return b.count;
    }

    private static void hall(TestRoom.Builder b) {
        int wx = HX + 1, wz = HZ + 1, roof = H + 1;
        // 받침과 바닥
        for (int x = -wx; x <= wx; x++) {
            for (int z = -wz; z <= wz; z++) {
                b.set(x, -1, z, b.pick(x, -1, z, Material.COBBLED_DEEPSLATE, 80, Material.DEEPSLATE, 20));
                b.set(x, 0, z, floor(b, x, z));
            }
        }
        // 가운데 길 (문에서 북쪽 벽까지)
        for (int z = -HZ; z <= wz; z++) {
            for (int x = -1; x <= 1; x++) b.set(x, 0, z, x == 0 ? Material.POLISHED_DEEPSLATE : b.pick(x, 0, z, Material.POLISHED_DEEPSLATE, 70,
                    Material.DEEPSLATE_TILES, 30));
        }
        // 동쪽 달리기 길 x 6..8, z -6..13: 시험 방 구르기 길처럼 2칸마다 가장자리 눈금, 시작 칸은 조각 심층암
        for (int z = -6; z <= 13; z++) {
            for (int x = 6; x <= 8; x++) {
                Material m = Material.POLISHED_DEEPSLATE;
                if (x != 7 && (13 - z) % 2 == 0) m = Material.DEEPSLATE_BRICKS;
                if (x == 7 && z == 13) m = Material.CHISELED_DEEPSLATE;
                b.set(x, 0, z, m);
            }
        }
        // 허수아비 발밑
        for (Spot s : SPOTS) b.set((int) Math.floor(s.x()), 0, (int) Math.floor(s.z()), Material.CHISELED_DEEPSLATE);

        // 벽 (y 0..roof), 창은 아래에서 비운다
        for (int y = 0; y <= roof; y++) {
            for (int i = -wx; i <= wx; i++) {
                b.set(i, y, -wz, wall(b, i, y, -wz));
                b.set(i, y, wz, wall(b, i, y, wz));
            }
            for (int i = -wz; i <= wz; i++) {
                b.set(-wx, y, i, wall(b, -wx, y, i));
                b.set(wx, y, i, wall(b, wx, y, i));
            }
        }
        // 벽 밑동 한 줄은 다듬은 돌
        for (int i = -wx; i <= wx; i++) {
            b.set(i, 1, -wz, Material.POLISHED_DEEPSLATE);
            b.set(i, 1, wz, Material.POLISHED_DEEPSLATE);
        }
        for (int i = -wz; i <= wz; i++) {
            b.set(-wx, 1, i, Material.POLISHED_DEEPSLATE);
            b.set(wx, 1, i, Material.POLISHED_DEEPSLATE);
        }
        // 지붕 (y = roof) 과 1:2 박공 (남북으로 길게)
        for (int x = -wx; x <= wx; x++) {
            int rise = (wx - Math.abs(x)) / 2;
            boolean half = (wx - Math.abs(x)) % 2 == 1;
            for (int z = -wz; z <= wz; z++) {
                for (int y = roof; y <= roof + rise; y++) {
                    b.set(x, y, z, y == roof && Math.abs(x) < wx && Math.abs(z) < wz ? Material.DEEPSLATE_TILES
                            : b.pick(x, y, z, Material.DEEPSLATE_TILES, 70, Material.CRACKED_DEEPSLATE_TILES, 30));
                }
                if (half) b.set(x, roof + rise + 1, z, slab(Material.DEEPSLATE_TILE_SLAB, Slab.Type.BOTTOM));
            }
        }
        // 네 모서리 뾰족탑
        for (int sx : new int[]{-wx, wx}) {
            for (int sz : new int[]{-wz, wz}) {
                for (int y = roof + 1; y <= roof + 3; y++) b.set(sx, y, sz, Material.DEEPSLATE_BRICK_WALL);
            }
        }

        // 벽기둥과 늑재, 매단 랜턴: z 12, 8, 4, 0, -4, -8, -12
        for (int z = -12; z <= 12; z += 4) {
            for (int sx : new int[]{-HX, HX}) {
                for (int y = 1; y <= H - 1; y++) b.set(sx, y, z, y == 1 ? Material.CHISELED_DEEPSLATE : Material.POLISHED_DEEPSLATE);
                // 기둥머리: 늑재를 받치는 거꾸로 계단 (아래 반쪽이 벽 쪽)
                b.set(sx + (sx < 0 ? 1 : -1), H - 1, z, TestRoom.archStair(sx < 0 ? BlockFace.WEST : BlockFace.EAST));
            }
            for (int x = -HX; x <= HX; x++) b.set(x, H, z, Material.POLISHED_DEEPSLATE);
            for (int x : new int[]{-5, 5}) {
                b.set(x, H - 1, z, chain());
                b.set(x, H - 2, z, lantern(true));
            }
        }
        // 기둥 사이 좁은 창 (y 4..7, 쇠창살), 동서 벽
        for (int z = -10; z <= 10; z += 4) {
            for (int sx : new int[]{-wx, wx}) {
                for (int y = 4; y <= 7; y++) b.set(sx, y, z, bars(BlockFace.NORTH, BlockFace.SOUTH));
                b.set(sx, 8, z, Material.CHISELED_DEEPSLATE);
            }
        }
        // 북쪽 벽 가운데 큰 창
        for (int x = -2; x <= 2; x++) {
            int y0 = Math.abs(x) == 2 ? 5 : 3, y1 = Math.abs(x) == 2 ? 6 : x == 0 ? 8 : 7;
            for (int y = y0; y <= y1; y++) b.set(x, y, -wz, bars(BlockFace.EAST, BlockFace.WEST));
        }
        b.set(0, 9, -wz, Material.CHISELED_DEEPSLATE);
        // 남쪽 문 (x -1..1, y 1..3) 과 아치
        for (int x = -1; x <= 1; x++) {
            for (int y = 1; y <= 3; y++) b.set(x, y, wz, Material.AIR);
            b.set(x, 0, wz, Material.POLISHED_DEEPSLATE);
        }
        for (int y = 1; y <= 4; y++) {
            b.set(-2, y, wz, Material.POLISHED_DEEPSLATE);
            b.set(2, y, wz, Material.POLISHED_DEEPSLATE);
        }
        b.set(-1, 4, wz, TestRoom.archStair(BlockFace.WEST));
        b.set(0, 4, wz, Material.AIR);
        b.set(1, 4, wz, TestRoom.archStair(BlockFace.EAST));
        b.set(0, 5, wz, Material.CHISELED_DEEPSLATE);
        // 문 안쪽 양옆의 랜턴 기둥
        for (int x : new int[]{-3, 3}) {
            b.set(x, 1, HZ, Material.DEEPSLATE_BRICK_WALL);
            b.set(x, 2, HZ, lantern(false));
        }
    }

    /** 복도: z = CORR0 .. corrEnd, 안쪽 x -1..1 · y 1..3. */
    private static void corridor(TestRoom.Builder b, int corrEnd) {
        for (int z = CORR0; z <= corrEnd; z++) {
            for (int x = -3; x <= 3; x++) {
                b.set(x, -1, z, Material.COBBLED_DEEPSLATE);
                Material fl = x == 0 ? Material.POLISHED_DEEPSLATE : Math.abs(x) == 1 ? b.pick(x, 0, z, Material.DEEPSLATE_TILES, 70,
                        Material.CRACKED_DEEPSLATE_TILES, 30) : Material.DEEPSLATE_BRICKS;
                b.set(x, 0, z, fl);
                if (Math.abs(x) >= 2) {
                    for (int y = 1; y <= 3; y++) b.set(x, y, z, wall(b, x, y, z));
                }
                b.set(x, 4, z, b.pick(x, 4, z, Material.DEEPSLATE_TILES, 75, Material.CRACKED_DEEPSLATE_TILES, 25));
                if (Math.abs(x) <= 2) b.set(x, 5, z, slab(Material.DEEPSLATE_TILE_SLAB, Slab.Type.BOTTOM));
            }
            // 4칸마다 아치 늑재 (위 모서리의 거꾸로 계단, 밑동은 다듬은 돌)
            if ((z - CORR0) % 4 == 1) {
                b.set(-1, 3, z, TestRoom.archStair(BlockFace.WEST));
                b.set(1, 3, z, TestRoom.archStair(BlockFace.EAST));
                for (int y = 1; y <= 3; y++) {
                    b.set(-2, y, z, Material.POLISHED_DEEPSLATE);
                    b.set(2, y, z, Material.POLISHED_DEEPSLATE);
                }
            }
            // 벽감의 랜턴 (양쪽을 엇갈려 4칸마다)
            if ((z - CORR0) % 4 == 3) {
                int side = ((z - CORR0) / 4) % 2 == 0 ? 2 : -2;
                b.set(side, 2, z, lantern(false));
            }
        }
    }

    private static Material floor(TestRoom.Builder b, int x, int z) {
        int h = b.hash(x, 0, z) % 100;
        if (h < 58) return Material.DEEPSLATE_TILES;
        if (h < 74) return Material.CRACKED_DEEPSLATE_TILES;
        if (h < 90) return Material.POLISHED_DEEPSLATE;
        return Material.COBBLED_DEEPSLATE;
    }

    private static Material wall(TestRoom.Builder b, int x, int y, int z) {
        return b.pick(x, y, z, Material.DEEPSLATE_BRICKS, 72, Material.CRACKED_DEEPSLATE_BRICKS, 28);
    }

    private static BlockData lantern(boolean hanging) {
        Lantern l = (Lantern) Material.LANTERN.createBlockData();
        l.setHanging(hanging);
        return l;
    }

    private static BlockData chain() {
        return Material.IRON_CHAIN.createBlockData();
    }

    private static BlockData slab(Material m, Slab.Type t) {
        Slab s = (Slab) m.createBlockData();
        s.setType(t);
        return s;
    }

    /** 쇠창살 (물리 갱신 없이 놓으므로 잇는 쪽을 직접 준다). */
    private static BlockData bars(BlockFace a, BlockFace c) {
        MultipleFacing f = (MultipleFacing) Material.IRON_BARS.createBlockData();
        f.setFace(a, true);
        f.setFace(c, true);
        return f;
    }

    @SuppressWarnings("unused")
    private static BlockData stairs(Material m, BlockFace facing, Bisected.Half half) {
        Stairs s = (Stairs) m.createBlockData();
        s.setFacing(facing);
        s.setHalf(half);
        return s;
    }
}
