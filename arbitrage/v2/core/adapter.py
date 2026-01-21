"""
ExchangeAdapter - Implementation Layer

Interface for translating OrderIntent to exchange-specific payloads.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

from .order_intent import OrderIntent


@dataclass
class OrderResult:
    """
    Standardized order result.
    
    Attributes:
        success: Whether the order was successful
        order_id: Exchange-specific order ID
        filled_qty: Filled quantity (base asset)
        filled_price: Average fill price
        fee: Transaction fee (in quote currency)
        ref_price: Reference price used for slippage calculation
        slippage_bps: Applied slippage in basis points
        pessimistic_drift_bps: Applied pessimistic drift in basis points
        latency_ms: Simulated execution latency (milliseconds)
        reject_flag: Whether the order was rejected
        partial_fill_ratio: Partial fill ratio (0.0~1.0)
        error_message: Error message if failed
        raw_response: Raw exchange response (for debugging)
    """
    success: bool
    order_id: Optional[str] = None
    filled_qty: Optional[float] = None
    filled_price: Optional[float] = None
    fee: Optional[float] = None
    ref_price: Optional[float] = None
    slippage_bps: Optional[float] = None
    pessimistic_drift_bps: Optional[float] = None
    latency_ms: Optional[float] = None
    reject_flag: Optional[bool] = None
    partial_fill_ratio: Optional[float] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange adapters.
    
    Responsibility:
    1. Translate OrderIntent to exchange-specific payload
    2. Submit order to exchange (or mock)
    3. Parse exchange response to OrderResult
    
    Exchange-specific validation and quirks are handled here,
    NOT in the engine layer.
    """
    
    @abstractmethod
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Translate OrderIntent to exchange-specific payload.
        
        This method should:
        1. Validate that the intent is supported by this exchange
        2. Convert semantic fields to exchange API format
        3. Apply exchange-specific rules and quirks
        
        Args:
            intent: Exchange-independent order intent
            
        Returns:
            Exchange API payload (ready for submission)
            
        Raises:
            ValueError: If intent is not supported by this exchange
        """
        pass
    
    @abstractmethod
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit order to exchange.
        
        In V2, the default implementation should return a mock response.
        Real API calls require explicit override and READ_ONLY flag check.
        
        Args:
            payload: Exchange-specific payload from translate_intent()
            
        Returns:
            Raw exchange response
            
        Raises:
            Exception: If submission fails
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        """
        Parse exchange response to standardized OrderResult.
        
        Args:
            response: Raw response from submit_order()
            
        Returns:
            Standardized OrderResult
        """
        pass
    
    def execute(self, intent: OrderIntent) -> OrderResult:
        """
        Complete execution flow: translate → submit → parse.
        
        This is a convenience method that chains the three steps.
        
        Args:
            intent: Order intent to execute
            
        Returns:
            Standardized order result
        """
        intent.validate()
        payload = self.translate_intent(intent)
        response = self.submit_order(payload)
        return self.parse_response(response)
