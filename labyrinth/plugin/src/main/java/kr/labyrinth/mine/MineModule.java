package kr.labyrinth.mine;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;

/**
 * 광산 엔진 (0.3.6 Q1, 계약 design/036/CONTRACT.md §2.1~2.6 + §0 주인 늦은 결정) — {@link MineApi} 의 실제 구현.
 * <ul>
 *   <li>광산 월드 {@code labyrinth_mine} (공허 + 층마다 바이옴 띠, 미궁 월드와 같은 규칙 + PvP 끔) · 층 6 (jar 청사진, 바뀐 층만 다시 지음)</li>
 *   <li>승강기 (6층 모두 처음부터, 잠김 없음) · 광산 관리소 (얕은 갱도 홀) · {@code /미궁 광산}</li>
 *   <li>함께 쓰는 광맥 ({@link MineVeins}) · tier 규칙 · 곡괭이 구성요소 ({@link MinePickaxes}) · 광산 밖 곡괭이 막기</li>
 *   <li>안전: 피해 0 · 몹 0 · 배고픔 · 진주·후렴과·양동이 · 떨어지면 승강장 · 게임 모드 규칙 ({@link MineGameModeRule})</li>
 * </ul>
 * 기력·매크로 막기는 없다 (계약 §0-1·§0-2).
 */
public final class MineModule implements Module, MineApi {

    private final Services services;
    private volatile MineConfig config = MineConfig.DEFAULT;
    private volatile boolean active;
    private World world;
    private final List<MineLevel> levels = new ArrayList<>();
    private final Map<Integer, String> built = new HashMap<>();
    private final Map<Long, String> interacts = new HashMap<>();
    private final Set<Material> mineBlocks = EnumSet.noneOf(Material.class);
    private final MineVeins veins = new MineVeins(this);
    private final MineBuilder builder = new MineBuilder(this);
    private final MineLift lift = new MineLift(this);
    private final MineMenus menus = new MineMenus(this);
    private final MinePickaxes pickaxes = new MinePickaxes(this);
    private final MineStats stats = new MineStats();
    private MineListener listener;
    private final List<BukkitTask> tasks = new ArrayList<>();
    private boolean commandsRegistered;

    public MineModule(Services services) { this.services = services; }

    @Override
    public String name() { return "mine"; }

    // ── 켜기·끄기 ───────────────────────────────────────────────────────

    @Override
    public void enable() {
        config = MineConfig.fromRoot(services.plugin().getConfig());
        if (!commandsRegistered) {
            new MineCommands(this).register(services.commands());
            commandsRegistered = true;
        }
        MineDef mine = services.content().mine();
        if (!config.enabled()) {
            Log.info("[광산] 꺼짐 (config mine.enabled: false)");
            return;
        }
        if (mine == null || mine.isEmpty()) {
            Log.warn("[광산] content/mine.yml 이 없거나 비어 있어 광산을 켜지 않습니다.");
            return;
        }
        loadLevels(mine);
        if (levels.isEmpty()) {
            Log.warn("[광산] 청사진을 하나도 읽지 못해 광산을 켜지 않습니다.");
            return;
        }
        world = loadWorld(mine);
        if (world == null) {
            Log.warn("[광산] 광산 월드를 만들지 못했습니다.");
            return;
        }
        veins.reset(levels, config.regenPlayersCap());
        listener = new MineListener(this);
        Bukkit.getPluginManager().registerEvents(listener, services.plugin());
        var plugin = services.plugin();
        tasks.add(Bukkit.getScheduler().runTaskTimer(plugin, this::safeVeinTick, 20L, 20L));
        tasks.add(Bukkit.getScheduler().runTaskTimer(plugin, veins::sparkle, 40L, 40L));
        tasks.add(Bukkit.getScheduler().runTaskTimer(plugin, this::sweepPlayers, 10L, 10L));
        tasks.add(Bukkit.getScheduler().runTaskTimer(plugin, this::sweepMobs, 600L, 600L));
        active = true;
        services.setMine(this);
        startBuild(null, null);
        Log.info("[광산] 켜짐: 층 " + levels.size() + " · 광맥 " + veins.total() + " (함께 씀, 다시 차는 시간 ÷ 광산 사람 수 최대 "
                + config.regenPlayersCap() + ") · 월드 " + world.getName());
    }

    @Override
    public void disable() {
        for (BukkitTask t : tasks) t.cancel();
        tasks.clear();
        builder.cancel();
        lift.cancelAll();
        if (active) {
            int n = veins.refillAll();
            if (n > 0) Log.info("[광산] 빈 광맥 " + n + "곳을 다 찬 상태로 되돌림 (끄기)");
            veins.removeAllDisplays();
        }
        if (listener != null) HandlerList.unregisterAll(listener);
        listener = null;
        if (world != null) world.removePluginChunkTickets(services.plugin());
        active = false;
        services.setMine(new NoopMineApi());
    }

    @Override
    public void reload() {
        MineConfig old = config;
        config = MineConfig.fromRoot(services.plugin().getConfig());
        if (!active) {
            if (config.enabled() && !old.enabled()) Log.info("[광산] config 에서 켰습니다 — 다음 서버 시작 때 광산이 열립니다.");
            return;
        }
        if (!config.enabled()) Log.info("[광산] config 에서 껐습니다 — 다음 서버 시작 때 닫힙니다.");
        MineDef mine = services.content().mine();
        if (mine != null && !mine.isEmpty()) {
            veins.refillAll();
            loadLevels(mine);
            veins.reset(levels, config.regenPlayersCap());
            startBuild(null, null);
        }
    }

    private void loadLevels(MineDef mine) {
        levels.clear();
        interacts.clear();
        mineBlocks.clear();
        for (MineDef.Node n : mine.ores().values()) addMineBlock(n.block());
        for (MineDef.Node n : mine.gems().values()) addMineBlock(n.block());
        for (MineDef.Level def : mine.levels()) {
            String path = MineNames.blueprintPath(def.n());
            try (InputStream in = services.plugin().getResource(path)) {
                if (in == null) {
                    Log.warn("[광산] jar 에 " + path + " 이 없어 " + def.name() + " 을(를) 건너뜁니다.");
                    continue;
                }
                MineBlueprint bp = MineBlueprint.parse(new String(in.readAllBytes(), StandardCharsets.UTF_8));
                MineLevel l = new MineLevel(mine, def, bp);
                for (String p : l.problems) Log.warn("[광산] " + def.name() + ": " + p);
                levels.add(l);
                for (MineBlueprint.Marker m : bp.markers()) {
                    if (m.type().equals("lift")) {
                        // 승강기 = 자석석 + 위 쇠사슬 기둥 전부
                        for (int y = m.by(); y < m.by() + 12; y++) interacts.put(MineBlueprint.blockKey(m.bx(), y, m.bz()), MineNames.INTERACT_LIFT);
                    } else if (m.type().equals("office")) {
                        interacts.put(MineBlueprint.blockKey(m.bx(), m.by(), m.bz()), MineNames.INTERACT_OFFICE);
                    } else if (m.type().equals("sign") && !m.lines().isEmpty()) {
                        String all = String.join(" ", m.lines());
                        if (all.contains("관리소")) interacts.put(MineBlueprint.blockKey(m.bx(), m.by(), m.bz()), MineNames.INTERACT_OFFICE);
                        else if (all.contains("승강기")) interacts.put(MineBlueprint.blockKey(m.bx(), m.by(), m.bz()), MineNames.INTERACT_LIFT);
                    }
                }
            } catch (Exception e) {
                Log.warn("[광산] " + path + " 를 읽지 못했습니다: " + e.getMessage());
            }
        }
    }

    private void addMineBlock(String key) {
        Material m = key == null ? null : Material.matchMaterial(key);
        if (m != null) mineBlocks.add(m);
    }

    private World loadWorld(MineDef mine) {
        World w = Bukkit.getWorld(config.world());
        if (w == null) {
            try {
                w = new WorldCreator(config.world()).environment(World.Environment.NORMAL).generator(new MineGenerator(mine))
                        .generateStructures(false).createWorld();
            } catch (Throwable t) {
                Log.error("[광산] 월드 만들기 실패", t);
                return null;
            }
        }
        if (w == null) return null;
        kr.labyrinth.dungeon.LabyrinthWorld.applyRules(w);
        try {
            w.setGameRule(GameRules.PVP, false);
        } catch (Throwable ignored) {
            // PvpModule 이 1초마다 다시 끈다
        }
        MineDef.Level top = mine.level(1);
        if (top != null) w.setSpawnLocation(new Location(w, 0.5, top.floorY() + 1, 3.5));
        for (int cx = -2; cx <= 1; cx++) for (int cz = -2; cz <= 1; cz++) w.addPluginChunkTicket(cx, cz, services.plugin());
        w.setAutoSave(true);
        return w;
    }

    /** 층 짓기·맞추기 시작 (only = 그 층만 다시 짓기, null = 지문이 다른 층만). */
    void startBuild(Integer only, org.bukkit.command.CommandSender who) {
        if (builder.running()) {
            if (who != null) Text.error(who, "광산을 짓는 중입니다. 끝난 뒤 다시 해 주세요.");
            return;
        }
        Map<Integer, String> meta = MineBuilder.readMeta(world);
        Set<Integer> rebuild = new HashSet<>();
        for (MineLevel l : levels) {
            boolean same = l.hash.equals(meta.get(l.n));
            if (only != null ? only == l.n || only == 0 : !same) rebuild.add(l.n);
        }
        built.keySet().removeIf(rebuild::contains);
        if (!rebuild.isEmpty()) Log.info("[광산] 층 다시 짓기: " + rebuild + (meta.isEmpty() ? " (처음)" : ""));
        builder.start(new ArrayList<>(levels), rebuild, who, () -> {
            if (who != null) Text.send(who, "<#7fe07f>광산 준비 끝 <gray>(층 " + levels.size() + ")");
        });
    }

    void markBuilt(MineLevel l) { built.put(l.n, l.hash); }

    String builtHash(int n) { return built.get(n); }

    boolean ready(int n) {
        for (MineLevel l : levels) if (l.n == n) return l.hash.equals(built.get(n));
        return false;
    }

    private void safeVeinTick() {
        try {
            veins.tick();
        } catch (Throwable t) {
            Log.error("[광산] 광맥 갱신 오류", t);
        }
    }

    /** 0.5초마다 광산 사람: 게임 모드 규칙 · 성급함·전달체 효과 지움 · 떨어지면 승강장. */
    private void sweepPlayers() {
        World w = world;
        if (w == null) return;
        for (Player p : w.getPlayers()) {
            try {
                applyRules(p);
                double y = p.getLocation().getY();
                if (levelAt(p.getLocation()) == null && !lift.riding(p)) rescue(p, y);
            } catch (Throwable t) {
                Log.error("[광산] 사람 정리 오류", t);
            }
        }
    }

    private void rescue(Player p, double y) {
        MineLevel target = null;
        for (MineLevel l : levels) {
            if (l.boxBottom() > y && (target == null || l.boxBottom() < target.boxBottom())) target = l;
        }
        if (target == null && !levels.isEmpty()) target = levels.get(0);
        if (target == null) return;
        p.setFallDistance(0);
        kr.labyrinth.core.Teleports.to(p, target.landing(world));
        Text.send(p, "<gray>떨어져서 " + target.coloredName() + "<gray> 승강장으로 옮겼습니다.");
    }

    /** 30초마다: 광산 월드 몹 지움 · 사라진 보석 결정 다시 놓기. */
    private void sweepMobs() {
        World w = world;
        if (w == null) return;
        int removed = 0;
        for (Entity e : w.getEntities()) {
            if (e instanceof Mob) {
                e.remove();
                removed++;
            }
        }
        if (removed > 0) Log.info("[광산] 광산 월드 몹 " + removed + "마리를 지웠습니다.");
        veins.ensureDisplays();
    }

    /** 게임 모드 규칙 + 광산 안이면 HASTE·CONDUIT_POWER 지움 (캐는 시간 계약). */
    void applyRules(Player p) {
        boolean in = isMineWorld(p.getWorld());
        GameMode t = MineGameModeRule.target(p.getGameMode(), in);
        if (t != null) p.setGameMode(t);
        if (in) {
            if (p.hasPotionEffect(PotionEffectType.HASTE)) p.removePotionEffect(PotionEffectType.HASTE);
            if (p.hasPotionEffect(PotionEffectType.CONDUIT_POWER)) p.removePotionEffect(PotionEffectType.CONDUIT_POWER);
            if (config.noHunger() && p.getFoodLevel() < 20) p.setFoodLevel(20);
        }
    }

    void afterArrive(Player p) {
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (!p.isOnline()) return;
            applyRules(p);
            pickaxes.refresh(p);
        });
    }

    // ── 수확 안내 ───────────────────────────────────────────────────────

    void feedback(Player p, MineVeins.Harvest h) {
        switch (h.result()) {
            case OK -> {
                MineDef mine = mineDef();
                MineDef.Node node = h.vein().node();
                ItemDef def = services.content().item(h.item());
                String name = def != null ? def.name() : node.name();
                String c = node.color();
                StringBuilder sb = new StringBuilder("<" + c + ">+" + h.amount() + " " + Text.escape(name) + "</" + c + "> <gray>(가방 "
                        + h.bagCount() + ")</gray>");
                if (h.bonus() && !h.rich()) sb.append(" <gold>덤 +1</gold>");
                if (h.rich()) sb.append(" <gold>풍부한 광맥! ×").append(config.richMultiplier()).append("</gold>");
                if (h.gem() != null) {
                    MineDef.Node g = mine.gems().get(h.gem());
                    ItemDef gd = services.content().item(h.gem());
                    String gc = g == null ? "#ffffff" : g.color();
                    sb.append(" <").append(gc).append(">✦ ").append(Text.escape(gd != null ? gd.name() : g == null ? h.gem() : g.name()))
                            .append("!</").append(gc).append(">");
                }
                services.hud().actionBar(p, Text.mm(sb.toString()), 40);
                p.playSound(p.getLocation(), Sound.ENTITY_ITEM_PICKUP, 0.3f, 1.4f);
                if (h.gem() != null || h.rich()) p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.6f, 1.6f);
                if (config.fxPop()) pop(p, h);
            }
            case NO_PICKAXE, TOO_WEAK -> services.hud().actionBar(p, Text.mm("<red>"
                    + TierRule.message(h.result() == MineVeins.Result.TOO_WEAK ? TierRule.Verdict.TOO_WEAK : TierRule.Verdict.NO_PICKAXE)), 30);
            case BAG_FULL -> {
                services.hud().actionBar(p, Text.mm("<red>" + MineNames.BAG_FULL), 40);
                p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.5f, 0.7f);
            }
            case NO_ITEMS -> services.hud().actionBar(p, Text.mm("<red>광석 아이템이 아직 준비되지 않았습니다"), 40);
            default -> { }
        }
    }

    /** 광석 날아오기: 블록 앞에서 캔 사람 쪽으로 (그 사람에게만 보임, 8틱). */
    private void pop(Player p, MineVeins.Harvest h) {
        ItemStack icon = services.items().create(h.item(), 1);
        if (icon == null) return;
        Location from = MineVeins.face(h.vein());
        from.setWorld(world);
        try {
            ItemDisplay d = world.spawn(from, ItemDisplay.class, e -> {
                e.setItemStack(icon);
                e.setVisibleByDefault(false);
                e.setPersistent(false);
                e.setTeleportDuration(6);
                e.setTransformation(new org.bukkit.util.Transformation(new org.joml.Vector3f(), new org.joml.Quaternionf(),
                        new org.joml.Vector3f(0.4f, 0.4f, 0.4f), new org.joml.Quaternionf()));
                e.setBillboard(org.bukkit.entity.Display.Billboard.CENTER);
            });
            p.showEntity(services.plugin(), d);
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
                if (d.isValid() && p.isOnline() && p.getWorld().equals(d.getWorld())) d.teleport(p.getLocation().add(0, 1.0, 0));
            }, 2L);
            Bukkit.getScheduler().runTaskLater(services.plugin(), d::remove, 10L);
        } catch (Throwable t) {
            Log.warnOnce("mine-pop", "[광산] 광석 날아오기 연출 오류: " + t.getMessage());
        }
    }

    // ── 위치·이름 ───────────────────────────────────────────────────────

    /** 그 자리의 층 (광산 월드 밖이거나 층 상자 밖이면 null). */
    MineLevel levelAt(Location l) {
        if (l == null || !isMineWorld(l.getWorld())) return null;
        for (MineLevel lv : levels) if (lv.containsY(l.getY())) return lv;
        return null;
    }

    int minersAt(MineLevel l) {
        if (world == null) return 0;
        int n = 0;
        for (Player p : world.getPlayers()) {
            if ((p.getGameMode() == GameMode.ADVENTURE || p.getGameMode() == GameMode.SURVIVAL) && l.containsY(p.getLocation().getY())) n++;
        }
        return n;
    }

    String interactAt(Block b) {
        return interacts.get(MineBlueprint.blockKey(b.getX(), b.getY(), b.getZ()));
    }

    boolean isMineBlock(Material m) { return m != null && mineBlocks.contains(m); }

    /** 광산에서 "마을로": 구역 승강장 mine_exit → 마을 광장 → 주 월드 스폰. */
    Location exitLocation() {
        MineLinks.District d = MineLinks.district();
        if (MineLinks.usable(d)) return d.exit();
        try {
            var v = kr.labyrinth.village.VillageService.get();
            if (v != null && v.spawn() != null) return v.spawn();
        } catch (Throwable ignored) {
            // 마을 없음
        }
        return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0).getSpawnLocation();
    }

    // ── MineApi ─────────────────────────────────────────────────────────

    @Override
    public boolean enabled() { return active; }

    @Override
    public boolean isMineWorld(World w) {
        return w != null && w.getName().equals(config.world());
    }

    @Override
    public boolean safe() { return config.safe(); }

    @Override
    public void openLift(Player p) {
        if (p == null) return;
        if (!active) {
            Text.error(p, "광산이 아직 열리지 않았습니다.");
            return;
        }
        if (isMineWorld(p.getWorld()) || MineLinks.nearLift(p.getLocation(), 12)) {
            lift.open(p);
            return;
        }
        openMine(p);
    }

    @Override
    public void openMine(Player p) {
        if (p == null) return;
        if (!active) {
            Text.error(p, "광산이 아직 열리지 않았습니다.");
            return;
        }
        if (isMineWorld(p.getWorld())) {
            lift.open(p);
            return;
        }
        if (services.dungeon().isInLabyrinth(p) || services.dungeon().currentInstance(p).isPresent()) {
            Text.error(p, "미궁 안에서는 쓸 수 없습니다. 먼저 <white>/미궁 귀환</white>");
            return;
        }
        boolean villageTp = services.plugin().getConfig().getBoolean("village.teleport_command", true);
        MineLinks.District d = MineLinks.district();
        if (!config.teleportAllowed(villageTp) && !p.hasPermission(CommandService.PERM_ADMIN)) {
            Text.error(p, MineLinks.usable(d) ? "이 서버에서는 광산 텔레포트를 쓰지 않습니다. 광산 마을 승강장을 이용하세요."
                    : "이 서버에서는 광산 텔레포트를 쓰지 않습니다. (config mine.teleport_command)");
            return;
        }
        if (MineLinks.usable(d)) {
            if (MineLinks.nearLift(p.getLocation(), 12)) {
                lift.open(p);
                return;
            }
            p.setFallDistance(0);
            kr.labyrinth.core.Teleports.to(p, d.exit());
            p.playSound(d.exit(), Sound.ENTITY_ENDERMAN_TELEPORT, 0.6f, 1.2f);
            Text.send(p, "<#e8c58a>광산 승강장</#e8c58a><gray> 앞입니다. 승강기를 우클릭하면 광산으로 내려갑니다.");
            return;
        }
        if (!levels.isEmpty()) lift.ride(p, levels.get(0));
    }

    @Override
    public void openOffice(Player p) {
        if (p == null) return;
        if (!active) {
            Text.error(p, "광산이 아직 열리지 않았습니다.");
            return;
        }
        menus.office(p);
    }

    @Override
    public void openInfo(Player p) {
        if (p == null) return;
        if (!active) {
            Text.error(p, "광산이 아직 열리지 않았습니다.");
            return;
        }
        menus.info(p);
    }

    @Override
    public ItemStack applyPickaxe(ItemStack stack, ItemDef def) {
        try {
            return pickaxes.apply(stack, def);
        } catch (Throwable t) {
            Log.warnOnce("mine-apply-pickaxe", "[광산] 곡괭이 구성요소 오류: " + t);
            return stack;
        }
    }

    // ── 안쪽 접근 ───────────────────────────────────────────────────────

    Services services() { return services; }
    MineConfig config() { return config; }
    World world() { return world; }
    List<MineLevel> levels() { return levels; }
    MineVeins veins() { return veins; }
    MineLift lift() { return lift; }
    MinePickaxes pickaxes() { return pickaxes; }
    MineStats stats() { return stats; }
    MineBuilder builder() { return builder; }
    boolean active() { return active; }
    MineDef mineDef() { return services.content().mine(); }

    MineLevel level(int n) {
        for (MineLevel l : levels) if (l.n == n) return l;
        return null;
    }
}
