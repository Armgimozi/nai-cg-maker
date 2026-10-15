package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
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
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;

/**
 * 8층 `book_cipher`: 벽을 따라 책장 N개, 각자 기호가 떠 있다. 가운데 독서대의 수수께끼 3줄(기호의 은유 2 + 위치 1)로
 * 정답 책장 books 개를 찾아 우클릭. 틀리면 먹물 원령, 기회 소진·시간 초과 = 실패.
 */
public final class BookCipher extends GimmickRoom {

    /** 기호, 이름, 은유 (수수께끼). */
    private static final String[][] SYMBOLS = {
        {"☀", "태양", "한낮을 다스리는 불덩이"}, {"☾", "달", "밤하늘에 걸린 은빛 낫"}, {"★", "별", "길 잃은 이의 이정표"},
        {"❄", "눈꽃", "녹지 않는 하얀 꽃"}, {"⚔", "쌍검", "서로를 겨눈 두 칼날"}, {"⚓", "닻", "배를 붙드는 쇠갈고리"},
        {"✿", "꽃", "다섯 장 꽃잎의 봄"}, {"♥", "심장", "멈추지 않는 북소리"}, {"♠", "창끝", "검게 벼린 창의 날"},
        {"☂", "우산", "비를 막는 둥근 지붕"}, {"✉", "편지", "봉인된 채 도착한 소식"}, {"⌛", "모래시계", "흘러내리는 모래의 시간"},
        {"☯", "음양", "서로를 품은 빛과 어둠"}, {"♪", "음표", "종이 위에 잠든 노래"}, {"⚖", "저울", "기울지 않는 두 접시"},
        {"✦", "불티", "네 갈래로 빛나는 불씨"}
    };
    private static final String[] WALL_NAME = {"북쪽", "동쪽", "남쪽", "서쪽"};
    /** 벽을 따라 놓는 위치 (내부 좌표 오프셋 0..18, 출입구 통로 8..10 피함). */
    private static final int[] OFFSETS = {2, 5, 13, 16};

    /** {x, z, wall(0..3), orderOnWall(왼쪽부터 1..)} */
    private final List<int[]> shelves = new ArrayList<>();
    private final List<Integer> symbolOf = new ArrayList<>();
    private final Set<Integer> answers = new HashSet<>();
    private final Set<Integer> found = new HashSet<>();
    private final List<TextDisplay> labels = new ArrayList<>();
    private TextDisplay riddle;
    private int attempts;

    public BookCipher(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(4, Math.min(16, params.integer("shelves", 12)));
        int perWall = (int) Math.ceil(n / 4.0);
        for (int wall = 0; wall < 4 && shelves.size() < n; wall++) {
            for (int k = 0; k < perWall && shelves.size() < n; k++) {
                int off = OFFSETS[k];
                int x, z;
                switch (wall) {
                    case 0 -> { x = info.minX() + off; z = info.minZ(); }
                    case 1 -> { x = info.maxX(); z = info.minZ() + off; }
                    case 2 -> { x = info.maxX() - off; z = info.maxZ(); }
                    default -> { x = info.minX(); z = info.maxZ() - off; }
                }
                shelves.add(new int[] {x, z, wall, k + 1});
            }
        }
        // 벽마다 "왼쪽부터" 순서: 방 안에서 그 벽을 바라볼 때 기준 (북: x 증가, 동: z 증가, 남: x 감소, 서: z 감소) — 위 배치 순서와 같음
    }

    @Override protected String title() { return "망각의 암호"; }

    @Override
    protected String rules() {
        return "<gray>독서대가 잃어버린 책 " + params.integer("books", 3) + "권을 찾고 있다\n"
                + "<gray>틀린 손길은 먹물을 깨운다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "독서대의 말은 은유다. 책장 위에 떠 있는 기호를 살펴라.",
                "수수께끼 한 줄은 기호 하나를 가리킨다. 마지막 줄만은 기호가 아니라 자리를 말한다.",
                "수수께끼의 은유에 맞는 기호(예: 밤하늘의 은빛 낫 = ☾)가 떠 있는 책장을 우클릭. 마지막 줄은 그 벽을 바라보고 왼쪽부터 센 책장이다. 틀리면 먹물 원령이 깨어난다.");
    }

    @Override
    protected int timeLimit() { return params.integer("time_limit", 180); }

    @Override
    public void prepare(BlockList list) {
        for (int[] s : shelves) {
            BlockFace facing = switch (s[2]) {
                case 0 -> BlockFace.SOUTH;
                case 1 -> BlockFace.WEST;
                case 2 -> BlockFace.NORTH;
                default -> BlockFace.EAST;
            };
            org.bukkit.block.data.BlockData chiseled = Material.CHISELED_BOOKSHELF.createBlockData();
            if (chiseled instanceof Directional d) d.setFacing(facing);
            list.add(fs.ox() + s[0], fs.y0() + 1, fs.oz() + s[1], Material.BOOKSHELF.createBlockData());
            list.add(fs.ox() + s[0], fs.y0() + 2, fs.oz() + s[1], chiseled);
        }
        org.bukkit.block.data.BlockData lectern = Material.LECTERN.createBlockData();
        if (lectern instanceof Directional d) d.setFacing(BlockFace.NORTH);
        list.add(fs.ox() + info.centerX(), fs.y0() + 1, fs.oz() + info.centerZ(), lectern);
    }

    @Override
    protected void begin() {
        attempts = Math.max(1, params.integer("attempts", 3));
        found.clear();
        answers.clear();
        symbolOf.clear();
        List<Integer> pool = new ArrayList<>();
        for (int i = 0; i < SYMBOLS.length; i++) pool.add(i);
        for (int i = pool.size() - 1; i > 0; i--) {
            int j = rng.nextInt(i + 1);
            int t = pool.get(i);
            pool.set(i, pool.get(j));
            pool.set(j, t);
        }
        for (int i = 0; i < shelves.size(); i++) symbolOf.add(pool.get(i % pool.size()));
        int books = Math.max(1, Math.min(shelves.size(), params.integer("books", 3)));
        while (answers.size() < books) answers.add(rng.nextInt(shelves.size()));
        StringBuilder sb = new StringBuilder("<yellow><b>수수께끼</b></yellow>");
        int line = 0;
        for (int a : answers) {
            line++;
            sb.append("\n<gray>").append(line).append(". ");
            if (line == answers.size() && answers.size() >= 2) {
                int[] s = shelves.get(a);
                sb.append("<white>").append(WALL_NAME[s[2]]).append(" 벽</white>, 왼쪽에서 <white>").append(s[3]).append("번째</white> 책장");
            } else {
                sb.append("「<white>").append(SYMBOLS[symbolOf.get(a)][2]).append("</white>」의 표식");
            }
        }
        riddle = fs.text(fs.tile(info.centerX(), info.centerZ(), 2.7), sb.toString());
        for (int i = 0; i < shelves.size(); i++) {
            int[] s = shelves.get(i);
            int ix = s[0] + (s[2] == 1 ? -1 : s[2] == 3 ? 1 : 0), iz = s[1] + (s[2] == 0 ? 1 : s[2] == 2 ? -1 : 0);
            labels.add(fs.text(fs.tile(s[0] * 0.6 + ix * 0.4, s[1] * 0.6 + iz * 0.4, 3.4), "<gold>" + SYMBOLS[symbolOf.get(i)][0]));
        }
    }

    @Override
    protected void update(long t) {
        if (t % 10 == 0) {
            for (int i : found) {
                int[] s = shelves.get(i);
                fs.world().spawnParticle(Particle.ENCHANT, fs.tile(s[0], s[1], 2.5), 6, 0.3, 0.4, 0.3, 0.4);
            }
        }
    }

    @Override
    protected String status() { return "찾은 책 " + found.size() + "/" + answers.size() + " · 기회 " + attempts; }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        Material m = block.getType();
        if (m == Material.LECTERN) return true;
        if (m != Material.BOOKSHELF && m != Material.CHISELED_BOOKSHELF) return false;
        int bx = block.getX() - fs.ox(), bz = block.getZ() - fs.oz();
        for (int i = 0; i < shelves.size(); i++) {
            int[] s = shelves.get(i);
            if (s[0] != bx || s[1] != bz) continue;
            if (!running || action != Action.RIGHT_CLICK_BLOCK) return true;
            Location at = fs.tile(s[0], s[1], 2.0);
            if (found.contains(i)) {
                Text.send(p, "<gray>이미 찾은 책장입니다.");
                return true;
            }
            if (answers.contains(i)) {
                found.add(i);
                labels.get(i).text(Text.mm("<green><b>" + SYMBOLS[symbolOf.get(i)][0] + " ✔</b>"));
                fs.sound(at, Sound.ITEM_BOOK_PAGE_TURN, 1.0f, 1.2f);
                fs.sound(at, Sound.BLOCK_ENCHANTMENT_TABLE_USE, 0.8f, 1.4f);
                fs.world().spawnParticle(Particle.ENCHANT, at, 40, 0.4, 0.6, 0.4, 0.8);
                if (found.size() >= answers.size()) succeed();
                return true;
            }
            attempts--;
            noteMistake();
            labels.get(i).text(Text.mm("<dark_gray>" + SYMBOLS[symbolOf.get(i)][0] + " ✘"));
            fs.sound(at, Sound.ENTITY_GHAST_SCREAM, 0.5f, 1.4f);
            failSpawn();
            if (attempts <= 0) {
                fail("먹물이 서고를 덮었습니다");
                return true;
            }
            fs.actionBar(fs.allPlayers(), "<red>먹물이 번진다!</red> <gray>원령이 깨어난다 — 남은 기회 " + attempts, 50);
            return true;
        }
        return false;
    }

    @Override
    protected void cleanup() {
        for (TextDisplay d : labels) fs.untrack(d);
        labels.clear();
        if (riddle != null) fs.untrack(riddle);
        riddle = null;
    }
}
