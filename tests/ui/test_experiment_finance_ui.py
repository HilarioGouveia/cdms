from datetime import date
from decimal import Decimal
from cryptography.fernet import Fernet
from test_studio_auth import account, app, login
from cdms.config.workspace_storage import workspace_db_path
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.domain.entities.hypothesis import VariableType, MetricDirection
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.domain.entities.tenant import UserRole


def create_hypothesis(account):
    root=account[5]
    path=workspace_db_path(root,account[2])
    path.parent.mkdir(parents=True,exist_ok=True)
    growth=SQLiteGrowthRepository(str(path))
    h=ManageHypothesesUseCase(growth).create_hypothesis('Testar CTA',VariableType.CTA,'ctr_pct','%',
        MetricDirection.HIGHER_IS_BETTER,Decimal('3'),Decimal('5'),Decimal('2'),'Aumentar cliques',8,8,8)
    return path,h


def test_budget_and_ab_forms_save_per_workspace_and_show_history(account):
    path,h=create_hypothesis(account)
    at=app()
    login(at)
    at.date_input(key='studio_cycle').set_value(date(2026,10,19)).run()
    at.button(key='studio_nav_Experimentos').click().run()
    at.button(key='studio_page_budget').click().run()
    assert not at.exception
    next(b for b in at.button if b.label=='Salvar alocação').click().run()
    assert not at.exception
    repo=SQLiteCGSPhase2Repository(path)
    assert repo.get_budget_by_hypothesis(h.id,'2026-10-19').allocated_amount_cents==10000
    next(n for n in at.number_input if n.label=='Gasto acumulado real (R$)').set_value(40.0)
    next(b for b in at.button if b.label=='Registrar gasto').click().run()
    assert not at.exception
    assert repo.get_budget_by_hypothesis(h.id,'2026-10-19').spent_amount_cents==4000
    at.button(key='studio_page_ab_evaluation').click().run()
    next(c for c in at.checkbox if c.label.startswith('Conferi')).check()
    next(b for b in at.button if b.label=='Avaliar e salvar').click().run()
    assert not at.exception
    assert repo.get_evaluation_by_hypothesis(h.id,'2026-10-19')
    at.selectbox(key='account_workspace').set_value(account[3]).run()
    at.button(key='studio_nav_Experimentos').click().run()
    at.button(key='studio_page_budget').click().run()
    assert not any(b.label=='Salvar alocação' for b in at.button)


def test_viewer_cannot_write_finance_or_configure_meta(account):
    path,h=create_hypothesis(account)
    account[0].set_member(account[2],account[1]['id'],UserRole.VIEWER)
    at=app()
    login(at)
    at.button(key='studio_nav_Experimentos').click().run()
    for page in ('budget','ab_evaluation'):
        at.button(key='studio_page_'+page).click().run()
        assert not at.exception
        assert not any(b.label in ('Salvar alocação','Salvar teto','Registrar gasto','Avaliar e salvar') for b in at.button)
    assert not any(b.key=='studio_nav_Configurações' for b in at.button)


def test_completed_meta_batch_prefills_only_ritual_draft(account):
    path,_=create_hypothesis(account)
    repo=SQLiteIngestionRepository(path)
    c=repo.save_connection(account_id='act_123',encrypted_credentials='not-read-in-test',api_version='v26.0',
        conversion_action_type='purchase',timezone_name='America/Sao_Paulo',currency='BRL',created_by=account[1]['id'])
    job,_=repo.enqueue(c['id'],'2026-10-19',account[1]['id'])
    claimed=repo.claim(job['id'])
    repo.finish(claimed,{'platform':'META_ADS','account_id':'act_123','cycle_id':'2026-10-19',
        'period_start':'2026-10-19','period_end':'2026-10-25','timezone_name':'America/Sao_Paulo','currency':'BRL',
        'metrics':{'reach':2000,'avg_retention_pct':None,'ctr_pct':'3.0','conversions':4},
        'unavailability_reasons':{'avg_retention_pct':'NOT_SUPPORTED'}})
    at=app()
    login(at)
    at.date_input(key='studio_cycle').set_value(date(2026,10,19)).run()
    assert not at.exception
    at.checkbox(key='meta_review_'+job['id']).check().run()
    at.button(key='meta_apply').click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state['studio_section']=='Governança'
    assert at.number_input(key='val_reach').value==2000
    assert not at.checkbox(key='avail_avg_retention_pct').value
    from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
    assert SQLiteRepository(path).get_ritual_by_cycle('2026-10-19') is None
    assert repo.ritual_source('2026-10-19')['job_id']==job['id']


def test_meta_configuration_encrypts_token_and_queue_failure_keeps_job(account,monkeypatch):
    from types import SimpleNamespace
    from cdms.adapters.tasks import ingestion_runtime
    from cdms.config.credential_vault import CredentialVault
    monkeypatch.setenv('CDMS_CREDENTIAL_KEY',Fernet.generate_key().decode())
    monkeypatch.setattr(ingestion_runtime,'meta_connector_factory',lambda connection,token:
        SimpleNamespace(validate_account=lambda account_id:{'timezone_name':'America/Sao_Paulo','currency':'BRL'}))
    def offline(*args):
        raise RuntimeError('broker offline')
    monkeypatch.setattr(ingestion_runtime,'dispatch_job',offline)
    at=app()
    login(at)
    at.button(key='studio_nav_Configurações').click().run()
    at.button(key='studio_page_integrations').click().run()
    assert not at.exception
    next(t for t in at.text_input if t.label=='ID da conta Meta').set_value('act_123')
    next(t for t in at.text_input if t.label=='Token de acesso Meta').set_value('private-test-token')
    next(c for c in at.checkbox if c.label.startswith('Autorizo')).check()
    next(b for b in at.button if b.label=='Validar e salvar conexão').click().run()
    assert not at.exception
    path=workspace_db_path(account[5],account[2])
    repo=SQLiteIngestionRepository(path)
    stored=repo.list_connections()[0]
    assert CredentialVault().decrypt(stored['encrypted_credentials'])=='private-test-token'
    assert b'private-test-token' not in path.read_bytes()
    at.button(key='studio_nav_Cockpit').click().run()
    at.date_input(key='studio_cycle').set_value(date(2026,10,19)).run()
    next(b for b in at.button if b.label=='Solicitar sincronização').click().run()
    assert not at.exception
    assert repo.list_jobs()[0]['status']=='PENDING'
    assert any('envio à fila está pendente' in w.value for w in at.warning)


def test_evidence_inspector_tracks_hypothesis_cycle_and_workspace(account):
    path,h=create_hypothesis(account)
    repo=SQLiteCGSPhase2Repository(path)
    from cgs.domain.entities.budget_allocation import BudgetAllocation
    from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer
    repo.save_budget_allocation(BudgetAllocation(h.id,'2026-10-19',15000))
    repo.save_statistical_evaluation(BayesianExperimentAnalyzer.evaluate(h.id,20,1000,40,1000,cycle_id='2026-10-19'))
    at=app()
    login(at)
    assert not at.session_state['studio_evidence']
    at.date_input(key='studio_cycle').set_value(date(2026,10,19)).run()
    at.button(key='studio_nav_Experimentos').click().run()
    at.button(key='studio_page_backlog').click().run()
    at.button(key=f'evidence_hypothesis_{h.id}').click().run()
    assert not at.exception
    assert at.session_state['studio_evidence']
    assert any('Probabilidade de ganho:' in m.value for m in at.markdown)
    assert any('150.00' in m.value for m in at.markdown)
    at.button(key='evidence_close').click().run()
    assert not at.session_state['studio_evidence']
    at.button(key='studio_page_budget').click().run()
    next(n for n in at.number_input if n.label=='Valor alocado (R$)').set_value(175.0)
    at.button(key='studio_toggle_evidence').click().run()
    assert not at.exception
    assert next(n for n in at.number_input if n.label=='Valor alocado (R$)').value==175.0
    assert any('150.00' in m.value for m in at.markdown)
    at.date_input(key='studio_cycle').set_value(date(2026,10,26)).run()
    assert not at.exception
    assert not any('150.00' in m.value for m in at.markdown)
    at.selectbox(key='account_workspace').set_value(account[3]).run()
    at.button(key='studio_toggle_evidence').click().run()
    assert not at.exception
    assert not any('Testar CTA' in m.value or '150.00' in m.value for m in at.markdown)
