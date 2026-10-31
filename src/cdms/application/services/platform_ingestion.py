"""Orquestração de conexões e fila compartilhada pela API e pelo Studio."""
import json
from cdms.adapters.connectors.meta_ads import MetaAdsConnector, closed_week
from cdms.domain.entities.tenant import UserRole


class PlatformIngestion:
    def __init__(self, repo, identity, tenant, connector_factory, vault_factory, dispatcher):
        self.repo, self.identity, self.tenant = repo, identity, tenant
        self.connector_factory, self.vault_factory, self.dispatcher = connector_factory, vault_factory, dispatcher

    def authorize(self, manager=False):
        current=self.identity.get_tenant(self.tenant.user_id,self.tenant.workspace_id)
        user=self.identity.get_user(self.tenant.user_id)
        if not current or user['must_change_password'] or current.role == UserRole.VIEWER or (manager and current.role not in (UserRole.ADMIN,UserRole.OWNER)):
            raise ValueError('Seu perfil não permite esta operação.')

    def connect(self, account_id, access_token, api_version, conversion_action_type, app_secret=None, automatic_sync=False):
        self.authorize(manager=True)
        MetaAdsConnector.account_id(account_id)
        for value in (access_token,app_secret):
            if value is not None and (not value or len(value)>4096 or not value.isascii() or any(c.isspace() for c in value)):
                raise ValueError('Credencial da plataforma inválida.')
        MetaAdsConnector(access_token,api_version=api_version,conversion_action_type=conversion_action_type)
        vault=self.vault_factory()
        credentials=json.dumps({'access_token':access_token,'app_secret':app_secret}) if app_secret else access_token
        connection={'platform':'META_ADS','api_version':api_version,'timezone_name':'UTC','conversion_action_type':conversion_action_type}
        metadata=self.connector_factory(connection,credentials).validate_account(account_id)
        self.authorize(manager=True)
        return self.repo.save_connection(account_id=account_id,encrypted_credentials=vault.encrypt(credentials),
            api_version=api_version,conversion_action_type=conversion_action_type,timezone_name=metadata['timezone_name'],
            currency=metadata['currency'],created_by=self.tenant.user_id,automatic_sync=automatic_sync)

    def deactivate(self, connection_id):
        self.authorize(manager=True)
        if not self.repo.deactivate(connection_id):
            raise ValueError('Conexão não encontrada neste workspace.')

    def enqueue(self, connection_id, cycle_id, retry_failed=False, force_refresh=False):
        self.authorize()
        if retry_failed and force_refresh:
            raise ValueError('Escolha retentativa ou atualização, não ambas.')
        connection=self.repo.get_connection(connection_id)
        if not connection:
            raise ValueError('Conexão não encontrada neste workspace.')
        closed_week(cycle_id,connection['timezone_name'])
        job,changed=self.repo.enqueue(connection_id,cycle_id,self.tenant.user_id,retry_failed=retry_failed,force_refresh=force_refresh)
        status='EXISTING'
        if changed:
            try:
                self.dispatcher(self.tenant.workspace_id,job['id'])
                status='ENQUEUED'
            except Exception:
                status='DEFERRED'
        return job,status

    def prepare_ritual(self, job_id, core_repository):
        self.authorize()
        job=self.repo.get_job(job_id)
        if not job or job['status'] != 'SUCCESS':
            raise ValueError('Selecione uma sincronização concluída neste workspace.')
        result=self.repo.get_batch(job_id)
        if not result or result['cycle_id'] != job['cycle_id']:
            raise ValueError('Resultado incompatível com o ciclo da sincronização.')
        if core_repository.get_ritual_by_cycle(job['cycle_id']):
            raise ValueError('O ritual deste ciclo já foi encerrado e não pode ser sobrescrito.')
        self.repo.record_ritual_source(job_id,job['cycle_id'],self.tenant.user_id)
        return result
