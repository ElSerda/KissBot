"""
Performance Tracker - Microsecond precision timing

Track all operations in microseconds for performance analysis and bottleneck identification.
"""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class TimingData:
    """Store timing information in microseconds"""
    operation: str
    duration_us: float
    start_time: float
    end_time: float
    metadata: Dict = field(default_factory=dict)


class PerformanceTracker:
    """Track all operations in microseconds"""
    
    def __init__(self):
        self.timings: List[TimingData] = []
        self._stack: List[tuple] = []  # Stack for nested timings
    
    @contextmanager
    def track(self, operation: str, **metadata):
        """
        Context manager for tracking operation time
        
        Usage:
            with tracker.track("cache_check"):
                result = db.get_cached_game(name)
        
        Args:
            operation: Name of the operation being tracked
            **metadata: Additional metadata to store with timing
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            duration_us = (end - start) * 1_000_000
            
            self.timings.append(TimingData(
                operation=operation,
                duration_us=duration_us,
                start_time=start,
                end_time=end,
                metadata=metadata
            ))
    
    def get_report(self) -> str:
        """
        Generate performance report with statistics per operation
        
        Returns:
            str: Formatted report with avg/min/max/calls for each operation
        """
        if not self.timings:
            return "No timings recorded"
        
        lines = ["⏱️ Performance Report (µs):"]
        lines.append("=" * 60)
        
        # Group by operation
        by_operation = {}
        for timing in self.timings:
            if timing.operation not in by_operation:
                by_operation[timing.operation] = []
            by_operation[timing.operation].append(timing.duration_us)
        
        # Stats per operation
        for operation, durations in sorted(by_operation.items()):
            avg = sum(durations) / len(durations)
            min_val = min(durations)
            max_val = max(durations)
            count = len(durations)
            
            lines.append(
                f"{operation:30s} | "
                f"avg={avg:7.1f}µs | "
                f"min={min_val:7.1f}µs | "
                f"max={max_val:7.1f}µs | "
                f"calls={count}"
            )
        
        # Total
        total = sum(t.duration_us for t in self.timings)
        lines.append("=" * 60)
        lines.append(f"{'TOTAL':30s} | {total:7.1f}µs")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict:
        """
        Get summary statistics as dictionary
        
        Returns:
            dict: Summary with total_us, operation_count, avg_us_per_operation
        """
        if not self.timings:
            return {
                'total_us': 0,
                'operation_count': 0,
                'avg_us_per_operation': 0
            }
        
        total_us = sum(t.duration_us for t in self.timings)
        operation_count = len(self.timings)
        
        return {
            'total_us': total_us,
            'operation_count': operation_count,
            'avg_us_per_operation': total_us / operation_count
        }
    
    def clear(self):
        """Clear all timings"""
        self.timings.clear()
        self._stack.clear()
