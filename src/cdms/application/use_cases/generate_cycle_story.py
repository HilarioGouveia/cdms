"""Read-only, deterministic storytelling over cycle evidence. No LLM or inferred ROI."""
from dataclasses import dataclass
from datetime import date
from enum import Enum
import re
from typing import Optional, Protocol

from cdms.domain.entities.learning import Learning
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cgs.domain.entities.funnel import FunnelOpportunityAudit


class StoryAudience(str, Enum):
    EXECUTIVE = "Gestor"
    OPERATOR = "Operador"
    COMMUNICATION = "Comunicação"


class StoryCorePort(Protocol):
    def get_ritual_by_cycle(self, cycle_id: str) -> Optional[WeeklyRitualRecord]: ...
    def get_learning_by_decision_id(self, decision_id: int) -> Optional[Learning]: ...


class StoryGrowthPort(Protocol):
    def get_funnel_audit(self, source_cycle_id: str) -> Optional[FunnelOpportunityAudit]: ...


@dataclass(frozen=True)
class StoryBlock:
    title: str
    text: str
    sources: tuple[str, ...]


def safe_markdown(text):
    # Treat source fields as text, including HTML, links, headings and images.
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~>-])", r"\\\1", str(text))


@dataclass(frozen=True)
class CycleStory:
    cycle_id: str
    audience: StoryAudience
    blocks: tuple[StoryBlock, ...]
    next_step: str
    simulated: bool = False
    version: str = "1.0"

    @property
    def markdown(self):
        lines = [f"# Narrativa do ciclo {self.cycle_id}", "",
                 f"Público: {self.audience.value} · Gerador v{self.version}", ""]
        if self.simulated:
            lines += ["DADOS SIMULADOS · Demonstração", ""]
        if self.audience == StoryAudience.COMMUNICATION:
            lines += ["Resumo para revisão antes de compartilhar. Não inclui valores financeiros, responsáveis ou notas internas.", ""]
        for block in self.blocks:
            lines += [f"## {block.title}", "", safe_markdown(block.text), "",
                      "Fontes: " + "; ".join(safe_markdown(source) for source in block.sources), ""]
        lines += ["## Próximo passo", "", safe_markdown(self.next_step), "",
                  "Oportunidade estimada não é receita realizada. Resultado registrado não comprova causalidade ou execução na plataforma."]
        return "\n".join(lines)


STAGES = {"NONE": "nenhum gargalo crítico frente à baseline", "ATTENTION": "atenção / exposição",
          "INTENTION": "intenção / CTR", "CONVERSION": "conversão em venda",
          "LEAD_CAPTURE": "captura de leads", "LEAD_CLOSING": "fechamento comercial"}
OUTCOMES = {"ACHIEVED": "Meta atingida", "PARTIAL": "Meta parcialmente atingida",
            "NOT_ACHIEVED": "Meta não atingida", "INCONCLUSIVE": "Resultado inconclusivo"}


def br_money(value):
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


class GenerateCycleStoryUseCase:
    def __init__(self, core: StoryCorePort, growth: StoryGrowthPort):
        self.core, self.growth = core, growth

    def execute(self, cycle_id: str, audience=StoryAudience.EXECUTIVE, *, simulated=False):
        cycle = date.fromisoformat(cycle_id)
        if cycle.isoformat() != cycle_id or cycle.weekday() != 0:
            raise ValueError("O ciclo deve ser uma segunda-feira no formato YYYY-MM-DD.")
        audience = StoryAudience(audience)
        public = audience == StoryAudience.COMMUNICATION
        audit = self.growth.get_funnel_audit(cycle_id)
        ritual = self.core.get_ritual_by_cycle(cycle_id)
        if audit and audit.source_cycle_id != cycle_id:
            raise ValueError("Diagnóstico não corresponde ao ciclo consultado.")
        if ritual and (ritual.cycle_id != cycle_id or ritual.decision.cycle_id != cycle_id):
            raise ValueError("Decisão não corresponde ao ciclo consultado.")
        learning = None
        if ritual and ritual.decision.id is not None:
            learning = self.core.get_learning_by_decision_id(ritual.decision.id)
            if learning and learning.target_decision_id != ritual.decision.id:
                raise ValueError("Aprendizado não corresponde à decisão do ciclo.")
        context_sources, action_sources, result_sources = [], [], []
        if audit:
            context_sources.append(f"Diagnóstico do ciclo {cycle_id} · cálculo v{audit.calculation_version}")
            context = f"O diagnóstico registrado indica: {STAGES[audit.primary_bottleneck.value]}."
            if not public:
                context += f" Oportunidade recuperável estimada: {br_money(audit.total_opportunity_reais)}. Não representa receita realizada."
        else:
            context = "Não há diagnóstico financeiro salvo para este ciclo. O impacto financeiro ainda não pode ser apresentado."
        if ritual:
            context_sources.append(f"Ritual do ciclo {cycle_id} · regras v{ritual.rules_version}")
            if not public:
                context += f" Cenário heurístico registrado: {ritual.scenario.type.value}."
            decision = ritual.decision
            action_sources.append(f"Decisão #{decision.id} · ciclo {cycle_id}")
            if public:
                action = "Uma decisão foi registrada com hipótese e critério de avaliação. O registro não confirma sua execução na plataforma."
            else:
                action = f"Decisão registrada: {decision.summary}\nHipótese: {decision.hypothesis}\nCritério de sucesso: {decision.success_criterion}\nAvaliação prevista: {decision.evaluation_due_date:%d/%m/%Y}."
                if audience == StoryAudience.OPERATOR:
                    action += f"\nResponsável registrado: {decision.owner}."
                action += "\nA decisão registrada não confirma execução na plataforma."
        else:
            action = "Não há decisão registrada no ritual deste ciclo. Hipóteses do backlog não são tratadas como ações executadas."
        if learning:
            result_sources.append(f"Aprendizado #{learning.id} · decisão #{learning.target_decision_id} · registrado em {learning.recorded_at:%d/%m/%Y}")
            result = f"{OUTCOMES[learning.outcome.value]}, conforme o aprendizado registrado para esta decisão."
            if not public:
                result += f"\nEvidências registradas: {learning.evidence_notes or 'Sem notas adicionais.'}"
            result += "\nEste registro não comprova, por si só, ganho de ROI ou efeito causal."
            next_step = "Revisar o aprendizado e definir a próxima decisão com base nas evidências."
        elif ritual:
            result = "Aguardando avaliação: nenhum aprendizado auditado foi encontrado para a decisão deste ciclo. Não há resultado comprovado a narrar."
            next_step = "Registrar o resultado observado e as evidências no próximo ritual de avaliação."
        else:
            result = "Sem resultado auditado para uma decisão deste ciclo."
            next_step = "Registrar o diagnóstico e a decisão do ciclo." if not audit else "Registrar uma decisão com hipótese, critério e prazo."
        return CycleStory(cycle_id, audience, (
            StoryBlock("Contexto e tensão", context, tuple(context_sources) or ("Consulta do ciclo: diagnóstico e ritual ausentes",)),
            StoryBlock("Decisão e ação", action, tuple(action_sources) or ("Consulta do ciclo: ritual ausente",)),
            StoryBlock("Resultado e aprendizado", result, tuple(result_sources) or (
                f"Consulta da decisão #{ritual.decision.id}: aprendizado não disponível" if ritual
                else "Consulta do ciclo: decisão ausente; aprendizado não consultado",)),
        ), next_step, simulated=simulated)
