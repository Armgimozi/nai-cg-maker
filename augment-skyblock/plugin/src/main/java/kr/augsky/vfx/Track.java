package kr.augsky.vfx;

import org.bukkit.Location;
import org.bukkit.util.Vector;

/** 움직이는 스킬(투사체·돌진·낙하·장판...)에 매 틱 붙는 연출 손잡이. 기술 쪽은 위치만 알려 준다 */
public interface Track {
    default void tick(Location pos, Vector vel) {}

    /** 궤도 칼날처럼 여러 점이 도는 기술: i 번째 점의 이번 틱 위치 */
    default void point(int i, Location p) {}

    default void end(Location at, boolean impact) {}

    Track NOOP = new Track() {};

    static Track both(Track a, Track b) {
        if (a == null || a == NOOP) return b == null ? NOOP : b;
        if (b == null || b == NOOP) return a;
        return new Track() {
            @Override
            public void tick(Location pos, Vector vel) {
                a.tick(pos, vel);
                b.tick(pos, vel);
            }

            @Override
            public void point(int i, Location p) {
                a.point(i, p);
                b.point(i, p);
            }

            @Override
            public void end(Location at, boolean impact) {
                a.end(at, impact);
                b.end(at, impact);
            }
        };
    }
}
