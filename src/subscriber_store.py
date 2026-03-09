"""
구독자 요청 관리 모듈
구독 요청 및 취소 요청을 JSON 파일에 기록
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STORE_PATH = Path(__file__).parent.parent / 'data' / 'subscribers.json'


def _load() -> dict:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"[구독자 저장소] 로드 실패: {e}")
    return {"pending_add": [], "pending_remove": []}


def _save(data: dict):
    STORE_PATH.parent.mkdir(exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def add_request(chat_id: str, username: str, name: str):
    """구독 요청 추가"""
    data = _load()
    # 이미 pending_add에 있으면 스킵
    if any(r['chat_id'] == chat_id for r in data['pending_add']):
        return
    # pending_remove에서 제거 (재구독)
    data['pending_remove'] = [r for r in data['pending_remove'] if r['chat_id'] != chat_id]
    data['pending_add'].append({
        'chat_id': chat_id,
        'username': username or '',
        'name': name or '',
        'requested_at': datetime.now().isoformat()
    })
    _save(data)
    logger.info(f"[구독자 저장소] 구독 요청 추가: {chat_id} ({name})")


def remove_request(chat_id: str, username: str, name: str):
    """구독 취소 요청 추가"""
    data = _load()
    # 이미 pending_remove에 있으면 스킵
    if any(r['chat_id'] == chat_id for r in data['pending_remove']):
        return
    # pending_add에서 제거 (요청 후 바로 취소)
    data['pending_add'] = [r for r in data['pending_add'] if r['chat_id'] != chat_id]
    data['pending_remove'].append({
        'chat_id': chat_id,
        'username': username or '',
        'name': name or '',
        'requested_at': datetime.now().isoformat()
    })
    _save(data)
    logger.info(f"[구독자 저장소] 구독 취소 요청 추가: {chat_id} ({name})")


def clear_pending_add(chat_id: str):
    """pending_add에서 제거 (관리자가 처리 완료 후)"""
    data = _load()
    data['pending_add'] = [r for r in data['pending_add'] if r['chat_id'] != chat_id]
    _save(data)


def clear_pending_remove(chat_id: str):
    """pending_remove에서 제거 (관리자가 처리 완료 후)"""
    data = _load()
    data['pending_remove'] = [r for r in data['pending_remove'] if r['chat_id'] != chat_id]
    _save(data)


def get_pending_add() -> list:
    return _load()['pending_add']


def get_pending_remove() -> list:
    return _load()['pending_remove']
