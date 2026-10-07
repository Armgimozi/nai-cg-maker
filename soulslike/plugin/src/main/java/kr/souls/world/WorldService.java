package kr.souls.world;

import io.papermc.paper.event.player.AsyncPlayerSpawnLocationEvent;
import kr.souls.Config;
import kr.souls.Keys;
import kr.souls.Lang;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameMode;
import org.bukkit.GameRule;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.WorldBorder;
import org.bukkit.WorldCreator;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.persistence.PersistentDataType;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Level;

/**
 * 세계 둘 (8.1): 로비(world, 플레이어 저장 파일이 있는 빈 세계)와 게임 세계(souls_world, 공허 + 지역 바이옴).
 * 게임 규칙(12.7)과 난이도 normal 을 켤 때 맞추고, 짓는 동안은 접속을 막고 서버가 멈추지 않게 한다 (8.10).
 * 처음 들어오는 플레이어는 로비를 거치지 않고 곧바로 souls_world 의 시험 방에 선다 (AsyncPlayerSpawnLocationEvent).
 */
public final class WorldService implements Listener {
    private final Souls plugin;
    private volatile boolean building;
    /** 시험 방 첫 자리. 비동기 접속 이벤트가 읽으므로 volatile */
    private volatile Location roomSpawn;
    private String lastBuild = "아직 짓지 않음";
    /** 이번 켜기에서 souls_world 를 처음 만들었다 (level.dat 이 없었다) */
    private boolean freshWorld;

    public WorldService(Souls plugin) {
        this.plugin = plugin;
    }

    private Config cfg() {
        return plugin.cfg();
    }

    public World lobby() {
        return Bukkit.getWorlds().get(0);
    }

    /** 게임 세계 (없으면 null). 잡아 두지 않고 매번 이름으로 찾는다. */
    public World world() {
        return Bukkit.getWorld(cfg().world.name());
    }

    public boolean isGameWorld(World w) {
        return w != null && w.getName().equals(cfg().world.name());
    }

    /** 우리가 다루는 세계 (로비 또는 게임 세계). */
    public boolean ours(World w) {
        return w != null && (w.equals(lobby()) || isGameWorld(w));
    }

    public boolean building() {
        return building;
    }

    public String lastBuild() {
        return lastBuild;
    }

    public Location roomSpawn() {
        Location l = roomSpawn;
        return l == null ? lobby().getSpawnLocation() : l.clone();
    }

    public int[] roomCenter() {
        Config.WorldCfg c = cfg().world;
        return new int[]{c.roomX(), c.roomY(), c.roomZ()};
    }

    // ------------------------------------------------------------------ 켜기

    /** 켤 때 부른다. 세계를 열고, 규칙과 난이도를 맞추고, 시험 방이 옛 판이면 다시 짓는다. */
    public void start() {
        Config.WorldCfg c = cfg().world;
        building = true;
        World w = ensureWorld();
        if (w == null) {
            building = false;
            plugin.getLogger().severe("게임 세계(" + c.name() + ")를 만들지 못했습니다. 로비에서만 돕니다.");
            return;
        }
        roomSpawn = TestRoom.spawn(w, c.roomX(), c.roomY(), c.roomZ());
        // 플러그인이 새로 만든 세계는 easy 로 생긴다. 처음 한 번은 조용히 맞춘다 (그 뒤에 어긋나면 checkDifficulty 가 크게 알린다)
        if (freshWorld && w.getDifficulty() != Difficulty.NORMAL) {
            plugin.getLogger().info(w.getName() + " 을 새로 만들어 난이도를 " + w.getDifficulty() + " 에서 normal 로 맞췄습니다.");
            w.setDifficulty(Difficulty.NORMAL);
        }
        for (World x : List.of(lobby(), w)) {
            applyRules(x);
            checkDifficulty(x);
        }
        w.setSpawnLocation(roomSpawn);
        w.setTime(c.time());
        w.setStorm(false);
        w.setThundering(false);
        w.setClearWeatherDuration(Integer.MAX_VALUE / 2);
        WorldBorder border = w.getWorldBorder();
        border.setCenter(c.borderX(), c.borderZ());
        border.setSize(c.borderSize());
        checkBiomeLayout(w);
        // 난이도는 바뀔 때 알려 주는 이벤트가 없어서 가끔 맞춘다 (/difficulty 를 누가 쳐도 normal 로 돌아온다)
        Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            checkDifficulty(lobby());
            World g = world();
            if (g != null) checkDifficulty(g);
        }, 200, 200);
        Integer built = w.getPersistentDataContainer().get(Keys.ROOM, PersistentDataType.INTEGER);
        if (built != null && built >= TestRoom.VERSION) {
            building = false;
            lastBuild = "시험 방 판 " + built + " (이미 지음)";
            plugin.getLogger().info("시험 방은 이미 지었습니다 (판 " + built + "). 짓지 않습니다.");
            return;
        }
        // 첫 틱에 짓는다. 그동안 접속을 막고 (아무도 없어도) 서버가 멈추지 않게 한다
        Bukkit.getServer().allowPausing(plugin, false);
        Bukkit.getScheduler().runTask(plugin, () -> buildRoom(Bukkit.getConsoleSender()));
    }

    private World ensureWorld() {
        Config.WorldCfg c = cfg().world;
        World w = world();
        if (w != null) return w;
        int[] rc = {c.roomX(), c.roomY(), c.roomZ()};
        freshWorld = !new File(Bukkit.getWorldContainer(), c.name() + File.separator + "level.dat").exists();
        try {
            SoulsGenerator gen = new SoulsGenerator(plugin.getLogger(), () -> TestRoom.spawn(null, rc[0], rc[1], rc[2]));
            // keepSpawnLoaded 는 제거 예정이라 쓰지 않는다 (1.21.11 에는 스폰 청크가 없다)
            w = WorldCreator.name(c.name()).environment(World.Environment.NORMAL).generator(gen)
                    .generateStructures(false).seed(c.seed()).createWorld();
        } catch (RuntimeException ex) {
            plugin.getLogger().log(Level.SEVERE, "게임 세계를 만들다 오류가 났습니다", ex);
            return null;
        }
        if (w != null && !w.getPersistentDataContainer().has(Keys.BIOMES, PersistentDataType.INTEGER)) {
            w.getPersistentDataContainer().set(Keys.BIOMES, PersistentDataType.INTEGER, SoulsGenerator.BIOME_LAYOUT);
        }
        return w;
    }

    /** 바이옴 경계 판이 다르면 이미 만든 청크와 새 청크의 바이옴이 어긋난다. 고치지 않고 크게 알린다. */
    private void checkBiomeLayout(World w) {
        if (!(w.getGenerator() instanceof SoulsGenerator)) {
            plugin.getLogger().warning(w.getName() + " 에 이 플러그인의 생성기가 붙어 있지 않습니다. /reload 를 했다면 서버를 다시 켜 주세요.");
        }
        Integer v = w.getPersistentDataContainer().get(Keys.BIOMES, PersistentDataType.INTEGER);
        if (v != null && v != SoulsGenerator.BIOME_LAYOUT) {
            plugin.getLogger().severe("=================================================================");
            plugin.getLogger().severe(w.getName() + " 의 바이옴 경계 판(" + v + ")이 플러그인의 판(" + SoulsGenerator.BIOME_LAYOUT + ")과 다릅니다.");
            plugin.getLogger().severe("이미 만든 청크의 바이옴은 바뀌지 않습니다. 서버를 끄고 " + w.getName() + " 폴더를 지운 뒤 다시 켜세요.");
            plugin.getLogger().severe("=================================================================");
        }
    }

    // ------------------------------------------------------------------ 규칙

    /** 12.7 의 게임 규칙. GameRules 의 snake_case 상수만 쓴다 (옛 camelCase 문자열은 예외를 던진다). */
    public static List<RuleValue<?>> rules() {
        List<RuleValue<?>> r = new ArrayList<>();
        r.add(new RuleValue<>(GameRules.KEEP_INVENTORY, true));
        r.add(new RuleValue<>(GameRules.IMMEDIATE_RESPAWN, false));
        r.add(new RuleValue<>(GameRules.NATURAL_HEALTH_REGENERATION, false));
        r.add(new RuleValue<>(GameRules.SPAWN_MOBS, false));
        r.add(new RuleValue<>(GameRules.SPAWN_MONSTERS, false));
        r.add(new RuleValue<>(GameRules.SPAWN_PATROLS, false));
        r.add(new RuleValue<>(GameRules.SPAWN_PHANTOMS, false));
        r.add(new RuleValue<>(GameRules.SPAWN_WANDERING_TRADERS, false));
        r.add(new RuleValue<>(GameRules.SPAWN_WARDENS, false));
        r.add(new RuleValue<>(GameRules.RAIDS, false));
        r.add(new RuleValue<>(GameRules.MOB_GRIEFING, false));
        r.add(new RuleValue<>(GameRules.SHOW_ADVANCEMENT_MESSAGES, false));
        // 사망 화면 밑 문구를 비우는 deathScreenMessageOverride 는 이 규칙이 켜져 있어야 듣는다 (채팅 알림은 DeathFlow 가 막는다)
        r.add(new RuleValue<>(GameRules.SHOW_DEATH_MESSAGES, true));
        r.add(new RuleValue<>(GameRules.ADVANCE_TIME, false));
        r.add(new RuleValue<>(GameRules.ADVANCE_WEATHER, false));
        r.add(new RuleValue<>(GameRules.FIRE_SPREAD_RADIUS_AROUND_PLAYER, 0));
        r.add(new RuleValue<>(GameRules.RANDOM_TICK_SPEED, 0));
        r.add(new RuleValue<>(GameRules.PVP, false));
        r.add(new RuleValue<>(GameRules.MOB_DROPS, false));
        r.add(new RuleValue<>(GameRules.BLOCK_DROPS, false));
        r.add(new RuleValue<>(GameRules.TNT_EXPLODES, false));
        r.add(new RuleValue<>(GameRules.SPREAD_VINES, false));
        r.add(new RuleValue<>(GameRules.RESPAWN_RADIUS, 0));
        // 위치 표시 막대가 경험치 막대(=스태미나)를 가린다
        r.add(new RuleValue<>(GameRules.LOCATOR_BAR, false));
        r.add(new RuleValue<>(GameRules.ALLOW_ENTERING_NETHER_USING_PORTALS, false));
        r.add(new RuleValue<>(GameRules.FALL_DAMAGE, true));
        r.add(new RuleValue<>(GameRules.ENTITY_DROPS, false));
        r.add(new RuleValue<>(GameRules.PROJECTILES_CAN_BREAK_BLOCKS, false));
        r.add(new RuleValue<>(GameRules.SPAWNER_BLOCKS_WORK, false));
        r.add(new RuleValue<>(GameRules.UNIVERSAL_ANGER, false));
        return r;
    }

    public record RuleValue<T>(GameRule<T> rule, T value) {
        boolean apply(World w) {
            T cur = w.getGameRuleValue(rule);
            if (value.equals(cur)) return false;
            w.setGameRule(rule, value);
            return true;
        }

        public boolean matches(World w) {
            return value.equals(w.getGameRuleValue(rule));
        }
    }

    private void applyRules(World w) {
        int changed = 0;
        for (RuleValue<?> rv : rules()) {
            try {
                if (rv.apply(w)) changed++;
            } catch (RuntimeException ex) {
                plugin.getLogger().warning(w.getName() + " 게임 규칙 " + rv.rule().getKey() + " 를 맞추지 못했습니다: " + ex.getMessage());
            }
        }
        if (changed > 0) plugin.getLogger().info(w.getName() + " 게임 규칙 " + changed + "개를 맞췄습니다.");
    }

    /** 바뀐 규칙 목록 (/souls check). */
    public List<String> ruleMismatches(World w) {
        List<String> out = new ArrayList<>();
        for (RuleValue<?> rv : rules()) {
            if (!rv.matches(w)) out.add(rv.rule().getKey().getKey() + "=" + w.getGameRuleValue(rv.rule()) + " (" + rv.value() + " 이어야 함)");
        }
        return out;
    }

    /**
     * 난이도는 normal 이어야 한다 (3.9). 바닐라 피해 종류는 "살아 있는 비플레이어가 일으키면 난이도로 배율" 규칙이 있어
     * hard 면 모든 적 피해가 1.5배가 된다.
     */
    private void checkDifficulty(World w) {
        if (w.getDifficulty() == Difficulty.NORMAL) return;
        plugin.getLogger().severe("=================================================================");
        plugin.getLogger().severe(w.getName() + " 의 난이도가 " + w.getDifficulty() + " 입니다. normal 로 바꿉니다."
                + " (hard 면 적 피해가 1.5배, easy 면 줄어든다. server.properties 의 difficulty=normal 을 확인하세요)");
        plugin.getLogger().severe("=================================================================");
        w.setDifficulty(Difficulty.NORMAL);
    }

    // ------------------------------------------------------------------ 짓기

    /** 시험 방을 지운 뒤 짓는다 (/souls build room 도 이것을 부른다). */
    public void buildRoom(CommandSender to) {
        World w = world();
        if (w == null) {
            to.sendMessage("게임 세계가 없다.");
            return;
        }
        building = true;
        Bukkit.getServer().allowPausing(plugin, false);
        try {
            int[] c = roomCenter();
            long t0 = System.nanoTime();
            int n = TestRoom.build(w, c[0], c[1], c[2]);
            double ms = (System.nanoTime() - t0) / 1e6;
            w.getPersistentDataContainer().set(Keys.ROOM, PersistentDataType.INTEGER, TestRoom.VERSION);
            roomSpawn = TestRoom.spawn(w, c[0], c[1], c[2]);
            w.setSpawnLocation(roomSpawn);
            // 표시를 남기기 전에 청크를 디스크에 쓴다. 표시만 남은 채 서버가 죽으면 다음에 빈 방을 지은 것으로 여긴다
            w.save(true);
            lastBuild = String.format("시험 방 판 %d, 블록 %d개, %.0f ms", TestRoom.VERSION, n, ms);
            plugin.getLogger().info("시험 방을 지었습니다: " + lastBuild);
            if (to instanceof Player) to.sendMessage("시험 방을 지었다: " + lastBuild);
        } catch (RuntimeException ex) {
            plugin.getLogger().log(Level.SEVERE, "시험 방을 짓다가 오류가 났습니다", ex);
            to.sendMessage("시험 방을 짓지 못했다: " + ex.getMessage());
        } finally {
            building = false;
            Bukkit.getServer().allowPausing(plugin, true);
        }
    }

    // ------------------------------------------------------------------ 접속

    @EventHandler(priority = EventPriority.HIGH)
    public void onPreLogin(AsyncPlayerPreLoginEvent e) {
        if (building) e.disallow(AsyncPlayerPreLoginEvent.Result.KICK_OTHER, Lang.c("build.refuse"));
    }

    /** 처음 들어오면 곧바로 시험 방 (로비에 먼저 떨어지지 않는다). 그 뒤로는 저장된 자리에서 들어오되, 로비에 있었다면 옮긴다. */
    @EventHandler
    public void onSpawnLocation(AsyncPlayerSpawnLocationEvent e) {
        Location spawn = roomSpawn;
        if (spawn == null) return;
        Location cur = e.getSpawnLocation();
        World at = cur.getWorld();
        if (e.isNewPlayer() || at == null || !at.getName().equals(cfg().world.name())) e.setSpawnLocation(spawn);
    }

    @EventHandler(priority = EventPriority.LOW)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (cfg().world.forceAdventure() && p.getGameMode() == GameMode.SURVIVAL) p.setGameMode(GameMode.ADVENTURE);
    }
}
