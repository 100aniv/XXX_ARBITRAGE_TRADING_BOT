"""
D68 - Parameter Tuning Test Harness
전략 파라미터 자동 튜닝 실행 스크립트
"""

import sys
import os
import logging
import argparse
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tuning.parameter_tuner import ParameterTuner, TuningConfig, TuningResult

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_d68_report(
    config: TuningConfig,
    results: list[TuningResult],
    top_n: int = 5
) -> str:
    """
    D68_REPORT.md 자동 생성
    
    Args:
        config: 튜닝 설정
        results: 모든 결과
        top_n: 상위 N개 결과 표시
    
    Returns:
        리포트 마크다운 문자열
    """
    if not results:
        return "# D68 Report\n\nNo results available."
    
    # 상위 결과 추출 (PnL 기준)
    sorted_results = sorted(results, key=lambda r: r.total_pnl, reverse=True)
    top_results = sorted_results[:top_n]
    
    # 평균 메트릭 계산
    valid_results = [r for r in results if r.total_exits > 0 and not r.error_message]
    if valid_results:
        avg_pnl = sum(r.total_pnl for r in valid_results) / len(valid_results)
        avg_winrate = sum(r.winrate for r in valid_results) / len(valid_results)
        avg_trades = sum(r.total_exits for r in valid_results) / len(valid_results)
    else:
        avg_pnl = avg_winrate = avg_trades = 0.0
    
    # 리포트 생성
    report = f"""# D68 – PARAMETER_TUNING REPORT

## 📊 실행 정보

- **Session ID:** {config.session_id}
- **실행 시각:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **튜닝 모드:** {config.mode}
- **캠페인 패턴:** {config.campaign_id}
- **테스트 모드:** {config.test_mode}
- **테스트 시간:** {config.duration_seconds}초 ({config.duration_seconds // 60}분)
- **심볼:** {', '.join(config.symbols)}

## 🎯 튜닝 파라미터 범위

"""
    
    # 파라미터 범위 표시
    for param_name, param_values in config.param_ranges.items():
        report += f"- **{param_name}:** {param_values}\n"
    
    report += f"\n## 📈 전체 결과 요약\n\n"
    report += f"- **총 테스트 수:** {len(results)}\n"
    report += f"- **성공 테스트 수:** {len(valid_results)}\n"
    report += f"- **실패 테스트 수:** {len(results) - len(valid_results)}\n\n"
    
    report += f"**평균 메트릭:**\n"
    report += f"- 평균 PnL: ${avg_pnl:.2f}\n"
    report += f"- 평균 Winrate: {avg_winrate:.1f}%\n"
    report += f"- 평균 거래 수: {avg_trades:.1f}\n\n"
    
    report += f"## 🏆 상위 {top_n}개 파라미터 조합\n\n"
    report += "| Rank | PnL | Winrate | Trades | Parameters |\n"
    report += "|------|-----|---------|--------|-----------|\n"
    
    for idx, result in enumerate(top_results, start=1):
        params_str = ', '.join([f"{k}={v}" for k, v in result.param_set.items()])
        report += (
            f"| {idx} | ${result.total_pnl:.2f} | {result.winrate:.1f}% | "
            f"{result.total_exits} | {params_str} |\n"
        )
    
    # 최고 성능 파라미터 상세
    best = top_results[0]
    report += f"\n## 🎖️ 최고 성능 파라미터 조합\n\n"
    report += f"```json\n"
    report += "{\n"
    for k, v in best.param_set.items():
        report += f'  "{k}": {v},\n'
    report = report.rstrip(',\n') + '\n'
    report += "}\n```\n\n"
    
    report += f"**성능:**\n"
    report += f"- Total PnL: ${best.total_pnl:.2f}\n"
    report += f"- Winrate: {best.winrate:.1f}%\n"
    report += f"- Total Trades: {best.total_exits}\n"
    report += f"- Avg PnL/Trade: ${best.avg_pnl_per_trade:.2f}\n\n"
    
    # 분석 및 인사이트
    report += "## 🔍 분석 및 인사이트\n\n"
    
    # min_spread_bps 분석 (예시)
    if 'min_spread_bps' in config.param_ranges:
        report += "### min_spread_bps 영향\n\n"
        spread_analysis = {}
        for result in valid_results:
            spread_val = result.param_set.get('min_spread_bps')
            if spread_val not in spread_analysis:
                spread_analysis[spread_val] = []
            spread_analysis[spread_val].append(result.total_pnl)
        
        report += "| min_spread_bps | 평균 PnL | 샘플 수 |\n"
        report += "|----------------|----------|--------|\n"
        for spread in sorted(spread_analysis.keys()):
            pnls = spread_analysis[spread]
            avg = sum(pnls) / len(pnls)
            report += f"| {spread} | ${avg:.2f} | {len(pnls)} |\n"
        report += "\n"
    
    # 한계점 및 다음 단계
    report += "## ⚠️ 한계점\n\n"
    report += "- 짧은 테스트 시간 (2분)으로 인해 통계적 유의성 제한\n"
    report += "- 백테스트가 아닌 Paper 모드로 실행되어 합성 데이터 기반\n"
    report += "- MaxDD, Sharpe Ratio 등 고급 메트릭 미구현\n"
    report += "- 단일 캠페인 패턴만 테스트 (다양한 시장 상황 미반영)\n\n"
    
    report += "## 🚀 다음 단계 (D69+)\n\n"
    report += "- **D69 - ROBUSTNESS_TEST:** 극단 상황 및 스트레스 테스트\n"
    report += "- 장시간 백테스트 (실제 시장 데이터)\n"
    report += "- 멀티심볼 포트폴리오 튜닝\n"
    report += "- 베이지안 최적화 등 고급 튜닝 알고리즘 적용\n"
    report += "- 리스크 조정 수익률 (Sharpe, Sortino) 최적화\n\n"
    
    report += "---\n\n"
    report += f"**D68 – PARAMETER_TUNING: ✅ COMPLETED**\n"
    
    return report


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='D68 Parameter Tuning Test')
    parser.add_argument('--mode', choices=['grid', 'random'], default='grid',
                        help='Tuning mode (grid or random)')
    parser.add_argument('--campaign', default='C1',
                        help='Campaign ID (C1/C2/C3)')
    parser.add_argument('--duration', type=int, default=120,
                        help='Test duration in seconds (default: 120)')
    parser.add_argument('--db-host', default='localhost',
                        help='PostgreSQL host')
    parser.add_argument('--db-name', default='arbitrage_db',
                        help='PostgreSQL database name')
    parser.add_argument('--db-user', default='postgres',
                        help='PostgreSQL user')
    parser.add_argument('--db-password', default='password',
                        help='PostgreSQL password')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("[D68_TUNING] D68 Parameter Tuning Test Starting")
    logger.info("="*80)
    
    # 튜닝 파라미터 범위 정의
    # 실제 운영 시에는 더 넓은 범위와 세밀한 간격 사용
    param_ranges = {
        'min_spread_bps': [20.0, 30.0, 40.0],  # 최소 스프레드
        'slippage_bps': [3.0, 5.0, 10.0],      # 슬리피지
        'max_position_usd': [800.0, 1000.0, 1200.0]  # 최대 포지션 크기
    }
    
    # 튜닝 설정
    tuning_config = TuningConfig(
        param_ranges=param_ranges,
        mode=args.mode,
        random_samples=10 if args.mode == 'random' else 0,
        test_mode='paper',
        campaign_id=args.campaign,
        duration_seconds=args.duration,
        symbols=['BTCUSDT'],
        db_host=args.db_host,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        notes=f'D68 {args.mode} tuning test - {args.campaign}'
    )
    
    logger.info(f"[D68_TUNING] Tuning mode: {tuning_config.mode}")
    logger.info(f"[D68_TUNING] Campaign: {tuning_config.campaign_id}")
    logger.info(f"[D68_TUNING] Duration: {tuning_config.duration_seconds}s")
    logger.info(f"[D68_TUNING] Parameter ranges:")
    for param, values in param_ranges.items():
        logger.info(f"  - {param}: {values}")
    
    # 예상 조합 수 계산
    if tuning_config.mode == 'grid':
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        logger.info(f"[D68_TUNING] Total combinations: {total_combinations}")
        logger.info(
            f"[D68_TUNING] Estimated total time: "
            f"{total_combinations * tuning_config.duration_seconds // 60} minutes"
        )
    
    # 튜너 초기화 및 실행
    tuner = ParameterTuner(tuning_config)
    
    try:
        # 튜닝 실행
        results = tuner.run_tuning()
        
        # 상위 결과 출력
        logger.info("="*80)
        logger.info("[D68_TUNING] Top 5 Results:")
        logger.info("="*80)
        
        top_results = tuner.get_top_results(n=5, sort_by='total_pnl')
        for idx, result in enumerate(top_results, start=1):
            logger.info(
                f"[D68_TUNING] #{idx}: PnL=${result.total_pnl:.2f}, "
                f"Winrate={result.winrate:.1f}%, Trades={result.total_exits}, "
                f"Params={result.param_set}"
            )
        
        # 리포트 생성
        logger.info("="*80)
        logger.info("[D68_TUNING] Generating D68_REPORT.md...")
        logger.info("="*80)
        
        report_content = generate_d68_report(tuning_config, results, top_n=5)
        
        # 리포트 저장
        report_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'docs',
            'D68_REPORT.md'
        )
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"[D68_TUNING] Report saved to: {report_path}")
        
        # Acceptance Criteria 검증
        logger.info("="*80)
        logger.info("[D68_TUNING] Acceptance Criteria Check:")
        logger.info("="*80)
        
        acceptance_passed = True
        
        # 1. 튜닝 파라미터 조합 ≥ 3개 실행 성공
        valid_results = [r for r in results if not r.error_message and r.total_exits > 0]
        check1 = len(valid_results) >= 3
        logger.info(f"[D68_TUNING]   ✓ Valid results >= 3: {'PASS' if check1 else 'FAIL'} ({len(valid_results)})")
        acceptance_passed &= check1
        
        # 2. PostgreSQL 저장 확인
        check2 = all(r.run_id is not None for r in valid_results)
        logger.info(f"[D68_TUNING]   ✓ All results saved to DB: {'PASS' if check2 else 'FAIL'}")
        acceptance_passed &= check2
        
        # 3. 크래시 없음
        check3 = len([r for r in results if r.error_message]) == 0
        logger.info(f"[D68_TUNING]   ✓ No errors/crashes: {'PASS' if check3 else 'FAIL'}")
        acceptance_passed &= check3
        
        # 4. Top-N 정렬 가능
        check4 = len(top_results) > 0
        logger.info(f"[D68_TUNING]   ✓ Top-N sorting available: {'PASS' if check4 else 'FAIL'}")
        acceptance_passed &= check4
        
        # 5. D68_REPORT.md 생성
        check5 = os.path.exists(report_path)
        logger.info(f"[D68_TUNING]   ✓ D68_REPORT.md generated: {'PASS' if check5 else 'FAIL'}")
        acceptance_passed &= check5
        
        # 최종 판정
        logger.info("="*80)
        if acceptance_passed:
            logger.info("[D68_TUNING] ✅ D68_ACCEPTED: All acceptance criteria passed!")
        else:
            logger.error("[D68_TUNING] ❌ D68_FAILED: Some acceptance criteria failed")
        logger.info("="*80)
        
        return 0 if acceptance_passed else 1
        
    except Exception as e:
        logger.error(f"[D68_TUNING] Tuning failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
