# 🚀 로컬 병렬 처리 테스트 프로젝트

RunPod Serverless API의 병렬 처리를 **로컬에서 테스트**할 수 있는 Mock 프로젝트입니다.

## 📖 개요

실제 RunPod API 호출 없이 병렬 처리 성능을 테스트할 수 있습니다:
- JSON 형태의 input을 받음
- 랜덤한 시간(1-5초) 동안 대기
- 대기 시간과 결과를 텍스트 파일로 반환

## 🎯 핵심 질문에 대한 답변

### Q: 다중으로 작업을 진행할 수 있나요?
**✅ 네, 가능합니다!** 이 프로젝트가 그것을 증명합니다.

### Q: 워커 5개로 5배 속도를 낼 수 있나요?
**📊 이론: 5배 / 현실: 2-4배**
- 병렬 처리가 I/O 대기 시간을 크게 단축
- Cold start, 네트워크 지연 등의 오버헤드 존재
- 그래도 **엄청난 속도 향상!**

---

## 🛠️ 설치 및 실행

### 1. 패키지 설치
```bash
pip install flask aiohttp
```

또는

```bash
pip install -r requirements.txt
```

### 2. Mock 서버 실행
**터미널 1번:**
```bash
python mock_server.py
```

출력:
```
🚀 Mock RunPod Serverless 서버 시작
서버 주소: http://localhost:5000
...
```

### 3. 테스트 클라이언트 실행
**터미널 2번:**

#### 옵션 A: 간단한 테스트 (5개 작업)
```bash
python run_simple_test.py
```

#### 옵션 B: 전체 성능 비교 (순차 vs 병렬)
```bash
python run_full_test.py
```

---

## 📂 프로젝트 구조

```
Runpod_serverless/
├── mock_server.py              # Mock API 서버 (Flask)
├── test_parallel_local.py      # 병렬 처리 클라이언트
├── run_simple_test.py          # 간단한 테스트 실행
├── run_full_test.py            # 전체 성능 비교 테스트
├── LOCAL_TEST_GUIDE.md         # 상세 가이드
├── test2.ipynb                 # 이론 및 코드 설명 노트북
└── results_*/                  # 결과 파일 저장 폴더
```

---

## 🎮 사용 방법

### 방법 1: 빠른 시작 (추천)

**1단계: 서버 시작**
```bash
# 터미널 1
python mock_server.py
```

**2단계: 테스트 실행**
```bash
# 터미널 2
python run_simple_test.py
```

### 방법 2: 커스텀 테스트

Python 스크립트 작성:
```python
import asyncio
from test_parallel_local import LocalMockProcessor

async def my_test():
    processor = LocalMockProcessor(num_workers=5)
    
    # 작업 정의
    tasks = [
        {"task": f"작업_{i}", "wait_time": 2.0}
        for i in range(10)
    ]
    
    # 병렬 실행
    results = await processor.process_batch_parallel(tasks)
    
    # 결과 저장
    await processor.save_results_to_files(results, "my_results")
    
    print(f"완료! {len(results)}개 작업 처리됨")

asyncio.run(my_test())
```

---

## 📊 예상 결과

### 간단한 테스트 (5개 작업)
```
5개 작업을 동시에 처리합니다...

[Worker  1] 작업 제출 중...
[Worker  2] 작업 제출 중...
[Worker  3] 작업 제출 중...
[Worker  4] 작업 제출 중...
[Worker  5] 작업 제출 중...
[Worker  1] Job ID: a1b2c3d4... - 대기 중...
[Worker  2] Job ID: e5f6g7h8... - 대기 중...
...
[Worker  1] ✅ 완료! (대기: 2.34초, 전체: 2.50초)
[Worker  3] ✅ 완료! (대기: 1.89초, 전체: 2.05초)
...

✅ 완료! 총 소요 시간: 3.21초
```

### 전체 성능 비교 (10개 작업)
```
📊 성능 비교 결과
======================================================================
순차 처리 시간:      18.45초
병렬 처리 시간:       4.12초
────────────────────────────────────────
속도 향상:            4.48배
절약된 시간:         14.33초 (77.7%)
병렬화 효율:          89.6%

병렬 처리 성공률:    10/10 (100%)
순차 처리 성공률:    10/10 (100%)
```

---

## 📁 결과 파일

### 개별 결과 파일 예시
`results_parallel/result_00_a1b2c3d4.txt`:
```
작업 완료 보고서
==================
Job ID: a1b2c3d4-5e6f-7890-abcd-ef1234567890
대기 시간: 2.34초
입력 데이터: {
  "task_name": "작업_1",
  "wait_time": 2.34,
  "data": "테스트 데이터 1"
}
완료 시각: 2025-11-13T15:30:45.123456
==================
```

### 요약 파일
`results_parallel/summary.json`:
```json
{
  "timestamp": "2025-11-13T15:30:42.000000",
  "total_jobs": 10,
  "successful": 10,
  "failed": 0,
  "results": [...]
}
```

---

## ⚙️ 설정 옵션

### 워커 수 변경
```python
processor = LocalMockProcessor(num_workers=10)  # 10개로 증가
```

### 대기 시간 범위 변경
`mock_server.py`에서:
```python
# 1-5초 → 2-10초로 변경
wait_time = random.uniform(2, 10)
```

### 작업 수 변경
```python
num_jobs = 20  # 20개 작업
test_inputs = [
    {"task": f"작업_{i}", "wait_time": round(random.uniform(1, 3), 2)}
    for i in range(num_jobs)
]
```

---

## 🔍 API 엔드포인트

Mock 서버는 다음 엔드포인트를 제공합니다:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/v2/<endpoint>/run` | 작업 제출 |
| GET | `/v2/<endpoint>/status/<id>` | 상태 조회 |
| POST | `/v2/<endpoint>/cancel/<id>` | 작업 취소 |
| GET | `/health` | 헬스 체크 |
| GET | `/jobs` | 모든 작업 목록 |
| POST | `/reset` | 작업 초기화 |

### 예시: curl로 테스트
```bash
# 작업 제출
curl -X POST http://localhost:5000/v2/test/run \
  -H "Content-Type: application/json" \
  -d '{"input": {"task": "테스트", "wait_time": 2.0}}'

# 상태 조회
curl http://localhost:5000/v2/test/status/<job_id>

# 헬스 체크
curl http://localhost:5000/health
```

---

## 🚀 실전 RunPod 적용

로컬 테스트가 성공하면, 실제 RunPod API로 전환:

### 1. 클래스 변경
```python
# 로컬 테스트
from test_parallel_local import LocalMockProcessor
processor = LocalMockProcessor()

# 실제 RunPod (test2.ipynb 참고)
from test2 import RunPodParallelProcessor
processor = RunPodParallelProcessor(
    api_key="your_runpod_api_key",
    endpoint_id="your_endpoint_id",
    num_workers=5
)
```

### 2. 코드는 동일!
```python
# 로컬이든 RunPod이든 사용법은 똑같습니다
results = await processor.process_batch_parallel(input_list)
await processor.save_results_to_files(results, "results")
```

---

## 🎓 학습 포인트

이 프로젝트를 통해 배우는 것:

1. **비동기 프로그래밍** (`asyncio`, `aiohttp`)
2. **병렬 처리 개념** (동시성 vs 병렬성)
3. **REST API 설계** (Flask)
4. **작업 큐 시뮬레이션**
5. **성능 측정 및 비교**

---

## 🐛 문제 해결

### "Connection refused" 에러
```
→ mock_server.py가 실행 중인지 확인
→ 포트 5000이 사용 중인지 확인: netstat -ano | findstr :5000
```

### "ModuleNotFoundError: No module named 'flask'"
```bash
pip install flask aiohttp
```

### 서버가 종료됨
```
→ 터미널에서 Ctrl+C를 눌렀는지 확인
→ 서버를 다시 시작: python mock_server.py
```

### 결과 파일이 생성되지 않음
```
→ results_* 폴더의 권한 확인
→ 디스크 공간 확인
```

---

## 💡 팁

### 개발 팁
1. 서버는 한 번만 실행하고 유지
2. 클라이언트는 여러 번 실행 가능
3. `/reset` 엔드포인트로 작업 초기화 가능

### 성능 팁
1. 워커 수 = CPU 코어 수 × 2 (I/O 바운드)
2. 너무 많은 워커는 오버헤드 증가
3. 배치 크기를 조정해 최적화

### 디버깅 팁
```python
# 로깅 추가
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📚 추가 자료

- `test2.ipynb` - 병렬 처리 이론 및 설명
- `LOCAL_TEST_GUIDE.md` - 상세 가이드
- `mock_server.py` - 서버 코드 (주석 포함)
- `test_parallel_local.py` - 클라이언트 코드 (주석 포함)

---

## 🎯 다음 단계

1. ✅ 로컬 테스트 성공
2. 📝 실제 작업 로직 구현
3. 🚀 RunPod에 배포
4. 🔄 실제 API로 전환
5. 📊 프로덕션 모니터링

---

## ❓ FAQ

**Q: 실제 RunPod와 차이가 있나요?**
A: 기본 동작은 동일하지만, Cold start, GPU 초기화 등은 시뮬레이션되지 않습니다.

**Q: 얼마나 빠른가요?**
A: 로컬 테스트에서는 2-4배, 실제 RunPod에서는 환경에 따라 다릅니다.

**Q: 프로덕션에서 사용 가능한가요?**
A: 이것은 테스트용입니다. 실제로는 RunPod API를 사용하세요.

---

## 📞 지원

문제가 있으면:
1. 로그 확인
2. 서버/클라이언트 재시작
3. 코드 주석 참고

---

**즐거운 병렬 처리 되세요! 🚀**
