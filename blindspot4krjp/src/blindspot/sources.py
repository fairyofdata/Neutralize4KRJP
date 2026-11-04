"""sources.yaml 로더 + Phase 0 완료 조건 점검."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import TypeAdapter

from .models import SourceProfile

_ADAPTER = TypeAdapter(list[SourceProfile])


class SourceRegistry:
    def __init__(self, profiles: list[SourceProfile]) -> None:
        dupes = {p.id for p in profiles if sum(1 for q in profiles if q.id == p.id) > 1}
        if dupes:
            raise ValueError(f"source id 중복: {sorted(dupes)}")
        self.by_id = {p.id: p for p in profiles}

    @property
    def all(self) -> list[SourceProfile]:
        return list(self.by_id.values())

    @property
    def sources(self) -> list[SourceProfile]:
        """해외 소스. 브리핑 본문에 투입된다."""
        return [p for p in self.all if p.role == "source"]

    @property
    def baselines(self) -> list[SourceProfile]:
        """P6: 보도 공백 계산 전용. 브리핑 본문에 절대 투입하지 않는다."""
        return [p for p in self.all if p.role == "baseline"]

    @property
    def blocs(self) -> set[str]:
        return {p.bloc for p in self.sources}

    def phase0_report(self) -> dict:
        """헌장 §7 의 DoD 를 기계적으로 점검한다. 통과/실패와 함께 수치를 돌려준다."""
        anglo = [p for p in self.sources if p.bloc == "anglo"]
        checks = {
            "overseas_sources>=8": len(self.sources) >= 8,
            "blocs>=4": len(self.blocs) >= 4,
            "baselines>=2": len(self.baselines) >= 2,
            "all_lean_has_basis": all(
                p.political_lean == "unclassified" or p.lean_basis.strip() for p in self.all
            ),
            "all_have_tos_note": all(p.tos_note.strip() for p in self.all),
        }
        return {
            "checks": checks,
            "passed": all(checks.values()),
            "counts": {
                "overseas": len(self.sources),
                "baseline": len(self.baselines),
                "blocs": sorted(self.blocs),
                "anglo_share": round(len(anglo) / len(self.sources), 3) if self.sources else 0.0,
            },
        }


def load_sources(path: str | Path) -> SourceRegistry:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    if isinstance(raw, dict):
        raw = raw.get("sources", [])
    return SourceRegistry(_ADAPTER.validate_python(raw))
