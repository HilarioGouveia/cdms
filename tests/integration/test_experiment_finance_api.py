from test_workspace_api import api,password_hash,create_hypothesis,PREFIX


def test_api_budget_spend_limits_and_ab_history_are_isolated(api):
    owner=api.login()
    hid=create_hypothesis(api,owner)
    cycle='2026-10-19'
    root=PREFIX+'/growth-v2'
    payload={'hypothesis_id':hid,'cycle_id':cycle,'amount_reais':80}
    response=api.client.put(root+f'/cycles/{cycle}/limit',headers=owner,json={'amount_reais':100})
    assert response.status_code==204,response.text
    assert api.client.post(root+'/allocate-budget',headers=owner,json=payload).status_code==200
    assert api.client.put(root+f'/budgets/{hid}/cycles/{cycle}/spend',headers=owner,json={'amount_reais':90}).status_code==204
    assert api.client.post(root+'/allocate-budget',headers=owner,json={**payload,'amount_reais':95}).status_code==200
    assert api.client.get(root+f'/budgets/{hid}?cycle_id={cycle}',headers=owner).json()['spent_amount_cents']==9000
    assert api.client.put(root+f'/cycles/{cycle}/limit',headers=api.login('member'),json={'amount_reais':200}).status_code==403
    assert api.client.post(root+'/allocate-budget',headers=api.login('viewer'),json=payload).status_code==403
    assert api.client.get(root+f'/budgets/{hid}',headers=api.login('bob')).status_code==404
    evaluation={'hypothesis_id':hid,'cycle_id':cycle,'control_conversions':0,'control_sample':100,
                'treatment_conversions':20,'treatment_sample':100,'event_definition':'Compra por visitante'}
    response=api.client.post(root+'/evaluate-statistical-significance',headers=owner,json=evaluation)
    assert response.status_code==200,response.text
    assert response.json()['lift_pct'] is None
    assert response.json()['method']=='beta-binomial-mc-v1'
    assert api.client.post(root+'/evaluate-statistical-significance',headers=owner,json={**evaluation,'control_conversions':10}).status_code==200
    history=api.client.get(root+f'/evaluations/{hid}/history?cycle_id={cycle}',headers=owner).json()
    assert len(history)==2
    assert history[0]['control_conversions']==10
    assert history[1]['control_conversions']==0
    assert api.client.post(root+'/evaluate-statistical-significance',headers=owner,json={**evaluation,'treatment_conversions':101}).status_code==400
    from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
    from cdms.config.workspace_storage import workspace_db_path
    growth=SQLiteGrowthRepository(str(workspace_db_path(api.root,api.wa)))
    hypothesis=growth.get_hypothesis_by_id(hid)
    hypothesis.discard()
    growth.save_hypothesis(hypothesis)
    assert api.client.post(root+'/allocate-budget',headers=owner,json=payload).status_code==400
    assert api.client.put(root+f'/budgets/{hid}/cycles/{cycle}/spend',headers=owner,json={'amount_reais':95}).status_code==204
