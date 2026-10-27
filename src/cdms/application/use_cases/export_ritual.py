from cdms.application.ports.repository import RepositoryPort


class ExportRitualUseCase:
    """Gera o relatório executivo formatado em Markdown a partir do registro persistido."""

    def __init__(self, repo: RepositoryPort):
        self.repo = repo

    def execute_markdown(self, cycle_id: str) -> str:
        ritual = self.repo.get_ritual_by_cycle(cycle_id)
        if not ritual:
            raise ValueError(f"Ritual do ciclo '{cycle_id}' não encontrado para exportação.")

        lines = [
            f"# Ritual Semanal de Decisão - Ciclo {ritual.cycle_id}",
            f"- **Data de Início da Semana:** {ritual.week_start.isoformat()}",
            f"- **Versão das Regras:** {ritual.rules_version}",
            f"- **Finalizado em (UTC):** {ritual.completed_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 1. Diagnóstico do Sistema",
            f"- **Cenário:** {ritual.scenario.name if hasattr(ritual.scenario, 'name') else ritual.scenario}",
        ]

        if hasattr(ritual.scenario, "description") and ritual.scenario.description:
            lines.append(f"- **Descrição:** {ritual.scenario.description}")

        lines.extend([
            "",
            "## 2. Snapshots das Métricas",
            "| Métrica | Unidade | Valor Observado | Faixa Saudável | Estado |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ])

        for snap in ritual.snapshots:
            unit = snap.definition.unit
            name = snap.definition.name
            cal = snap.calibration
            faixa = f"{cal.healthy_min:g} a {cal.healthy_max:g} {unit}"

            if snap.is_available:
                lines.append(
                    f"| {name} | {unit} | {snap.observed_value:g} | {faixa} | Disponível |"
                )
            else:
                motivo = snap.unavailability_reason or "Não informado"
                lines.append(
                    f"| {name} | {unit} | *N/D* | {faixa} | Indisponível ({motivo}) |"
                )

        dec = ritual.decision
        lines.extend([
            "",
            "## 3. Decisão Prioritária Única",
            f"- **Resumo:** {dec.summary}",
            f"- **Hipótese:** {dec.hypothesis}",
            f"- **Critério de Sucesso:** {dec.success_criterion}",
            f"- **Prazo de Avaliação:** {dec.evaluation_due_date.isoformat()}",
            f"- **Responsável:** {dec.owner}",
        ])

        if ritual.learning:
            learn = ritual.learning
            outcome_val = learn.outcome.value if hasattr(learn.outcome, "value") else str(learn.outcome)
            lines.extend([
                "",
                "## 4. Auditoria de Aprendizado (Decisão Anterior)",
                f"- **ID da Decisão Avaliada:** {learn.target_decision_id}",
                f"- **Resumo da Decisão:** {learn.target_decision_summary}",
                f"- **Resultado da Hipótese:** {outcome_val}",
                f"- **Notas de Evidência:** {learn.evidence_notes or 'Sem notas adicionais'}",
            ])

        lines.append("")
        return "\n".join(lines)