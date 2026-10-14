package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
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
import org.bukkit.entity.Player;
import org.bukkit.event.block.Action;

/**
 * 7층 `resonance_tune`: 자수정 N개가 각자 다른 음. 방이 멜로디를 연주 → 같은 순서로 친다. rounds 라운드(라운드마다 한 음 더),
 * 틀리면 친 사람에게 fail_damage, 기회 소진 = 실패.
 */
public final class ResonanceTune extends GimmickRoom {

    /** 오음계 (반음 0,2,5,7,9 를 벨 소리 피치로). */
    private static final float[] PITCH = {0.707f, 0.794f, 0.944f, 1.059f, 1.189f, 1.335f, 1.414f};

    private final List<int[]> crystals = new ArrayList<>();
    private final List<Integer> melody = new ArrayList<>();
    private final Map<UUID, Long> cooldown = new HashMap<>();
    private int round;
    private int input;
    private int attempts;
    private long playingUntil;

    public ResonanceTune(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(3, Math.min(7, params.integer("crystals", 5)));
        for (int i = 0; i < n; i++) {
            double a = Math.toRadians(200 + 140.0 * i / (n - 1));
            crystals.add(new int[] {rx((int) Math.round(Math.cos(a) * 6)), rz((int) Math.round(Math.sin(a) * 6))});
        }
    }

    @Override protected String title() { return "공명의 노래"; }

    @Override
    protected String rules() {
        return "<gray>수정이 노래를 부른다. 메아리는 아직 없다\n<gray>어긋난 음은 몸을 찢는다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "수정은 같은 노래를 다시 듣고 싶어 한다.",
                "노래한 차례대로 수정을 두드려라. 노래는 매번 한 음씩 길어진다.",
                "수정이 빛나며 노래한 순서를 외웠다가, 노래가 멎으면 같은 순서로 수정을 쳐라 (좌·우클릭). 라운드마다 한 음씩 늘고, 틀리면 친 사람이 다친다.");
    }

    @Override
    public void prepare(BlockList list) {
        for (int[] c : crystals) {
            list.add(fs.ox() + c[0], fs.y0() + 1, fs.oz() + c[1], Material.AMETHYST_BLOCK.createBlockData());
            list.add(fs.ox() + c[0], fs.y0() + 2, fs.oz() + c[1], Material.AMETHYST_CLUSTER.createBlockData());
        }
    }

    @Override
    protected void begin() {
        round = 0;
        attempts = Math.max(1, params.integer("attempts", 3));
        nextRound();
    }

    private void nextRound() {
        melody.clear();
        int len = Math.max(2, params.integer("melody_length", 5)) + round;
        int prev = -1;
        for (int i = 0; i < len; i++) {
            int k;
            do { k = rng.nextInt(crystals.size()); } while (k == prev);
            melody.add(k);
            prev = k;
        }
        input = 0;
        play(1500);
    }

    private void play(long delayMs) {
        long step = 750;
        for (int i = 0; i < melody.size(); i++) {
            int k = melody.get(i);
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> ring(k, true), (delayMs + i * step) / 50);
        }
        playingUntil = System.currentTimeMillis() + delayMs + melody.size() * step;
        fs.actionBar(fs.allPlayers(), "<light_purple>수정이 노래한다…</light_purple>", 40);
    }

    private void ring(int k, boolean show) {
        if (!running) return;
        int[] c = crystals.get(k);
        Location at = fs.tile(c[0], c[1], 2.4);
        fs.sound(at, Sound.BLOCK_NOTE_BLOCK_BELL, 1.2f, PITCH[k % PITCH.length]);
        fs.sound(at, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 0.6f, PITCH[k % PITCH.length]);
        fs.world().spawnParticle(Particle.END_ROD, at, show ? 14 : 6, 0.2, 0.4, 0.2, 0.03);
        fs.setBlock(c[0], 1, c[1], Material.PEARLESCENT_FROGLIGHT);
        Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> fs.setBlock(c[0], 1, c[1], Material.AMETHYST_BLOCK), 10L);
    }

    @Override
    protected void update(long t) {
        if (playingUntil > 0 && System.currentTimeMillis() >= playingUntil) {
            playingUntil = -1;
            fs.actionBar(fs.allPlayers(), "<yellow>노래가 멎었다.</yellow>", 50);
        }
    }

    @Override
    protected String status() {
        return "라운드 " + (round + 1) + "/" + params.integer("rounds", 2) + " · " + input + "/" + melody.size() + " · 기회 " + attempts;
    }

    @Override
    protected float progress() {
        int rounds = Math.max(1, params.integer("rounds", 2));
        return (round + (melody.isEmpty() ? 0 : input / (float) melody.size())) / rounds;
    }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        int bx = block.getX() - fs.ox(), bz = block.getZ() - fs.oz(), dy = block.getY() - fs.y0();
        if (dy < 1 || dy > 2) return false;
        int idx = -1;
        for (int i = 0; i < crystals.size(); i++) if (crystals.get(i)[0] == bx && crystals.get(i)[1] == bz) idx = i;
        if (idx < 0) return false;
        if (!running || playingUntil > 0) return true;
        if (action != Action.LEFT_CLICK_BLOCK && action != Action.RIGHT_CLICK_BLOCK) return true;
        long now = System.currentTimeMillis();
        if (now - cooldown.getOrDefault(p.getUniqueId(), 0L) < 300) return true;
        cooldown.put(p.getUniqueId(), now);
        ring(idx, false);
        if (melody.get(input) == idx) {
            input++;
            if (input >= melody.size()) {
                round++;
                if (round >= Math.max(1, params.integer("rounds", 2))) {
                    succeed();
                } else {
                    fs.actionBar(fs.allPlayers(), "<green>완벽한 화음!</green> <gray>노래가 길어진다…", 50);
                    nextRound();
                }
            }
            return true;
        }
        attempts--;
        hurt(p, params.dbl("fail_damage", 0.08), "resonance_discord");
        fs.sound(block.getLocation(), Sound.BLOCK_GLASS_BREAK, 1.0f, 0.6f);
        if (attempts <= 0) {
            fail("불협화음이 수정을 깨뜨렸습니다");
            return true;
        }
        fs.actionBar(fs.allPlayers(), "<red>불협화음!</red> <gray>처음부터 다시 — 남은 기회 " + attempts, 50);
        input = 0;
        play(2000);
        return true;
    }

    @Override
    protected void cleanup() {
        for (int[] c : crystals) fs.setBlock(c[0], 1, c[1], Material.AMETHYST_BLOCK);
        playingUntil = -1;
    }
}
