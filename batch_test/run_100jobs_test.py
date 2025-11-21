"""대규모 작업 테스트: 100개 작업을 10개 워커로 병렬 처리"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import random
import time
from test_parallel_local import LocalMockProcessor

async def test_100_jobs_10_workers():
    """100개 작업을 10개 워커로 처리"""
    print("\n" + "=" * 80)
    print("🚀 대규모 병렬 처리 테스트")
    print("=" * 80)
    print("\n📋 테스트 설정:")
    print("   - 총 작업 수: 100개")
    print("   - 워커 수: 10개")
    print("   - 예상: 각 워커가 약 10개씩 처리")
    
    # 100개 작업 생성 (각각 1-3초 랜덤 대기)
    num_jobs = 100
    num_workers = 10
    
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
    print(f"   - 병렬 처리 예상 시간: ~{(total_expected_time/num_workers)*1.2:.1f}초 (오버헤드 포함)")
    
    # 프로세서 생성
    processor = LocalMockProcessor(
        base_url="http://localhost:5000",
        num_workers=num_workers
    )
    
    # 병렬 처리 시작 (워커 수만큼씩 배치 처리)
    print("\n" + "-" * 80)
    print(f"🔥 {num_workers}개 워커로 {num_jobs}개 작업 병렬 처리 시작!")
    print(f"   (배치 방식: {num_workers}개씩 동시 처리)")
    print("-" * 80)
    print()
    
    start_time = time.time()
    
    # 워커 수만큼씩 배치로 나눠서 처리
    all_results = []
    batch_size = num_workers
    
    for batch_idx in range(0, num_jobs, batch_size):
        batch = test_inputs[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        total_batches = (num_jobs + batch_size - 1) // batch_size
        
        print(f"\n📦 배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 작업)...")
        
        batch_results = await processor.process_batch_parallel(batch)
        all_results.extend(batch_results)
        
        completed = len(all_results)
        progress = (completed / num_jobs) * 100
        print(f"   진행률: {completed}/{num_jobs} ({progress:.1f}%)")
    
    results = all_results
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
    
    # 처리량 계산
    throughput = num_jobs / elapsed_time
    print(f"\n📊 처리량: {throughput:.2f} 작업/초")
    
    # 결과 저장
    print("\n💾 결과 저장 중...")
    await processor.save_results_to_files(successful, "results_100jobs")
    
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
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║               대규모 병렬 처리 테스트 (100개 작업, 10개 워커)              ║
╚════════════════════════════════════════════════════════════════════════════╝

이 테스트는 실제 환경과 유사한 대규모 작업 처리를 시뮬레이션합니다.

실행 전 확인:
  ✅ Mock 서버가 실행 중이어야 합니다
     → python mock_server.py
  
  ✅ 서버 주소: http://localhost:5000
""")
    
    input("준비되었으면 Enter를 눌러 시작하세요...")
    
    try:
        result = asyncio.run(test_100_jobs_10_workers())
        
        print("\n" + "=" * 80)
        print("🎯 최종 결과 요약")
        print("=" * 80)
        print(f"총 작업: {result['num_jobs']}개")
        print(f"워커 수: {result['num_workers']}개")
        print(f"성공률: {result['successful']}/{result['num_jobs']} ({result['successful']/result['num_jobs']*100:.1f}%)")
        print(f"처리 시간: {result['elapsed_time']:.2f}초")
        print(f"속도 향상: {result['speedup']:.2f}배")
        print(f"처리량: {result['throughput']:.2f} 작업/초")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n💡 Mock 서버가 실행 중인지 확인하세요!")
        import traceback
        traceback.print_exc()
