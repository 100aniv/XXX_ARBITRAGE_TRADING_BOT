#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — FastAPI Backend
===================================

실시간 거래 상태 조회 API:
- /health: 헬스 체크
- /metrics/live: 실시간 메트릭
- /positions: 포지션 조회
- /signals: 신호 조회
- /orders: 주문 조회
- /executions: 실행 결과 조회
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import JSONResponse
import asyncio
import json

from arbitrage.state_manager import StateManager

logger = logging.getLogger(__name__)

app = FastAPI(title="Arbitrage Live Trading API")

# 상태 관리자
state_manager: Optional[StateManager] = None


@app.on_event("startup")
async def startup():
    """앱 시작"""
    global state_manager
    state_manager = StateManager()
    state_manager.connect()
    logger.info("API server started")


@app.on_event("shutdown")
async def shutdown():
    """앱 종료"""
    if state_manager:
        state_manager.disconnect()
    logger.info("API server stopped")


# ========== 헬스 체크 ==========

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    헬스 체크
    
    Returns:
        상태 정보
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


# ========== 메트릭 ==========

@app.get("/metrics/live")
async def get_live_metrics() -> Dict[str, Any]:
    """
    실시간 메트릭 조회
    
    Returns:
        메트릭 정보
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        metrics = state_manager.get_metrics()
        portfolio = state_manager.get_portfolio_state()
        
        return {
            "metrics": metrics,
            "portfolio": portfolio,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 포지션 ==========

@app.get("/positions")
async def get_positions() -> Dict[str, Any]:
    """
    모든 포지션 조회
    
    Returns:
        포지션 목록
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        positions = state_manager.get_all_positions()
        
        return {
            "positions": positions,
            "count": len(positions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions/{symbol}")
async def get_position(symbol: str) -> Dict[str, Any]:
    """
    특정 심볼 포지션 조회
    
    Args:
        symbol: 심볼
    
    Returns:
        포지션 정보
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        position = state_manager.get_position(symbol)
        
        if not position:
            raise HTTPException(status_code=404, detail=f"Position not found: {symbol}")
        
        return {
            "position": position,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 신호 ==========

@app.get("/signals")
async def get_signals() -> Dict[str, Any]:
    """
    모든 신호 조회
    
    Returns:
        신호 목록
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        signals = state_manager.get_all_signals()
        
        return {
            "signals": signals,
            "count": len(signals),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/{symbol}")
async def get_signal(symbol: str) -> Dict[str, Any]:
    """
    특정 심볼 신호 조회
    
    Args:
        symbol: 심볼
    
    Returns:
        신호 정보
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        signal = state_manager.get_signal(symbol)
        
        if not signal:
            raise HTTPException(status_code=404, detail=f"Signal not found: {symbol}")
        
        return {
            "signal": signal,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 주문 ==========

@app.get("/orders")
async def get_orders() -> Dict[str, Any]:
    """
    모든 주문 조회
    
    Returns:
        주문 목록
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        orders = state_manager.get_all_orders()
        
        return {
            "orders": orders,
            "count": len(orders),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders/{order_id}")
async def get_order(order_id: str) -> Dict[str, Any]:
    """
    특정 주문 조회
    
    Args:
        order_id: 주문 ID
    
    Returns:
        주문 정보
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        order = state_manager.get_order(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
        
        return {
            "order": order,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 실행 결과 ==========

@app.get("/executions")
async def get_executions(symbol: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    실행 결과 조회
    
    Args:
        symbol: 심볼 (선택)
        limit: 조회 개수
    
    Returns:
        실행 결과 목록
    """
    try:
        if not state_manager:
            raise HTTPException(status_code=503, detail="State manager not initialized")
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        executions = state_manager.get_executions(symbol, limit)
        
        return {
            "executions": executions,
            "count": len(executions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== WebSocket (실시간 업데이트) ==========

@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    실시간 메트릭 WebSocket
    
    클라이언트에 1초마다 메트릭 전송.
    """
    await websocket.accept()
    
    try:
        while True:
            if state_manager:
                metrics = state_manager.get_metrics()
                portfolio = state_manager.get_portfolio_state()
                
                data = {
                    "type": "metrics",
                    "metrics": metrics,
                    "portfolio": portfolio,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                await websocket.send_json(data)
            
            await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """
    실시간 신호 WebSocket
    
    클라이언트에 신호 업데이트 전송.
    """
    await websocket.accept()
    
    try:
        last_signals = {}
        
        while True:
            if state_manager:
                signals = state_manager.get_all_signals()
                
                # 새로운 신호만 전송
                for symbol, signal in signals.items():
                    if symbol not in last_signals or last_signals[symbol] != signal:
                        data = {
                            "type": "signal",
                            "symbol": symbol,
                            "signal": signal,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_json(data)
                
                last_signals = signals
            
            await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()


# ========== 에러 핸들러 ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
