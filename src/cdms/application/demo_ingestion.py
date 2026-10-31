"""Simulador Meta offline: nunca instancia conector, cofre ou dispatcher real."""
from datetime import date,timedelta
from pathlib import Path
from uuid import UUID
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository


def demo_payload(cycle, snapshots=None):
    metrics={'reach':2400,'impressions':4000,'inline_link_clicks':120,'ctr_pct':'3.0',
             'conversions':8,'avg_retention_pct':None,'spend':'125.00'}
    if snapshots:
        values={s.definition.key:s.observed_value for s in snapshots}
        for key in ('reach','conversions'):
            metrics[key]=int(values[key]) if values[key] is not None else None
        metrics['impressions']=max(metrics['impressions'],metrics['reach'] or 0)
        metrics['ctr_pct']=str(values['ctr_pct']) if values['ctr_pct'] is not None else None
        metrics['inline_link_clicks']=int(metrics['impressions']*float(metrics['ctr_pct'])/100) if metrics['ctr_pct'] is not None else 0
        if all(value is None for value in values.values()):
            metrics.update(impressions=0,inline_link_clicks=0,spend='0.00')
    start=date.fromisoformat(cycle)
    return {'simulated':True,'platform':'META_ADS','account_id':'act_000000001',
            'cycle_id':cycle,'period_start':cycle,'period_end':(start+timedelta(days=6)).isoformat(),
            'timezone_name':'America/Sao_Paulo','currency':'BRL','api_version':'SIMULATED',
            'conversion_action_type':'SIMULATED_PURCHASE','click_definition':'inline_link_clicks',
            'attribution':'simulada','metrics':metrics,
            'unavailability_reasons':{key:'NOT_SUPPORTED' if key=='avg_retention_pct' else 'NO_DATA'
                                     for key,value in metrics.items() if value is None}}


def finish_demo_job(repo,job,payload):
    claimed=repo.claim(job['id'])
    if claimed:
        payload={**payload,'account_id':repo.get_connection(job['connection_id'])['account_id']}
        repo.finish(claimed,payload)
    return repo.get_job(job['id'])


class DemoPlatformIngestion:
    def __init__(self,path,demo_root):
        path=Path(path).resolve()
        if not path.is_relative_to(Path(demo_root).resolve()) or path.suffix!='.db':
            raise ValueError('A simulação exige um banco exclusivo do Demo.')
        UUID(path.stem)
        UUID(path.parent.name)
        self.repo=SQLiteIngestionRepository(path)

    def enqueue(self,connection_id,cycle_id,retry_failed=False,force_refresh=False):
        start=date.fromisoformat(cycle_id)
        if start.weekday()!=0:
            raise ValueError('Escolha uma segunda-feira para o cenário simulado.')
        if retry_failed and force_refresh:
            raise ValueError('Escolha retentativa ou nova versão.')
        job,changed=self.repo.enqueue(connection_id,cycle_id,'demo',retry_failed=retry_failed,force_refresh=force_refresh)
        if changed:
            job=finish_demo_job(self.repo,job,demo_payload(cycle_id))
        return job,'SIMULATED' if changed else 'EXISTING'

    def complete_pending(self,job_id):
        job=self.repo.get_job(job_id)
        if not job or job['status']!='PENDING':
            raise ValueError('Selecione uma coleta pendente simulada.')
        return finish_demo_job(self.repo,job,demo_payload(job['cycle_id']))

    def prepare_ritual(self,job_id,core_repository):
        job=self.repo.get_job(job_id)
        if not job or job['status']!='SUCCESS':
            raise ValueError('Selecione uma coleta simulada concluída.')
        if core_repository.get_ritual_by_cycle(job['cycle_id']):
            raise ValueError('O ritual deste ciclo já foi encerrado.')
        payload=self.repo.get_batch(job_id)
        if not payload or payload.get('simulated') is not True:
            raise ValueError('O resultado não pertence à simulação.')
        self.repo.record_ritual_source(job_id,job['cycle_id'],'demo')
        return payload
