#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-Performance Machine Learning Based Volatility Model (PHASE D15)
====================================================================

LSTM 기반 변동성 예측 모델 (고성능 버전).

특징:
- PyTorch LSTM 신경망 (GPU 지원)
- NumPy 벡터화 연산
- 배치 처리 최적화
- 모델 저장/로드 지원
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

logger = logging.getLogger(__name__)


class VolatilityLSTM(nn.Module):
    """
    LSTM 기반 변동성 예측 신경망
    
    입력: (batch_size, seq_length, 1)
    출력: (batch_size, 1)
    """
    
    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        output_size: int = 1,
        dropout: float = 0.2
    ):
        """
        Args:
            input_size: 입력 특성 수 (기본값: 1)
            hidden_size: LSTM 숨겨진 상태 크기
            num_layers: LSTM 레이어 수
            output_size: 출력 크기 (기본값: 1)
            dropout: 드롭아웃 비율
        """
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_size = output_size
        
        # LSTM 레이어
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True
        )
        
        # 완전 연결 레이어 (FC)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, output_size),
            nn.Sigmoid()  # 변동성은 [0, 1] 범위
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        순전파
        
        Args:
            x: (batch_size, seq_length, input_size)
        
        Returns:
            (batch_size, output_size)
        """
        # LSTM 순전파
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # 마지막 시간 스텝의 출력만 사용
        last_output = lstm_out[:, -1, :]  # (batch_size, hidden_size)
        
        # 완전 연결 레이어
        output = self.fc(last_output)  # (batch_size, output_size)
        
        return output


class VolatilityPredictor:
    """
    고성능 변동성 예측기
    
    NumPy 벡터화 연산과 PyTorch GPU 지원을 활용한 변동성 예측.
    """
    
    def __init__(
        self,
        model_path: str = "models/volatility_lstm.pt",
        sequence_length: int = 20,
        device: Optional[str] = None
    ):
        """
        Args:
            model_path: 모델 저장 경로
            sequence_length: 입력 시퀀스 길이
            device: 실행 디바이스 ('cpu', 'cuda', None=자동 선택)
        """
        self.model_path = Path(model_path)
        self.sequence_length = sequence_length
        
        # 디바이스 자동 선택
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        logger.info(f"[VolatilityPredictor] Using device: {self.device}")
        
        # 모델 초기화
        self.model: Optional[VolatilityLSTM] = None
        self._load_or_create_model()
        
        # 변동성 히스토리 (NumPy 배열로 관리)
        self.volatility_history = np.array([], dtype=np.float32)
        self.max_history = 1000
    
    def _load_or_create_model(self) -> None:
        """모델 로드 또는 새로 생성"""
        try:
            if self.model_path.exists():
                # 기존 모델 로드
                self.model = VolatilityLSTM()
                state_dict = torch.load(self.model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info(f"[VolatilityPredictor] Model loaded from {self.model_path}")
            else:
                # 새 모델 생성
                self.model = VolatilityLSTM()
                logger.info("[VolatilityPredictor] New model created")
            
            # 모델을 디바이스로 이동
            self.model.to(self.device)
            self.model.eval()
        
        except Exception as e:
            logger.error(f"[VolatilityPredictor] Model initialization failed: {e}")
            self.model = VolatilityLSTM().to(self.device)
            self.model.eval()
    
    def record_volatility(self, volatility: float) -> None:
        """
        변동성 기록 (벡터화)
        
        Args:
            volatility: 변동성 값
        """
        # NumPy 배열에 추가
        self.volatility_history = np.append(self.volatility_history, volatility)
        
        # 히스토리 크기 제한
        if len(self.volatility_history) > self.max_history:
            self.volatility_history = self.volatility_history[-self.max_history:]
    
    def record_volatilities_batch(self, volatilities: np.ndarray) -> None:
        """
        배치 변동성 기록 (벡터화)
        
        Args:
            volatilities: (N,) 형태의 변동성 배열
        """
        volatilities = np.asarray(volatilities, dtype=np.float32)
        self.volatility_history = np.append(self.volatility_history, volatilities)
        
        if len(self.volatility_history) > self.max_history:
            self.volatility_history = self.volatility_history[-self.max_history:]
    
    def predict(self) -> float:
        """
        다음 변동성 예측
        
        Returns:
            예측된 변동성 (0.0~1.0)
        """
        if len(self.volatility_history) < self.sequence_length:
            # 데이터 부족하면 현재 변동성 반환
            if len(self.volatility_history) > 0:
                return float(self.volatility_history[-1])
            return 0.5
        
        try:
            # 최근 sequence_length개 데이터 추출 (벡터화)
            recent_vol = self.volatility_history[-self.sequence_length:]
            
            # (1, seq_length, 1) 형태로 변환
            x = torch.FloatTensor(recent_vol).reshape(1, -1, 1).to(self.device)
            
            # 예측
            with torch.no_grad():
                pred = self.model(x)
                pred_value = pred.item()
            
            # 범위 클리핑
            return float(np.clip(pred_value, 0.0, 1.0))
        
        except Exception as e:
            logger.error(f"[VolatilityPredictor] Prediction failed: {e}")
            if len(self.volatility_history) > 0:
                return float(self.volatility_history[-1])
            return 0.5
    
    def predict_batch(self, num_predictions: int = 5) -> np.ndarray:
        """
        배치 예측 (벡터화)
        
        Args:
            num_predictions: 예측 개수
        
        Returns:
            (num_predictions,) 형태의 예측 배열
        """
        predictions = []
        
        for _ in range(num_predictions):
            pred = self.predict()
            predictions.append(pred)
            # 예측값을 히스토리에 추가 (다음 예측을 위해)
            self.record_volatility(pred)
        
        return np.array(predictions, dtype=np.float32)
    
    def save_model(self) -> None:
        """모델 저장"""
        if self.model is None:
            return
        
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(self.model.state_dict(), self.model_path)
            logger.info(f"[VolatilityPredictor] Model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"[VolatilityPredictor] Failed to save model: {e}")
    
    def get_stats(self) -> dict:
        """
        통계 반환 (벡터화)
        
        Returns:
            통계 딕셔너리
        """
        if len(self.volatility_history) == 0:
            return {
                'history_length': 0,
                'current_volatility': 0.0,
                'mean_volatility': 0.0,
                'std_volatility': 0.0,
                'min_volatility': 0.0,
                'max_volatility': 0.0
            }
        
        # NumPy 벡터화 연산
        return {
            'history_length': len(self.volatility_history),
            'current_volatility': float(self.volatility_history[-1]),
            'mean_volatility': float(np.mean(self.volatility_history)),
            'std_volatility': float(np.std(self.volatility_history)),
            'min_volatility': float(np.min(self.volatility_history)),
            'max_volatility': float(np.max(self.volatility_history))
        }
    
    def train_mode(self) -> None:
        """학습 모드 활성화"""
        if self.model is not None:
            self.model.train()
    
    def eval_mode(self) -> None:
        """평가 모드 활성화"""
        if self.model is not None:
            self.model.eval()
