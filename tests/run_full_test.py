"""전체 성능 비교 테스트 실행"""
import asyncio
from test_parallel_local import test_parallel_performance

if __name__ == "__main__":
    asyncio.run(test_parallel_performance())
