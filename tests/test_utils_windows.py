"""
D99-5: Windows 파일 락 대응 유틸리티

Windows에서 PermissionError: [WinError 32] 해결을 위한 재시도 로직
"""

import gc
import shutil
import time
from pathlib import Path
from typing import Union


def safe_rmtree(path: Union[str, Path], max_retries: int = 8, initial_delay: float = 0.05) -> bool:
    """Windows-safe recursive directory removal with exponential backoff
    
    Args:
        path: Directory path to remove
        max_retries: Maximum number of retry attempts (default: 8)
        initial_delay: Initial delay in seconds (default: 0.05)
    
    Returns:
        True if successful, False otherwise
    
    Note:
        Uses exponential backoff: 0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4 seconds
    """
    path = Path(path)
    if not path.exists():
        return True
    
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path)
            return True
        except PermissionError as e:
            if "WinError 32" in str(e) or "being used by another process" in str(e):
                if attempt < max_retries - 1:
                    # Force garbage collection to release file handles
                    gc.collect()
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    return False
            else:
                # Different permission error, not file lock
                raise
        except Exception:
            # Other errors (not file lock related)
            raise
    
    return False
