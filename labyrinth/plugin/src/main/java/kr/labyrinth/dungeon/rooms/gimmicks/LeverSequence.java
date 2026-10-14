package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.FaceAttachable;
import org.bukkit.block.data.type.Switch;
import org.bukkit.entity.Player;
import org.bukkit.event.block.Action;

/** 1층 `lever_sequence`: 이끼 받침대가 순서대로 빛남 → 같은 순서로 레버. 틀리면 몹 + 처음부터, 시도 소진 = 실패. */
public final class LeverSequence extends GimmickRoom {

    private final List<int[]> levers = new ArrayList<>();
    private final List<Integer> sequence = new ArrayList<>();
    private int input;
    private int attempts;
    private long showUntil;
    private boolean showing;

    public LeverSequence(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(3, Math.min(7, params.integer("levers", 5)));
        for (int i = 0; i < n; i++) {
            double a = Math.toRadians(200 + 140.0 * i / (n - 1));
            levers.add(new int[] {rx((int) Math.round(Math.cos(a) * 6)), rz((int) Math.round(Math.sin(a) * 6))});
        }
    }

    @Override protected String title() { return "이끼의 기억"; }

    @Override
    protected String rules() {
        return "<gray>이끼는 단 한 번 숨을 쉰다\n<gray>기억하는 자에게만 길이 열린다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "이끼가 빛나는 차례에는 뜻이 있다.",
                "레버는 이끼가 빛난 차례를 기억하고 있다. 처음부터 끝까지, 같은 차례로.",
                "받침대가 빛난 순서를 외워 두었다가, 빛이 멈춘 뒤 같은 순서로 레버를 당겨라 (우클릭). 틀리면 이끼 짐승이 깨어나고 처음부터 다시 보여 준다.");
    }

    @Override
    protected int timeLimit() { return 0; }

    @Override
    public void prepare(BlockList list) {
        for (int[] l : levers) {
            list.add(fs.ox() + l[0], fs.y0() + 1, fs.oz() + l[1], Material.MOSS_BLOCK.createBlockData());
            list.add(fs.ox() + l[0], fs.y0() + 2, fs.oz() + l[1], lever(l, false));
        }
    }

    private org.bukkit.block.data.BlockData lever(int[] l, boolean powered) {
        Switch sw = (Switch) Material.LEVER.createBlockData();
        sw.setAttachedFace(FaceAttachable.AttachedFace.FLOOR);
        int dx = info.centerX() - l[0], dz = info.centerZ() - l[1];
        sw.setFacing(Math.abs(dx) > Math.abs(dz) ? (dx > 0 ? BlockFace.EAST : BlockFace.WEST) : (dz > 0 ? BlockFace.SOUTH : BlockFace.NORTH));
        sw.setPowered(powered);
        return sw;
    }

    @Override
    protected void begin() {
        attempts = Math.max(1, params.integer("attempts", 3));
        newSequence();
        playSequence(1500);
    }

    private void newSequence() {
        sequence.clear();
        int len = Math.max(2, params.integer("sequence_length", 4));
        int prev = -1;
        for (int i = 0; i < len; i++) {
            int k;
            do { k = rng.nextInt(levers.size()); } while (k == prev);
            sequence.add(k);
            prev = k;
        }
        input = 0;
    }

    private void playSequence(long delayMs) {
        showing = true;
        long interval = Math.round(params.dbl("show_interval", 0.9) * 1000);
        long base = delayMs;
        for (int i = 0; i < sequence.size(); i++) {
            int idx = sequence.get(i);
            long at = base + i * interval;
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> flash(idx, true), at / 50);
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> flash(idx, false), (at + interval * 2 / 3) / 50);
        }
        showUntil = System.currentTimeMillis() + base + sequence.size() * interval;
        fs.actionBar(fs.allPlayers(), "<green>이끼가 차례로 숨을 쉰다…</green>", 40);
    }

    private void flash(int idx, boolean on) {
        if (!running) return;
        int[] l = levers.get(idx);
        fs.setBlock(l[0], 1, l[1], on ? Material.VERDANT_FROGLIGHT : Material.MOSS_BLOCK);
        if (on) {
            Location at = fs.tile(l[0], l[1], 2.2);
            fs.world().spawnParticle(Particle.HAPPY_VILLAGER, at, 10, 0.3, 0.3, 0.3, 0.0);
            fs.sound(at, Sound.BLOCK_NOTE_BLOCK_CHIME, 1.0f, 0.7f + idx * 0.15f);
        }
    }

    @Override
    protected void update(long t) {
        if (showing && System.currentTimeMillis() >= showUntil) {
            showing = false;
            fs.actionBar(fs.allPlayers(), "<yellow>이끼가 숨을 멈췄다.</yellow>", 50);
        }
    }

    @Override
    protected String status() { return "진행 " + input + "/" + sequence.size() + " · 남은 기회 " + attempts; }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        if (block.getType() != Material.LEVER) return false;
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        int idx = -1;
        for (int i = 0; i < levers.size(); i++) if (levers.get(i)[0] == tx && levers.get(i)[1] == tz) idx = i;
        if (idx < 0) return false;
        if (!running || showing || action != Action.RIGHT_CLICK_BLOCK) return true;
        int[] l = levers.get(idx);
        fs.setBlock(l[0], 2, l[1], lever(l, true));
        int fi = idx;
        Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> fs.setBlock(l[0], 2, l[1], lever(levers.get(fi), false)), 8L);
        fs.sound(block.getLocation(), Sound.BLOCK_LEVER_CLICK, 1.0f, 1.0f);
        flash(idx, true);
        Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> flash(fi, false), 8L);
        if (sequence.get(input) == idx) {
            input++;
            if (input >= sequence.size()) succeed();
            return true;
        }
        attempts--;
        fs.sound(block.getLocation(), Sound.BLOCK_ANVIL_LAND, 0.6f, 0.6f);
        if (attempts <= 0) {
            failSpawn();
            fail("순서를 끝내 맞추지 못했습니다");
            return true;
        }
        fs.actionBar(fs.allPlayers(), "<red>이끼가 몸서리친다!</red> <gray>짐승이 깨어난다 — 남은 기회 " + attempts, 50);
        failSpawn();
        input = 0;
        playSequence(2500);
        return true;
    }

    @Override
    protected void cleanup() {
        for (int[] l : levers) fs.setBlock(l[0], 1, l[1], Material.MOSS_BLOCK);
        showing = false;
    }
}
