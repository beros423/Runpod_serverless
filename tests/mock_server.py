"""
로컬 Mock 서버 - RunPod Serverless 시뮬레이션
실제 API 호출 없이 병렬 처리 테스트 가능
"""
from flask import Flask, request, jsonify
import uuid
import time
import random
import threading
from datetime import datetime
from typing import Dict
import json

app = Flask(__name__)

# 작업 저장소 (메모리)
jobs: Dict[str, dict] = {}
job_lock = threading.Lock()


def process_job_async(job_id: str, input_data: dict):
    """백그라운드에서 작업 처리"""
    # 랜덤 대기 시간 (1-5초)
    wait_time = random.uniform(1, 5)
    
    # 입력 데이터에서 대기 시간 지정 가능
    if "wait_time" in input_data:
        wait_time = input_data["wait_time"]
    
    # 작업 상태 업데이트: IN_PROGRESS
    with job_lock:
        jobs[job_id]["status"] = "IN_PROGRESS"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
    
    # 실제 작업 시뮬레이션 (대기)
    time.sleep(wait_time)
    
    # 결과 생성
    result_text = f"""작업 완료 보고서
==================
Job ID: {job_id}
대기 시간: {wait_time:.2f}초
입력 데이터: {json.dumps(input_data, ensure_ascii=False, indent=2)}
완료 시각: {datetime.now().isoformat()}
==================
"""
    
    # 작업 완료 상태 업데이트
    with job_lock:
        jobs[job_id]["status"] = "COMPLETED"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["output"] = {
            "result_text": result_text,
            "wait_time": wait_time,
            "input_data": input_data
        }
        jobs[job_id]["executionTime"] = int(wait_time * 1000)  # 밀리초


@app.route('/v2/<endpoint_id>/run', methods=['POST'])
def submit_job(endpoint_id):
    """작업 제출 엔드포인트"""
    try:
        data = request.get_json()
        input_data = data.get("input", {})
        
        # 새 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        # 작업 초기화
        with job_lock:
            jobs[job_id] = {
                "id": job_id,
                "status": "IN_QUEUE",
                "input": input_data,
                "created_at": datetime.now().isoformat()
            }
        
        # 백그라운드에서 작업 처리 시작
        thread = threading.Thread(target=process_job_async, args=(job_id, input_data))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "id": job_id,
            "status": "IN_QUEUE"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/v2/<endpoint_id>/status/<job_id>', methods=['GET'])
def get_status(endpoint_id, job_id):
    """작업 상태 조회 엔드포인트"""
    with job_lock:
        job = jobs.get(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify(job)


@app.route('/v2/<endpoint_id>/cancel/<job_id>', methods=['POST'])
def cancel_job(endpoint_id, job_id):
    """작업 취소 엔드포인트"""
    with job_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "CANCELLED"
            return jsonify({"id": job_id, "status": "CANCELLED"})
    
    return jsonify({"error": "Job not found"}), 404


@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    return jsonify({
        "status": "healthy",
        "active_jobs": len([j for j in jobs.values() if j["status"] == "IN_PROGRESS"]),
        "total_jobs": len(jobs)
    })


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """모든 작업 목록 조회 (디버깅용)"""
    with job_lock:
        return jsonify({
            "total": len(jobs),
            "jobs": list(jobs.values())
        })


@app.route('/reset', methods=['POST'])
def reset():
    """모든 작업 초기화 (테스트용)"""
    global jobs
    with job_lock:
        jobs.clear()
    return jsonify({"message": "All jobs cleared"})


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Mock RunPod Serverless 서버 시작")
    print("=" * 60)
    print("서버 주소: http://localhost:5000")
    print("\n사용 가능한 엔드포인트:")
    print("  POST   /v2/<endpoint_id>/run           - 작업 제출")
    print("  GET    /v2/<endpoint_id>/status/<id>   - 상태 조회")
    print("  POST   /v2/<endpoint_id>/cancel/<id>   - 작업 취소")
    print("  GET    /health                          - 헬스 체크")
    print("  GET    /jobs                            - 모든 작업 목록")
    print("  POST   /reset                           - 작업 초기화")
    print("=" * 60)
    print("\n테스트 클라이언트는 test_parallel_local.py를 실행하세요!")
    print()
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
