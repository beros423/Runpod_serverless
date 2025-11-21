"""
대규모 작업 테스트 (개선 버전): 100개 작업을 10개 워커로 병렬 처리
각 워커가 독립적으로 작업을 가져가서 처리
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import random
import time
from test_parallel_local import LocalMockProcessor

async def test_100_jobs_independent_workers(num_workers=10):
    """100개 작업을 지정된 워커 수로 독립적으로 처리"""
    print("\n" + "=" * 80)
    print("🚀 대규모 병렬 처리 테스트 (독립 워커 방식)")
    print("=" * 80)
    print("\n📋 테스트 설정:")
    print("   - 총 작업 수: 100개")
    print(f"   - 워커 수: {num_workers}개")
    print("   - 방식: 각 워커가 독립적으로 작업 처리")
    print("   - 특징: 작업 완료 즉시 다음 작업 시작")
    
    # 100개 작업 생성
    num_jobs = 100
    
    test_inputs = [
        {
            "task_name": f"작업_{i+1:03d}",
            "wait_time": round(random.uniform(1, 3), 2),
            "batch": f"batch_{(i//10)+1}",
            "index": i+1
        }
        for i in range(num_jobs)
    ]
    
    total_expected_time = sum(inp["wait_time"] for inp in test_inputs)
    avg_wait_time = total_expected_time / num_jobs
    
    print(f"   - 총 대기 시간: {total_expected_time:.2f}초")
    print(f"   - 평균 대기 시간: {avg_wait_time:.2f}초/작업")
    print(f"   - 순차 처리 예상 시간: ~{total_expected_time:.1f}초")
    print(f"   - 병렬 처리 예상 시간: ~{(total_expected_time/num_workers):.1f}초 (이론적)")
    
    # 프로세서 생성
    processor = LocalMockProcessor(
        base_url="http://localhost:5000",
        num_workers=num_workers
    )
    
    # 독립적 워커 방식으로 처리
    print("\n" + "-" * 80)
    print(f"🔥 {num_workers}개 독립 워커로 {num_jobs}개 작업 처리 시작!")
    print(f"   각 워커는 자기 일이 끝나는 즉시 다음 작업을 시작합니다")
    print("-" * 80)
    print()
    
    start_time = time.time()
    
    # 세마포어로 동시 실행 워커 수 제한
    semaphore = asyncio.Semaphore(num_workers)
    completed_count = [0]  # 완료 카운터 (리스트로 mutable하게)
    lock = asyncio.Lock()  # 출력 동기화용
    
    async def process_with_semaphore(session, input_data, job_index):
        """세마포어를 사용해 워커 수 제한"""
        async with semaphore:
            # 작업 시작
            async with lock:
                print(f"[작업 {job_index+1:3d}] 시작... (워커 할당)")
            
            result = await processor.process_single_job(session, input_data, job_index)
            
            # 작업 완료
            async with lock:
                completed_count[0] += 1
                progress = (completed_count[0] / num_jobs) * 100
                wait_time = result.get("wait_time", 0) if not isinstance(result, Exception) else 0
                print(f"[작업 {job_index+1:3d}] ✅ 완료! (대기: {wait_time:.2f}초) | 진행률: {completed_count[0]}/{num_jobs} ({progress:.1f}%)")
            
            return result
    
    # aiohttp 세션 생성 및 모든 작업 동시 시작
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # 모든 작업을 동시에 시작하지만, 세마포어가 워커 수를 제한
        tasks = [
            process_with_semaphore(session, input_data, idx)
            for idx, input_data in enumerate(test_inputs)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed_time = time.time() - start_time
    
    # 결과 분석
    successful = [r for r in results if not isinstance(r, Exception)]
    failed = [r for r in results if isinstance(r, Exception)]
    
    print("\n" + "=" * 80)
    print("📊 처리 결과")
    print("=" * 80)
    
    print(f"\n✅ 성공: {len(successful)}/{num_jobs}개 ({len(successful)/num_jobs*100:.1f}%)")
    print(f"❌ 실패: {len(failed)}/{num_jobs}개")
    print(f"\n⏱️  총 처리 시간: {elapsed_time:.2f}초")
    print(f"📈 평균 처리 시간: {elapsed_time/num_jobs:.2f}초/작업")
    
    # 속도 비교
    estimated_sequential = total_expected_time
    speedup = estimated_sequential / elapsed_time if elapsed_time > 0 else 0
    efficiency = (speedup / num_workers) * 100
    
    print(f"\n🔥 성능 분석:")
    print(f"   - 예상 순차 처리: {estimated_sequential:.2f}초")
    print(f"   - 실제 병렬 처리: {elapsed_time:.2f}초")
    print(f"   - 속도 향상: {speedup:.2f}배")
    print(f"   - 절약된 시간: {estimated_sequential - elapsed_time:.2f}초 ({(1-elapsed_time/estimated_sequential)*100:.1f}%)")
    print(f"   - 병렬화 효율: {efficiency:.1f}%")
    print(f"   - 이론적 최적: {total_expected_time/num_workers:.2f}초")
    print(f"   - 실제 대비 이론: {(elapsed_time/(total_expected_time/num_workers)):.2f}배 (오버헤드 포함)")
    
    # 처리량 계산
    throughput = num_jobs / elapsed_time
    print(f"\n📊 처리량: {throughput:.2f} 작업/초")
    
    # 결과 저장
    print("\n💾 결과 저장 중...")
    await processor.save_results_to_files(successful, "results_100jobs_independent")
    
    print("\n" + "=" * 80)
    print("✨ 테스트 완료!")
    print("=" * 80)
    
    # 추가 통계
    if successful:
        wait_times = [r.get("wait_time", 0) for r in successful]
        total_times = [r.get("total_time", 0) for r in successful]
        
        print(f"\n📈 상세 통계:")
        print(f"   - 최소 대기 시간: {min(wait_times):.2f}초")
        print(f"   - 최대 대기 시간: {max(wait_times):.2f}초")
        print(f"   - 평균 대기 시간: {sum(wait_times)/len(wait_times):.2f}초")
        print(f"   - 평균 총 처리 시간: {sum(total_times)/len(total_times):.2f}초")
    
    return {
        "num_jobs": num_jobs,
        "num_workers": num_workers,
        "successful": len(successful),
        "failed": len(failed),
        "elapsed_time": elapsed_time,
        "speedup": speedup,
        "efficiency": efficiency,
        "throughput": throughput
    }


if __name__ == "__main__":
    
    # 워커 수 입력
    while True:
        try:
            num_workers_input = input("\n사용할 워커 수를 입력하세요 (기본값: 10, 권장: 5-20): ").strip()
            if num_workers_input == "":
                num_workers = 10
                print(f"→ 기본값 {num_workers}개 워커 사용")
                break
            num_workers = int(num_workers_input)
            if num_workers < 1:
                print("워커 수는 1 이상이어야 합니다.")
                continue
            if num_workers > 50:
                confirm = input(f"워커 {num_workers}개는 많습니다. 계속하시겠습니까? (y/n): ").lower()
                if confirm != 'y':
                    continue
            print(f"→ {num_workers}개 워커로 설정됨")
            break
        except ValueError:
            print("❌ 올바른 숫자를 입력하세요.")
    
    input("\n준비되었으면 Enter를 눌러 시작하세요...")
    
    try:
        result = asyncio.run(test_100_jobs_independent_workers(num_workers))
        
        print("\n" + "=" * 80)
        print("🎯 최종 결과 요약")
        print("=" * 80)
        print(f"총 작업: {result['num_jobs']}개")
        print(f"워커 수: {result['num_workers']}개")
        print(f"성공률: {result['successful']}/{result['num_jobs']} ({result['successful']/result['num_jobs']*100:.1f}%)")
        print(f"처리 시간: {result['elapsed_time']:.2f}초")
        print(f"속도 향상: {result['speedup']:.2f}배")
        print(f"병렬화 효율: {result['efficiency']:.1f}%")
        print(f"처리량: {result['throughput']:.2f} 작업/초")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n💡 Mock 서버가 실행 중인지 확인하세요!")
        import traceback
        traceback.print_exc()
