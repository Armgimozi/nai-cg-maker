package kr.souls.combat;

import com.destroystokyo.paper.event.entity.EntityKnockbackByEntityEvent;
import com.destroystokyo.paper.event.server.ServerTickEndEvent;
import kr.souls.Config;
import kr.souls.Souls;
import kr.souls.util.Fx;
import org.bukkit.Bukkit;
import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.SoundGroup;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 구르기 시제품 (3.3). 구르기 입력 (1.3판: 웅크리기 키를 짧게 눌렀다 뗀 입력, input/SneakTap. controls.roll-key: f 면 F) 을 받은 틱에
 * 누르고 있는 WASD 쪽으로 구른다. 방향키가 없으면 뒷걸음. 장비가 너무 무거우면 (5.8) 방향과 상관없이 뒷걸음.
 * 공중·물속·사다리·탈것 위에서는 안 된다. 막다가 구르기 입력이 오면 막기를 풀고 구른다 (2.3.7).
 * 무적이 막는 것: 원인 물체가 있는 피해(적이 일으킨 피해), 바닐라 밀림. 막지 않는 것: 낙하, 용암, 공허, 불붙음.
 * M1 에서 적 공격은 IncomingHitQueue 가 무적 구간과 판정 틱을 맞대어 본다 (핑 보정). 지금은 서버 틱 그대로다.
 * F 는 무기 기술 자리다 (M3, 촉매면 다음 술 M5): 지금은 시험 줄 ART 만 낸다 (roll-key: f·both 면 웅크리기 키를 누른 채 F 가 무기 기술).
 *
 * 돌진처럼 보이지 않게: 한 번 튕기는 대신 glide 틱 동안 같은 빠르기로 밀다가 끝 두 틱에 줄여 멈춘다.
 * 보이는 모습은 combat.roll.visual (3.3 "보이는 모습"): tumble 은 진짜 몸을 감추고 관절이 있는 대역이 어깨로 구른다 (Tumble),
 * spin 은 바닐라 급류 회전, crawl 은 대역 없이 기어가기 자세로 미끄러진다. tumble·crawl 은 combat.roll.crawl 이면 머리 위 칸에 그
 * 사람 화면에만 있는 막힘 ({@link #CEILING}) 을 깔아 클라이언트가 스스로 기어가기 자세로 바꾸게 한다 (1인칭은 시야가 바닥까지
 * 내려갔다 올라온다). tumble 은 숙인 눈에서 F5 카메라가 막히지 않을 때만 깐다 ({@link #cameraClear}: 올려다보거나 등 뒤에 턱이
 * 있으면 서서 구른다). 막힘은 진짜 블록이 아니라 다른 사람과 서버는 모른다. 모습은 보이는 것만 바꾼다. 미는 힘·무적·비용은 셋 다 같다.
 *
 * 미는 때: 구르기 입력 (웅크리기 키를 뗀 입력 패킷, roll-key: f 면 F) 은 틱 사이에 오고, 속도 패킷은 틱마다 한 번 (엔티티 추적기가
 * hurtMarked 를 볼 때) 나간다. 구르기 입력을 받은 자리에서 setVelocity 를 하면 다음 틱의 첫 밀기가 그 값을 덮어 클라이언트에 닿지 않는다.
 * 그래서 구르기 입력에서는 방향과 시작 틱만 적고, 미는 것은 모두 Ticker 가 1..glide 틱째에 한다 (밀기 번호 0..glide-1).
 */
public final class Roll implements Listener {
    /** tumble 대역의 왼어깨가 땅에 닿는 틱 (열쇠 자세 표 roll_anim.yml 의 "어깨 닿기" 가 3틱에 닿는다) */
    private static final int TUMBLE_CONTACT = 3;
    /**
     * 그 사람 화면에만 까는 머리 위 막힘 블록: 라임 색유리. 팩이 이 블록의 모형을 비워 보이지 않는다 (pack/roll_figure.py). 바닐라
     * TransparentBlock 이라 보이는 모양 (getVisualShape) 이 비어 3인칭 카메라 (Camera.getMaxZoom 은 VISUAL 모양으로 막힘을 본다)
     * 가 지나간다: 예전 방벽은 카메라를 막아 F5 카메라를 머리 속으로 당겼다 [확인 (클라이언트 코드)]. 부딪힘은 온 블록이라 서는
     * 상자·웅크린 상자를 막는다. 이 게임의 세계와 아이템은 라임 색유리를 쓰지 않는다 (3.3).
     */
    public static final Material CEILING = Material.LIME_STAINED_GLASS;
    /** 막힘을 깔 칸: 몸 상자를 구르는 쪽으로 AHEAD 블록 쓸고 둘레로 SIDE 넓힌 곳 (클라이언트는 서버가 아는 자리보다 한두 틱 앞선다) */
    private static final double AHEAD = 1.2, SIDE = 0.35;
    /** 기어가기 자세의 눈 높이 (바닐라 Pose.SWIMMING) */
    private static final double DUCK_EYE = 0.4;
    private final Souls plugin;
    /** 사람마다 화면에만 깔아 둔 머리 위 막힘 자리 (기어가기 상자 바로 위 층) */
    private final Map<UUID, Set<Pos>> fakes = new HashMap<>();
    /** 사람마다 화면에만 깔아 둔 틈 어귀의 막힘 자리 (1칸 높이 틈 아래 기어가기 상자 자리: {@link #crawl}) */
    private final Map<UUID, Set<Pos>> walls = new HashMap<>();
    /** 사람마다 기어가기 (막힘을 거둘 틱, 어귀 막힘을 거둘 틱, tumble 의 막힘인가, 아직 머리 위 막힘을 까는가) */
    private final Map<UUID, CrawlRun> crawling = new HashMap<>();
    /** 이 틱 끝 (추적 단계 뒤) 에 머리 위 막힘을 거둘 사람 (tumble 의 기어가기를 끝낼 때: Tumble.unduck) */
    private final Set<UUID> unceilAtEnd = new HashSet<>();

    private static final class CrawlRun {
        final long until, wallUntil;
        final boolean tumble;
        boolean ducking = true;

        CrawlRun(long until, long wallUntil, boolean tumble) {
            this.until = until;
            this.wallUntil = wallUntil;
            this.tumble = tumble;
        }
    }
    /** visual: tumble 의 대역 */
    private final Tumble tumble;

    private record Pos(int x, int y, int z) {
        Block in(org.bukkit.World w) {
            return w.getBlockAt(x, y, z);
        }
    }

    public Roll(Souls plugin) {
        this.plugin = plugin;
        this.tumble = new Tumble(plugin);
        // 플러그인을 다시 켰으면 (/reload) 접속 중인 사람의 스킨 색을 다시 받는다
        for (Player p : Bukkit.getOnlinePlayers()) tumble.tint().fetch(p);
    }

    private Config.RollCfg cfg() {
        return plugin.cfg().roll;
    }

    /**
     * F (손 바꾸기). 손 바꾸기는 늘 취소한다 (왼손 방패는 인벤토리에서 든다). roll-key 가 f·both 이고 웅크리기 키를 누르지 않았으면 구르고,
     * 아니면 무기 기술 (M3) 자리라 시험 줄 ART 만 (2.3 의 12).
     */
    @EventHandler(priority = EventPriority.LOW)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        if (!plugin.worlds().ours(p.getWorld())) return;
        e.setCancelled(true);
        if (!Stamina.fighting(p) || plugin.start().unborn(p)) return;
        if (plugin.cfg().controls.fRolls() && !p.isSneaking()) {
            tryRoll(p);
            return;
        }
        var held = plugin.weapons().of(p.getInventory().getItemInMainHand());
        plugin.test(p, "ART key=f item=" + (held == null ? "-" : held.id()) + " sneak=" + p.isSneaking() + " t=" + plugin.ticker().now());
    }

    /** 구른다. 구르지 못하면 false (이유는 시험 줄로). */
    public boolean tryRoll(Player p) {
        long now = plugin.ticker().now();
        CombatState st = CombatState.of(p);
        String why = blocked(p, st, now);
        if (why != null) {
            plugin.test(p, "ROLL_DENY why=" + why + " t=" + now);
            return false;
        }
        Input in = p.getCurrentInput();
        double f = (in.isForward() ? 1 : 0) - (in.isBackward() ? 1 : 0);
        double r = (in.isRight() ? 1 : 0) - (in.isLeft() ? 1 : 0);
        double yaw = Math.toRadians(p.getYaw());
        Vector fwd = new Vector(-Math.sin(yaw), 0, Math.cos(yaw));
        Vector right = new Vector(-Math.cos(yaw), 0, -Math.sin(yaw));
        Vector dir = fwd.clone().multiply(f).add(right.multiply(r));
        // 구르기 종류: 장비 무게 단계 (5.8, combat.roll.load: auto) 를 읽기만 한다. 너무 무거우면 방향키가 있어도 뒷걸음
        String load = "auto".equals(cfg().load()) ? plugin.load().rollKind(p) : cfg().load();
        boolean over = "backstep".equals(load);
        boolean back = over || dir.lengthSquared() < 1e-4;
        if (over) {
            f = 0;
            r = 0;
        }
        Config.RollKind kind = back ? cfg().kind("backstep") : cfg().kind(load);
        if (back) dir = fwd.clone().multiply(-1);

        if (!plugin.stamina().spend(p, kind.cost(), now + kind.end())) {
            plugin.test(p, "ROLL_DENY why=stamina t=" + now);
            return false;
        }
        // 막기·마시기를 풀고 구른다 (마시다 멈추면 횟수를 쓰지 않는다)
        if (p.hasActiveItem()) p.clearActiveItem();

        st.rollStart = now;
        st.roll = kind;
        st.rollFrom = p.getLocation();
        st.rollReported = false;
        st.rollDir = dir.normalize();
        // 걸어 둔 시험 피해 (/soulstest rollhit) 는 걸어 둔 뒤 처음 구른 이 구르기에 묶는다
        if (st.armedRollHit > 0 && st.armedRollStart == Long.MIN_VALUE) st.armedRollStart = now;
        Config.RollVisual vis = cfg().visual();
        // 기어가기 막힘: 대역 (tumble) 이 그 사람 화면의 탑승 자리를 기어가기 상자에 맞추므로 막힘을 먼저 깐다 (블록 패킷은 곧바로,
        // 대역의 생성 패킷은 이 틱의 추적 단계에 나간다). 바닥 높이 때문에 기어가기 자세가 안 나오면 (crawlable) 깔지 않는다
        boolean tum = vis == Config.RollVisual.TUMBLE;
        int duck = tum ? cfg().tumble().duck() : kind.glide() + 2;
        boolean crawl = !back && cfg().barrier() && duck > 0 && crawlable(p.getLocation().getY()) && (!tum || cameraClear(p));
        unceilAtEnd.remove(p.getUniqueId());
        if (crawl) {
            // 어귀 막힘은 미는 힘이 끝날 때까지 둔다 (머리 위 막힘을 걷은 뒤에 남은 밀기가 기어가는 몸을 틈 밑으로 밀어 넣지 않게)
            crawling.put(p.getUniqueId(), new CrawlRun(now + duck, now + Math.max(duck, kind.glide() + 2), tum));
            crawl(p, st.rollDir);
        } else {
            uncrawl(p);
        }
        // 뒷걸음은 진짜 몸 그대로 뒤로 뛴다 (이어 구른 대역이 남아 있으면 거둔다)
        if (back) tumble.stop(p);
        else if (vis == Config.RollVisual.TUMBLE) tumble.start(p, st.rollDir, now, crawl);
        else if (vis == Config.RollVisual.SPIN) p.startRiptideAttack(cfg().spinTicks(), 0f, null);
        visual(p, true, back || vis != Config.RollVisual.TUMBLE);
        plugin.test(p, String.format(Locale.ROOT, "ROLL kind=%s dir=%s cost=%.0f st=%.1f vis=%s duck=%s t=%d",
                kind.id(), dirName(f, r), kind.cost(), st.stamina.cur(), back ? "body" : vis.name().toLowerCase(Locale.ROOT), crawl, now));
        return true;
    }

    /** 땅 위인지는 클라이언트가 알려 준 값을 믿는다 (혼자 하는 서버라 속일 사람이 없다). */
    @SuppressWarnings("deprecation")
    private String blocked(Player p, CombatState st, long now) {
        if (!p.isOnGround()) return "air";
        if (p.isInWater() || p.isSwimming()) return "water";
        if (p.isClimbing()) return "climbing";
        if (p.isInsideVehicle()) return "vehicle";
        if (p.isGliding() || p.isFlying()) return "flying";
        if (!st.canRollAgain(now)) return "recovering";
        if (!st.stamina.canAct()) return "stamina";
        return null;
    }

    private static String dirName(double f, double r) {
        if (f == 0 && r == 0) return "back";
        StringBuilder sb = new StringBuilder();
        if (f > 0) sb.append("fwd");
        if (f < 0) sb.append("bwd");
        if (r > 0) sb.append(sb.isEmpty() ? "right" : "+right");
        if (r < 0) sb.append(sb.isEmpty() ? "left" : "+left");
        return sb.toString();
    }

    /**
     * i 번째 밀기 (0..glide-1, 구르기 i+1 틱째). 끝 두 번은 줄여서 미끄러지지 않고 멈춰 선다.
     * 위아래는 첫 밀기만 (뒷걸음의 작은 뜀).
     */
    private void push(Player p, CombatState st, Config.RollKind kind, long i) {
        double speed = kind.horizontal();
        if (i >= kind.glide() - 2) speed *= i == kind.glide() - 1 ? 0.35 : 0.65;
        Vector v = st.rollDir.clone().multiply(speed);
        // 기어가기 막힘 아래의 클라이언트는 방향키 입력을 웅크리기 속도 (0.3) 로 줄인다: 줄어든 몫을 더해 숙이지 않을 때와 같은 거리로
        CrawlRun cr = crawling.get(p.getUniqueId());
        if (cr != null && cr.ducking && !unceilAtEnd.contains(p.getUniqueId())) {
            Vector lost = lostInput(p);
            v.add(lost);
            if (i == 0) plugin.test(p, String.format(Locale.ROOT, "ROLL_INPUT lost=%.3f along=%.3f", lost.length(), lost.dot(st.rollDir)));
        }
        v.setY(i == 0 ? kind.vertical() : Math.min(p.getVelocity().getY(), 0));
        p.setVelocity(v);
    }

    /**
     * 기어가기 자세의 클라이언트가 이 틱에 덜 움직이는 방향키 몫 [확인 (클라이언트 코드: LocalPlayer.modifyInput, KeyboardInput,
     * Entity.getInputVector)]: 입력 (정규화) × 0.98 × 이동 속도 (달리기면 1.3 배, 보통 블록 위) × (1 − 웅크리기 속도).
     */
    private static Vector lostInput(Player p) {
        Input in = p.getCurrentInput();
        double fwd = (in.isForward() ? 1 : 0) - (in.isBackward() ? 1 : 0);
        double side = (in.isLeft() ? 1 : 0) - (in.isRight() ? 1 : 0);
        double len = Math.hypot(fwd, side);
        if (len < 1e-6) return new Vector();
        AttributeInstance speed = p.getAttribute(Attribute.MOVEMENT_SPEED), sneak = p.getAttribute(Attribute.SNEAKING_SPEED);
        double lost = 0.98 * (speed == null ? 0.1 : speed.getValue()) * (1 - (sneak == null ? 0.3 : sneak.getValue())) / len;
        double yaw = Math.toRadians(p.getYaw()), sin = Math.sin(yaw), cos = Math.cos(yaw);
        return new Vector((side * cos - fwd * sin) * lost, 0, (fwd * cos + side * sin) * lost);
    }

    /** 미는 것을 그만둔다 (순간이동, 죽음, 세계 이동: 도착한 곳에서 미끄러지지 않게). 무적과 회복 틱은 그대로. */
    private static void stopGlide(Player p) {
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st != null) st.rollDir = null;
    }

    /**
     * 발밑 먼지와 땅을 구르는 소리. start 가 아니면 일어서며 땅을 짚는 소리. dust 가 거짓이면 소리만 (tumble 의 시작: 대역이
     * 뛰어드는 때라 땅에 닿은 것이 없고, 먼지가 대역 뒤에 걸린 어두운 네모로 보였다 [확인 (클라)]. 먼지는 어깨가 닿는 틱에 {@link #puff}).
     */
    private void visual(Player p, boolean start, boolean dust) {
        Location feet = p.getLocation();
        BlockData bd = floor(feet);
        if (dust) puff(p, start ? 5 : 4);
        SoundGroup g = bd.getSoundGroup();
        if (start) {
            Fx.sound(feet, cfg().sound(), cfg().volume(), cfg().pitch());
            p.getWorld().playSound(feet, g.getStepSound(), g.getVolume() * 0.8f, g.getPitch() * 0.75f);
        } else {
            p.getWorld().playSound(feet, g.getFallSound(), g.getVolume() * 0.7f, g.getPitch() * 0.8f);
        }
    }

    /** 밟은 블록 (고체가 아니면 심층암) 의 모양. */
    private static BlockData floor(Location feet) {
        Block below = feet.clone().subtract(0, 0.2, 0).getBlock();
        Material m = below.getType().isSolid() ? below.getType() : Material.DEEPSLATE;
        return m.createBlockData();
    }

    /** 구르기 먼지: 옅은 잿빛 작은 티끌 (2026-10-08 비평: 밟은 블록 조각은 심층암 바닥에서 짙은 회색 네모라 바닥에 난 구멍처럼 보였다). */
    private static final Particle.DustOptions DUST = new Particle.DustOptions(org.bukkit.Color.fromRGB(0xb0a68e), 0.55f);

    /** 발밑에 옅은 잿빛 먼지 n 알 (작고, 금방 사라진다). */
    private static void puff(Player p, int n) {
        Location feet = p.getLocation();
        p.getWorld().spawnParticle(Particle.DUST, feet.clone().add(0, 0.15, 0), n, 0.22, 0.03, 0.22, 0, DUST);
    }

    /**
     * 기어가기 상자 (높이 0.6) 바로 위 층에 이 사람 화면에만 막힘 ({@link #CEILING}) 을 깐다. 구르며 움직이므로 틱마다 다시 깐다.
     * 칸: 몸 상자 (±0.3) 를 구르는 쪽 (dir, 없으면 제자리) 으로 {@link #AHEAD} 블록 쓸고 {@link #SIDE} 넓힌 곳 가운데 그 층이 빈 칸.
     * 클라이언트는 서버가 아는 자리보다 한두 틱 앞서 움직이므로 앞을 미리 깔아 둔다 (클라이언트의 서는 상자가 막힘 하나와만 겹쳐도
     * 기어가기 자세가 이어진다). 막힘이 카메라를 막지 않아 (CEILING) 넓게 깔아도 3인칭 카메라가 당겨지지 않는다.
     * 층은 ceil(발 높이 + 0.6): 온 블록 바닥이면 발 블록 + 1, 길·농지·영혼 모래처럼 덜 찬 바닥이면 + 2.
     * 발 높이의 턱 (발보다 높고 0.6 이하: 반 블록, 계단) 이 있는 칸에는 깔지 않는다 (막힘에 걸려 턱에 오르지 못한다).
     * 그 층에 진짜 블록이 있는 칸 (1칸 높이 틈의 천장) 은 서버가 아는 서는 몸이 들어갈 수 없는 칸이다 (서버는 막힘을 모른다:
     * 기어가는 클라이언트가 들어가면 서버가 되돌려 제자리에서 떤다). 그래서 그 칸의 기어가기 상자 자리 (층 바로 아래) 에도 막힘 (어귀
     * 막힘, {@link #walls}) 을 깔아 클라이언트도 벽처럼 멈추게 한다 (지금 몸이 선 칸은 빼고, 서버의 자세가 서기·웅크리기일 때만).
     * 어귀 막힘은 머리 위 막힘을 걷은 뒤에도 미는 힘이 끝날 때까지 남긴다 (CrawlRun.wallUntil): 머리 위 막힘과 함께 걷었더니 어귀에서
     * 기어가던 클라이언트가 남은 밀기로 틈 밑에 들어가 기어가기 자세로 남았다 (자세는 움직인 뒤에 고른다) [확인 (클라): 1칸 틈 구르기].
     */
    private void crawl(Player p, Vector dir) {
        Set<Pos> want = new HashSet<>(), wantWall = new HashSet<>();
        Location l = p.getLocation();
        org.bukkit.World w = p.getWorld();
        double x = l.getX(), y = l.getY(), z = l.getZ();
        int by = crawlLayer(y);
        double ax = dir == null ? 0 : dir.getX() * AHEAD, az = dir == null ? 0 : dir.getZ() * AHEAD;
        int x0 = (int) Math.floor(Math.min(x, x + ax) - 0.3 - SIDE), x1 = (int) Math.floor(Math.max(x, x + ax) + 0.3 + SIDE);
        int z0 = (int) Math.floor(Math.min(z, z + az) - 0.3 - SIDE), z1 = (int) Math.floor(Math.max(z, z + az) + 0.3 + SIDE);
        boolean standing = p.getPose() == org.bukkit.entity.Pose.STANDING || p.getPose() == org.bukkit.entity.Pose.SNEAKING;
        for (int bx = x0; bx <= x1; bx++) {
            for (int bz = z0; bz <= z1; bz++) {
                Block top = w.getBlockAt(bx, by, bz);
                if (top.getType().isAir()) {
                    if (!stepUp(w, bx, bz, y)) want.add(new Pos(bx, by, bz));
                } else if (standing && !top.isPassable() && !occupied(x, z, bx, bz) && w.getBlockAt(bx, by - 1, bz).getType().isAir()) {
                    wantWall.add(new Pos(bx, by - 1, bz));
                }
            }
        }
        sync(p, fakes.computeIfAbsent(p.getUniqueId(), k -> new HashSet<>()), want);
        sync(p, walls.computeIfAbsent(p.getUniqueId(), k -> new HashSet<>()), wantWall);
    }

    /** 깔아 둔 칸 have 를 want 로 맞춘다 (빠진 칸은 진짜 블록으로 되돌리고 새 칸에 막힘을 보낸다). */
    private static void sync(Player p, Set<Pos> have, Set<Pos> want) {
        org.bukkit.World w = p.getWorld();
        for (Iterator<Pos> it = have.iterator(); it.hasNext(); ) {
            Pos k = it.next();
            if (want.contains(k)) continue;
            Block b = k.in(w);
            p.sendBlockChange(b.getLocation(), b.getBlockData());
            it.remove();
        }
        BlockData ceiling = CEILING.createBlockData();
        for (Pos k : want) {
            if (have.add(k)) p.sendBlockChange(k.in(w).getLocation(), ceiling);
        }
    }

    /** 깔아 둔 칸을 진짜 블록 모양으로 되돌린다. */
    private static void restore(Player p, Set<Pos> have) {
        if (have == null || !p.isOnline()) return;
        for (Pos k : have) {
            Block b = k.in(p.getWorld());
            p.sendBlockChange(b.getLocation(), b.getBlockData());
        }
    }

    /** 몸 상자 (가운데 x, z, ±0.3, 조금 넉넉히) 가 그 칸에 걸치는가. */
    private static boolean occupied(double x, double z, int bx, int bz) {
        return x + 0.35 > bx && x - 0.35 < bx + 1 && z + 0.35 > bz && z - 0.35 < bz + 1;
    }

    /** 그 칸의 발 높이에 올라설 턱 (발보다 높고 0.6 이하) 이 있는가. */
    private static boolean stepUp(org.bukkit.World w, int bx, int bz, double feetY) {
        int fy = (int) Math.floor(feetY);
        for (int yy = fy; yy <= fy + 1; yy++) {
            Block b = w.getBlockAt(bx, yy, bz);
            if (b.isPassable()) continue;
            for (org.bukkit.util.BoundingBox bb : b.getCollisionShape().getBoundingBoxes()) {
                double top = yy + bb.getMaxY();
                if (top > feetY + 0.01 && top <= feetY + 0.6 + 1e-6) return true;
            }
        }
        return false;
    }

    /** 방벽을 깔 층 (블록 y). 기어가기 상자 꼭대기(발 + 0.6) 이상인 가장 낮은 정수. */
    static int crawlLayer(double feetY) {
        return (int) Math.ceil(feetY + 0.6 - 1e-6);
    }

    /**
     * 이 발 높이에서 막힘 층이 기어가기 자세를 만드는가: 층이 웅크린 상자 (발 + 1.5) 보다 낮아야 클라이언트가 웅크리기가 아니라
     * 기어가기를 고른다. 발 높이의 소수 자리가 0.4~0.5 (아래 반 블록, 계단 아랫단) 이면 서는 상자·웅크린 상자를 막으면서 기어가기
     * 상자는 비우는 층이 없다 (+2 층이면 웅크린 자세가 된다: 대역의 탑승 자리가 0.9 어긋난다). 그때는 깔지 않는다 (시야가 서 있다).
     */
    static boolean crawlable(double feetY) {
        return crawlLayer(feetY) - feetY < 1.5 - 1e-3;
    }

    /**
     * 숙인 눈 (발 위 {@link #DUCK_EYE}) 에서 바닐라 F5 등 뒤 카메라가 combat.roll.tumble.duck-camera 블록 넘게 물러날 수 있는가
     * (tumble 만 본다: 0 이면 늘 참). 바닐라 Camera.getMaxZoom 처럼 눈에서 ±0.1 비킨 여덟 점에서 시선 반대쪽으로 카메라 거리
     * (camera_distance × scale 속성) 만큼 빛을 쏘아 가장 가까이 막힌 곳을 본다 [확인 (클라이언트 코드)]. 서버는 부딪힘 모양으로 본다
     * (클라이언트는 보이는 모양: 유리·잎은 서버 쪽이 더 일찍 막힌다. 막힘 블록 ({@link #CEILING}) 은 서버에 없다).
     * 숙이면 눈이 바닥 가까이 내려가 F5 카메라도 함께 내려간다: 올려다보면 (6° 남짓 넘게) 카메라가 곧 바닥에 막혀 눈 곁으로
     * 당겨지고, 팩 셰이더는 카메라가 대역 곁이면 1인칭으로 여겨 대역을 감춘다 (2026-10-08 비평: F5 로 20° 올려다보며 구르면 대역이
     * 잘려 사라졌다). 그래서 그럴 때는 숙이지 않는다 (1인칭은 서 있는 눈 높이로 구른다. 대역은 그대로 감춰진다). 숙인 동안에도 틱마다
     * 보고 막히면 일찍 일어선다 (Roll.tick).
     */
    private boolean cameraClear(Player p) {
        double need = cfg().tumble().duckCamera();
        if (need <= 0) return true;
        double dist = 4.0, scale = 1.0;
        org.bukkit.attribute.AttributeInstance a = p.getAttribute(org.bukkit.attribute.Attribute.CAMERA_DISTANCE);
        if (a != null) dist = a.getValue();
        org.bukkit.attribute.AttributeInstance s = p.getAttribute(org.bukkit.attribute.Attribute.SCALE);
        if (s != null) scale = s.getValue();
        double max = dist * scale;
        if (max < need) return false;
        Location l = p.getLocation();
        Vector back = l.getDirection().multiply(-1);
        Vector eye = l.toVector().add(new Vector(0, DUCK_EYE, 0));
        org.bukkit.World w = p.getWorld();
        for (int i = 0; i < 8; i++) {
            Vector from = eye.clone().add(new Vector(((i & 1) * 2 - 1) * 0.1, ((i >> 1 & 1) * 2 - 1) * 0.1, ((i >> 2 & 1) * 2 - 1) * 0.1));
            org.bukkit.util.RayTraceResult r = w.rayTraceBlocks(from.toLocation(w), back, max, org.bukkit.FluidCollisionMode.NEVER, true);
            if (r != null && r.getHitPosition().distance(eye) < need) return false;
        }
        return true;
    }

    /** 깔아 둔 막힘을 모두 거둔다 (진짜 블록 모양으로 다시 보낸다). */
    private void uncrawl(Player p) {
        crawling.remove(p.getUniqueId());
        unceilAtEnd.remove(p.getUniqueId());
        restore(p, fakes.remove(p.getUniqueId()));
        restore(p, walls.remove(p.getUniqueId()));
    }

    /** 머리 위 막힘만 거둔다 (기어가기 끝: 클라이언트가 일어선다). 어귀 막힘은 CrawlRun.wallUntil 까지 그대로. */
    private void unceil(Player p) {
        unceilAtEnd.remove(p.getUniqueId());
        CrawlRun cr = crawling.get(p.getUniqueId());
        if (cr != null) cr.ducking = false;
        restore(p, fakes.remove(p.getUniqueId()));
    }

    /** 잊는다 (나가기, 세계 이동: 블록을 되돌려 보낼 곳이 없다). */
    private void forgetCrawl(UUID id) {
        fakes.remove(id);
        walls.remove(id);
        crawling.remove(id);
        unceilAtEnd.remove(id);
    }

    public Tumble tumble() {
        return tumble;
    }

    /** 플러그인을 끌 때: 깔린 방벽과 대역을 모두 거둔다. */
    public void shutdown() {
        for (Player p : Bukkit.getOnlinePlayers()) uncrawl(p);
        fakes.clear();
        walls.clear();
        crawling.clear();
        unceilAtEnd.clear();
        tumble.shutdown();
    }

    /**
     * 보이는 것을 지금 거둔다 (대역, 방벽). 플러그인이 다른 세계로 옮기기 전에 부른다: Paper 는 탑승물이 있는 플레이어를
     * 다른 세계로 옮기지 않는다 (teleport 가 이벤트 없이 false). 같은 세계 안이면 순간이동 이벤트에서 거둔다.
     */
    public void release(Player p) {
        tumble.stop(p);
        uncrawl(p);
    }

    /** 틱 끝 (엔티티 추적이 투명 깃발·대역 변환을 보낸 뒤): 장비를 바꿔 보내고, 기어가기를 끝낸 사람의 머리 위 막힘을 거둔다. */
    @EventHandler
    public void onTickEnd(ServerTickEndEvent e) {
        tumble.tickEnd();
        if (unceilAtEnd.isEmpty()) return;
        for (UUID id : List.copyOf(unceilAtEnd)) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) unceil(p);
        }
        unceilAtEnd.clear();
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        tumble.tint().fetch(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        tumble.forget(e.getPlayer());
        forgetCrawl(e.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent e) {
        stopGlide(e.getPlayer());
        tumble.stop(e.getPlayer());
        uncrawl(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        stopGlide(e.getPlayer());
        tumble.stop(e.getPlayer());
        uncrawl(e.getPlayer());
    }

    @EventHandler
    public void onWorld(PlayerChangedWorldEvent e) {
        stopGlide(e.getPlayer());
        tumble.stop(e.getPlayer());
        forgetCrawl(e.getPlayer().getUniqueId());
    }

    /**
     * Ticker: 1..glide 틱째에 민다 (밀기 번호 t-1), 막힘을 따라 옮기고 거둘 틱에 머리 위 막힘을 거둔다 (tumble: duck 틱째, 대역의
     * own 벌을 서는 몸 높이로 옮기고 (Tumble.unduck) 이 틱 끝에 거둔다. 대역이 먼저 거둬지면 곧바로. 바닥이 기어가기 자세가 안 나오는
     * 높이가 되면 일찍. crawl: glide+2 틱째, 마지막 밀기가 클라이언트에서 끝날 틈). 틈 어귀 막힘은 max(duck, glide+2) 틱째에 거둔다.
     * glide+1 틱째에 일어서는 소리, 구르기가 끝난 틱에 시험 줄 (서버에서 잰 거리), 걸어 둔 시험 피해.
     */
    public void tick(long now) {
        tumble.tick(now);
        for (Player p : Bukkit.getOnlinePlayers()) {
            CombatState st = CombatState.peek(p.getUniqueId());
            if (st == null || st.roll == null) continue;
            long t = now - st.rollStart;
            if (t >= 1 && t <= st.roll.glide() && st.rollDir != null && !p.isDead()) push(p, st, st.roll, t - 1);
            CrawlRun cr = crawling.get(p.getUniqueId());
            if (cr != null && !unceilAtEnd.contains(p.getUniqueId())) {
                if (p.isDead() || (cr.tumble && !tumble.active(p))) {
                    uncrawl(p);
                } else if (cr.ducking && (now >= cr.until || !crawlable(p.getLocation().getY()) || (cr.tumble && !cameraClear(p)))) {
                    if (now < cr.until) plugin.test(p, "ROLL_UNDUCK early=" + (cr.until - now) + " t=" + now);
                    if (cr.tumble) {
                        tumble.unduck(p);
                        unceilAtEnd.add(p.getUniqueId());
                    } else {
                        unceil(p);
                    }
                } else if (cr.ducking) {
                    crawl(p, st.rollDir);
                } else if (now >= cr.wallUntil) {
                    uncrawl(p);
                }
            }
            if (t == st.roll.glide() + 1 && st.rollDir != null) visual(p, false, true);
            // tumble: 어깨가 땅에 닿는 틱의 먼지. 발이 닿는 끝 먼지는 위 (glide + 1)
            if (t == TUMBLE_CONTACT && tumble.active(p) && st.rollDir != null && !"backstep".equals(st.roll.id())) puff(p, 4);
            if (st.armedRollHit > 0 && st.armedRollStart != Long.MIN_VALUE && st.armedRollStart != st.rollStart) {
                // 묶인 구르기가 그 틱에 닿기 전에 다음 구르기가 시작됐다
                plugin.test(p, "ROLLHIT dropped off=" + st.armedRollHit + " t=" + now);
                st.armedRollHit = -1;
                st.armedRollStart = Long.MIN_VALUE;
            }
            if (st.armedRollHit > 0 && st.armedRollStart == st.rollStart && t == st.armedRollHit) {
                int off = st.armedRollHit;
                st.armedRollHit = -1;
                st.armedRollStart = Long.MIN_VALUE;
                TestHits.Result res = plugin.testHits().hit(p, st.armedRollHitAmount, "generic", false);
                plugin.test(p, "ROLLHIT off=" + off + " iframes=" + st.roll.iframes() + " dodged=" + (res.dealt() <= 1e-6) + " " + res.line());
            }
            if (!st.rollReported && t >= st.roll.end()) {
                st.rollReported = true;
                Location a = st.rollFrom, b = p.getLocation();
                double dist = a == null || !a.getWorld().equals(b.getWorld()) ? -1
                        : Math.hypot(b.getX() - a.getX(), b.getZ() - a.getZ());
                plugin.test(p, String.format(Locale.ROOT, "ROLLEND kind=%s dist=%.2f st=%.1f t=%d", st.roll.id(), dist, st.stamina.cur(), now));
            }
        }
    }

    /** 무적: 원인 물체가 있는 피해만 피한다. 낙하·용암·공허·불붙음은 원인 물체가 없어 그대로 들어온다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st == null || !st.invulnerable(plugin.ticker().now())) return;
        Entity cause = e.getDamageSource().getCausingEntity();
        if (cause == null || cause == p) return;
        e.setCancelled(true);
        plugin.test(p, String.format(Locale.ROOT, "DODGE amount=%.2f t=%d", e.getDamage(), plugin.ticker().now()));
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onKnockback(EntityKnockbackByEntityEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st != null && st.invulnerable(plugin.ticker().now())) e.setCancelled(true);
    }
}
