package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.event.player.PlayerArmSwingEvent;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.ArmorPieceLayout.BodyState;
import kr.labyrinth.items.ArmorPieceLayout.Part;
import kr.labyrinth.items.ArmorPieceLayout.Placement;
import kr.labyrinth.items.ArmorPieceLayout.Stance;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.Pose;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Transformation;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 어깨·등 3D 장식 (바닐라 방어구 모양은 리소스팩으로 못 바꾸므로 — 장비 텍스처 위에 덧붙이는 입체 장식).
 * 미궁 상의(EQUIPPABLE chest, armor_set X)를 입은 플레이어마다 ItemDisplay 3개(labyrinth:armor_piece/X/shoulder_l·
 * shoulder_r·back)를 <b>플레이어의 탑승물</b>로 붙인다 → 클라이언트가 플레이어와 함께 매끄럽게 움직인다.
 * <ul>
 *   <li>방향: 몸 yaw 는 매 틱 {@link ArmorPieceLayout.BodyYaw} 로 직접 계산한다 (바닐라 클라이언트가 다른 플레이어의 몸통을 돌리는 계산 —
 *       서버의 {@link Player#getBodyYaw} 는 26.3 에서 이동 방향을 안 따라간다). {@code update_ticks}(기본 2)틱마다 바뀌었을 때만
 *       디스플레이 yaw 로 보내고, teleport_duration 으로 부드럽게 돌린다.</li>
 *   <li>자세: 서기·웅크리기 배치는 {@link ArmorPieceLayout} (순수 계산, 리소스팩 미리보기와 같은 표).
 *       헤엄·활공·급류·잠·탈것·투명(그림자 잠행 포함)이면 크기 0 으로 숨기고, 사망·관전이면 디스플레이를 지운다.</li>
 *   <li>착용자 본인에게는 기본으로 안 보인다 ({@link Player#hideEntity}, 스폰 패킷 전에) — 1인칭 시야를 가리지 않게.
 *       서버는 1인칭/3인칭(F5)을 모르므로 3인칭에서도 안 보인다 → {@code /미궁 장식 내화면 켜기} (ext {@value #EXT_SELF}) 로
 *       내 화면에도 보이게 할 수 있다. 관전자가 착용자 시점으로 들어가면(관전 대상) 그 관전자에게도 숨기고, 착용자를
 *       {@code hidePlayer}·{@code hideEntity} 로 못 보는 시청자에게도 숨긴다 (탈것 없는 장식이 허공에 떠 있지 않게).</li>
 *   <li>비영속·{@code Keys.FX} 임시 태그 (재시작 후 EntityJanitor 가 청소), 무적·무음, 히트박스 없음(디스플레이) →
 *       피해·조준·상호작용 대상이 아니다. 벗기·나가기·사망·월드 이동·플러그인 종료 때 제거, 순간이동 등으로 떨어지면 다시 태운다.</li>
 *   <li>Paper 26.3 은 탑승물이 있는 플레이어의 <b>월드 간</b> teleport 를 거부한다 → 미궁 코드는 {@code core.Teleports#to}
 *       로 옮긴다 (다른 월드면 탑승물을 먼저 내림, 같은 월드면 탑승물이 그대로 따라온다).</li>
 *   <li>설정 {@code cosmetics.armor_pieces}: enabled(기본 true) · update_ticks(기본 2) · view_range(기본 0.6, 64블록 배수).
 *       플레이어별 {@code /미궁 장식 [켜기|끄기]} — PlayerData ext {@value #EXT_KEY} (끄면 내 장식이 아예 안 생긴다),
 *       {@code /미궁 장식 내화면 [켜기|끄기]} — ext {@value #EXT_SELF} (기본 꺼짐).</li>
 * </ul>
 */
public final class ArmorCosmetics implements Listener {

    /** PlayerData ext 키 (Boolean, 없으면 켜짐). */
    public static final String EXT_KEY = "cosmetics.armor_pieces";
    /** PlayerData ext 키 (Boolean, 없으면 꺼짐): 내 장식을 내 화면에도 보이게 (3인칭 확인용). */
    public static final String EXT_SELF = "cosmetics.armor_pieces_self";
    /** 처음 장식이 생길 때 한 번만 안내했는가 (본인 화면에는 안 보이므로). */
    public static final String EXT_TOLD = "cosmetics.armor_pieces_told";
    /** Keys.FX 태그 값 접두어. */
    public static final String TAG = "armor_piece";

    /** config cosmetics.armor_pieces — 키가 없으면 코드 기본값. */
    public record Config(boolean enabled, int updateTicks, float viewRange) {
        public static final Config DEFAULT = new Config(true, 2, 0.6f);

        public static Config from(ConfigurationSection s) {
            if (s == null) return DEFAULT;
            int ticks = Math.max(1, Math.min(20, s.getInt("update_ticks", DEFAULT.updateTicks())));
            double vr = s.getDouble("view_range", DEFAULT.viewRange());
            if (!Double.isFinite(vr) || vr <= 0) vr = DEFAULT.viewRange();
            return new Config(s.getBoolean("enabled", DEFAULT.enabled()), ticks, (float) Math.min(4.0, vr));
        }
    }

    private static final Part[] PARTS = Part.values();
    /** 다시 태우기·생성이 실패하면 이 틱 동안 쉰다 (탑승물을 계속 내리는 다른 플러그인과 싸우지 않게). */
    private static final int BACKOFF_TICKS = 100;

    private final Services services;
    private final Map<UUID, Rig> rigs = new HashMap<>();
    private final Map<UUID, Long> backoffUntil = new HashMap<>();
    private Config cfg = Config.DEFAULT;
    private BukkitTask task;
    private long tick;

    /** 한 플레이어의 장식 한 벌. */
    private static final class Rig {
        final String set;
        final World world;
        final ItemDisplay[] parts = new ItemDisplay[PARTS.length];
        /** 다른 사람의 클라이언트와 같은 방식으로 매 틱 계산하는 몸 yaw. */
        final ArmorPieceLayout.BodyYaw body;
        Stance stance;
        double scale;
        /** 마지막으로 보낸 디스플레이 yaw. */
        float yaw;
        /** 착용자 본인에게 보이는 중인가 (내화면 켜기). */
        boolean selfShown;
        long lastReattach = Long.MIN_VALUE / 2;
        int burst;
        /** 숨겨 둔 시청자 (착용자 제외): 착용자 시점으로 관전 중이거나, 착용자를 못 보는(hidePlayer) 플레이어. */
        final Set<UUID> hiddenFrom = new HashSet<>();

        Rig(String set, World world, float bodyYaw) {
            this.set = set;
            this.world = world;
            this.body = new ArmorPieceLayout.BodyYaw(bodyYaw);
        }

        boolean valid() {
            for (ItemDisplay d : parts) if (d == null || !d.isValid()) return false;
            return true;
        }
    }

    public ArmorCosmetics(Services services) { this.services = services; }

    public void start() {
        cfg = Config.from(services.plugin().getConfig().getConfigurationSection("cosmetics.armor_pieces"));
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        schedule();
    }

    /** 매 틱 몸 yaw 만 계산하고 (가벼운 산수), 나머지 갱신·패킷은 update_ticks 마다. */
    private void schedule() {
        if (task != null) task.cancel();
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 5L, 1L);
    }

    public void stop() {
        if (task != null) task.cancel();
        task = null;
        HandlerList.unregisterAll(this);
        clearAll();
    }

    /** /labadmin reload: 설정을 다시 읽고 장식을 새로 만든다. */
    public void reload() {
        cfg = Config.from(services.plugin().getConfig().getConfigurationSection("cosmetics.armor_pieces"));
        clearAll();
        schedule();
    }

    public Config config() { return cfg; }

    private void clearAll() {
        for (Map.Entry<UUID, Rig> e : rigs.entrySet()) remove(Bukkit.getPlayer(e.getKey()), e.getValue());
        rigs.clear();
        backoffUntil.clear();
    }

    // ── 플레이어별 켜기/끄기 (/미궁 장식) ─────────────────────────────────

    public boolean isOn(Player p) {
        PlayerData d = services.data().getIfLoaded(p.getUniqueId());
        return d == null || ArmorPieceLayout.enabledFor(d.ext().get(EXT_KEY));
    }

    public void setOn(Player p, boolean on) {
        PlayerData d = services.data().get(p);
        d.ext().put(EXT_KEY, on);
        d.markDirty();
        if (!on) clear(p);
        else backoffUntil.remove(p.getUniqueId());
    }

    /** 내 장식을 내 화면에도 보일까 (/미궁 장식 내화면). 기록이 없으면 꺼짐. */
    public boolean isSelfView(Player p) {
        PlayerData d = services.data().getIfLoaded(p.getUniqueId());
        return d != null && ArmorPieceLayout.selfViewFor(d.ext().get(EXT_SELF));
    }

    public void setSelfView(Player p, boolean on) {
        PlayerData d = services.data().get(p);
        d.ext().put(EXT_SELF, on);
        d.markDirty();
        Rig r = rigs.get(p.getUniqueId());
        if (r != null) applySelf(p, r, on);
    }

    private void applySelf(Player p, Rig r, boolean show) {
        if (r.selfShown == show) return;
        r.selfShown = show;
        for (ItemDisplay d : r.parts) {
            if (d == null || !d.isValid()) continue;
            if (show) p.showEntity(services.plugin(), d);
            else p.hideEntity(services.plugin(), d);
        }
    }

    // ── 갱신 ──────────────────────────────────────────────────────────────

    private void tickAll() {
        tick++;
        for (Map.Entry<UUID, Rig> e : rigs.entrySet()) {
            Player p = Bukkit.getPlayer(e.getKey());
            if (p == null) continue;
            Location at = p.getLocation();
            e.getValue().body.tick(at.getX(), at.getZ(), at.getYaw(), p.isBlocking());
        }
        if (tick % cfg.updateTicks() != 0) return;
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                update(p);
            } catch (Throwable t) {
                Log.error("어깨·등 장식 갱신 오류: " + p.getName(), t);
                clear(p);
                backoffUntil.put(p.getUniqueId(), tick + BACKOFF_TICKS);
            }
        }
        if (!rigs.isEmpty()) syncViewers();
    }

    /**
     * 이 시청자에게 착용자의 장식을 숨겨야 하나 (착용자 본인 제외):
     * 착용자 시점으로 관전 중(착용자 1인칭 화면) · 착용자를 못 봄({@code hidePlayer}/{@code hideEntity} — 시청자 클라이언트에 탈것이
     * 없으니 장식이 탑승하지 못하고 처음 생긴 자리에 떠 있게 된다).
     */
    private static boolean hideFor(Player viewer, Player wearer) {
        if (viewer.getGameMode() == GameMode.SPECTATOR && wearer.equals(viewer.getSpectatorTarget())) return true;
        return !viewer.canSee(wearer);
    }

    /** 숨김 목록 맞추기 — update_ticks 마다 (시청자 수 × 장식 단 플레이어 수, 맵 조회뿐). */
    private void syncViewers() {
        for (Map.Entry<UUID, Rig> e : rigs.entrySet()) {
            Player wearer = Bukkit.getPlayer(e.getKey());
            if (wearer == null) continue;
            Rig r = e.getValue();
            for (Player v : Bukkit.getOnlinePlayers()) {
                if (v.equals(wearer)) continue;
                boolean hide = hideFor(v, wearer);
                if (hide == r.hiddenFrom.contains(v.getUniqueId())) continue;
                if (hide) {
                    r.hiddenFrom.add(v.getUniqueId());
                    for (ItemDisplay d : r.parts) if (d != null && d.isValid()) v.hideEntity(services.plugin(), d);
                } else {
                    r.hiddenFrom.remove(v.getUniqueId());
                    for (ItemDisplay d : r.parts) if (d != null && d.isValid()) v.showEntity(services.plugin(), d);
                }
            }
            // 나간 시청자는 목록에서만 뺀다 (Paper 가 접속 끊길 때 숨김 기록을 버린다)
            r.hiddenFrom.removeIf(id -> Bukkit.getPlayer(id) == null);
        }
    }

    /** 이 플레이어가 지금 보여야 할 세트 (미궁 상의 + 켜짐), 없으면 null. */
    String wantedSet(Player p) {
        if (!cfg.enabled() || !isOn(p)) return null;
        ItemStack chest = p.getInventory().getChestplate();
        if (chest == null || chest.getType().isAir()) return null;
        ItemDef def = services.items().defOf(chest).orElse(null);
        if (def == null || def.type() != ItemType.ARMOR || !"chest".equals(def.armorSlot())) return null;
        String set = def.armorSet();
        return set == null || set.isBlank() ? null : set;
    }

    static BodyState bodyState(Player p) {
        Pose pose = p.getPose();
        return new BodyState(p.isDead() || p.getHealth() <= 0, p.getGameMode() == GameMode.SPECTATOR,
                p.isInvisible() || p.hasPotionEffect(PotionEffectType.INVISIBILITY), p.isInsideVehicle(), p.isSleeping(),
                p.isGliding(), p.isSwimming(), p.isRiptiding(), pose == Pose.SNEAKING,
                pose != Pose.STANDING && pose != Pose.SNEAKING);
    }

    static double bodyScale(Player p) {
        AttributeInstance a = p.getAttribute(Attribute.SCALE);
        return a == null ? 1.0 : a.getValue();
    }

    private void update(Player p) {
        UUID id = p.getUniqueId();
        String set = wantedSet(p);
        Stance stance = set == null ? Stance.NONE : ArmorPieceLayout.stance(bodyState(p));
        Rig r = rigs.get(id);
        if (stance == Stance.NONE) {
            if (r != null) clear(p);
            return;
        }
        double scale = bodyScale(p);
        if (r == null || !r.set.equals(set) || !r.world.equals(p.getWorld()) || !r.valid()) {
            if (r != null) clear(p);
            if (tick < backoffUntil.getOrDefault(id, 0L)) return;
            r = spawn(p, set, stance, scale);
            if (r == null) {
                backoffUntil.put(id, tick + BACKOFF_TICKS);
                return;
            }
            rigs.put(id, r);
            tellOnce(p);
            return;
        }
        // 순간이동·다른 플러그인의 eject 등으로 떨어졌으면 다시 태운다
        for (ItemDisplay d : r.parts) {
            if (p.equals(d.getVehicle())) continue;
            r.burst = tick - r.lastReattach < 40 ? r.burst + 1 : 0;
            r.lastReattach = tick;
            if (r.burst > 6 || !reattach(p, d)) {     // 계속 떨어지면 잠깐 쉰다
                clear(p);
                backoffUntil.put(id, tick + BACKOFF_TICKS);
                return;
            }
        }
        if (stance != r.stance || Math.abs(scale - r.scale) > 1e-4) {
            for (int i = 0; i < PARTS.length; i++) {
                ItemDisplay d = r.parts[i];
                d.setInterpolationDelay(0);
                d.setInterpolationDuration(ArmorPieceLayout.STANCE_INTERPOLATION);
                d.setTransformation(transformation(ArmorPieceLayout.place(PARTS[i], stance, scale)));
            }
            r.stance = stance;
            r.scale = scale;
        }
        float yaw = r.body.body();
        if (ArmorPieceLayout.yawChanged(r.yaw, yaw)) {
            for (ItemDisplay d : r.parts) d.setRotation(yaw, 0f);
            r.yaw = yaw;
        }
    }

    /** 장식은 기본으로 내 화면에 안 보이므로 (3인칭 F5 에서도) 처음 생길 때 한 번 알려 준다. */
    private void tellOnce(Player p) {
        PlayerData d = services.data().getIfLoaded(p.getUniqueId());
        if (d == null || Boolean.TRUE.equals(d.ext().get(EXT_TOLD))) return;
        d.ext().put(EXT_TOLD, true);
        d.markDirty();
        kr.labyrinth.core.Text.send(p, "<gray>미궁 상의의 <white>어깨·등 입체 장식</white>이 생겼습니다 — 다른 사람에게만 보이고, 내 화면은 가리지 않도록 "
                + "<white>3인칭(F5)에서도 안 보입니다</white>. 내 모습을 직접 보려면 <white>/미궁 장식 내화면 켜기</white> "
                + "<dark_gray>(장식 끄기: /미궁 장식 끄기)");
    }

    private boolean reattach(Player p, ItemDisplay d) {
        if (!d.getWorld().equals(p.getWorld())) return false;
        if (d.getVehicle() != null) d.leaveVehicle();
        Location at = p.getLocation();
        at.setPitch(0f);
        d.teleport(at);
        return p.addPassenger(d);
    }

    static Transformation transformation(Placement pl) {
        return new Transformation(new Vector3f(pl.x(), pl.y(), pl.z()), new Quaternionf().rotationX(pl.pitch()),
                new Vector3f(pl.scale(), pl.scale(), pl.scale()), new Quaternionf());
    }

    /** labyrinth:armor_piece/&lt;세트&gt;/&lt;부위&gt; 모델을 단 아이템. */
    public static ItemStack pieceItem(String set, Part part) {
        ItemStack s = ItemStack.of(Material.PAPER);
        s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, ArmorPieceLayout.modelPath(set, part)));
        return s;
    }

    /** hideFrom = 처음부터 숨길 플레이어 (착용자 · 착용자를 못 보는 시청자 · 착용자 시점 관전자). */
    private ItemDisplay spawnPart(World w, Location at, String set, Part part, Placement pl, String owner,
                                  java.util.List<Player> hideFrom) {
        return w.spawn(at, ItemDisplay.class, e -> {
            e.setPersistent(false);
            Keys.tagTransient(e, Keys.FX, TAG + ":" + owner);
            e.setItemStack(pieceItem(set, part));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBillboard(Display.Billboard.FIXED);
            e.setViewRange(cfg.viewRange());
            e.setShadowRadius(0f);
            e.setShadowStrength(0f);
            e.setTeleportDuration(Math.min(59, cfg.updateTicks()));
            e.setInterpolationDelay(0);
            e.setInterpolationDuration(0);
            e.setTransformation(transformation(pl));
            e.setInvulnerable(true);
            e.setSilent(true);
            // 처음부터 숨김 — 월드에 넣기 전(스폰 패킷 전)에 등록해야 1틱도 안 보인다
            for (Player v : hideFrom) v.hideEntity(services.plugin(), e);
        });
    }

    private Rig spawn(Player p, String set, Stance stance, double scale) {
        World w = p.getWorld();
        Location at = p.getLocation();
        float yaw = p.getBodyYaw();       // 첫 값만 서버 값 — 이후는 BodyYaw 가 매 틱 계산
        at.setYaw(yaw);
        at.setPitch(0f);
        Rig r = new Rig(set, w, yaw);
        r.stance = stance;
        r.scale = scale;
        r.yaw = r.body.body();
        r.selfShown = isSelfView(p);
        java.util.List<Player> hide = new java.util.ArrayList<>();
        if (!r.selfShown) hide.add(p);
        for (Player v : Bukkit.getOnlinePlayers()) {
            if (!v.equals(p) && hideFor(v, p)) {
                hide.add(v);
                r.hiddenFrom.add(v.getUniqueId());
            }
        }
        for (int i = 0; i < PARTS.length; i++) {
            ItemDisplay d = spawnPart(w, at, set, PARTS[i], ArmorPieceLayout.place(PARTS[i], stance, scale),
                    p.getUniqueId().toString(), hide);
            r.parts[i] = d;
            if (d == null || !p.addPassenger(d)) {
                remove(p, r);
                return null;
            }
        }
        return r;
    }

    /** 장식 제거 (+ 착용자·시청자 숨김 목록 정리 — 지운 뒤에 보여 주기를 풀어야 스폰 패킷이 안 나간다). */
    private void remove(Player p, Rig r) {
        for (ItemDisplay d : r.parts) {
            if (d == null) continue;
            if (d.isValid()) d.remove();
            if (p != null && p.isOnline()) p.showEntity(services.plugin(), d);
            for (UUID id : r.hiddenFrom) {
                Player v = Bukkit.getPlayer(id);
                if (v != null) v.showEntity(services.plugin(), d);
            }
        }
        r.hiddenFrom.clear();
    }

    public void clear(Player p) {
        Rig r = rigs.remove(p.getUniqueId());
        if (r != null) remove(p, r);
    }

    /** 이 플레이어에게 붙은 장식 수 (자가 진단·테스트용). */
    public int pieceCount(Player p) {
        Rig r = rigs.get(p.getUniqueId());
        if (r == null) return 0;
        int n = 0;
        for (ItemDisplay d : r.parts) if (d != null && d.isValid() && p.equals(d.getVehicle())) n++;
        return n;
    }

    // ── 정리 이벤트 ───────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        clear(e.getPlayer());
        backoffUntil.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) { clear(e.getPlayer()); }

    /** 팔 휘두르기 (주손·보조손) — 다른 사람의 클라이언트는 휘두르는 동안 몸을 보는 방향으로 돌린다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwing(PlayerArmSwingEvent e) {
        Rig r = rigs.get(e.getPlayer().getUniqueId());
        if (r != null) r.body.swing();
    }

    /** 월드가 바뀌면 옛 월드에 남은 디스플레이를 지운다 (다음 갱신 때 새 월드에서 다시 만든다). */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) { clear(e.getPlayer()); }

    // ── 자가 진단 ─────────────────────────────────────────────────────────

    /**
     * 자가 진단: 첫 세트의 장식 3개를 at 에 띄웠다가 바로 지운다 (예외 없음 · 아이템 모델 키 · 변환값 확인).
     * 플러그인 데이터 폴더 pack/labyrinth-pack.zip (없으면 jar 안 pack/) 이 있으면 <b>모든</b> 세트 × 부위의
     * 아이템 정의(items/armor_piece/&lt;세트&gt;/&lt;부위&gt;.json)가 팩에 있는지도 본다.
     * @return 확인한 항목 수 (띄운 디스플레이 + 팩에서 찾은 정의)
     */
    public static int selfCheck(Services services, Location at, java.util.Collection<String> sets) {
        if (at == null || at.getWorld() == null) throw new IllegalStateException("위치 없음");
        if (sets == null || sets.isEmpty()) return 0;
        Set<String> packed = packEntries(services);
        String first = sets.iterator().next();
        int n = 0;
        for (Part part : PARTS) {
            Placement pl = ArmorPieceLayout.place(part, Stance.STAND, 1.0);
            ItemDisplay d = at.getWorld().spawn(at, ItemDisplay.class, e -> {
                e.setPersistent(false);
                Keys.tagTransient(e, Keys.FX, TAG + ":selftest");
                e.setItemStack(pieceItem(first, part));
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
                e.setTransformation(transformation(pl));
            });
            try {
                Key model = d.getItemStack().getData(DataComponentTypes.ITEM_MODEL);
                String want = ArmorPieceLayout.modelPath(first, part);
                if (model == null || !want.equals(model.value())) throw new IllegalStateException("아이템 모델 키 불일치: " + model);
                if (Math.abs(d.getTransformation().getScale().x() - pl.scale()) > 1e-4) {
                    throw new IllegalStateException("변환 배율 불일치");
                }
                n++;
            } finally {
                d.remove();
            }
        }
        if (packed != null) {
            StringBuilder missing = new StringBuilder();
            for (String set : sets) {
                for (Part part : PARTS) {
                    String path = "assets/labyrinth/items/" + ArmorPieceLayout.modelPath(set, part) + ".json";
                    if (packed.contains(path)) n++;
                    else missing.append(' ').append(set).append('/').append(part.id());
                }
            }
            if (!missing.isEmpty()) throw new IllegalStateException("리소스팩에 장식 모델 없음:" + missing);
        }
        return n;
    }

    /** 배포 중인 팩 zip 의 항목 이름 (없으면 null). */
    private static Set<String> packEntries(Services services) {
        Path file = services.plugin().getDataFolder().toPath().resolve("pack").resolve("labyrinth-pack.zip");
        try (InputStream in = Files.exists(file) ? Files.newInputStream(file) : services.plugin().getResource("pack/labyrinth-pack.zip")) {
            if (in == null) return null;
            Set<String> out = new HashSet<>();
            try (ZipInputStream z = new ZipInputStream(in)) {
                for (ZipEntry en; (en = z.getNextEntry()) != null; ) out.add(en.getName());
            }
            return out;
        } catch (Exception ex) {
            Log.warn("[자가 진단] 리소스팩 zip 을 읽지 못함: " + ex.getMessage());
            return null;
        }
    }

    /** 상의(EQUIPPABLE chest)가 있는 세트 id — 장식이 생길 수 있는 세트 (리소스팩도 이 세트들만 만든다). */
    public static java.util.SortedSet<String> chestSets(java.util.Collection<ItemDef> items) {
        java.util.SortedSet<String> out = new java.util.TreeSet<>();
        for (ItemDef d : items) {
            if (d.type() == ItemType.ARMOR && "chest".equals(d.armorSlot()) && d.armorSet() != null && !d.armorSet().isBlank()) {
                out.add(d.armorSet());
            }
        }
        return out;
    }

    /** 장식 디스플레이인가 (다른 시스템이 엔티티를 훑을 때 건너뛰도록). */
    public static boolean isPiece(Entity e) {
        String v = e.getPersistentDataContainer().get(Keys.FX, org.bukkit.persistence.PersistentDataType.STRING);
        return v != null && v.startsWith(TAG + ":");
    }
}
