#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D29 Kubernetes Job Generator

Orchestrator 설정에서 K8s Job YAML 파일들을 생성.
실제 K8s 조작 없음 (매니페스트 생성만).
"""

import argparse
import os
import sys
import yaml
import logging
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.k8s_orchestrator import (
    K8sOrchestratorConfig,
    build_k8s_jobs_from_orchestrator
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def load_orchestrator_config(config_path: str) -> dict:
    """Orchestrator 설정 파일 로드"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_k8s_config(config_path: str) -> K8sOrchestratorConfig:
    """K8s Orchestrator 설정 파일 로드"""
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return K8sOrchestratorConfig(**data)


def save_job_yaml(job_dict: dict, output_path: str) -> None:
    """K8s Job YAML 파일 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(job_dict, f, default_flow_style=False, allow_unicode=True)
    
    logger.info(f"[D29_K8S] Saved job YAML: {output_path}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D29 Kubernetes Job Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/gen_d29_k8s_jobs.py \
    --orchestrator-config configs/d28_orchestrator/demo_baseline.yaml \
    --k8s-config configs/d29_k8s/orchestrator_k8s_baseline.yaml \
    --output-dir outputs/d29_k8s_jobs
        """
    )
    
    parser.add_argument(
        "--orchestrator-config",
        required=True,
        help="Orchestrator 설정 파일 경로 (D28)"
    )
    
    parser.add_argument(
        "--k8s-config",
        required=True,
        help="K8s Orchestrator 설정 파일 경로 (D29)"
    )
    
    parser.add_argument(
        "--output-dir",
        required=True,
        help="K8s Job YAML 파일 출력 디렉토리"
    )
    
    args = parser.parse_args()
    
    try:
        # 설정 로드
        logger.info(f"[D29_K8S] Loading orchestrator config: {args.orchestrator_config}")
        orch_config = load_orchestrator_config(args.orchestrator_config)
        
        logger.info(f"[D29_K8S] Loading K8s config: {args.k8s_config}")
        k8s_config = load_k8s_config(args.k8s_config)
        
        # 출력 디렉토리 생성
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[D29_K8S] Output directory: {output_dir}")
        
        # K8s Job 스펙 생성
        job_specs = build_k8s_jobs_from_orchestrator(orch_config, k8s_config)
        
        # 각 Job을 YAML 파일로 저장
        print("\n" + "=" * 70)
        print("[D29_K8S] KUBERNETES JOB GENERATION SUMMARY")
        print("=" * 70)
        print(f"Session ID:              {k8s_config.session_id}")
        print(f"Kubernetes Namespace:    {k8s_config.k8s_namespace}")
        print(f"Total Jobs:              {len(job_specs)}")
        print(f"Total Iterations:        {k8s_config.total_iterations}")
        print(f"Workers:                 {k8s_config.workers}")
        print(f"Mode:                    {k8s_config.mode}")
        print(f"Environment:             {k8s_config.env}")
        print(f"Optimizer:               {k8s_config.optimizer}")
        print(f"Image:                   {k8s_config.image}")
        print("=" * 70)
        print("\n[D29_K8S] GENERATED JOB FILES:\n")
        
        for idx, job_spec in enumerate(job_specs):
            # YAML 딕셔너리로 변환
            job_dict = job_spec.to_dict()
            
            # K8s 리소스 형식으로 변환
            from arbitrage.k8s_orchestrator import K8sTuningJobFactory
            factory = K8sTuningJobFactory(k8s_config)
            k8s_job = factory.to_yaml_dict(job_spec)
            
            # 파일명
            output_file = output_dir / f"job-{idx:02d}-{job_spec.name}.yaml"
            
            # 저장
            save_job_yaml(k8s_job, str(output_file))
            
            print(f"  [{idx + 1}/{len(job_specs)}] {output_file.name}")
            print(f"      Name: {job_spec.name}")
            print(f"      Worker: {job_spec.labels.get('worker_id', 'N/A')}")
            print(f"      Args: {' '.join(job_spec.args[:3])}...")
            print()
        
        print("=" * 70)
        print(f"[D29_K8S] Successfully generated {len(job_specs)} K8s Job YAML files")
        print(f"[D29_K8S] Output directory: {output_dir}")
        print("=" * 70 + "\n")
        
        return 0
    
    except Exception as e:
        logger.error(f"[D29_K8S] Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
