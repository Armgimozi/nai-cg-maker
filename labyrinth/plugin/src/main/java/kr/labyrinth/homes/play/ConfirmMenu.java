package kr.labyrinth.homes.play;

import java.util.List;
import java.util.function.Consumer;
import kr.labyrinth.ui.Button;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/** 한 번 더 묻기 (받기·비우기): 가운데 설명 · 왼쪽 예 · 오른쪽 아니오. */
final class ConfirmMenu extends HomeMenu {

    private final String question;
    private final List<String> lines;
    private final String yesLabel;
    private final Consumer<Player> yes;
    private final Consumer<Player> no;

    ConfirmMenu(PlayUi ui, String question, List<String> lines, String yesLabel, Consumer<Player> yes, Consumer<Player> no) {
        super(ui, "confirm", 3, "<dark_gray>" + question);
        this.question = question;
        this.lines = lines == null ? List.of() : lines;
        this.yesLabel = yesLabel == null ? "예" : yesLabel;
        this.yes = yes;
        this.no = no;
    }

    @Override
    protected void draw(Player p) {
        deco(13, Button.icon(Material.PAPER, "<#ffd36b>" + question, lines));
        set(11, Button.icon(Material.LIME_CONCRETE, "<#7fe07f><b>" + yesLabel + "</b>", List.of("<gray>클릭: " + yesLabel)), ctx -> {
            click(ctx.player());
            ctx.player().closeInventory();
            if (yes != null) yes.accept(ctx.player());
        });
        set(15, Button.icon(Material.RED_CONCRETE, "<#ff6b6b><b>아니오</b>", List.of("<gray>그만두고 돌아갑니다.")), ctx -> {
            click(ctx.player());
            if (no != null) no.accept(ctx.player());
            else ctx.player().closeInventory();
        });
    }
}
