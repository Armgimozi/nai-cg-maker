package kr.augsky.nether;

import io.papermc.paper.event.entity.EntityKnockbackEvent;
import io.papermc.paper.event.entity.EntityPortalReadyEvent;
import io.papermc.paper.event.world.WorldGameRuleChangeEvent;
import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.map.NetherMap;
import kr.augsky.mob.MobManager;
import kr.augsky.skill.Targets;
import kr.augsky.util.Text;
import net.kyori.adventure.util.TriState;
import org.bukkit.Axis;
import org.bukkit.Bukkit;
import org.bukkit.GameRule;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.PortalType;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.Orientable;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.AbstractSkeleton;
import org.bukkit.entity.Enderman;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.ExperienceOrb;
import org.bukkit.entity.Ghast;
import org.bukkit.entity.LargeFireball;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Wither;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.world.PortalCreateEvent;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataContainer;

import java.io.File;
import java.io.IOException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import java.util.logging.Level;

/**
 * 하늘 네더: 플러그인이 만든 공허 네더 월드(world_augsky_nether)와 그리로 가는 네더 문.
 * 바닐라 네더(allow-nether)는 쓰지 않는다. 네더 문을 타면 EntityPortalReadyEvent 에서 대상을 이 월드로 바꿀 뿐,
 * 배율(1/8)과 문 찾기·만들기 반경은 Paper 에 맡긴다. 처음 켤 때 섬을 한 번 짓고 월드 폴더에 표시 파일을 남긴다.
 */
public final class NetherService implements Listener {
    public static final NamespacedKey KEY = new NamespacedKey(Keys.NS, "sky_nether");
    private static final String MARKER = "augsky-nether.yml";
    private static final String CLOSED = "<gray>이 하늘에서는 네더 문이 열리지 않습니다";
    // 스폰 조정 값 (몇 번 놀아 보고 고친다)
    /** 쉼터 둘레 이 거리 안에는 몬스터가 생기지 않는다 (문으로 처음 나오는 곳) */
    private static final double HUB_CALM = 16;
    /** 64칸 안 가스트 수. 불덩이가 다리 위 사람을 민다 */
    private static final int GHASTS_NEAR = 2;
    /** 둘레 16칸(위아래 8칸) 안 몬스터 수. 작은 섬이 몬스터로 가득 차지 않게 */
    private static final int ENEMIES_NEAR = 5;
    /** 24칸 안 해골 수 (밀어내는 화살을 쏘는 몹이 다리 끝에 몰리지 않게) */
    private static final int ARCHERS_NEAR = 3;
    /** 가스트 불덩이에 밀리는 힘의 배율 (피해와 불은 그대로) */
    private static final double GHAST_PUSH = 0.3;
    /** 하늘에 새 짝 문이 생길 수 있는 곳: 하늘 스폰 둘레. 쉼터 문이 하늘로 이어지는 범위(탐색 128)와 같다 */
    private static final double PAIR_RADIUS = 128;

    private final AugSky plugin;
    private final NetherMap map;
    private boolean ready, building;
    /** 마지막으로 지을 때 실패한 섬 수 (-1: 아직 모름) */
    private int failed = -1;
    private String builtAt;
    private final Map<UUID, Integer> ghastHit = new HashMap<>();
    private boolean timer;

    public NetherService(AugSky plugin) {
        this.plugin = plugin;
        this.map = new NetherMap(plugin);
    }

    // ------------------------------------------------------------------ 월드

    /** 하늘 네더 월드 폴더 이름. '<level-name>_nether' 가 아니어야 한다 (아래 ensureWorld). */
    public static String name() {
        return Bukkit.getWorlds().get(0).getName() + "_augsky_nether";
    }

    public boolean enabled() {
        return plugin.getConfig().getBoolean("nether.enabled", true);
    }

    /** 지금 불려 있는 하늘 네더 (없으면 null). 월드를 잡아 두지 않고 매번 이름으로 찾는다. */
    public World world() {
        return Bukkit.getWorld(name());
    }

    public boolean isSky(World w) {
        return w != null && w.getName().equals(name());
    }

    public boolean ready() {
        return ready;
    }

    /** 쉼터에 처음 서는 자리. 하늘 네더가 없으면 null. */
    public Location hubSpawn() {
        World w = world();
        return w == null ? null : NetherMap.hubSpawn(w);
    }

    /**
     * 켤 때와 /증강관리 리로드 때 부른다 (여러 번 불러도 된다). 월드를 열고, 처음이면 섬을 짓는다.
     * 여기서 무엇이 실패해도 플러그인의 나머지는 그대로 돌고 네더 문만 닫힌다.
     */
    public void start() {
        try {
            if (!enabled()) return;
            World w = ensureWorld();
            if (w == null) {
                plugin.getLogger().severe("하늘 네더 월드(" + name() + ")를 만들지 못했습니다. 네더 문은 닫힌 채로 둡니다.");
                return;
            }
            if (!(w.getGenerator() instanceof VoidNether)) {
                plugin.getLogger().warning("하늘 네더(" + name() + ")에 이 플러그인의 생성기가 붙어 있지 않습니다. /reload 를 했다면 서버를 다시 켜 주세요.");
            }
            syncRules(w);
            if (!timer) {
                timer = true;
                // 난이도는 바뀔 때 알려 주는 이벤트가 없어서 가끔 맞춘다
                Bukkit.getScheduler().runTaskTimer(plugin, this::syncDifficulty, 200, 200);
            }
            YamlConfiguration mk = marker(w);
            if (mk != null) {
                ready = true;
                failed = mk.getInt("failed", 0);
                builtAt = mk.getString("built", "?");
                if (mk.getInt("layout", 0) < NetherMap.LAYOUT) {
                    plugin.getLogger().info("하늘 네더 섬 배치가 새 판(" + NetherMap.LAYOUT + ")으로 바뀌었습니다. 지은 섬은 그대로 둡니다"
                            + " (새 배치로 다시 지으려면 모두 하늘로 돌아온 뒤 /증강관리 네더 짓기 강제).");
                }
                return;
            }
            if (!building) Bukkit.getScheduler().runTask(plugin, () -> build(Bukkit.getConsoleSender(), false));
        } catch (RuntimeException ex) {
            ready = false;
            plugin.getLogger().log(Level.SEVERE, "하늘 네더를 열지 못했습니다. 네더 문은 닫힌 채로 둡니다", ex);
        }
    }

    private World ensureWorld() {
        World w = world();
        if (w != null) return w;
        // '<level-name>_nether' 로 만들면 CraftBukkit 이 바닐라 네더로 여겨 allow-nether=false 에 막힌다. 그래서 이름과 키를 따로 쓴다
        return WorldCreator.ofNameAndKey(name(), KEY).environment(World.Environment.NETHER).generator(new VoidNether())
                .generateStructures(false).keepSpawnLoaded(TriState.FALSE).seed(NetherMap.SEED).createWorld();
    }

    /** 게임 규칙은 월드마다 따로라서 하늘의 것을 옮긴다 (공허 위에서만 keepInventory 가 다르면 큰일). */
    private void syncRules(World w) {
        World home = Bukkit.getWorlds().get(0);
        for (GameRule<?> rule : GameRule.values()) copy(home, w, rule);
        w.setGameRule(GameRule.SPAWN_CHUNK_RADIUS, 0);
        w.setGameRule(GameRule.SPAWN_RADIUS, 0);
        w.setDifficulty(home.getDifficulty());
    }

    /** 규칙 하나를 옮긴다. 실험 기능 규칙(minecartMaxSpeed 등)은 그 기능이 켜진 월드에만 있으므로 양쪽에 다 있을 때만. */
    private static <T> void copy(World from, World to, GameRule<T> rule) {
        if (rule == GameRule.SPAWN_CHUNK_RADIUS || rule == GameRule.SPAWN_RADIUS) return;
        if (!from.isGameRule(rule.getName()) || !to.isGameRule(rule.getName())) return;
        T v = from.getGameRuleValue(rule);
        if (v != null && !v.equals(to.getGameRuleValue(rule))) to.setGameRule(rule, v);
    }

    private void syncDifficulty() {
        World w = world(), home = Bukkit.getWorlds().get(0);
        if (w != null && w.getDifficulty() != home.getDifficulty()) w.setDifficulty(home.getDifficulty());
    }

    /** /gamerule 은 명령을 친 사람의 월드에만 적용되므로, 하늘에서 바꾼 규칙을 하늘 네더에도 옮긴다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onGameRule(WorldGameRuleChangeEvent e) {
        World home = Bukkit.getWorlds().get(0);
        if (!e.getWorld().equals(home) || world() == null) return;
        GameRule<?> rule = e.getGameRule();
        // 값은 이벤트가 끝난 뒤에 바뀐다
        Bukkit.getScheduler().runTask(plugin, () -> {
            World w = world();
            if (w != null) copy(home, w, rule);
        });
    }

    private static YamlConfiguration marker(World w) {
        File f = new File(w.getWorldFolder(), MARKER);
        return f.exists() ? YamlConfiguration.loadConfiguration(f) : null;
    }

    /**
     * 섬을 짓는다. force 가 아니면 아직 안 지었을 때만. 짓는 동안은 네더 문이 열리지 않는다.
     * force 면 섬 자리를 비우고 처음 모습으로 다시 짓는다 (섬 위에 지은 것과 고친 곳은 사라지고 상자도 다시 채운다).
     */
    public void build(CommandSender to, boolean force) {
        World w = world();
        if (w == null) {
            to.sendMessage(Text.mm("<#ff7070>하늘 네더가 열려 있지 않습니다 (config.yml 의 nether.enabled 를 확인하세요)."));
            return;
        }
        if (building) {
            to.sendMessage(Text.mm("<gray>이미 짓는 중입니다."));
            return;
        }
        if (!force && marker(w) != null) {
            to.sendMessage(Text.mm("<gray>하늘 네더는 이미 지었습니다. 다시 지으려면 /증강관리 네더 짓기 강제"));
            return;
        }
        building = true;
        ready = false;
        plugin.getLogger().info("하늘 네더(" + w.getName() + ")에 섬을 짓습니다...");
        if (to instanceof Player) to.sendMessage(Text.mm("<gray>하늘 네더에 섬을 짓는 중... (몇 초 걸립니다)"));
        boolean player = to instanceof Player;
        map.buildAll(w, force, player ? m -> to.sendMessage(Text.mm("<gray>" + m)) : null, f -> {
            failed = f;
            builtAt = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
            w.setSpawnLocation(0, NetherMap.HUB_Y + 1, 3);
            // 표시 파일보다 섬 청크를 먼저 디스크에 다 쓴다. 표시만 남은 채 서버가 죽으면 다음에 켤 때 빈 네더를 지은 것으로 여긴다
            w.save(true);
            YamlConfiguration y = new YamlConfiguration();
            y.set("layout", NetherMap.LAYOUT);
            y.set("built", builtAt);
            y.set("failed", f);
            try {
                y.save(new File(w.getWorldFolder(), MARKER));
            } catch (IOException ex) {
                plugin.getLogger().warning("하늘 네더 표시 파일을 쓰지 못했습니다 (다음에 켤 때 다시 짓습니다): " + ex.getMessage());
            }
            building = false;
            // 섬 몇 곳이 실패해도 문은 연다 (실패는 기록에 남고 /증강관리 네더 에 보인다)
            ready = true;
            if (player) to.sendMessage(Text.mm((f == 0 ? "<#7cff8c>" : "<#ff7070>") + "하늘 네더 완성 (실패 " + f + ")"));
        });
    }

    // ------------------------------------------------------------------ 네더 문

    /** 네더 문: 하늘 ↔ 하늘 네더. 바닐라 네더가 꺼져 있어도(대상 null) 대상을 바꿔 보낸다. 배율(1/8)·탐색 반경은 Paper 가 정한다. */
    @EventHandler(ignoreCancelled = true)
    public void onPortalReady(EntityPortalReadyEvent e) {
        if (e.getPortalType() != PortalType.NETHER) return;
        Entity en = e.getEntity();
        boolean up = en.getWorld().getEnvironment() == World.Environment.NORMAL;
        if (!up && !isSky(en.getWorld())) return;   // 바닐라 네더 등은 손대지 않는다
        if (up && !enabled()) {
            e.setCancelled(true);
            bar(en, CLOSED);
            return;
        }
        if (stays(en, up)) {
            e.setCancelled(true);
            return;
        }
        World to = up ? world() : Bukkit.getWorlds().get(0);
        if (to == null) {
            e.setCancelled(true);
            bar(en, "<gray>네더 하늘이 닫혀 있습니다");
            return;
        }
        if (up && !ready) {
            e.setCancelled(true);
            // 취소하면 문 안에 서 있는 동안은 다시 시도하지 않는다 (바닐라 문 대기 시간)
            bar(en, "<gray>네더 하늘을 짓는 중입니다. 잠시 뒤 문에 다시 들어오세요");
            return;
        }
        e.setTargetWorld(to);
    }

    /**
     * 문을 지나지 않는 것: 보스·커스텀 몬스터·소환수·보스 모델 조각(둥지와 능력이 월드를 넘나들면 깨진다),
     * 그리고 하늘 네더에서 하늘로 가는 몬스터 (위더 해골, 블레이즈 같은 것이 시작 섬 문으로 따라 나오지 않게).
     */
    private boolean stays(Entity en, boolean up) {
        if (plugin.mobs().idOf(en) != null || Targets.isAlly(en)) return true;
        PersistentDataContainer pdc = en.getPersistentDataContainer();
        if (pdc.has(Keys.MAP_PART) || pdc.has(Keys.RIG)) return true;
        return !up && en instanceof Enemy;
    }

    /** 액션 바: 플레이어, 또는 탈것에 탄 플레이어. */
    private static void bar(Entity en, String mm) {
        if (en instanceof Player p) p.sendActionBar(Text.mm(mm));
        for (Entity pass : en.getPassengers()) if (pass instanceof Player p) p.sendActionBar(Text.mm(mm));
    }

    /**
     * 하늘 쪽 문 만들기. 꺼져 있으면 예전처럼 불을 붙여도 문이 열리지 않는다.
     * 하늘 네더에서 돌아올 때 새로 생기는 짝 문(NETHER_PAIR)은 하늘 스폰 둘레에만 생긴다:
     * 네더를 지름길 삼아 다리를 놓지 않은 먼 곳(맵 밖, 보스 둥지 안 등)을 찾아가지 못하게.
     * 플레이어가 하늘에 직접 세운 문으로는 그대로 이어진다 (Paper 가 128칸 안의 문을 먼저 찾는다).
     */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPortalCreate(PortalCreateEvent e) {
        if (e.getWorld().getEnvironment() != World.Environment.NORMAL) return;
        if (e.getReason() == PortalCreateEvent.CreateReason.FIRE) {
            if (enabled()) return;
            e.setCancelled(true);
            if (e.getEntity() != null) bar(e.getEntity(), CLOSED);
            return;
        }
        if (e.getReason() != PortalCreateEvent.CreateReason.NETHER_PAIR) return;
        Location spawn = e.getWorld().getSpawnLocation();
        for (BlockState s : e.getBlocks()) {
            boolean far = Math.hypot(s.getX() + 0.5 - spawn.getX(), s.getZ() + 0.5 - spawn.getZ()) > PAIR_RADIUS;
            if (far || plugin.altars().isGuarded(s.getLocation())) {
                e.setCancelled(true);
                if (e.getEntity() != null) bar(e.getEntity(), "<gray>문 건너편이 닫혀 있습니다");
                return;
            }
        }
    }

    /** 공허에 생긴 짝 문은 흑요석 발판이 좁아서 넓혀 준다 (섬 위에 생긴 문은 그대로). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPairPortal(PortalCreateEvent e) {
        if (e.getReason() != PortalCreateEvent.CreateReason.NETHER_PAIR) return;
        World w = e.getWorld();
        List<BlockState> blocks = new ArrayList<>(e.getBlocks());
        // 블록은 이벤트가 끝난 뒤에 놓인다
        Bukkit.getScheduler().runTask(plugin, () -> pad(w, blocks));
    }

    private static void pad(World w, List<BlockState> blocks) {
        int minY = Integer.MAX_VALUE, a0 = Integer.MAX_VALUE, a1 = Integer.MIN_VALUE, c = 0;
        Axis axis = null;
        for (BlockState s : blocks) {
            if (s.getType() != Material.NETHER_PORTAL || !(s.getBlockData() instanceof Orientable o)) continue;
            axis = o.getAxis();
            int along = axis == Axis.X ? s.getX() : s.getZ();
            c = axis == Axis.X ? s.getZ() : s.getX();
            minY = Math.min(minY, s.getY());
            a0 = Math.min(a0, along);
            a1 = Math.max(a1, along);
        }
        if (axis == null) return;
        int fy = minY - 1, mid = (a0 + a1) / 2;
        Block under = axis == Axis.X ? w.getBlockAt(mid, fy - 1, c) : w.getBlockAt(c, fy - 1, mid);
        if (!under.getType().isAir()) return;
        // 흑요석이 아니라 흑암 (발판을 캐서 흑요석을 모을 수 없게)
        for (int a = a0 - 2; a <= a1 + 2; a++)
            for (int p = -2; p <= 2; p++) {
                Block b = axis == Axis.X ? w.getBlockAt(a, fy, c + p) : w.getBlockAt(c + p, fy, a);
                if (b.getType().isAir()) b.setType(Material.BLACKSTONE, false);
            }
    }

    // ------------------------------------------------------------------ 몹과 블록

    /** 하늘 네더의 자연 스폰 (MobManager 가 부른다). 바닐라 네더 몹은 그대로 나오되 다리·쉼터·작은 섬이 몹으로 막히지 않게. */
    public boolean allowNatural(LivingEntity le) {
        EntityType t = le.getType();
        // 호글린은 사람을 위로 쳐올려 공허로 떨어뜨린다 (하늘과 같은 이유)
        if (t == EntityType.HOGLIN || t == EntityType.ZOGLIN) return false;
        if (!(le instanceof Enemy)) return true;                 // 스트라이더 등
        Location l = le.getLocation();
        if (Math.hypot(l.getX(), l.getZ()) < HUB_CALM) return false;
        if (MobManager.onBridge(l)) return false;
        World w = l.getWorld();
        if (t == EntityType.GHAST && w.getNearbyEntitiesByType(Ghast.class, l, 64).size() >= GHASTS_NEAR) return false;
        if (le instanceof AbstractSkeleton && w.getNearbyEntitiesByType(AbstractSkeleton.class, l, 24).size() >= ARCHERS_NEAR) return false;
        return w.getNearbyEntities(l, 16, 8, 16, en -> en instanceof Enemy && en != le).size() < ENEMIES_NEAR;
    }

    /** 섬은 다시 자라지 않는다: 위더(소환 폭발, 해골 탄)는 어느 월드에서든, 하늘 네더의 큰 불덩이(가스트, 되받아친 것)는 블록을 부수지 않는다. */
    @EventHandler(ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent e) {
        EntityType t = e.getEntityType();
        if (t == EntityType.WITHER || t == EntityType.WITHER_SKULL || e.getEntity() instanceof LargeFireball && isSky(e.getEntity().getWorld())) {
            e.blockList().clear();
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {
        if (e.getIgnitingEntity() instanceof LargeFireball && isSky(e.getBlock().getWorld())) e.setCancelled(true);
    }

    /** 위더는 몸으로 블록을 부수지 못하고(제단 기둥, 둥지), 하늘 네더의 엔더맨은 섬 블록을 들고 가지 못한다. */
    @EventHandler(ignoreCancelled = true)
    public void onChangeBlock(EntityChangeBlockEvent e) {
        if (e.getEntity() instanceof Wither || e.getEntity() instanceof Enderman && isSky(e.getBlock().getWorld())) e.setCancelled(true);
    }

    /**
     * 공허 위에서 잡은 몹의 전리품(가스트 눈물, 네더의 별 …)과 경험치를 잡은 사람 발밑으로 옮긴다. 모든 월드.
     * 다른 처리(커스텀 몹 드롭, 증강 파편)가 드롭을 다 더한 뒤에 옮기도록 맨 나중(HIGHEST)에.
     */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDeath(EntityDeathEvent e) {
        if (e instanceof PlayerDeathEvent || e.getEntity() instanceof Player) return;
        LivingEntity dead = e.getEntity();
        Player killer = dead.getKiller();
        if (killer == null || !killer.getWorld().equals(dead.getWorld()) || !MobManager.overVoid(dead.getLocation())) return;
        Location at = killer.getLocation();
        for (ItemStack it : e.getDrops()) if (it != null && !it.getType().isAir()) killer.getWorld().dropItem(at, it);
        e.getDrops().clear();
        int xp = e.getDroppedExp();
        if (xp > 0) {
            e.setDroppedExp(0);
            killer.getWorld().spawn(at, ExperienceOrb.class, o -> o.setExperience(xp));
        }
    }

    /** 가스트 불덩이에 맞은 사람을 기억해 둔다 (밀리는 힘은 같은 틱에 따로 정해진다). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onGhastHit(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player p) || !isSky(p.getWorld())) return;
        if (e.getDamager() instanceof LargeFireball f && f.getShooter() instanceof Ghast) ghastHit.put(p.getUniqueId(), Bukkit.getCurrentTick());
    }

    /** 가스트 불덩이는 한 칸 다리 위 사람을 공허로 날려 버린다. 피해와 불은 그대로 두고 밀리는 힘만 줄인다. */
    @EventHandler(ignoreCancelled = true)
    public void onKnockback(EntityKnockbackEvent e) {
        // 직접 맞은 것(ENTITY_ATTACK)과 폭발(EXPLOSION) 둘 다 같은 틱에 온다
        if (!(e.getEntity() instanceof Player p)) return;
        Integer at = ghastHit.get(p.getUniqueId());
        if (at == null || at != Bukkit.getCurrentTick()) return;
        e.setKnockback(e.getKnockback().multiply(GHAST_PUSH));
    }

    // ------------------------------------------------------------------ 관리자

    /** /증강관리 네더 [정보|이동|짓기 [강제]|검사] */
    public void admin(CommandSender s, String[] a) {
        String sub = a.length > 1 ? a[1] : "정보";
        switch (sub) {
            case "이동", "tp" -> {
                World w = world();
                if (!(s instanceof Player p) || w == null) {
                    s.sendMessage(Text.mm("<#ff7070>게임 안에서, 하늘 네더가 열려 있을 때 씁니다."));
                    return;
                }
                p.teleport(NetherMap.hubSpawn(w));
                p.setFallDistance(0);
                s.sendMessage(Text.mm("<gray>쉼터로 이동했습니다."));
            }
            case "짓기", "build" -> {
                boolean force = a.length > 2 && (a[2].equals("강제") || a[2].equalsIgnoreCase("force"));
                if (force) {
                    s.sendMessage(Text.mm("<#ffcc55>섬을 처음 모습으로 다시 짓습니다. 섬 위에 지은 것과 고친 곳은 사라지고 상자는 다시 채워집니다."));
                }
                build(s, force);
            }
            case "검사", "check" -> {
                World w = world();
                if (w == null) {
                    s.sendMessage(Text.mm("<#ff7070>하늘 네더가 열려 있지 않습니다."));
                    return;
                }
                map.check(w, s);
            }
            default -> info(s);
        }
    }

    private void info(CommandSender s) {
        World w = world();
        String state = !enabled() ? "<gray>꺼 둠 (nether.enabled: false)" : w == null ? "<#ff7070>열리지 않음"
                : building ? "<#ffcc55>짓는 중" : ready ? "<#7cff8c>열림" : "<#ff7070>닫힘";
        s.sendMessage(Text.mm("<#ffcc55>━━━━ 하늘 네더 ━━━━"));
        s.sendMessage(Text.mm("<gray>월드 <white>" + name() + " <gray>· " + state));
        s.sendMessage(Text.mm("<gray>배치 판 " + NetherMap.LAYOUT + " · " + NetherMap.summary()));
        if (builtAt != null) s.sendMessage(Text.mm("<gray>지은 때 " + builtAt + " · 실패한 섬 " + (failed > 0 ? "<#ff7070>" : "") + failed));
        if (w == null) return;
        Map<String, Integer> count = new TreeMap<>();
        for (Entity en : w.getEntities()) {
            if (en instanceof LivingEntity && !(en instanceof Player)) count.merge(en.getType().name().toLowerCase(), 1, Integer::sum);
        }
        s.sendMessage(Text.mm("<gray>안에 있는 사람 <white>" + w.getPlayers().size() + " <gray>· 불린 청크 " + w.getLoadedChunks().length));
        s.sendMessage(Text.mm("<gray>몹: <white>" + (count.isEmpty() ? "없음" : count.toString())));
    }
}
