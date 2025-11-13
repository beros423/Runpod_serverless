"""
병렬 처리 테스트 클라이언트 (로컬 Mock 서버용)
"""
import asyncio
import aiohttp
import time
import random
from typing import List, Dict
import json
from datetime import datetime


class LocalMockProcessor:
    """로컬 Mock 서버를 사용한 병렬 처리 테스트"""
    
    def __init__(self, base_url: str = "http://localhost:5000", num_workers: int = 5):
        self.base_url = base_url
        self.num_workers = num_workers
        self.endpoint_id = "test-endpoint"
    
    async def submit_job(self, session: aiohttp.ClientSession, input_data: Dict) -> str:
        """작업 제출"""
        url = f"{self.base_url}/v2/{self.endpoint_id}/run"
        async with session.post(url, json={"input": input_data}) as response:
            result = await response.json()
            return result.get("id")
    
    async def check_status(self, session: aiohttp.ClientSession, job_id: str) -> Dict:
        """작업 상태 확인"""
        url = f"{self.base_url}/v2/{self.endpoint_id}/status/{job_id}"
        async with session.get(url) as response:
            return await response.json()
    
    async def wait_for_completion(self, session: aiohttp.ClientSession, job_id: str, 
                                  max_wait: int = 300, poll_interval: float = 0.5) -> Dict:
        """작업 완료 대기"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = await self.check_status(session, job_id)
            
            if status.get("status") == "COMPLETED":
                return status
            elif status.get("status") in ["FAILED", "CANCELLED"]:
                raise Exception(f"Job {job_id} failed: {status}")
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Job {job_id} timed out after {max_wait} seconds")
    
    async def process_single_job(self, session: aiohttp.ClientSession, 
                                 input_data: Dict, job_index: int) -> Dict:
        """단일 작업 처리"""
        print(f"[Worker {job_index+1:2d}] 작업 제출 중...")
        
        submit_time = time.time()
        job_id = await self.submit_job(session, input_data)
        
        print(f"[Worker {job_index+1:2d}] Job ID: {job_id[:8]}... - 대기 중...")
        
        result = await self.wait_for_completion(session, job_id)
        complete_time = time.time()
        
        elapsed = complete_time - submit_time
        wait_time = result.get("output", {}).get("wait_time", 0)
        
        print(f"[Worker {job_index+1:2d}] ✅ 완료! (대기: {wait_time:.2f}초, 전체: {elapsed:.2f}초)")
        
        return {
            "job_index": job_index,
            "job_id": job_id,
            "input": input_data,
            "output": result.get("output"),
            "wait_time": wait_time,
            "total_time": elapsed,
            "status": result.get("status")
        }
    
    async def process_batch_parallel(self, input_list: List[Dict]) -> List[Dict]:
        """배치를 병렬로 처리"""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.process_single_job(session, input_data, idx)
                for idx, input_data in enumerate(input_list)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
    
    async def process_batch_sequential(self, input_list: List[Dict]) -> List[Dict]:
        """배치를 순차적으로 처리"""
        results = []
        async with aiohttp.ClientSession() as session:
            for idx, input_data in enumerate(input_list):
                result = await self.process_single_job(session, input_data, idx)
                results.append(result)
        return results
    
    async def save_results_to_files(self, results: List[Dict], output_dir: str = "results"):
        """결과를 파일로 저장"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            
            job_id = result["job_id"]
            result_text = result.get("output", {}).get("result_text", "")
            
            # 개별 결과 파일 저장
            filename = f"{output_dir}/result_{result['job_index']:02d}_{job_id[:8]}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(result_text)
            
            print(f"💾 저장: {filename}")
        
        # 전체 요약 저장
        summary_file = f"{output_dir}/summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_jobs": len(results),
                "successful": len([r for r in results if not isinstance(r, Exception)]),
                "failed": len([r for r in results if isinstance(r, Exception)]),
                "results": [r for r in results if not isinstance(r, Exception)]
            }, f, ensure_ascii=False, indent=2)
        
        print(f"📊 요약 저장: {summary_file}")


async def test_parallel_performance():
    """병렬 처리 성능 테스트"""
    print("\n" + "=" * 70)
    print("🧪 병렬 처리 성능 테스트 시작")
    print("=" * 70)
    
    # 테스트 데이터 생성
    num_jobs = 10
    test_inputs = [
        {
            "task_name": f"작업_{i+1}",
            "wait_time": round(random.uniform(1, 3), 2),  # 1-3초 랜덤
            "data": f"테스트 데이터 {i+1}"
        }
        for i in range(num_jobs)
    ]
    
    total_expected_time = sum(inp["wait_time"] for inp in test_inputs)
    print(f"\n📋 테스트 설정:")
    print(f"   - 작업 수: {num_jobs}개")
    print(f"   - 대기 시간 합계: {total_expected_time:.2f}초")
    print(f"   - 예상 순차 처리 시간: ~{total_expected_time:.1f}초")
    print()
    
    processor = LocalMockProcessor(num_workers=5)
    
    # 1. 병렬 처리
    print("\n" + "-" * 70)
    print("🚀 병렬 처리 (5개 동시 실행)")
    print("-" * 70)
    
    start_parallel = time.time()
    parallel_results = await processor.process_batch_parallel(test_inputs)
    parallel_time = time.time() - start_parallel
    
    print(f"\n✅ 병렬 처리 완료: {parallel_time:.2f}초")
    
    # 결과 저장
    await processor.save_results_to_files(parallel_results, "results_parallel")
    
    # 2. 순차 처리 (비교용)
    print("\n" + "-" * 70)
    print("🐌 순차 처리 (1개씩 순차 실행)")
    print("-" * 70)
    
    start_sequential = time.time()
    sequential_results = await processor.process_batch_sequential(test_inputs)
    sequential_time = time.time() - start_sequential
    
    print(f"\n✅ 순차 처리 완료: {sequential_time:.2f}초")
    
    # 결과 저장
    await processor.save_results_to_files(sequential_results, "results_sequential")
    
    # 결과 비교
    print("\n" + "=" * 70)
    print("📊 성능 비교 결과")
    print("=" * 70)
    
    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    time_saved = sequential_time - parallel_time
    efficiency = (speedup / 5) * 100  # 5개 워커 기준
    
    print(f"\n순차 처리 시간:     {sequential_time:>8.2f}초")
    print(f"병렬 처리 시간:     {parallel_time:>8.2f}초")
    print(f"{'─' * 40}")
    print(f"속도 향상:         {speedup:>8.2f}배")
    print(f"절약된 시간:       {time_saved:>8.2f}초 ({time_saved/sequential_time*100:.1f}%)")
    print(f"병렬화 효율:       {efficiency:>8.1f}%")
    
    # 성공률
    parallel_success = len([r for r in parallel_results if not isinstance(r, Exception)])
    sequential_success = len([r for r in sequential_results if not isinstance(r, Exception)])
    
    print(f"\n병렬 처리 성공률:   {parallel_success}/{num_jobs} ({parallel_success/num_jobs*100:.0f}%)")
    print(f"순차 처리 성공률:   {sequential_success}/{num_jobs} ({sequential_success/num_jobs*100:.0f}%)")
    
    print("\n" + "=" * 70)
    print("✨ 테스트 완료!")
    print("=" * 70)
    
    return {
        "sequential_time": sequential_time,
        "parallel_time": parallel_time,
        "speedup": speedup,
        "efficiency": efficiency
    }


async def simple_test():
    """간단한 테스트 (5개 작업만)"""
    print("\n" + "=" * 70)
    print("🎯 간단한 병렬 처리 테스트")
    print("=" * 70)
    
    import random
    
    # 5개 작업
    test_inputs = [
        {"task": f"작업_{i+1}", "wait_time": round(random.uniform(1, 3), 2)}
        for i in range(5)
    ]
    
    processor = LocalMockProcessor(num_workers=5)
    
    print("\n5개 작업을 동시에 처리합니다...\n")
    
    start = time.time()
    results = await processor.process_batch_parallel(test_inputs)
    elapsed = time.time() - start
    
    print(f"\n✅ 완료! 총 소요 시간: {elapsed:.2f}초")
    
    # 결과 저장
    await processor.save_results_to_files(results, "results_simple")
    
    return results


if __name__ == "__main__":
    import random
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          로컬 Mock 서버 병렬 처리 테스트 클라이언트              ║
╚══════════════════════════════════════════════════════════════════╝

실행 전 확인:
  1. mock_server.py가 실행 중인지 확인하세요
  2. 서버 주소: http://localhost:5000

테스트 옵션:
  1. 간단한 테스트 (5개 작업)
  2. 전체 성능 비교 테스트 (10개 작업, 순차 vs 병렬)
""")
    
    choice = input("선택하세요 (1 또는 2, 기본값 1): ").strip() or "1"
    
    if choice == "2":
        asyncio.run(test_parallel_performance())
    else:
        asyncio.run(simple_test())
