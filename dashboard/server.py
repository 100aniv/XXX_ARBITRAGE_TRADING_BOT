#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Web Dashboard (PHASE D15)
===================================

FastAPI + WebSocket 기반 실시간 대시보드.

특징:
- 실시간 메트릭 스트리밍
- WebSocket 엔드포인트
- Grafana 호환성
- 프로덕션 급 설계
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# FastAPI 선택적 임포트
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    logger.warning("[Dashboard] FastAPI not installed, dashboard disabled")


class DashboardServer:
    """대시보드 서버"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        """
        Args:
            host: 바인드 호스트
            port: 바인드 포트
        """
        self.host = host
        self.port = port
        self.app: Optional[FastAPI] = None
        self.metrics_data: Dict[str, Any] = {}
        self.connected_clients: List[WebSocket] = []
        
        if HAS_FASTAPI:
            self._setup_app()
    
    def _setup_app(self) -> None:
        """FastAPI 앱 설정"""
        self.app = FastAPI(title="arbitrage-lite Dashboard")
        
        # CORS 설정
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 라우트 설정
        @self.app.get("/health")
        async def health():
            return {"status": "ok"}
        
        @self.app.get("/metrics/live")
        async def get_metrics():
            """현재 메트릭 조회"""
            return JSONResponse(self.metrics_data)
        
        @self.app.get("/risk/summary")
        async def get_risk_summary():
            """리스크 요약"""
            return JSONResponse({
                'var_95': self.metrics_data.get('var_95', 0.0),
                'var_99': self.metrics_data.get('var_99', 0.0),
                'expected_shortfall': self.metrics_data.get('expected_shortfall', 0.0),
                'max_drawdown': self.metrics_data.get('max_drawdown', 0.0),
                'sharpe_ratio': self.metrics_data.get('sharpe_ratio', 0.0)
            })
        
        @self.app.get("/logs/events")
        async def get_events():
            """이벤트 로그"""
            return JSONResponse({
                'events': self.metrics_data.get('events', []),
                'total_events': len(self.metrics_data.get('events', []))
            })
        
        @self.app.websocket("/ws/metrics")
        async def websocket_metrics(websocket: WebSocket):
            """메트릭 WebSocket"""
            await websocket.accept()
            self.connected_clients.append(websocket)
            
            try:
                while True:
                    # 클라이언트로부터 메시지 수신 (ping/pong)
                    data = await websocket.receive_text()
                    
                    # 메트릭 데이터 전송
                    await websocket.send_json(self.metrics_data)
            
            except WebSocketDisconnect:
                self.connected_clients.remove(websocket)
            except Exception as e:
                logger.error(f"[Dashboard] WebSocket error: {e}")
                if websocket in self.connected_clients:
                    self.connected_clients.remove(websocket)
    
    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        메트릭 업데이트
        
        Args:
            metrics: 메트릭 딕셔너리
        """
        self.metrics_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **metrics
        }
    
    async def broadcast_metrics(self) -> None:
        """모든 연결된 클라이언트에 메트릭 브로드캐스트"""
        if not self.connected_clients:
            return
        
        disconnected = []
        for client in self.connected_clients:
            try:
                await client.send_json(self.metrics_data)
            except Exception as e:
                logger.error(f"[Dashboard] Broadcast error: {e}")
                disconnected.append(client)
        
        # 연결 끊긴 클라이언트 제거
        for client in disconnected:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
    
    def start(self) -> None:
        """대시보드 서버 시작"""
        if not HAS_FASTAPI or self.app is None:
            logger.warning("[Dashboard] FastAPI not available, skipping dashboard")
            return
        
        logger.info(f"[Dashboard] Starting server on {self.host}:{self.port}")
        
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
        except Exception as e:
            logger.error(f"[Dashboard] Failed to start server: {e}")


# 글로벌 대시보드 인스턴스
_dashboard_server: Optional[DashboardServer] = None


def init_dashboard(host: str = "0.0.0.0", port: int = 8001) -> DashboardServer:
    """
    대시보드 초기화
    
    Args:
        host: 바인드 호스트
        port: 바인드 포트
    
    Returns:
        DashboardServer 인스턴스
    """
    global _dashboard_server
    _dashboard_server = DashboardServer(host, port)
    return _dashboard_server


def get_dashboard() -> Optional[DashboardServer]:
    """대시보드 조회"""
    return _dashboard_server
