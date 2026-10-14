package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.FaceAttachable;
import org.bukkit.block.data.type.Switch;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;
import org.joml.Matrix4f;

/**
 * 9층 `gear_timing`: 북쪽 벽 시계판의 바늘이 hand_period 초에 한 바퀴. 버튼 N개에 각자 시각이 적혀 있고,
 * 바늘이 그 숫자를 지날 때(±window 초) 눌러야 한다. 라운드의 버튼을 모두 맞추면 다음 라운드(rounds).
 * 틀리면 누른 사람 fail_damage + 그 라운드 처음부터. 파티는 버튼을 나눠 맡을 수 있다.
 */
public final class GearTiming extends GimmickRoom {

    private final List<int[]> buttons = new ArrayList<>();
    private int[] targets;
    private boolean[] done;
    private final List<TextDisplay> labels = new ArrayList<>();
    private final List<TextDisplay> numerals = new ArrayList<>();
    private BlockDisplay hand;
    private int round;
    private long roundStart;
    private Location clockCenter;
    private double radius;

    public GearTiming(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(1, Math.min(6, params.integer("buttons", 4)));
        int[] xs = {-6, -2, 2, 6, -4, 4};
        for (int i = 0; i < n; i++) buttons.add(new int[] {rx(xs[i]), rz(-2)});
    }

    @Override protected String title() { return "태엽의 박자"; }

    @Override
    protected String rules() {
        return "<gray>벽 시계의 <gold>바늘</gold>이 버튼에 적힌 <gold>시각</gold>을 지나는 순간 버튼을 눌러라\n<gray>" + params.integer("rounds", 3)
                + "라운드. 박자를 놓치면 태엽이 튕겨 나온다";
    }

    @Override
    protected int timeLimit() { return 180; }

    private double period() { return Math.max(2.0, params.dbl("hand_period", 6.0)); }

    @Override
    public void prepare(BlockList list) {
        for (int[] b : buttons) {
            list.add(fs.ox() + b[0], fs.y0() + 1, fs.oz() + b[1], Material.CHISELED_TUFF_BRICKS.createBlockData());
            Switch sw = (Switch) Material.POLISHED_BLACKSTONE_BUTTON.createBlockData();
            sw.setAttachedFace(FaceAttachable.AttachedFace.FLOOR);
            sw.setFacing(BlockFace.NORTH);
            list.add(fs.ox() + b[0], fs.y0() + 2, fs.oz() + b[1], sw);
        }
        // 시계판 테두리 (북쪽 벽 안쪽 면)
        int cx = info.centerX(), z = info.minZ() - 1;
        int cy = Math.min(4, info.height() - 2);
        for (int k = 0; k < 12; k++) {
            double a = Math.toRadians(k * 30);
            int x = cx + (int) Math.round(Math.sin(a) * 3), y = cy + (int) Math.round(Math.cos(a) * 3);
            if (y >= 1) list.add(fs.ox() + x, fs.y0() + y, fs.oz() + z, Material.WAXED_CHISELED_COPPER.createBlockData());
        }
        list.add(fs.ox() + cx, fs.y0() + cy, fs.oz() + z, Material.WAXED_COPPER_BLOCK.createBlockData());
    }

    @Override
    protected void begin() {
        int cy = Math.min(4, info.height() - 2);
        radius = 2.6;
        clockCenter = new Location(fs.world(), fs.ox() + info.centerX() + 0.5, fs.y0() + cy + 0.5, fs.oz() + info.minZ() + 0.08);
        for (int k = 1; k <= 12; k++) {
            double a = Math.toRadians(k * 30);
            Location at = clockCenter.clone().add(Math.sin(a) * (radius + 0.2), Math.cos(a) * (radius + 0.2) - 0.15, 0.05);
            TextDisplay td = fs.text(at, "<white>" + k);
            td.setBackgroundColor(org.bukkit.Color.fromARGB(0, 0, 0, 0));
            numerals.add(td);
        }
        hand = fs.track(fs.world().spawn(clockCenter.clone().add(0, 0, 0.1), BlockDisplay.class, d -> {
            d.setBlock(Material.GOLD_BLOCK.createBlockData());
            d.setTransformationMatrix(handMatrix(0));
            d.setInterpolationDuration(2);
            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));
        }));
        for (int[] b : buttons) labels.add(fs.text(fs.tile(b[0], b[1], 3.2), ""));
        round = 0;
        newRound();
    }

    /** 바늘 변환: 중심 기준 시계 방향 θ 회전 (북쪽 벽을 바라볼 때 오른쪽 = +x, 위 = +y). */
    private Matrix4f handMatrix(double theta) {
        float w = 0.16f, len = (float) radius - 0.3f, d = 0.06f;
        return new Matrix4f().rotateZ((float) -theta).translate(-w / 2, 0, 0).scale(w, len, d);
    }

    private void newRound() {
        targets = new int[buttons.size()];
        done = new boolean[buttons.size()];
        List<Integer> hours = new ArrayList<>();
        for (int h = 1; h <= 12; h++) hours.add(h);
        for (int i = 0; i < buttons.size(); i++) targets[i] = hours.remove(rng.nextInt(hours.size()));
        roundStart = System.currentTimeMillis();
        refreshLabels();
        fs.actionBar(fs.allPlayers(), "<gold>라운드 " + (round + 1) + "</gold> <gray>— 바늘이 숫자를 지날 때 누르세요", 50);
    }

    private void refreshLabels() {
        for (int i = 0; i < labels.size(); i++) {
            labels.get(i).text(Text.mm(done[i] ? "<green><b>" + targets[i] + "시 ✔</b>" : "<gold><b>" + targets[i] + "시</b>"));
        }
        for (int k = 1; k <= 12; k++) {
            boolean target = false;
            for (int i = 0; i < targets.length; i++) if (targets[i] == k && !done[i]) target = true;
            numerals.get(k - 1).text(Text.mm(target ? "<gold><b>" + k : "<gray>" + k));
        }
    }

    /** 현재 바늘 위치 (시, 0~12). */
    private double handHours() {
        double t = (System.currentTimeMillis() - roundStart) / 1000.0;
        return (t % period()) / period() * 12.0;
    }

    @Override
    protected void update(long t) {
        double hrs = handHours();
        if (hand != null) {
            hand.setInterpolationDelay(0);
            hand.setTransformationMatrix(handMatrix(hrs / 12.0 * Math.PI * 2));
        }
        if (t % 10 == 0) fs.sound(clockCenter, Sound.BLOCK_COPPER_BULB_TURN_ON, 0.25f, 1.8f);
    }

    @Override
    protected String status() {
        int ok = 0;
        if (done != null) for (boolean b : done) if (b) ok++;
        return "라운드 " + (round + 1) + "/" + params.integer("rounds", 3) + " · 버튼 " + ok + "/" + buttons.size();
    }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        Material m = block.getType();
        if (m != Material.POLISHED_BLACKSTONE_BUTTON && m != Material.CHISELED_TUFF_BRICKS) return false;
        int bx = block.getX() - fs.ox(), bz = block.getZ() - fs.oz();
        for (int i = 0; i < buttons.size(); i++) {
            int[] b = buttons.get(i);
            if (b[0] != bx || b[1] != bz) continue;
            if (!running || action != Action.RIGHT_CLICK_BLOCK || done[i]) return true;
            double hrs = handHours();
            double target = targets[i] % 12;
            double diff = Math.abs(hrs - target);
            diff = Math.min(diff, 12 - diff);
            double seconds = diff * period() / 12.0;
            Location at = fs.tile(b[0], b[1], 2.3);
            if (seconds <= params.dbl("window", 0.6)) {
                done[i] = true;
                fs.sound(at, Sound.BLOCK_NOTE_BLOCK_PLING, 1.0f, 1.6f);
                fs.world().spawnParticle(Particle.ELECTRIC_SPARK, at, 16, 0.3, 0.3, 0.3, 0.1);
                boolean all = true;
                for (boolean d : done) if (!d) all = false;
                refreshLabels();
                if (all) {
                    round++;
                    if (round >= Math.max(1, params.integer("rounds", 3))) succeed();
                    else newRound();
                }
            } else {
                hurt(p, params.dbl("fail_damage", 0.06), "gear_backlash");
                fs.sound(at, Sound.BLOCK_ANVIL_LAND, 0.7f, 1.4f);
                fs.world().spawnParticle(Particle.CRIT, at, 12, 0.3, 0.3, 0.3, 0.2);
                fs.actionBar(fs.allPlayers(), "<red>박자를 놓쳤다!</red> <gray>이 라운드를 처음부터", 40);
                java.util.Arrays.fill(done, false);
                refreshLabels();
            }
            return true;
        }
        return false;
    }

    @Override
    protected void cleanup() {
        for (TextDisplay d : labels) fs.untrack(d);
        labels.clear();
        for (TextDisplay d : numerals) fs.untrack(d);
        numerals.clear();
        if (hand != null) fs.untrack(hand);
        hand = null;
    }
}
