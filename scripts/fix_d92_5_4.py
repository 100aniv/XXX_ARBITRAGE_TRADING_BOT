#!/usr/bin/env python3
"""D92-5-4: SSOT 정합성 완결 - 자동 수정 스크립트"""
import re
from pathlib import Path

def fix_run_d77_0():
    """run_d77_0_topn_arbitrage_paper.py 수정"""
    file_path = Path("scripts/run_d77_0_topn_arbitrage_paper.py")
    content = file_path.read_text(encoding='utf-8')
    
    # 1. Optional import 추가
    content = content.replace(
        "from typing import Dict, List, Any, Tuple",
        "from typing import Dict, List, Any, Tuple, Optional"
    )
    
    # 2. 레거시 로깅 제거
    legacy_log = """# logs/ 디렉토리 생성
Path("logs/d77-0").mkdir(parents=True, exist_ok=True)

# D92-1-FIX: 로깅 설정 (직접 함수 호출 시 루트 로거 사용)
log_filename = f'logs/d77-0/paper_session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

# 루트 로거에 핸들러 추가 (모든 자식 로거에 propagate됨)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# FileHandler 추가 (중복 체크)
file_handler_exists = any(isinstance(h, logging.FileHandler) and 'paper_session' in str(h.baseFilename) for h in root_logger.handlers)
if not file_handler_exists:
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    )
    root_logger.addHandler(file_handler)

# 모듈 로거 (루트 로거로 propagate)
logger = logging.getLogger(__name__)
logger.info(f"[D92-1-FIX] Logger initialized with file: {log_filename}")"""
    
    content = content.replace(legacy_log, "# D92-5-4: 모듈 로거\nlogger = logging.getLogger(__name__)")
    
    # 3. stage_id 파라미터 추가
    content = content.replace(
        "        zone_profile_applier: Optional[Any] = None,  # D92-1-FIX\n    ):",
        "        zone_profile_applier: Optional[Any] = None,  # D92-1-FIX\n        stage_id: str = \"d77-0\",  # D92-5-4\n    ):"
    )
    
    # 4. run_paths 초기화 추가 (self.kpi_output_path 이후)
    init_code = """        self.kpi_output_path = kpi_output_path
        self.zone_profile_applier = zone_profile_applier
        self.stage_id = stage_id  # D92-5-2: Stage ID
        
        # D92-5-3: run_paths SSOT 초기화
        from arbitrage.common.run_paths import resolve_run_paths
        self.run_paths = resolve_run_paths(
            stage_id=self.stage_id,
            universe_mode=self.universe_mode.name.lower(),
        )
        logger.info(f"[D92-5-3] SSOT Paths: stage={self.stage_id}, run_id={self.run_paths['run_id']}")
        logger.info(f"[D92-5-3] KPI Path: {self.run_paths['kpi_summary']}")"""
    
    new_init = """        self.kpi_output_path = kpi_output_path
        self.zone_profile_applier = zone_profile_applier
        self.stage_id = stage_id
        
        # D92-5-4: run_paths SSOT
        from arbitrage.common.run_paths import resolve_run_paths
        self.run_paths = resolve_run_paths(
            stage_id=self.stage_id,
            universe_mode=self.universe_mode.name.lower(),
            create_dirs=True,
        )"""
    
    content = content.replace(init_code, new_init)
    
    # 5. d82-0- session_id 제거
    content = content.replace(
        '"session_id": f"d82-0-{universe_mode.name.lower()}-{datetime.now().strftime(\'%Y%m%d%H%M%S\')}",',
        '"session_id": self.run_paths["run_id"],'
    )
    
    # 6. KPI 경로 수정
    content = content.replace(
        'output_path = Path(f"logs/d77-0/{self.metrics[\'session_id\']}_kpi_summary.json")',
        'output_path = Path(self.run_paths["kpi_summary"])'
    )
    
    # 7. TradeLogger 경로 수정
    content = content.replace(
        'base_dir=Path("logs/d82-0/trades"),  # 레거시 경로 유지\n            run_id=self.run_paths["run_id"],  # D92-5-2: SSOT run_id',
        'base_dir=self.run_paths["run_dir"] / "trades",\n            run_id=self.run_paths["run_id"]'
    )
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✅ {file_path} 수정 완료")

def fix_run_d92_1():
    """run_d92_1_topn_longrun.py 수정"""
    file_path = Path("scripts/run_d92_1_topn_longrun.py")
    content = file_path.read_text(encoding='utf-8')
    
    # 1. Import + Provenance
    old_import = """    universe_mode = topn_mode_map[top_n]
    
    # run_d77_0 임포트 및 실행
    from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner
    
    start_time = time.time()"""
    
    new_import = """    universe_mode = topn_mode_map[top_n]
    
    # D92-5-4: Import Provenance
    from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner
    
    f = Path(inspect.getsourcefile(D77PAPERRunner)).resolve()
    h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    logger.info(f"[IMPORT_PROVENANCE] {f} / SHA256:{h}")
    assert str(f).startswith(str(REPO_ROOT)), f"Wrong: {f}"
    
    start_time = time.time()"""
    
    content = content.replace(old_import, new_import)
    
    # 2. data_source 추가
    content = content.replace(
        """        runner = D77PAPERRunner(
            universe_mode=universe_mode,
            duration_minutes=duration_minutes,""",
        """        runner = D77PAPERRunner(
            universe_mode=universe_mode,
            data_source="real",
            duration_minutes=duration_minutes,"""
    )
    
    # 3. KPI 사후 이동 제거
    move_block = """        # D92-5-2: KPI 파일을 stage_id 경로로 이동
        import shutil
        import glob
        if stage_id != "d92-1":
            source_pattern = Path("logs/d77-0/*_kpi_summary.json")
            target_dir = Path(f"logs/{stage_id}")
            target_dir.mkdir(parents=True, exist_ok=True)
            
            kpi_files = sorted(glob.glob(str(source_pattern)), key=lambda x: Path(x).stat().st_mtime, reverse=True)
            if kpi_files:
                latest_kpi = Path(kpi_files[0])
                session_id = latest_kpi.stem.replace("_kpi_summary", "")
                target_run_dir = target_dir / session_id
                target_run_dir.mkdir(parents=True, exist_ok=True)
                
                shutil.move(str(latest_kpi), str(target_run_dir / latest_kpi.name))
                logger.info(f"[D92-5-2] Moved KPI to: {target_run_dir / latest_kpi.name}")
        """
    
    content = content.replace(move_block, "        # D92-5-4: KPI는 stage_id 경로에 직접 생성\n        ")
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✅ {file_path} 수정 완료")

if __name__ == "__main__":
    fix_run_d77_0()
    fix_run_d92_1()
    print("\n✅ D92-5-4 수정 완료")
