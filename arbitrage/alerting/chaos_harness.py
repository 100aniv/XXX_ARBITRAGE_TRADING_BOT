"""
D80-12: Alerting Chaos & Resilience Test Harness

Chaos Engineering for Alert Infrastructure:
- Redis disconnect/reconnect simulation
- Network latency injection
- Notifier failure injection
- CPU load injection
- Worker thread kill & recovery
- Queue durability validation
- Mixed chaos scenarios
- 24h long-run harness

Design Principles:
- Non-destructive (mock-based for tests)
- Observable (metrics & logs)
- Repeatable (deterministic scenarios)
- Isolated (no production impact)
"""

import time
import random
import threading
import psutil
import logging
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FaultType(Enum):
    """Types of faults that can be injected"""
    REDIS_DISCONNECT = "redis_disconnect"
    REDIS_RESTART = "redis_restart"
    REDIS_FLUSH = "redis_flush"
    NETWORK_LATENCY = "network_latency"
    NOTIFIER_TIMEOUT = "notifier_timeout"
    NOTIFIER_EXCEPTION = "notifier_exception"
    CPU_LOAD = "cpu_load"
    WORKER_KILL = "worker_kill"
    MIXED = "mixed"


@dataclass
class ChaosScenario:
    """Definition of a chaos scenario"""
    name: str
    fault_type: FaultType
    duration_seconds: float
    params: Dict[str, Any] = field(default_factory=dict)
    invariants: List[str] = field(default_factory=list)


@dataclass
class ChaosResult:
    """Result of a chaos scenario execution"""
    scenario: ChaosScenario
    success: bool
    duration_seconds: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    invariant_violations: List[str] = field(default_factory=list)


class RedisConnectionSimulator:
    """Simulates Redis connection failures"""
    
    def __init__(self):
        self._connected = True
        self._lock = threading.Lock()
    
    def disconnect(self, duration_seconds: float = 5.0):
        """Simulate Redis disconnect for given duration"""
        with self._lock:
            self._connected = False
        
        logger.warning(f"[CHAOS] Redis disconnected for {duration_seconds}s")
        
        def reconnect():
            time.sleep(duration_seconds)
            with self._lock:
                self._connected = True
            logger.info("[CHAOS] Redis reconnected")
        
        threading.Thread(target=reconnect, daemon=True).start()
    
    def restart(self, flush: bool = False):
        """Simulate Redis restart"""
        logger.warning(f"[CHAOS] Redis restart (flush={flush})")
        
        with self._lock:
            self._connected = False
        
        time.sleep(0.5)  # Brief downtime
        
        with self._lock:
            self._connected = True
        
        logger.info("[CHAOS] Redis restarted")
        return flush  # Indicates if data was flushed
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        with self._lock:
            return self._connected


class NetworkLatencyInjector:
    """Injects network latency into operations"""
    
    def __init__(self):
        self._latency_ms = 0.0
        self._enabled = False
        self._lock = threading.Lock()
    
    def enable(self, min_ms: float = 50.0, max_ms: float = 2000.0):
        """Enable latency injection with random delay range"""
        with self._lock:
            self._enabled = True
            self._min_ms = min_ms
            self._max_ms = max_ms
        logger.warning(f"[CHAOS] Network latency enabled: {min_ms}-{max_ms}ms")
    
    def disable(self):
        """Disable latency injection"""
        with self._lock:
            self._enabled = False
        logger.info("[CHAOS] Network latency disabled")
    
    def inject(self):
        """Inject latency if enabled"""
        with self._lock:
            if not self._enabled:
                return
            latency_ms = random.uniform(self._min_ms, self._max_ms)
        
        time.sleep(latency_ms / 1000.0)


class NotifierFailureInjector:
    """Injects failures into notifiers"""
    
    def __init__(self):
        self._failure_rate = 0.0
        self._failure_type = "timeout"
        self._enabled = False
        self._lock = threading.Lock()
    
    def enable(self, failure_rate: float = 1.0, failure_type: str = "timeout"):
        """
        Enable failure injection
        
        Args:
            failure_rate: Probability of failure (0.0-1.0)
            failure_type: 'timeout' or 'exception'
        """
        with self._lock:
            self._enabled = True
            self._failure_rate = failure_rate
            self._failure_type = failure_type
        logger.warning(f"[CHAOS] Notifier failures enabled: rate={failure_rate}, type={failure_type}")
    
    def disable(self):
        """Disable failure injection"""
        with self._lock:
            self._enabled = False
        logger.info("[CHAOS] Notifier failures disabled")
    
    def should_fail(self) -> tuple[bool, str]:
        """Check if notifier should fail this time"""
        with self._lock:
            if not self._enabled:
                return False, ""
            
            if random.random() < self._failure_rate:
                return True, self._failure_type
        
        return False, ""


class CPULoadInjector:
    """Injects CPU load"""
    
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self, target_load: float = 0.8, duration_seconds: float = 30.0):
        """
        Start CPU load injection
        
        Args:
            target_load: Target CPU load (0.0-1.0)
            duration_seconds: Duration of load injection
        """
        if self._running:
            return
        
        self._running = True
        logger.warning(f"[CHAOS] CPU load injection started: {target_load*100}% for {duration_seconds}s")
        
        def cpu_burn():
            start = time.time()
            while time.time() - start < duration_seconds and self._running:
                # Burn CPU for target_load fraction of time
                burn_start = time.time()
                while time.time() - burn_start < target_load * 0.1:
                    _ = sum(range(10000))
                
                # Sleep for remaining fraction
                time.sleep((1 - target_load) * 0.1)
            
            self._running = False
            logger.info("[CHAOS] CPU load injection stopped")
        
        self._thread = threading.Thread(target=cpu_burn, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop CPU load injection"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)


class WorkerKiller:
    """Simulates worker thread crashes and resurrection"""
    
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
    
    def kill_worker(self):
        """Kill worker thread"""
        if not self.dispatcher._worker_running:
            return False
        
        logger.warning("[CHAOS] Killing worker thread")
        self.dispatcher.stop_worker()
        return True
    
    def resurrect_worker(self):
        """Resurrect worker thread"""
        if self.dispatcher._worker_running:
            return False
        
        logger.info("[CHAOS] Resurrecting worker thread")
        self.dispatcher.start_worker()
        return True


class ChaosOrchestrator:
    """Orchestrates chaos scenarios"""
    
    # Pre-defined chaos scenarios
    SCENARIOS = {
        "SC01_REDIS_DISCONNECT": ChaosScenario(
            name="SC01: Redis Disconnect 5s",
            fault_type=FaultType.REDIS_DISCONNECT,
            duration_seconds=5.0,
            params={"disconnect_duration": 5.0},
            invariants=["zero_alert_loss", "zero_dlq_growth"],
        ),
        "SC02_REDIS_RESTART": ChaosScenario(
            name="SC02: Redis Restart (no flush)",
            fault_type=FaultType.REDIS_RESTART,
            duration_seconds=1.0,
            params={"flush": False},
            invariants=["zero_alert_loss", "zero_dlq_growth"],
        ),
        "SC03_REDIS_FLUSH": ChaosScenario(
            name="SC03: Redis Restart (flush all)",
            fault_type=FaultType.REDIS_FLUSH,
            duration_seconds=1.0,
            params={"flush": True},
            invariants=["zero_dlq_growth"],  # Alert loss expected but DLQ should be 0
        ),
        "SC04_NOTIFIER_DEAD": ChaosScenario(
            name="SC04: Notifier Dead 10x timeout → Circuit Breaker",
            fault_type=FaultType.NOTIFIER_TIMEOUT,
            duration_seconds=30.0,
            params={"failure_rate": 1.0, "count": 10},
            invariants=["circuit_breaker_opens", "zero_crash"],
        ),
        "SC05_CPU_LOAD": ChaosScenario(
            name="SC05: CPU Load 80% for 30s",
            fault_type=FaultType.CPU_LOAD,
            duration_seconds=30.0,
            params={"target_load": 0.8},
            invariants=["zero_crash", "latency_under_200ms"],
        ),
        "SC06_WORKER_KILL": ChaosScenario(
            name="SC06: Worker Thread Kill → Auto-Recover",
            fault_type=FaultType.WORKER_KILL,
            duration_seconds=5.0,
            params={"auto_resurrect": True},
            invariants=["worker_resurrection", "zero_crash"],
        ),
        "SC07_MIXED": ChaosScenario(
            name="SC07: Mixed (Latency + Redis Jitter + Notifier Fail)",
            fault_type=FaultType.MIXED,
            duration_seconds=60.0,
            params={
                "latency_range": (50, 500),
                "redis_jitter": True,
                "notifier_failure_rate": 0.3,
            },
            invariants=["zero_crash", "zero_hang"],
        ),
        "SC08_MASSIVE_INGESTION": ChaosScenario(
            name="SC08: 200K Alerts Under Chaos",
            fault_type=FaultType.MIXED,
            duration_seconds=120.0,
            params={
                "alert_count": 200000,
                "latency_range": (10, 100),
                "notifier_failure_rate": 0.1,
            },
            invariants=["zero_crash", "throughput_degradation_under_15pct"],
        ),
    }
    
    def __init__(self):
        self.redis_sim = RedisConnectionSimulator()
        self.latency_injector = NetworkLatencyInjector()
        self.notifier_injector = NotifierFailureInjector()
        self.cpu_injector = CPULoadInjector()
    
    def execute_scenario(
        self,
        scenario: ChaosScenario,
        dispatcher,
        pre_check: Optional[Callable] = None,
        post_check: Optional[Callable] = None,
    ) -> ChaosResult:
        """
        Execute a chaos scenario
        
        Args:
            scenario: Scenario to execute
            dispatcher: AlertDispatcher instance
            pre_check: Optional pre-condition check
            post_check: Optional post-condition check
        
        Returns:
            ChaosResult with metrics and violations
        """
        logger.info(f"[CHAOS] Executing scenario: {scenario.name}")
        
        result = ChaosResult(
            scenario=scenario,
            success=False,
            duration_seconds=0.0,
        )
        
        # Pre-condition check
        if pre_check:
            try:
                pre_check()
            except Exception as e:
                result.errors.append(f"Pre-check failed: {e}")
                return result
        
        # Execute chaos
        start_time = time.time()
        
        try:
            if scenario.fault_type == FaultType.REDIS_DISCONNECT:
                self._execute_redis_disconnect(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.REDIS_RESTART:
                self._execute_redis_restart(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.REDIS_FLUSH:
                self._execute_redis_flush(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.NOTIFIER_TIMEOUT:
                self._execute_notifier_timeout(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.CPU_LOAD:
                self._execute_cpu_load(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.WORKER_KILL:
                self._execute_worker_kill(scenario, dispatcher)
            
            elif scenario.fault_type == FaultType.MIXED:
                self._execute_mixed(scenario, dispatcher)
            
            result.success = True
        
        except Exception as e:
            result.errors.append(f"Execution error: {e}")
            logger.error(f"[CHAOS] Scenario execution failed: {e}")
        
        result.duration_seconds = time.time() - start_time
        
        # Post-condition check
        if post_check:
            try:
                violations = post_check()
                if violations:
                    result.invariant_violations.extend(violations)
                    result.success = False
            except Exception as e:
                result.errors.append(f"Post-check failed: {e}")
                result.success = False
        
        # Collect metrics
        if hasattr(dispatcher, 'get_stats'):
            result.metrics = dispatcher.get_stats()
        
        logger.info(f"[CHAOS] Scenario completed: {scenario.name} (success={result.success})")
        return result
    
    def _execute_redis_disconnect(self, scenario: ChaosScenario, dispatcher):
        """Execute Redis disconnect scenario"""
        duration = scenario.params.get("disconnect_duration", 5.0)
        self.redis_sim.disconnect(duration)
        time.sleep(duration + 1.0)  # Wait for reconnect
    
    def _execute_redis_restart(self, scenario: ChaosScenario, dispatcher):
        """Execute Redis restart scenario"""
        flush = scenario.params.get("flush", False)
        self.redis_sim.restart(flush=flush)
        time.sleep(1.0)
    
    def _execute_redis_flush(self, scenario: ChaosScenario, dispatcher):
        """Execute Redis flush scenario"""
        self.redis_sim.restart(flush=True)
        time.sleep(1.0)
    
    def _execute_notifier_timeout(self, scenario: ChaosScenario, dispatcher):
        """Execute notifier timeout scenario"""
        failure_rate = scenario.params.get("failure_rate", 1.0)
        count = scenario.params.get("count", 10)
        
        self.notifier_injector.enable(failure_rate=failure_rate, failure_type="timeout")
        
        # Trigger failures
        for _ in range(count):
            time.sleep(0.5)
        
        self.notifier_injector.disable()
    
    def _execute_cpu_load(self, scenario: ChaosScenario, dispatcher):
        """Execute CPU load scenario"""
        target_load = scenario.params.get("target_load", 0.8)
        duration = scenario.duration_seconds
        
        self.cpu_injector.start(target_load=target_load, duration_seconds=duration)
        time.sleep(duration)
        self.cpu_injector.stop()
    
    def _execute_worker_kill(self, scenario: ChaosScenario, dispatcher):
        """Execute worker kill scenario"""
        killer = WorkerKiller(dispatcher)
        
        killed = killer.kill_worker()
        if not killed:
            raise RuntimeError("Worker was not running")
        
        time.sleep(2.0)
        
        auto_resurrect = scenario.params.get("auto_resurrect", True)
        if auto_resurrect:
            resurrected = killer.resurrect_worker()
            if not resurrected:
                raise RuntimeError("Worker resurrection failed")
        
        time.sleep(scenario.duration_seconds)
    
    def _execute_mixed(self, scenario: ChaosScenario, dispatcher):
        """Execute mixed chaos scenario"""
        latency_range = scenario.params.get("latency_range", (50, 500))
        redis_jitter = scenario.params.get("redis_jitter", False)
        notifier_failure_rate = scenario.params.get("notifier_failure_rate", 0.3)
        
        # Enable all chaos
        self.latency_injector.enable(min_ms=latency_range[0], max_ms=latency_range[1])
        self.notifier_injector.enable(failure_rate=notifier_failure_rate)
        
        # Redis jitter if enabled
        if redis_jitter:
            for _ in range(3):
                time.sleep(scenario.duration_seconds / 4)
                self.redis_sim.disconnect(duration_seconds=1.0)
        else:
            time.sleep(scenario.duration_seconds)
        
        # Disable all chaos
        self.latency_injector.disable()
        self.notifier_injector.disable()


class LongRunHarness:
    """24h long-run test harness"""
    
    def __init__(self, dispatcher, alerts_per_minute: int = 200):
        self.dispatcher = dispatcher
        self.alerts_per_minute = alerts_per_minute
        self.running = False
        self.checkpoints: List[Dict[str, Any]] = []
        self._thread: Optional[threading.Thread] = None
    
    def start(self, duration_hours: float = 24.0):
        """Start long-run test"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"[LONG_RUN] Starting {duration_hours}h test at {self.alerts_per_minute} alerts/min")
        
        def run():
            from arbitrage.alerting import AlertRecord, AlertSeverity, AlertSource
            
            start_time = time.time()
            end_time = start_time + (duration_hours * 3600)
            checkpoint_interval = 3600  # 1 hour
            next_checkpoint = start_time + checkpoint_interval
            
            alert_count = 0
            
            while time.time() < end_time and self.running:
                # Send alerts
                for _ in range(self.alerts_per_minute):
                    if not self.running:
                        break
                    
                    alert = AlertRecord(
                        severity=AlertSeverity.P2,
                        source=AlertSource.FX_LAYER,
                        title=f"Long-run test alert {alert_count}",
                        message=f"Alert #{alert_count}",
                    )
                    
                    self.dispatcher.enqueue(alert, rule_id="LONG-RUN")
                    alert_count += 1
                    
                    time.sleep(60.0 / self.alerts_per_minute)
                
                # Checkpoint
                if time.time() >= next_checkpoint:
                    self._create_checkpoint(alert_count)
                    next_checkpoint += checkpoint_interval
            
            logger.info(f"[LONG_RUN] Completed: {alert_count} alerts sent")
        
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop long-run test"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def _create_checkpoint(self, alert_count: int):
        """Create checkpoint with metrics"""
        stats = self.dispatcher.get_stats()
        memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        
        checkpoint = {
            "timestamp": time.time(),
            "alert_count": alert_count,
            "stats": stats,
            "memory_mb": memory_mb,
        }
        
        self.checkpoints.append(checkpoint)
        logger.info(f"[LONG_RUN] Checkpoint: {alert_count} alerts, {memory_mb:.1f} MB")
    
    def get_report(self) -> Dict[str, Any]:
        """Get long-run test report"""
        if not self.checkpoints:
            return {}
        
        initial_memory = self.checkpoints[0]["memory_mb"]
        final_memory = self.checkpoints[-1]["memory_mb"]
        memory_growth = final_memory / initial_memory if initial_memory > 0 else 1.0
        
        return {
            "checkpoints": len(self.checkpoints),
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_growth": memory_growth,
            "total_alerts": self.checkpoints[-1]["alert_count"],
        }
