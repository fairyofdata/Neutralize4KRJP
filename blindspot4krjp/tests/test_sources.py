"""소스 레지스트리와 Phase 0 완료 조건 점검."""

from __future__ import annotations

import pytest
import yaml

from blindspot.sources import SourceRegistry, load_sources


@pytest.fixture
def registry():
    return load_sources("sources.example.yaml")


def test_example_file_parses(registry):
    assert len(registry.all) == 6


def test_baselines_are_separated_from_sources(registry):
    """P6: baseline 은 소스 목록에 섞이지 않는다."""
    assert {p.id for p in registry.baselines} == {"yonhap", "japantimes"}
    assert "yonhap" not in {p.id for p in registry.sources}


def test_blocs_only_counts_overseas_sources(registry):
    assert "other" not in registry.blocs  # baseline 의 bloc 은 집계되지 않는다


def test_example_does_not_yet_satisfy_phase0(registry):
    """템플릿은 의도적으로 DoD 를 통과하지 못한다. 실제 조사가 필요하다."""
    rep = registry.phase0_report()
    assert rep["passed"] is False
    assert rep["checks"]["overseas_sources>=8"] is False
    assert rep["checks"]["baselines>=2"] is True


def test_phase0_report_counts_anglo_share(registry):
    """앵글로권 비중을 드러낸다 — P7 의 블록 기반 랭킹이 필요한 이유."""
    rep = registry.phase0_report()
    assert 0.0 <= rep["counts"]["anglo_share"] <= 1.0


def test_duplicate_ids_rejected():
    raw = yaml.safe_load(open("sources.example.yaml", encoding="utf-8"))["sources"]
    from pydantic import TypeAdapter

    from blindspot.models import SourceProfile

    profiles = TypeAdapter(list[SourceProfile]).validate_python(raw)
    with pytest.raises(ValueError, match="중복"):
        SourceRegistry(profiles + [profiles[0]])


def test_measured_fields_are_null_until_probed(registry):
    """P9: 측정하지 않은 값은 비어 있어야 한다. 추측으로 채우면 이 테스트가 깨진다."""
    g = registry.by_id["guardian_world"]
    assert g.feed.lead_coverage is None
    assert g.feed.items_per_day is None
