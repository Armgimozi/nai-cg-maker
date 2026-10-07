package kr.souls.hud;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.Pool;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerExpChangeEvent;
import org.bukkit.event.player.PlayerGameModeChangeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;

import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.function.ToLongFunction;

/**
 * HUD (10.2). 행동 막대를 쓰는 곳은 여기 한 곳이다 (skyblock 에서 여러 곳이 행동 막대를 덮어쓰던 문제를 막는다).
 * 다른 체계는 값만 넘긴다.
 *  - 스태미나: 경험치 막대 (sendExperienceChange(진행, 0)). 레벨 인수가 0 이면 클라이언트가 형광 초록 숫자를 그리지 않는다.
 *    바뀐 틱에만 보내고, 서버가 진짜 경험치를 다시 보내는 때(접속, 부활, 세계 이동, 모드 변경)에는 곧바로 다시 보낸다.
 *  - 행동 막대 한 줄: [축적 막대 (M5)] [마나 막대 (마법)] 소울 N. refresh 틱마다, 그리고 바뀔 때 보낸다.
 * 진짜 경험치는 늘 0 이다 (경험치 구슬도 0).
 */
public final class Hud implements Listener {
    /** 경험치 막대는 182 픽셀. 반 픽셀보다 덜 바뀌면 보내지 않는다 */
    private static final float XP_STEP = 0.5f / 182f;
    /** 혹시 놓친 재전송을 메우려고 이 틱마다 한 번은 다시 보낸다 */
    private static final int XP_SAFETY = 100;
    /**
     * 서버는 접속·부활·세계 이동 뒤 첫 플레이어 틱에 진짜 경험치(0)를 보낸다 (lastSentExp 를 -1 로 되돌린 뒤).
     * 그 틱은 예약 작업보다 늦게 돌아서 우리 값을 덮는다. 그래서 그런 일이 있은 뒤 이 틱 수 동안은 틱마다 보낸다.
     */
    private static final int XP_FORCE = 10;

    private static final class View {
        float xp = -1;
        long xpAt;
        long forceUntil;
        Component bar;
        long barAt;
        /** 행동 막대를 만든 값 (바뀔 때만 글을 다시 만든다: MiniMessage 해석은 틱마다 하기엔 비싸다) */
        String barKey;
    }

    private final Souls plugin;
    private final Map<UUID, View> views = new HashMap<>();
    /** 소울 수 (M2 의 SoulPurse 가 바꿔 끼운다). 그 전에는 0 */
    private ToLongFunction<Player> souls = p -> 0;

    public Hud(Souls plugin) {
        this.plugin = plugin;
    }

    public void setSoulSource(ToLongFunction<Player> f) {
        souls = f == null ? p -> 0 : f;
    }

    private View view(Player p) {
        return views.computeIfAbsent(p.getUniqueId(), k -> new View());
    }

    /** 경험치 막대와 행동 막대를 다시 보낸다 (경험치 막대는 XP_FORCE 틱 동안 틱마다). */
    public void invalidate(Player p) {
        View v = view(p);
        v.xp = -1;
        v.bar = null;
        v.barKey = null;
        v.forceUntil = plugin.ticker() == null ? 0 : plugin.ticker().now() + XP_FORCE;
    }

    public void tick(long now) {
        int refresh = plugin.cfg().hud.actionbarRefresh();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.isDead()) continue;
            View v = view(p);
            CombatState st = CombatState.of(p);
            float prog = (float) Math.max(0, Math.min(1, st.stamina.ratio()));
            if (v.xp < 0 || now <= v.forceUntil || Math.abs(prog - v.xp) >= XP_STEP || (prog == 1f && v.xp != 1f) || (prog == 0f && v.xp != 0f)
                    || now - v.xpAt >= XP_SAFETY) {
                p.sendExperienceChange(prog, 0);
                v.xp = prog;
                v.xpAt = now;
            }
            String key = barKey(p, st);
            if (key.isEmpty()) continue;
            boolean changed = !key.equals(v.barKey) || v.bar == null;
            if (changed) {
                v.bar = actionBar(p, st);
                v.barKey = key;
            }
            if (v.bar != null && (changed || now - v.barAt >= refresh)) {
                p.sendActionBar(v.bar);
                v.barAt = now;
            }
        }
    }

    /** 행동 막대에 들어가는 값들을 이은 열쇠. 비어 있으면 보일 것이 없다. */
    private String barKey(Player p, CombatState st) {
        StringBuilder k = new StringBuilder();
        if (st.mana != null) k.append('m').append(Math.round(st.mana.cur())).append('/').append(Math.round(st.mana.max()));
        if (plugin.cfg().hud.showSouls()) k.append('s').append(souls.applyAsLong(p));
        return k.toString();
    }

    /** 행동 막대 한 줄. 보일 것이 없으면 null. */
    private Component actionBar(Player p, CombatState st) {
        List<Component> parts = new ArrayList<>();
        // 축적 막대(독·출혈, 0 보다 클 때만)는 M5 에 여기 더한다
        Pool mana = st.mana;
        if (mana != null) {
            // 마법이 들어오면 손으로 찍은 마나 막대 그림 글자로 바꾼다. 그 전까지는 숫자 자리만
            parts.add(Component.text(Math.round(mana.cur()) + "/" + Math.round(mana.max()), Glyphs.ASH3));
        }
        if (plugin.cfg().hud.showSouls()) {
            String n = NumberFormat.getIntegerInstance(Locale.US).format(souls.applyAsLong(p));
            parts.add(Lang.c("hud.souls", "n", n));
        }
        if (parts.isEmpty()) return null;
        Component out = Component.empty();
        for (int i = 0; i < parts.size(); i++) {
            if (i > 0) out = out.append(Component.text("   "));
            out = out.append(parts.get(i));
        }
        return out;
    }

    // ------------------------------------------------------------------ 서버가 경험치를 다시 보내는 때

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        p.setLevel(0);
        p.setExp(0);
        p.setTotalExperience(0);
        invalidate(p);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        views.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerPostRespawnEvent e) {
        invalidate(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        invalidate(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        invalidate(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onMode(PlayerGameModeChangeEvent e) {
        invalidate(e.getPlayer());
    }

    /** 진짜 경험치는 쌓이지 않는다 (막대는 스태미나 자리다). */
    @EventHandler(priority = EventPriority.HIGH)
    public void onExp(PlayerExpChangeEvent e) {
        e.setAmount(0);
        invalidate(e.getPlayer());
    }
}
