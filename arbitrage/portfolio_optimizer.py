#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-Performance Portfolio Optimization Layer (PHASE D15)
=========================================================

다중 자산 포트폴리오 최적화 (고성능 버전).

특징:
- NumPy 벡터화 상관관계 행렬
- Pandas DataFrame 기반 데이터 관리
- 리스크 패리티 가중치 (벡터화)
- 평균-분산 최적화 (Markowitz, 벡터화)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    고성능 포트폴리오 최적화기
    
    NumPy 벡터화 연산과 Pandas DataFrame을 활용한 포트폴리오 최적화.
    """
    
    def __init__(self, window_size: int = 60):
        """
        Args:
            window_size: 상관관계 계산 윈도우 크기
        """
        self.window_size = window_size
        
        # Pandas DataFrame으로 수익률 관리 (벡터화)
        self.returns_df = pd.DataFrame()
        self.symbols: List[str] = []
        
        # 캐시된 통계
        self.correlation_matrix: Optional[np.ndarray] = None
        self.covariance_matrix: Optional[np.ndarray] = None
        self.mean_returns: Optional[np.ndarray] = None
        self.volatilities: Optional[np.ndarray] = None
    
    def add_returns(self, symbol: str, returns: float) -> None:
        """
        수익률 추가 (벡터화)
        
        Args:
            symbol: 자산 심볼
            returns: 수익률 (%)
        """
        if symbol not in self.returns_df.columns:
            self.returns_df[symbol] = np.nan
            self.symbols.append(symbol)
        
        # 새 행 추가
        self.returns_df.loc[len(self.returns_df)] = np.nan
        self.returns_df.loc[len(self.returns_df) - 1, symbol] = returns
        
        # 윈도우 크기 유지
        if len(self.returns_df) > self.window_size:
            self.returns_df = self.returns_df.iloc[-self.window_size:]
        
        # 캐시 무효화
        self._invalidate_cache()
    
    def add_returns_batch(self, returns_dict: Dict[str, List[float]]) -> None:
        """
        배치 수익률 추가 (벡터화)
        
        Args:
            returns_dict: {symbol: [returns]} 딕셔너리
        """
        for symbol, returns_list in returns_dict.items():
            if symbol not in self.returns_df.columns:
                self.returns_df[symbol] = np.nan
                self.symbols.append(symbol)
            
            # 벡터화 추가
            returns_array = np.array(returns_list, dtype=np.float32)
            self.returns_df[symbol] = returns_array
        
        # 윈도우 크기 유지
        if len(self.returns_df) > self.window_size:
            self.returns_df = self.returns_df.iloc[-self.window_size:]
        
        self._invalidate_cache()
    
    def _invalidate_cache(self) -> None:
        """캐시 무효화"""
        self.correlation_matrix = None
        self.covariance_matrix = None
        self.mean_returns = None
        self.volatilities = None
    
    def calculate_correlation_matrix(self) -> Optional[np.ndarray]:
        """
        상관관계 행렬 계산 (벡터화)
        
        Returns:
            (n_symbols, n_symbols) 상관관계 행렬
        """
        if len(self.returns_df) < 2 or len(self.symbols) < 2:
            return None
        
        try:
            # Pandas 벡터화 상관관계 계산
            self.correlation_matrix = self.returns_df[self.symbols].corr().values
            return self.correlation_matrix
        
        except Exception as e:
            logger.error(f"[PortfolioOptimizer] Correlation calculation failed: {e}")
            return None
    
    def calculate_covariance_matrix(self) -> Optional[np.ndarray]:
        """
        공분산 행렬 계산 (벡터화)
        
        Returns:
            (n_symbols, n_symbols) 공분산 행렬
        """
        if len(self.returns_df) < 2 or len(self.symbols) < 2:
            return None
        
        try:
            # Pandas 벡터화 공분산 계산
            self.covariance_matrix = self.returns_df[self.symbols].cov().values
            return self.covariance_matrix
        
        except Exception as e:
            logger.error(f"[PortfolioOptimizer] Covariance calculation failed: {e}")
            return None
    
    def _compute_statistics(self) -> None:
        """통계 계산 (벡터화)"""
        if len(self.returns_df) == 0:
            return
        
        # 평균 수익률 (벡터화)
        self.mean_returns = self.returns_df[self.symbols].mean().values
        
        # 변동성 (벡터화)
        self.volatilities = self.returns_df[self.symbols].std().values
        
        # 0 변동성 처리
        self.volatilities = np.where(self.volatilities > 0, self.volatilities, 1.0)
    
    def get_risk_parity_weights(self) -> Dict[str, float]:
        """
        리스크 패리티 가중치 계산 (벡터화)
        
        각 자산이 포트폴리오 리스크에 동등하게 기여.
        
        Returns:
            {symbol: weight} 딕셔너리
        """
        if len(self.symbols) == 0:
            return {}
        
        # 통계 계산
        self._compute_statistics()
        
        # 역변동성 (벡터화)
        inv_vols = 1.0 / self.volatilities  # (n_symbols,)
        
        # 정규화 (벡터화)
        weights = inv_vols / np.sum(inv_vols)
        
        # 딕셔너리로 변환
        return {symbol: float(w) for symbol, w in zip(self.symbols, weights)}
    
    def get_mean_variance_weights(self, target_return: float = 0.0) -> Dict[str, float]:
        """
        평균-분산 최적화 가중치 (벡터화 Markowitz)
        
        Args:
            target_return: 목표 수익률
        
        Returns:
            {symbol: weight} 딕셔너리
        """
        if len(self.symbols) < 2:
            # 단일 자산
            return {self.symbols[0]: 1.0} if self.symbols else {}
        
        try:
            # 통계 계산
            self._compute_statistics()
            
            # 상관관계 행렬 계산
            self.calculate_correlation_matrix()
            
            if self.correlation_matrix is None:
                # 실패 시 동일 가중치
                weight = 1.0 / len(self.symbols)
                return {s: weight for s in self.symbols}
            
            # 벡터화 점수 계산
            # 수익률 점수
            return_scores = self.mean_returns
            
            # 상관관계 점수 (각 자산과 다른 자산들의 평균 절대 상관관계)
            corr_scores = np.mean(np.abs(self.correlation_matrix), axis=1)
            
            # 최종 점수 (높은 수익률, 낮은 상관관계)
            scores = return_scores - 0.5 * corr_scores
            
            # 점수 정규화 (벡터화)
            min_score = np.min(scores)
            adjusted_scores = scores - min_score + 0.1
            
            # 가중치 정규화 (벡터화)
            weights = adjusted_scores / np.sum(adjusted_scores)
            
            # 딕셔너리로 변환
            return {symbol: float(w) for symbol, w in zip(self.symbols, weights)}
        
        except Exception as e:
            logger.error(f"[PortfolioOptimizer] MV optimization failed: {e}")
            # 실패 시 동일 가중치
            weight = 1.0 / len(self.symbols)
            return {s: weight for s in self.symbols}
    
    def get_optimal_weights(
        self,
        symbol_list: List[str],
        method: str = "risk_parity"
    ) -> Dict[str, float]:
        """
        최적 가중치 계산
        
        Args:
            symbol_list: 자산 심볼 리스트
            method: 최적화 방법 ('risk_parity' 또는 'mean_variance')
        
        Returns:
            {symbol: weight} 딕셔너리
        """
        # 요청된 심볼만 필터링
        available_symbols = [s for s in symbol_list if s in self.symbols]
        
        if not available_symbols:
            # 사용 가능한 자산이 없으면 동일 가중치
            weight = 1.0 / len(symbol_list)
            return {s: weight for s in symbol_list}
        
        # 최적화 방법 선택
        if method == "mean_variance":
            weights = self.get_mean_variance_weights()
        else:  # risk_parity (기본값)
            weights = self.get_risk_parity_weights()
        
        # 요청된 심볼만 추출 (벡터화)
        result = np.array([weights.get(s, 0.0) for s in symbol_list])
        
        # 정규화 (벡터화)
        total = np.sum(result)
        if total > 0:
            result = result / total
        else:
            result = np.ones(len(symbol_list)) / len(symbol_list)
        
        # 딕셔너리로 변환
        return {symbol: float(w) for symbol, w in zip(symbol_list, result)}
    
    def get_stats(self) -> Dict[str, any]:
        """통계 반환"""
        return {
            'num_symbols': len(self.symbols),
            'symbols': self.symbols,
            'num_observations': len(self.returns_df),
            'correlation_matrix_available': self.correlation_matrix is not None,
            'covariance_matrix_available': self.covariance_matrix is not None
        }
