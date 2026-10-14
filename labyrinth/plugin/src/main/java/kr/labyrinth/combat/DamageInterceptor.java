package kr.labyrinth.combat;

/**
 * 피해 적용 직전 가로채기 (보호막·방어 자세·무적·자동 부활 등). {@link DamageService#addInterceptor} 로 등록.
 * 회피되지 않은 피해의 최종값(방어·감소 적용 후)을 받아 바꾼 값을 돌려준다. 0 = 완전히 막음(피해 숫자 "막음").
 * 메인 스레드에서 등록 순서대로 호출된다. 예외는 DamageService 가 잡아 로그만 남긴다.
 */
@FunctionalInterface
public interface DamageInterceptor {
    double intercept(DamageContext ctx, double damage);
}
