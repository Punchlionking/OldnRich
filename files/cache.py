"""
계층적 캐시 저장소.

데이터는 변하는 속도가 다르다 → 느린 데이터(재무제표·목표가 등)는 캐시하고
주기를 늘려 API 한도를 아낀다. 각 카테고리에 '일일 갱신 예산'을 두어, 오래된
항목부터 예산 한도 내에서만 새로 호출하고 나머지는 캐시(다소 stale)를 쓴다.
→ 며칠에 걸쳐 순환 갱신되므로 한도를 절대 넘기지 않으면서 큰 유니버스 커버.

저장: cache/<category>.json  = { key: {"v": <data>, "t": <ISO fetched_at>} }
CI(임시 러너)에서도 유지되도록 이 디렉터리는 저장소에 커밋한다.
"""

from __future__ import annotations

import json
import datetime as dt
from pathlib import Path


class CacheStore:
    def __init__(self, cache_dir: str | None = None):
        self.dir = Path(cache_dir) if cache_dir else \
            (Path(__file__).resolve().parent.parent / "cache")
        self.dir.mkdir(exist_ok=True)
        self._data: dict[str, dict] = {}     # category -> {key: {"v","t"}}
        self._budget: dict[str, int] = {}    # category -> 남은 일일 예산
        self._dirty: set[str] = set()
        self.fetched = 0                     # 이번 실행에서 실제 새로 호출한 횟수

    # --- 예산 ---------------------------------------------------------------
    def set_budget(self, category: str, n: int) -> None:
        self._budget[category] = n

    # --- 내부 ---------------------------------------------------------------
    def _load(self, category: str) -> dict:
        if category not in self._data:
            f = self.dir / f"{category}.json"
            if f.exists():
                try:
                    self._data[category] = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    self._data[category] = {}
            else:
                self._data[category] = {}
        return self._data[category]

    @staticmethod
    def _age_days(iso: str) -> float:
        try:
            t = dt.datetime.fromisoformat(iso)
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400.0
        except Exception:
            return 1e9

    # --- 조회/저장 ----------------------------------------------------------
    def is_fresh(self, category: str, key: str, ttl_days: float) -> bool:
        d = self._load(category).get(key)
        return d is not None and self._age_days(d.get("t", "")) <= ttl_days

    def get(self, category: str, key: str):
        d = self._load(category).get(key)
        return d.get("v") if d else None

    def put(self, category: str, key: str, value) -> None:
        self._load(category)[key] = {
            "v": value, "t": dt.datetime.now(dt.timezone.utc).isoformat()}
        self._dirty.add(category)

    def get_or_fetch(self, category: str, key: str, ttl_days: float, fetch_fn):
        """
        신선하면 캐시 반환. 오래/없음이면 예산 내에서만 새로 호출.
        예산 초과 시 stale 캐시라도 반환(없으면 None) → 다음 실행에서 순환 갱신.
        """
        if self.is_fresh(category, key, ttl_days):
            return self.get(category, key)
        if self._budget.get(category, 0) > 0:
            try:
                v = fetch_fn()
            except Exception:
                v = None
            if v is not None:
                self.put(category, key, v)
                self._budget[category] -= 1
                self.fetched += 1
                return v
        return self.get(category, key)   # stale 또는 None

    def save(self) -> None:
        for cat in self._dirty:
            f = self.dir / f"{cat}.json"
            f.write_text(json.dumps(self._data[cat], ensure_ascii=False), encoding="utf-8")
        self._dirty.clear()
