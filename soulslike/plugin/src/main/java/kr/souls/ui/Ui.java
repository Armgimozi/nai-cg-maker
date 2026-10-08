package kr.souls.ui;

import io.papermc.paper.connection.PlayerGameConnection;
import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.dialog.DialogResponseView;
import io.papermc.paper.event.player.PlayerCustomClickEvent;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.action.DialogAction;
import kr.souls.Keys;
import kr.souls.Souls;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.nbt.api.BinaryTagHolder;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import java.security.SecureRandom;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 우리 Dialog 창의 단추 길 (5.7, 5.9, 5.10, 검토 T5). 모든 단추는 고정 열쇠 souls:ui 의 사용자 지정 클릭 하나로 서버에 온다
 * (DialogAction.customClick(souls:ui, {d: 창, n: 띄울 때마다 새 값, b: 단추})). 그래서 Paper 의 콜백처럼 5분 뒤에 말없이 사라지지
 * 않고, 봇도 같은 패킷 (custom_click_action) 으로 진짜 단추를 누를 수 있다 (검토 T17).
 * 아무 클라이언트나 이 패킷을 아무 때나 보낼 수 있으므로, 서버가 사람마다 지금 띄운 창 (세션: 창 이름과 n) 을 들고 있다가 맞는 것만
 * 받는다 (지난 창의 단추·꾸며 낸 값은 UI_STALE). 한 창의 단추는 한 번만 듣는다: 누르면 세션이 닫히고, 다음 창을 띄우는 처리기가 새 세션을
 * 연다. 그래서 처리기는 늘 새 창을 띄우거나 창을 닫는다 (afterAction NONE 인 창이 열린 채 남지 않게, 검토 T7).
 * 창이 열려 있는 동안: 짧게 누른 웅크리기 키는 구르기가 되지 않고 (SneakTap), 다른 플레이어에게 맞지 않는다 (Pvp).
 */
public final class Ui implements Listener {
    public static final Key KEY = Key.key(Keys.NS, "ui");
    private static final SecureRandom RNG = new SecureRandom();

    @FunctionalInterface
    public interface Click {
        void run(Player p, DialogResponseView view);
    }

    /** 띄운 창 하나: 이름, 띄울 때마다 새 값, 단추 → 처리기. */
    public static final class Session {
        final String dialog;
        final String nonce;
        final Map<String, Click> handlers = new HashMap<>();

        Session(String dialog) {
            this.dialog = dialog;
            this.nonce = Long.toHexString(RNG.nextLong() & 0xffffffffffL);
        }

        public String dialog() {
            return dialog;
        }
    }

    private final Souls plugin;
    private final Map<UUID, Session> open = new HashMap<>();
    private final Map<UUID, Long> shownAt = new HashMap<>();

    public Ui(Souls plugin) {
        this.plugin = plugin;
    }

    /** 새 창의 세션 (show 로 띄운다). */
    public Session begin(String dialog) {
        return new Session(dialog);
    }

    /** 이 세션의 단추. id 는 창 안에서 하나 (시험 줄과 봇이 쓰는 이름). tooltip 은 null 이어도 된다. */
    public ActionButton button(Session s, String id, Component label, Component tooltip, int width, Click c) {
        s.handlers.put(id, c);
        ActionButton.Builder b = ActionButton.builder(label).width(width).action(action(s, id));
        if (tooltip != null) b.tooltip(tooltip);
        return b.build();
    }

    static DialogAction action(Session s, String id) {
        String snbt = "{d:\"" + s.dialog + "\",n:\"" + s.nonce + "\",b:\"" + id + "\"}";
        return DialogAction.customClick(KEY, BinaryTagHolder.binaryTagHolder(snbt));
    }

    public void show(Player p, Session s, Dialog d) {
        open.put(p.getUniqueId(), s);
        shownAt.put(p.getUniqueId(), plugin.ticker().now());
        p.showDialog(d);
        plugin.test(p, "UI show d=" + s.dialog + " buttons=" + String.join(",", s.handlers.keySet()) + " t=" + plugin.ticker().now());
    }

    /**
     * 창을 닫는다 (서버가 닫으면 나가기 동작이 오지 않으므로 세션도 여기서 닫는다). 단추를 누른 뒤에는 onClick 이 세션을 이미 지웠어도
     * 클라이언트에는 창이 그대로 떠 있다 (afterAction NONE) 그래서 세션과 상관없이 늘 닫기 패킷을 보낸다 (클라이언트는 창 화면일 때만 닫는다).
     */
    public void close(Player p) {
        open.remove(p.getUniqueId());
        p.closeDialog();
    }

    /** 우리 창이 열려 있나. */
    public boolean open(Player p) {
        return open.containsKey(p.getUniqueId());
    }

    /** 열린 창 이름 (없으면 null). */
    public String openDialog(Player p) {
        Session s = open.get(p.getUniqueId());
        return s == null ? null : s.dialog;
    }

    /** 마지막으로 창을 띄운 틱 (없으면 Long.MIN_VALUE). SneakTap 이 창이 뜰 때 떼어진 웅크리기를 거른다. */
    public long shownAt(Player p) {
        return shownAt.getOrDefault(p.getUniqueId(), Long.MIN_VALUE / 2);
    }

    @EventHandler
    public void onClick(PlayerCustomClickEvent e) {
        if (!KEY.equals(e.getIdentifier()) || !(e.getCommonConnection() instanceof PlayerGameConnection gc)) return;
        Player p = gc.getPlayer();
        DialogResponseView v = e.getDialogResponseView();
        String d = v == null ? null : v.getText("d"), n = v == null ? null : v.getText("n"), b = v == null ? null : v.getText("b");
        Session s = open.get(p.getUniqueId());
        if (s == null || d == null || n == null || b == null || !s.dialog.equals(d) || !s.nonce.equals(n)) {
            plugin.test(p, "UI_STALE d=" + d + " b=" + b + " open=" + (s == null ? "-" : s.dialog) + " t=" + plugin.ticker().now());
            return;
        }
        Click c = s.handlers.get(b);
        if (c == null) {
            plugin.test(p, "UI_STALE d=" + d + " b=" + b + " unknown_button t=" + plugin.ticker().now());
            return;
        }
        open.remove(p.getUniqueId());
        plugin.test(p, "UI click d=" + d + " b=" + b + " t=" + plugin.ticker().now());
        c.run(p, v);
    }

    /** 시험 명령이 단추를 누른 것처럼 (봇이 진짜 패킷을 못 보낼 때). 열린 창이 dialog 가 아니면 false. */
    public boolean press(Player p, String dialog, String button) {
        Session s = open.get(p.getUniqueId());
        if (s == null || !s.dialog.equals(dialog.toLowerCase(Locale.ROOT))) return false;
        Click c = s.handlers.get(button);
        if (c == null) return false;
        open.remove(p.getUniqueId());
        plugin.test(p, "UI click d=" + dialog + " b=" + button + " via=command t=" + plugin.ticker().now());
        c.run(p, null);
        return true;
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        open.remove(e.getPlayer().getUniqueId());
        shownAt.remove(e.getPlayer().getUniqueId());
    }

    /** 죽으면 사망 화면이 창을 덮는다 (나가기 동작이 오지 않는다): 세션을 닫는다. */
    @EventHandler
    public void onDeath(PlayerDeathEvent e) {
        open.remove(e.getEntity().getUniqueId());
    }
}
