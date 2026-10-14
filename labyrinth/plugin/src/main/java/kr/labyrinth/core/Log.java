package kr.labyrinth.core;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.logging.Logger;

/** 플러그인 로거 정적 접근 + "아직 구현 안 됨" 1회 경고. 테스트에서는 기본 JUL 로거를 쓴다. */
public final class Log {

    private static volatile Logger logger = Logger.getLogger("Labyrinth");
    private static final Set<String> WARNED = ConcurrentHashMap.newKeySet();

    private Log() {}

    public static void init(Logger l) {
        logger = l;
        WARNED.clear();
    }

    public static Logger get() { return logger; }

    public static void info(String msg) { logger.info(msg); }

    public static void warn(String msg) { logger.warning(msg); }

    public static void error(String msg, Throwable t) { logger.log(Level.SEVERE, msg, t); }

    /** 같은 key 로는 한 번만 경고한다 (기본 구현이 불렸을 때). */
    public static void notImplemented(String key) {
        if (WARNED.add(key)) {
            logger.warning("[미구현] " + key + " — 아직 구현되지 않은 기능이 호출됨(기본 동작으로 대체)");
        }
    }

    public static void warnOnce(String key, String msg) {
        if (WARNED.add(key)) logger.warning(msg);
    }
}
