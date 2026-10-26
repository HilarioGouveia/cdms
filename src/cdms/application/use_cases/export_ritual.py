from cdms.application.ports.repository import RepositoryPort

class ExportRitualUseCase:
    """Gera o relatório executivo formatado em Markdown a partir do registro persistido."""

    def __init__(self, repo: RepositoryPort):
        self.repo = repo

    def execute_markdown(self, cycle_id: str) -> str:
        ritual = self.repo.get_ritual_by_cycle(cycle_id)
        if not ritual:
            raise ValueError(f"Ritual do ciclo '{cycle_id}' não encontrado para exportação.")
        ...
        return "\n".join(lines)