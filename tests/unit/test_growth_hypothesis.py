"""Testes unitários para a entidade GrowthHypothesis e o cálculo do ICE Score no CGS."""

from decimal import Decimal
import pytest

from cgs.domain.entities.hypothesis import (
    GrowthHypothesis,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


@pytest.fixture
def valid_higher_hypothesis():
    """Retorna uma hipótese válida configurada para otimização de métrica crescente (HIGHER_IS_BETTER)."""
    return GrowthHypothesis(
        id=1,
        source_cycle_id="2026-10-26",
        target_cycle_id="2026-11-02",
        promoted_decision_id=None,
        action_description="Inserir CTA verbal direto nos primeiros 5 segundos",
        tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3.0"),
        success_metric_target=Decimal("4.5"),
        invalidation_floor=Decimal("2.5"),
        expected_impact_description="Aumentar cliques qualificados para o link da bio",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
        sample_exposure_minimum=100,
        window_days=7,
        status=HypothesisStatus.BACKLOG,
    )


@pytest.fixture
def valid_lower_hypothesis():
    """Retorna uma hipótese válida configurada para redução de métrica (LOWER_IS_BETTER, ex: CPA/Custo)."""
    return GrowthHypothesis(
        id=2,
        source_cycle_id="2026-10-26",
        target_cycle_id="2026-11-02",
        promoted_decision_id=None,
        action_description="Segmentar público para reduzir custo de aquisição",
        tested_variable=VariableType.OFFER,
        target_metric_key="cpa_reais",
        target_metric_unit="R$",
        metric_direction=MetricDirection.LOWER_IS_BETTER,
        baseline_reference_value=Decimal("45.00"),
        success_metric_target=Decimal("30.00"),
        invalidation_floor=Decimal("50.00"),  # Teto de invalidação
        expected_impact_description="Reduzir custo por aquisição mantendo taxa de conversão",
        impact_score=9,
        confidence_score=8,
        ease_score=6,
        sample_exposure_minimum=50,
        window_days=7,
        status=HypothesisStatus.BACKLOG,
    )


def test_ice_score_calculation(valid_higher_hypothesis):
    """Testa o cálculo do ICE Score com fórmula (I * C * E) / 10 e precisão de duas casas decimais."""
    assert valid_higher_hypothesis.ice_score == Decimal("50.40")


def test_ice_score_lower_metric(valid_lower_hypothesis):
    """Valida o cálculo do ICE score em hipótese de métrica decrescente."""
    assert valid_lower_hypothesis.ice_score == Decimal("43.20")


def test_ice_score_boundary_values():
    """Testa os limites operacionais mínimo (1, 1, 1 -> 0.10) e máximo (10, 10, 10 -> 100.00)."""
    min_hypo = GrowthHypothesis(
        id=None,
        source_cycle_id=None,
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Teste mínimo",
        tested_variable=VariableType.HOOK,
        target_metric_key="reach",
        target_metric_unit="un",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("1000"),
        success_metric_target=Decimal("1200"),
        invalidation_floor=Decimal("900"),
        expected_impact_description="Impacto mínimo",
        impact_score=1,
        confidence_score=1,
        ease_score=1,
    )
    assert min_hypo.ice_score == Decimal("0.10")

    max_hypo = GrowthHypothesis(
        id=None,
        source_cycle_id=None,
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Teste máximo",
        tested_variable=VariableType.CREATIVE,
        target_metric_key="conversions",
        target_metric_unit="un",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("50"),
        success_metric_target=Decimal("100"),
        invalidation_floor=Decimal("40"),
        expected_impact_description="Impacto máximo",
        impact_score=10,
        confidence_score=10,
        ease_score=10,
    )
    assert max_hypo.ice_score == Decimal("100.00")


@pytest.mark.parametrize(
    "impact,confidence,ease",
    [
        (0, 5, 5),      # Abaixo de 1
        (11, 5, 5),     # Acima de 10
        (5, -1, 5),     # Negativo
        (5, 5, 12),     # Facilidade acima de 10
    ],
)
def test_ice_score_out_of_range_raises_value_error(impact, confidence, ease):
    """Garante rejeição de notas fora do intervalo estrito [1, 10]."""
    with pytest.raises(ValueError):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Ajuste",
            tested_variable=VariableType.CTA,
            target_metric_key="ctr_pct",
            target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=Decimal("3.0"),
            success_metric_target=Decimal("4.5"),
            invalidation_floor=Decimal("2.5"),
            expected_impact_description="Teste",
            impact_score=impact,
            confidence_score=confidence,
            ease_score=ease,
        )


@pytest.mark.parametrize(
    "impact,confidence,ease",
    [
        (True, 5, 5),       # Booleano disfarçado de int
        (5, False, 5),
        (5.5, 5, 5),       # Float
        ("7", 5, 5),       # String
    ],
)
def test_ice_score_invalid_types_raise_type_error(impact, confidence, ease):
    """Garante que apenas inteiros estritos são aceitos para notas ICE."""
    with pytest.raises(TypeError):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Ajuste",
            tested_variable=VariableType.CTA,
            target_metric_key="ctr_pct",
            target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=Decimal("3.0"),
            success_metric_target=Decimal("4.5"),
            invalidation_floor=Decimal("2.5"),
            expected_impact_description="Teste",
            impact_score=impact,
            confidence_score=confidence,
            ease_score=ease,
        )


def test_invalidation_floor_higher_is_better_validation():
    """Para HIGHER_IS_BETTER, invalidation_floor deve ser estritamente menor que success_metric_target."""
    with pytest.raises(ValueError, match="deve ser estritamente menor que success_metric_target"):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Ajuste",
            tested_variable=VariableType.CTA,
            target_metric_key="ctr_pct",
            target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=Decimal("3.0"),
            success_metric_target=Decimal("4.0"),
            invalidation_floor=Decimal("4.0"),
            expected_impact_description="Teste",
            impact_score=5,
            confidence_score=5,
            ease_score=5,
        )


def test_invalidation_floor_lower_is_better_validation():
    """Para LOWER_IS_BETTER, invalidation_floor deve ser estritamente maior que success_metric_target."""
    with pytest.raises(ValueError, match="deve ser estritamente maior que success_metric_target"):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Redução de CPA",
            tested_variable=VariableType.OFFER,
            target_metric_key="cpa_reais",
            target_metric_unit="R$",
            metric_direction=MetricDirection.LOWER_IS_BETTER,
            baseline_reference_value=Decimal("40.00"),
            success_metric_target=Decimal("30.00"),
            invalidation_floor=Decimal("25.00"),
            expected_impact_description="Teste",
            impact_score=5,
            confidence_score=5,
            ease_score=5,
        )


def test_target_metrics_must_be_decimal():
    """Rejeita valores numéricos que não sejam instâncias de Decimal (ex: float)."""
    with pytest.raises(TypeError, match="deve ser do tipo Decimal"):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Ajuste",
            tested_variable=VariableType.HOOK,
            target_metric_key="ctr_pct",
            target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=3.0,
            success_metric_target=Decimal("4.5"),
            invalidation_floor=Decimal("2.0"),
            expected_impact_description="Teste",
            impact_score=5,
            confidence_score=5,
            ease_score=5,
        )


def test_exposure_minimum_validation():
    """Garante que sample_exposure_minimum seja um inteiro não negativo."""
    with pytest.raises(ValueError):
        GrowthHypothesis(
            id=None,
            source_cycle_id=None,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description="Ajuste",
            tested_variable=VariableType.LANDING_PAGE,
            target_metric_key="ctr_pct",
            target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=Decimal("3.0"),
            success_metric_target=Decimal("4.5"),
            invalidation_floor=Decimal("2.0"),
            expected_impact_description="Teste",
            impact_score=5,
            confidence_score=5,
            ease_score=5,
            sample_exposure_minimum=-10,
        )