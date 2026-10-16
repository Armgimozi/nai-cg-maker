package kr.labyrinth.dungeon.treasure;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import java.util.UUID;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.Palette;
import kr.labyrinth.dungeon.rooms.Room;
import kr.labyrinth.items.GearItemService;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Lidded;
import org.bukkit.block.data.Bisected;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.type.Door;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Transformation;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 미로 보물 런타임 (GDD §5.6): 막다른 길·미로 굴·비밀방·금고 상자, 열쇠 금고, 미믹.
 * <ul>
 *   <li>상자는 <b>파티원마다 따로</b> — 같은 상자를 열면 각자 자기 몫을 굴린다(한 사람당 한 번, {@link ChestLedger}).
 *       내 몫을 챙긴 상자는 반짝임이 나에게만 멈추고 "빈 상자" 표시가 나에게만 뜬다. 살아 있는 파티원 전원이 챙기면 뚜껑이 열린 채로 남는다.</li>
 *   <li>등급 표시: 철 상자 = 철 띠, 금 상자 = 금 띠 + 금빛 반짝임 (블록 표시 엔티티).</li>
 *   <li>미믹: 처음 연 순간 층 일반 몹 무리를 부르고 잠긴다. 몹을 다 잡으면(또는 {@code treasure.mimic_lock_seconds}) 풀리고 한 단계 좋은 상자가 된다.</li>
 *   <li>금고: 잠긴 철문 — 이 층 금고 열쇠({@link VaultKeys})를 들고 우클릭하면 열린다. 열쇠는 정예 처치 또는 막다른 길 철 상자 하나에서.</li>
 * </ul>
 * 칭호 카운터: {@code titles.treasure.chest|gold_chest|vault|mimic} (titles.yml TREASURE 조건).
 */
public final class Treasures {

    private static final Color GOLD_SPARK = Color.fromRGB(0xFFD36B);

    private final FloorState fs;
    private final TreasurePlan plan;
    private final Map<Integer, Integer> chestAt = new HashMap<>();
    private final Set<Integer> doorTiles = new HashSet<>();
    private final ChestLedger ledger = new ChestLedger();
    private final ChestTier[] tier;
    private final boolean[] emptied;
    private final boolean[] sprung;
    private final boolean[] tamed;
    private final long[] lockUntil;
    private final List<List<CustomMob>> mimicMobs = new ArrayList<>();
    private final Map<UUID, Long> lockedMsg = new HashMap<>();
    private final SplittableRandom rng;
    private boolean vaultOpen;
    private boolean keyGiven;
    private TextDisplay vaultLabel;
    private int opens;

    public Treasures(FloorState fs, TreasurePlan plan) {
        this.fs = fs;
        this.plan = plan;
        int n = plan.chests().size();
        this.tier = new ChestTier[n];
        this.emptied = new boolean[n];
        this.sprung = new boolean[n];
        this.tamed = new boolean[n];
        this.lockUntil = new long[n];
        for (TreasurePlan.Chest c : plan.chests()) {
            chestAt.put(FloorLayout.pack(c.x(), c.z()), c.index());
            tier[c.index()] = c.tier();
            mimicMobs.add(new ArrayList<>());
        }
        if (plan.vault() != null) for (int d : plan.vault().door()) doorTiles.add(d);
        this.rng = new SplittableRandom(fs.seed() ^ 0x6A09E667L);
    }

    public TreasurePlan plan() { return plan; }
    public int chestCount() { return plan.chests().size(); }
    public int vaultCount() { return plan.vault() == null ? 0 : 1; }
    public int mimicCount() { return plan.mimics(); }
    public boolean vaultOpen() { return vaultOpen; }
    public int opens() { return opens; }

    /** 금고·미믹 표 이름 (loot.yml {@code hoard_fNN}, 0.3.5). */
    public static String hoardTable(int floor) { return String.format(java.util.Locale.ROOT, "hoard_f%02d", floor); }

    /** 금고·미믹 상자인가 — 열쇠 금고 안 상자이거나 길들인 미믹 (순수). */
    public static boolean isHoard(TreasurePlan plan, TreasurePlan.Chest c, boolean tamed) {
        if (tamed) return true;
        TreasurePlan.Vault v = plan == null ? null : plan.vault();
        return v != null && c != null && v.contains(c.x(), c.z());
    }

    // ── 생성 ──────────────────────────────────────────────────────────────

    public void prepare(BlockList list, Palette palette) {
        int ox = fs.ox(), y0 = fs.y0(), oz = fs.oz();
        FloorLayout l = fs.layout();
        for (TreasurePlan.Chest c : plan.chests()) {
            BlockData chest = Material.CHEST.createBlockData();
            if (chest instanceof Directional d) d.setFacing(face(c.dirX(), c.dirZ()));
            list.add(ox + c.x(), y0 + l.elevation(c.x(), c.z()) + 1, oz + c.z(), chest);
        }
        TreasurePlan.Vault v = plan.vault();
        if (v != null) {
            BlockData frame = palette.first("accent").createBlockData();
            BlockFace facing = face(v.dirX(), v.dirZ());
            for (int d : v.door()) {
                int x = FloorLayout.unpackX(d), z = FloorLayout.unpackZ(d);
                int h = l.height(x, z);
                boolean gutter = l.kind(x, z) == FloorLayout.GUTTER;
                boolean center = x == v.doorX() && z == v.doorZ();
                for (int y = gutter ? 2 : 1; y <= h; y++) {
                    BlockData b = frame;
                    if (center && y <= 2) b = door(facing, y == 2);
                    list.add(ox + x, y0 + y, oz + z, b);
                }
            }
            // 금고 바닥: 가운데 줄 장식 (안이 특별해 보이게)
            for (int z = v.minZ() + 1; z <= v.maxZ() - 1; z++) {
                for (int x = v.minX() + 1; x <= v.maxX() - 1; x++) {
                    if ((x + z) % 2 == 0) list.add(ox + x, y0, oz + z, palette.first("accent").createBlockData());
                }
            }
        }
    }

    private static BlockData door(BlockFace facing, boolean upper) {
        BlockData d = Material.IRON_DOOR.createBlockData();
        if (d instanceof Door door) {
            door.setFacing(facing);
            door.setHalf(upper ? Bisected.Half.TOP : Bisected.Half.BOTTOM);
            door.setOpen(false);
        }
        return d;
    }

    public void onReady() {
        for (TreasurePlan.Chest c : plan.chests()) {
            if (c.tier() == ChestTier.WOOD) continue;
            band(c, c.tier() == ChestTier.GOLD ? Material.GOLD_BLOCK : Material.IRON_BLOCK);
        }
        TreasurePlan.Vault v = plan.vault();
        if (v != null) {
            vaultLabel = fs.text(fs.tile(v.doorX() + v.dirX() * 0.6, v.doorZ() + v.dirZ() * 0.6, 3.1),
                    "<gold><b>잠긴 금고</b></gold>\n<gray>열쇠 구멍이 희미하게 빛난다");
        }
    }

    /** 철·금 상자 띠 (상자 아래쪽을 두르는 얇은 금속 띠 — 뚜껑과 겹치지 않게). */
    private void band(TreasurePlan.Chest c, Material m) {
        int e = fs.layout().elevation(c.x(), c.z());
        Location corner = new Location(fs.world(), fs.ox() + c.x(), fs.y0() + e + 1, fs.oz() + c.z());
        BlockData data = m.createBlockData();
        for (float[] b : new float[][] {{0.18f, 0.12f}, {0.42f, 0.09f}}) {
            fs.track(fs.world().spawn(corner, BlockDisplay.class, d -> {
                d.setBlock(data);
                d.setTransformation(new Transformation(new Vector3f(0.045f, b[0], 0.045f), new Quaternionf(),
                        new Vector3f(0.91f, b[1], 0.91f), new Quaternionf()));
                d.setBrightness(new Display.Brightness(13, 15));
            }));
        }
    }

    // ── 진행 ──────────────────────────────────────────────────────────────

    /** 2틱마다. */
    public void tick(long t) {
        if (plan.chests().isEmpty()) return;
        long now = System.currentTimeMillis();
        for (int i = 0; i < sprung.length; i++) {
            if (!sprung[i] || tamed[i]) continue;
            List<CustomMob> ms = mimicMobs.get(i);
            ms.removeIf(m -> !FloorState.alive(m));
            if (ms.isEmpty() || now >= lockUntil[i]) tame(i, ms.isEmpty());
        }
        if (t % 20 != 0) return;
        List<Player> alive = fs.alivePlayers();
        for (TreasurePlan.Chest c : plan.chests()) {
            int i = c.index();
            if (emptied[i] || (sprung[i] && !tamed[i])) continue;
            Location at = fs.tile(c.x(), c.z(), fs.layout().elevation(c.x(), c.z()) + 1.5);
            for (Player p : alive) {
                if (ledger.has(i, p.getUniqueId()) || p.getLocation().distanceSquared(at) > 14 * 14) continue;
                switch (tier[i]) {
                    case GOLD -> {
                        p.spawnParticle(Particle.WAX_ON, at, 3, 0.35, 0.3, 0.35, 0);
                        p.spawnParticle(Particle.DUST, at, 2, 0.4, 0.3, 0.4, 0, new Particle.DustOptions(GOLD_SPARK, 0.8f));
                    }
                    case IRON -> p.spawnParticle(Particle.WAX_OFF, at, 2, 0.3, 0.3, 0.3, 0);
                    default -> p.spawnParticle(Particle.WAX_OFF, at, 1, 0.3, 0.3, 0.3, 0);
                }
            }
            // 미믹은 가끔 덜컥 (눈치 빠르면)
            if (c.mimic() && !sprung[i] && t % 120 == 0) {
                for (Player p : alive) {
                    if (p.getLocation().distanceSquared(at) < 7 * 7) {
                        p.playSound(at, Sound.BLOCK_CHEST_CLOSE, 0.25f, 0.5f);
                        break;
                    }
                }
            }
        }
    }

    /** 이 블록이 미로 상자·금고 문이면 처리. @return 처리했으면 true (이벤트 취소) */
    public boolean onInteract(Player p, Block b, Action action) {
        if (!fs.onThisFloor(b.getLocation())) return false;
        int tx = b.getX() - fs.ox(), tz = b.getZ() - fs.oz(), dy = b.getY() - fs.y0();
        int packed = FloorLayout.pack(tx, tz);
        Integer idx = chestAt.get(packed);
        if (idx != null && b.getType() == Material.CHEST) {
            if (action == Action.RIGHT_CLICK_BLOCK) open(p, idx, b);
            return true;
        }
        if (doorTiles.contains(packed) && !vaultOpen && dy >= 1 && dy <= fs.layout().height(tx, tz)) {
            if (action == Action.RIGHT_CLICK_BLOCK) tryVault(p);
            return true;
        }
        return false;
    }

    /** 이 블록이 미로 상자나 금고 문인가 (보조손 이벤트 막기용). */
    public boolean owns(Block b) {
        if (!fs.onThisFloor(b.getLocation())) return false;
        int packed = FloorLayout.pack(b.getX() - fs.ox(), b.getZ() - fs.oz());
        return chestAt.containsKey(packed) || (doorTiles.contains(packed) && !vaultOpen);
    }

    private void open(Player p, int i, Block block) {
        TreasurePlan.Chest c = plan.chests().get(i);
        if (c.mimic() && !sprung[i]) {
            spring(i, block);
            return;
        }
        if (sprung[i] && !tamed[i]) {
            long now = System.currentTimeMillis();
            Long last = lockedMsg.get(p.getUniqueId());
            if (last == null || now - last > 1500) {
                lockedMsg.put(p.getUniqueId(), now);
                fs.services().hud().actionBar(p, Text.mm("<red>상자가 이빨을 딱딱거리며 잠겨 있다!</red> <gray>몬스터를 먼저 쓰러뜨리자"), 40);
            }
            p.playSound(block.getLocation(), Sound.BLOCK_CHEST_LOCKED, 0.8f, 0.6f);
            return;
        }
        if (!ledger.open(i, p.getUniqueId())) {
            Text.send(p, "<gray>이 상자의 내 몫은 이미 챙겼습니다.");
            p.playSound(block.getLocation(), Sound.BLOCK_CHEST_LOCKED, 0.5f, 1.4f);
            return;
        }
        opens++;
        ChestTier t = tier[i];
        Location at = block.getLocation().add(0.5, 1.0, 0.5);
        // 층별 표(maze_chest_<tier>_f<층>)가 있으면 그것 — 구간 표는 3개 층이 같이 써서 장비가 없다 (floors.yml chests.bracket 강제 시만)
        fs.loot(t.table(fs.floor(), bracket(), id -> fs.services().content().lootTable(id) != null), List.of(p), at, "chest");
        String et = t.enhanceTable(fs.floor());   // 강화석은 층 기준 등급으로 따로 한 번 (철·금만)
        if (et != null) fs.loot(et, List.of(p), at, "chest");
        // 0.3.5 금고·미믹 (gear_spec §4.3): 금고 안 상자이거나 길들인 미믹이면 층 표 hoard_fNN 을 한 번 더 (칭호 카운터는 그대로)
        if (isHoard(plan, c, tamed[i])) {
            String ht = hoardTable(fs.floor());
            if (fs.services().content().lootTable(ht) != null) fs.loot(ht, List.of(p), at, "chest");
        }
        p.playSound(at, Sound.BLOCK_CHEST_OPEN, 0.8f, t == ChestTier.GOLD ? 0.8f : 1.1f);
        p.spawnParticle(t == ChestTier.GOLD ? Particle.TOTEM_OF_UNDYING : Particle.HAPPY_VILLAGER, at, t == ChestTier.GOLD ? 24 : 10,
                0.3, 0.3, 0.3, 0.15);
        fs.services().hud().actionBar(p, Text.mm(t.color() + t.displayName() + "</" + t.color().substring(1)
                + " <gray>— 내 몫을 챙겼다"), 40);
        count(p, "chest");
        if (t == ChestTier.GOLD) count(p, "gold_chest");
        if (i == plan.keyChest() && !keyGiven) giveKey(p, "상자 속");
        lidPulse(block);
        mineOnly(p, c);
        List<UUID> party = new ArrayList<>();
        for (Player o : fs.alivePlayers()) party.add(o.getUniqueId());
        if (ledger.allOpened(i, party)) {
            emptied[i] = true;
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
                if (!fs.destroyed() && block.getState() instanceof Lidded lid) lid.open();
            }, 32L);
        }
    }

    private int bracket() {
        try {
            return ChestSettings.of(fs.def().raw().sub("chests")).bracket();
        } catch (Throwable t) {
            return 0;
        }
    }

    private void lidPulse(Block block) {
        if (block.getState() instanceof Lidded lid) {
            lid.open();
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
                if (!fs.destroyed() && block.getState() instanceof Lidded l2) l2.close();
            }, 30L);
        }
    }

    /** 나에게만 보이는 "빈 상자" 표시. */
    private void mineOnly(Player p, TreasurePlan.Chest c) {
        Location at = fs.tile(c.x(), c.z(), fs.layout().elevation(c.x(), c.z()) + 1.75);
        TextDisplay d = fs.track(fs.world().spawn(at, TextDisplay.class, e -> {
            e.text(Text.mm("<dark_gray>빈 상자"));
            e.setBillboard(Display.Billboard.CENTER);
            e.setVisibleByDefault(false);
            e.setBackgroundColor(Color.fromARGB(0, 0, 0, 0));
            e.setViewRange(0.3f);
        }));
        p.showEntity(fs.services().plugin(), d);
    }

    // ── 미믹 ──────────────────────────────────────────────────────────────

    private void spring(int i, Block block) {
        sprung[i] = true;
        lockUntil[i] = System.currentTimeMillis() + fs.config().traps().mimicLockSeconds() * 1000L;
        TreasurePlan.Chest c = plan.chests().get(i);
        Location at = block.getLocation().add(0.5, 0, 0.5);
        fs.world().spawnParticle(Particle.LARGE_SMOKE, at.clone().add(0, 0.8, 0), 30, 0.4, 0.4, 0.4, 0.05);
        fs.sound(at, Sound.ENTITY_EVOKER_PREPARE_ATTACK, 1.0f, 0.7f);
        fs.sound(at, Sound.BLOCK_CHEST_LOCKED, 1.0f, 0.5f);
        lidPulse(block);
        fs.actionBar(fs.allPlayers(), "<red><b>미믹이다!</b></red> <gray>상자가 이빨을 드러내고 동료를 부른다", 60);
        int n = fs.config().mimicMobs() + fs.floor() / 4;
        List<CustomMob> list = mimicMobs.get(i);
        FloorLayout l = fs.layout();
        for (int k = 0; k < n; k++) {
            int fx = c.x() + c.dirX() * (1 + k % 3), fz = c.z() + c.dirZ() * (1 + k % 3);
            Location spot = l.walkable(fx, fz) ? fs.tile(fx, fz, l.standHeight(fx, fz)) : at.clone().add(0, 1, 0);
            spot.add(rng.nextDouble() - 0.5, 0, rng.nextDouble() - 0.5);
            CustomMob m = fs.spawnMob(fs.randomFloorMob(rng), spot);
            if (m != null) list.add(m);
        }
    }

    private void tame(int i, boolean defeated) {
        tamed[i] = true;
        tier[i] = tier[i].up();
        TreasurePlan.Chest c = plan.chests().get(i);
        Location at = fs.tile(c.x(), c.z(), fs.layout().elevation(c.x(), c.z()) + 1.3);
        fs.world().spawnParticle(Particle.HAPPY_VILLAGER, at, 16, 0.4, 0.3, 0.4, 0);
        fs.sound(at, Sound.BLOCK_CHEST_CLOSE, 1.0f, 1.4f);
        band(c, tier[i] == ChestTier.GOLD ? Material.GOLD_BLOCK : Material.IRON_BLOCK);
        if (defeated) {
            fs.broadcast("<gold>미믹을 길들였다!</gold> <gray>얌전해진 상자가 " + tier[i].displayName() + "(으)로 변했습니다 — 각자 열어 보세요.");
            for (Player p : fs.alivePlayers()) count(p, "mimic");
        } else {
            fs.broadcast("<gray>미믹이 지쳐 입을 다물었습니다. 이제 열 수 있습니다.");
        }
    }

    // ── 금고·열쇠 ─────────────────────────────────────────────────────────

    private void tryVault(Player p) {
        if (vaultOpen) return;
        if (!VaultKeys.consume(p, fs.run().id(), fs.floor())) {
            long now = System.currentTimeMillis();
            Long last = lockedMsg.get(p.getUniqueId());
            if (last == null || now - last > 2000) {
                lockedMsg.put(p.getUniqueId(), now);
                Text.send(p, "<gray>굳게 잠긴 금고 문이다. <gold>이 층의 금고 열쇠</gold>가 필요하다. "
                        + (plan.keyFromElite() ? "<dark_gray>(정예가 지니고 있다는 소문)" : "<dark_gray>(어느 막다른 길 상자 속에)"));
            }
            p.playSound(p.getLocation(), Sound.BLOCK_IRON_DOOR_CLOSE, 0.6f, 0.6f);
            return;
        }
        openVault(p);
    }

    /** 금고 문을 연다 (by = null 이면 자가 진단). */
    public void openVault(Player by) {
        TreasurePlan.Vault v = plan.vault();
        if (v == null || vaultOpen) return;
        vaultOpen = true;
        FloorLayout l = fs.layout();
        BlockData air = Material.AIR.createBlockData();
        // 문짝(위·아래) 먼저 지워야 이웃 갱신으로 반쪽이 남지 않는다
        for (int d : v.door()) {
            int x = FloorLayout.unpackX(d), z = FloorLayout.unpackZ(d);
            int h = l.height(x, z);
            for (int y = h; y >= (l.kind(x, z) == FloorLayout.GUTTER ? 2 : 1); y--) fs.setBlock(x, y, z, air);
            fs.world().spawnParticle(Particle.CLOUD, fs.tile(x, z, 1.5), 6, 0.3, 0.6, 0.3, 0.02);
        }
        if (vaultLabel != null) fs.untrack(vaultLabel);
        Location c = fs.tile(v.doorX(), v.doorZ(), 1.5);
        fs.sound(c, Sound.BLOCK_IRON_DOOR_OPEN, 1.2f, 0.6f);
        fs.sound(c, Sound.BLOCK_VAULT_OPEN_SHUTTER, 1.0f, 0.9f);
        fs.world().spawnParticle(Particle.WAX_ON, fs.tile((v.minX() + v.maxX()) / 2.0, (v.minZ() + v.maxZ()) / 2.0, 1.5), 40, 1.6, 0.6, 1.6, 0);
        if (by == null) return;
        fs.broadcast("<gold><b>금고가 열렸다!</b></gold> <gray>" + Text.escape(by.getName()) + " 님이 금고 열쇠로 문을 열었습니다. 금 상자 "
                + v.chests().size() + "개 — 각자 자기 몫을 챙기세요.");
        count(by, "vault");
    }

    /** 정예방을 정리했다 — 열쇠가 정예에게서 나오는 층이면 방 안 파티원 한 명에게. */
    public void onEliteCleared(Room room) {
        if (plan.vault() == null || !plan.keyFromElite() || keyGiven) return;
        List<Player> inside = room.alivePlayersInside();
        if (inside.isEmpty()) inside = fs.alivePlayers();
        if (inside.isEmpty()) return;
        giveKey(inside.get(rng.nextInt(inside.size())), "정예의 품속");
    }

    private void giveKey(Player p, String where) {
        ItemStack key = VaultKeys.create(fs.services(), fs.run().id(), fs.floor());
        if (key == null) {
            Log.warn("items.yml 에 " + VaultKeys.ITEM_ID + " 가 없어 금고 열쇠를 줄 수 없습니다.");
            return;
        }
        keyGiven = true;
        GearItemService.deliver(p, key);
        p.playSound(p.getLocation(), Sound.ITEM_ARMOR_EQUIP_CHAIN, 1.0f, 1.4f);
        fs.broadcast("<gold>금고 열쇠!</gold> <gray>" + Text.escape(p.getName()) + " 님이 " + where + "에서 <gold>지하 " + fs.floor()
                + "층 금고 열쇠</gold>를 찾았습니다. 어딘가의 잠긴 금고 문에 대고 우클릭하세요. <dark_gray>(이 층에서만 쓸 수 있음)");
    }

    /** 칭호 카운터 + 재판정. */
    private void count(Player p, String kind) {
        try {
            fs.services().data().get(p).increment("titles.treasure." + kind, 1);
            fs.services().titles().onTreasure(p, kind);
        } catch (Throwable t) {
            Log.error("보물 칭호 카운터 실패", t);
        }
    }

    // ── 자가 진단 ─────────────────────────────────────────────────────────

    /** 상자 블록이 놓였나·금고 문이 열리나·미믹이 부르나 (예외는 위로). @return [놓인 상자, 금고 열림 1/0, 미믹 몹 수] */
    public int[] selfTest() {
        int ok = 0;
        FloorLayout l = fs.layout();
        for (TreasurePlan.Chest c : plan.chests()) {
            Block b = fs.block(c.x(), l.elevation(c.x(), c.z()) + 1, c.z());
            if (b.getType() != Material.CHEST) throw new IllegalStateException("상자 블록 없음 (" + b.getType() + ")");
            ok++;
        }
        int vault = 0;
        TreasurePlan.Vault v = plan.vault();
        if (v != null) {
            if (fs.block(v.doorX(), 1, v.doorZ()).getType() != Material.IRON_DOOR) throw new IllegalStateException("금고 문 없음");
            openVault(null);
            if (!fs.block(v.doorX(), 1, v.doorZ()).getType().isAir()) throw new IllegalStateException("금고 문이 열리지 않음");
            vault = 1;
        }
        int mobs = 0;
        for (TreasurePlan.Chest c : plan.chests()) {
            if (!c.mimic()) continue;
            spring(c.index(), fs.block(c.x(), l.elevation(c.x(), c.z()) + 1, c.z()));
            mobs += mimicMobs.get(c.index()).size();
            break;
        }
        return new int[] {ok, vault, mobs};
    }

    static BlockFace face(int dx, int dz) {
        if (dx > 0) return BlockFace.EAST;
        if (dx < 0) return BlockFace.WEST;
        if (dz > 0) return BlockFace.SOUTH;
        return BlockFace.NORTH;
    }
}
