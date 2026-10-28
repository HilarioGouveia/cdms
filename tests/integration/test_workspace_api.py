"""Autenticação HTTP e isolamento de dados com dois workspaces reais temporários."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from cdms.adapters.api.main import create_app
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.config.security import create_access_token, get_password_hash, ISSUER, AUDIENCE
from cdms.domain.entities.tenant import UserRole

KEY = "workspace-test-signing-key-with-more-than-32-bytes"
PASSWORD = "An isolated test passphrase 123!"
PREFIX = "/api/v1"


@pytest.fixture(scope="module")
def password_hash():
    # O custo da política de produção é verificado nos testes de segurança; aqui testamos autorização.
    from passlib.hash import pbkdf2_sha256
    return pbkdf2_sha256.using(rounds=1000).hash(PASSWORD)


@pytest.fixture
def api(tmp_path, password_hash, monkeypatch):
    monkeypatch.setattr("cdms.adapters.api.main.get_password_hash", lambda _: password_hash)
    identity_path = tmp_path / "identity.db"
    identity = SQLiteIdentityRepository(identity_path)
    users = {name: identity.create_user(f"{name}@example.com", password_hash, name)
             for name in ("alice", "bob", "member", "viewer", "admin", "outsider")}
    wa = identity.create_workspace("Workspace Alice", "alice", users["alice"]["id"])
    wb = identity.create_workspace("Workspace Bob", "bob", users["bob"]["id"])
    for name, role in (("member", UserRole.MEMBER), ("viewer", UserRole.VIEWER), ("admin", UserRole.ADMIN)):
        identity.set_member(wa, users[name]["id"], role)
    app = create_app(identity_db_path=identity_path, workspace_data_dir=tmp_path / "workspaces", secret_key=KEY)
    with TestClient(app) as client:
        def login(name="alice", workspace=None):
            response = client.post(PREFIX + "/auth/login", json={
                "email": f"{name}@example.com", "password": PASSWORD,
                "workspace_id": workspace or (wb if name == "bob" else wa),
            })
            assert response.status_code == 200, response.text
            return {"Authorization": "Bearer " + response.json()["access_token"]}
        yield SimpleNamespace(client=client, identity=identity, users=users, wa=wa, wb=wb, login=login,
                              root=tmp_path / "workspaces")


def hypothesis(action="Testar CTA"):
    return dict(action_description=action, tested_variable="CTA", target_metric_key="ctr_pct",
                target_metric_unit="%", metric_direction="HIGHER_IS_BETTER", baseline_reference_value="3",
                success_metric_target="5", invalidation_floor="2", expected_impact_description="Aumentar cliques",
                impact_score=8, confidence_score=7, ease_score=9)


def ritual(cycle="2026-10-19", **changes):
    payload = dict(week_start=cycle, snapshots=[
        {"key": "reach", "observed_value": 3000}, {"key": "avg_retention_pct", "observed_value": 45},
        {"key": "ctr_pct", "observed_value": 3}, {"key": "conversions", "observed_value": 20}],
        decision_summary="Ação do workspace", decision_hypothesis="Hipótese causal",
        decision_success_criterion="CTR >= 5%", decision_evaluation_due_date="2026-10-26")
    payload.update(changes)
    return payload


def create_hypothesis(api, headers, action="Testar CTA"):
    response = api.client.post(PREFIX + "/growth/hypotheses", json=hypothesis(action), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_login_and_current_workspace_are_backed_by_membership(api):
    headers = api.login()
    current = api.client.get(PREFIX + "/workspaces/current", headers=headers)
    assert current.status_code == 200
    assert current.json()["id"] == api.wa
    assert current.json()["role"] == "OWNER"
    assert [w["id"] for w in api.client.get(PREFIX + "/workspaces", headers=headers).json()] == [api.wa]
    assert "hashed_password" not in current.text


@pytest.mark.parametrize("case", ["wrong_password", "unknown_email", "other_workspace", "inactive", "demo_login"])
def test_invalid_login_is_rejected_without_account_details(api, case):
    payload = {"email": "alice@example.com", "password": PASSWORD, "workspace_id": api.wa}
    if case == "wrong_password":
        payload["password"] = "Wrong password"
    elif case == "unknown_email":
        payload["email"] = "missing@example.com"
    elif case == "other_workspace":
        payload["workspace_id"] = api.wb
    elif case == "inactive":
        with api.identity.connection() as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (api.users["alice"]["id"],))
    else:
        payload.update(email="creator@cdms.dev", password="Secret123!")
    response = api.client.post(PREFIX + "/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inválidas ou acesso ao workspace indisponível."


@pytest.mark.parametrize("case", ["missing", "expired", "tampered", "wrong_key", "wrong_audience", "missing_exp", "wrong_version"])
def test_invalid_tokens_are_rejected(api, case):
    data = {"sub": api.users["alice"]["id"], "workspace_id": api.wa, "token_version": 0}
    token = create_access_token(data, secret_key=KEY)
    if case == "missing":
        headers = {}
    else:
        if case == "expired":
            token = create_access_token(data, timedelta(seconds=-1), secret_key=KEY)
        elif case == "wrong_key":
            token = create_access_token(data, secret_key="another-signing-key-with-more-than-32-bytes")
        elif case == "tampered":
            header, payload, signature = token.split(".")
            signature = ("A" if signature[0] != "A" else "B") + signature[1:]
            token = ".".join((header, payload, signature))
        elif case in ("wrong_audience", "missing_exp"):
            decoded = jwt.decode(token, KEY, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER)
            if case == "wrong_audience":
                decoded["aud"] = "other-application"
            else:
                del decoded["exp"]
            token = jwt.encode(decoded, KEY, algorithm="HS256")
        elif case == "wrong_version":
            token = create_access_token({**data, "token_version": 42}, secret_key=KEY)
        headers = {"Authorization": "Bearer " + token}
    response = api.client.get(PREFIX + "/workspaces/current", headers=headers)
    assert response.status_code == 401


def test_workspace_cannot_be_changed_by_headers_paths_or_payload(api):
    headers = {**api.login(), "X-Workspace-ID": api.wb}
    assert api.client.get(PREFIX + "/workspaces/current", headers=headers).json()["id"] == api.wa
    payload = {**hypothesis(), "workspace_id": api.wb}
    assert api.client.post(PREFIX + "/growth/hypotheses", json=payload, headers=headers).status_code == 422
    assert api.client.post(PREFIX + "/auth/login", json={"email": "alice@example.com", "password": PASSWORD,
                                                       "workspace_id": "../../cdms_dev"}).status_code == 401


def test_viewer_role_comes_from_database_even_when_token_claims_owner(api):
    token = create_access_token({"sub": api.users["viewer"]["id"], "workspace_id": api.wa, "role": "OWNER"}, secret_key=KEY)
    headers = {"Authorization": "Bearer " + token}
    assert api.client.get(PREFIX + "/growth/hypotheses", headers=headers).status_code == 200
    assert api.client.post(PREFIX + "/growth/hypotheses", headers=headers, json=hypothesis()).status_code == 403


def test_role_changes_and_removal_apply_to_existing_token(api):
    member_headers, owner_headers = api.login("member"), api.login()
    member_id = api.users["member"]["id"]
    url = PREFIX + f"/workspaces/current/members/{member_id}"
    assert api.client.put(url, json={"role": "VIEWER"}, headers=owner_headers).status_code == 204
    assert api.client.post(PREFIX + "/growth/hypotheses", json=hypothesis(), headers=member_headers).status_code == 403
    assert api.client.delete(url, headers=owner_headers).status_code == 204
    assert api.client.get(PREFIX + "/growth/hypotheses", headers=member_headers).status_code == 401


def test_member_cannot_manage_members_and_admin_cannot_promote_admin(api):
    url = PREFIX + f"/workspaces/current/members/{api.users['viewer']['id']}"
    assert api.client.put(url, json={"role": "MEMBER"}, headers=api.login("member")).status_code == 403
    assert api.client.put(url, json={"role": "ADMIN"}, headers=api.login("admin")).status_code == 403
    assert api.client.put(url, json={"role": "OWNER"}, headers=api.login()).status_code == 403
    owner_url = PREFIX + f"/workspaces/current/members/{api.users['alice']['id']}"
    assert api.client.delete(owner_url, headers=api.login()).status_code == 403


def test_logout_revokes_issued_tokens(api):
    first, second = api.login(), api.login()
    assert api.client.post(PREFIX + "/auth/logout", headers=first).status_code == 204
    assert api.client.get(PREFIX + "/workspaces/current", headers=first).status_code == 401
    assert api.client.get(PREFIX + "/workspaces/current", headers=second).status_code == 401
    assert api.client.get(PREFIX + "/workspaces/current", headers=api.login()).status_code == 200


def test_baselines_and_same_cycle_audits_are_isolated(api):
    ha, hb = api.login(), api.login("bob")
    baseline = {"ticket_price": "150", "expected_ctr_pct": "4", "expected_conversion_rate_pct": "8"}
    assert api.client.put(PREFIX + "/growth/baseline", json=baseline, headers=ha).status_code == 200
    assert api.client.get(PREFIX + "/growth/baseline", headers=hb).status_code == 404
    assert api.client.put(PREFIX + "/growth/baseline", json={**baseline, "ticket_price": "300"}, headers=hb).status_code == 200
    payload = {"source_cycle_id": "2026-10-19", "impressions": 10000, "clicks": 300, "conversions": 15}
    a = api.client.post(PREFIX + "/growth/audit-funnel", json=payload, headers=ha)
    b = api.client.post(PREFIX + "/growth/audit-funnel", json=payload, headers=hb)
    assert a.status_code == b.status_code == 200
    assert float(b.json()["total_opportunity_reais"]) == 2 * float(a.json()["total_opportunity_reais"])
    assert float(api.client.get(PREFIX + "/growth/baseline", headers=ha).json()["ticket_price"]) == 150
    assert len(list(api.root.glob("*.db"))) == 2


def test_hypotheses_and_guessed_ids_cannot_cross_workspace(api):
    ha, hb = api.login(), api.login("bob")
    aid = create_hypothesis(api, ha, "Segredo Alice")
    bid = create_hypothesis(api, hb, "Segredo Bob")
    foreign_id = create_hypothesis(api, ha, "Outra hipótese Alice")
    assert aid == bid  # IDs são locais ao workspace.
    assert api.client.get(PREFIX + f"/growth/hypotheses/{bid}", headers=hb).json()["action_description"] == "Segredo Bob"
    assert api.client.get(PREFIX + f"/growth/hypotheses/{foreign_id}", headers=hb).status_code == 404
    response = api.client.post(PREFIX + f"/growth/hypotheses/{foreign_id}/proposal", json={"target_cycle_start": "2026-10-19"}, headers=hb)
    assert response.status_code == 404
    assert "Segredo Alice" not in api.client.get(PREFIX + "/growth/hypotheses", headers=hb).text


def test_ritual_and_linked_hypothesis_lifecycle_are_isolated(api):
    ha, hb = api.login(), api.login("bob")
    hid = create_hypothesis(api, ha)
    assert api.client.post(PREFIX + f"/growth/hypotheses/{hid}/proposal", headers=ha,
                           json={"target_cycle_start": "2026-10-19"}).status_code == 200
    payload = ritual(source_hypothesis_id=hid)
    assert api.client.post(PREFIX + "/rituals", json=payload, headers=hb).status_code == 404
    first = api.client.post(PREFIX + "/rituals", json=payload, headers=ha)
    assert first.status_code == 200, first.text
    assert api.client.post(PREFIX + "/rituals", json=payload, headers=ha).json()["id"] == first.json()["id"]
    assert api.client.get(PREFIX + "/rituals/2026-10-19", headers=hb).status_code == 404
    assert api.client.get(PREFIX + "/rituals", headers=hb).json() == []
    next_payload = ritual("2026-10-26", decision_evaluation_due_date="2026-11-02",
                          target_decision_id=first.json()["decision"]["id"], learning_outcome="ACHIEVED",
                          learning_evidence_notes="CTR observado de 5.5%")
    assert api.client.post(PREFIX + "/rituals", json=next_payload, headers=ha).status_code == 200
    assert api.client.get(PREFIX + f"/growth/hypotheses/{hid}", headers=ha).json()["status"] == "COMPLETED"
    assert "Testar CTA" not in api.client.get(PREFIX + "/growth/reports/2026-10-19", headers=hb).text


@pytest.mark.parametrize("endpoint,payload", [
    ("/growth-v2/allocate-budget", {"hypothesis_id": 1, "cycle_id": "2026-10-19", "amount_reais": 100}),
    ("/growth-v2/evaluate-statistical-significance", {"hypothesis_id": 1, "control_conversions": 10, "control_sample": 100,
                                                  "treatment_conversions": 20, "treatment_sample": 100}),
    ("/growth-v3/optimize-traffic", {"hypothesis_id": 1, "cycle_id": "2026-10-19", "arms": [], "current_cpa_reais": 10,
                                   "current_spend_reais": 10, "max_budget_reais": 100}),
])
def test_advanced_endpoints_reject_foreign_hypotheses(api, endpoint, payload):
    create_hypothesis(api, api.login())
    assert api.client.post(PREFIX + endpoint, json=payload, headers=api.login("bob")).status_code == 404
    assert api.client.post(PREFIX + endpoint, json=payload, headers=api.login("viewer")).status_code == 403


def test_budgets_for_same_local_id_do_not_overwrite_each_other(api):
    ha, hb = api.login(), api.login("bob")
    create_hypothesis(api, ha)
    create_hypothesis(api, hb)
    payload = {"hypothesis_id": 1, "cycle_id": "2026-10-19", "amount_reais": 100}
    assert api.client.post(PREFIX + "/growth-v2/allocate-budget", json=payload, headers=ha).status_code == 200
    assert api.client.post(PREFIX + "/growth-v2/allocate-budget", json={**payload, "amount_reais": 250}, headers=hb).status_code == 200
    assert api.client.get(PREFIX + "/growth-v2/budgets/1", headers=ha).json()["allocated_amount_cents"] == 10000
    assert api.client.get(PREFIX + "/growth-v2/budgets/1", headers=hb).json()["allocated_amount_cents"] == 25000


def test_ai_does_not_invent_audit_from_another_workspace(api):
    response = api.client.post(PREFIX + "/automation/ai-suggestions?source_cycle_id=2026-10-19", headers=api.login())
    assert response.status_code == 404
    assert api.client.get(PREFIX + "/growth/audits", headers=api.login()).json() == []
    response = api.client.post(PREFIX + "/automation/connect-platform", json={"platform": "YOUTUBE_STUDIO", "account_id": "UC-test", "access_token": "test-only-token"}, headers=api.login())
    assert response.status_code == 501


@pytest.mark.parametrize("key", ["", "short", "cdms-super-secret-key-production-change-me"])
def test_api_refuses_missing_or_demonstration_signing_key(tmp_path, key):
    with pytest.raises(RuntimeError, match="chave|CDMS_SECRET_KEY"):
        with TestClient(create_app(identity_db_path=tmp_path / "identity.db", secret_key=key)):
            pass


def test_password_change_revokes_old_tokens_and_requires_current_password(api):
    headers = api.login()
    new_password = "A new workspace passphrase 456!"
    response = api.client.post(PREFIX + "/auth/password", headers=headers,
                               json={"current_password": "wrong", "new_password": new_password})
    assert response.status_code == 401
    assert api.client.post(PREFIX + "/auth/password", headers=headers,
                           json={"current_password": PASSWORD, "new_password": new_password}).status_code == 204
    assert api.client.get(PREFIX + "/workspaces/current", headers=headers).status_code == 401
    payload = {"email": "alice@example.com", "password": new_password, "workspace_id": api.wa}
    assert api.client.post(PREFIX + "/auth/login", json=payload).status_code == 200
    assert api.client.post(PREFIX + "/auth/login", json={**payload, "password": PASSWORD}).status_code == 401


def test_deactivation_rejects_previously_issued_token(api):
    headers = api.login()
    with api.identity.connection() as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (api.users["alice"]["id"],))
    assert api.client.get(PREFIX + "/workspaces/current", headers=headers).status_code == 401


def test_calibration_and_identical_ritual_cycles_are_isolated(api):
    ha, hb = api.login(), api.login("bob")
    payload = {"metric_key": "ctr_pct", "healthy_min": 10, "healthy_max": 20}
    assert api.client.put(PREFIX + "/rituals/calibrations", json=payload, headers=ha).status_code == 200
    assert api.client.get(PREFIX + "/rituals/calibrations", headers=hb).json() == []
    a = api.client.post(PREFIX + "/rituals", json=ritual(decision_summary="Alice action"), headers=ha)
    b = api.client.post(PREFIX + "/rituals", json=ritual(decision_summary="Bob action"), headers=hb)
    assert a.status_code == b.status_code == 200
    assert api.client.get(PREFIX + "/rituals/2026-10-19", headers=ha).json()["decision"]["summary"] == "Alice action"
    assert api.client.get(PREFIX + "/rituals/2026-10-19", headers=hb).json()["decision"]["summary"] == "Bob action"


def test_legacy_bcrypt_password_is_supported(api):
    from passlib.hash import bcrypt
    with api.identity.connection() as conn:
        conn.execute("UPDATE users SET hashed_password = ? WHERE id = ?", (bcrypt.hash(PASSWORD), api.users["alice"]["id"]))
    assert api.client.get(PREFIX + "/workspaces/current", headers=api.login()).status_code == 200


def test_all_business_routes_require_authentication_and_viewer_cannot_write(api):
    viewer = api.login("viewer")
    for path, methods in api.client.app.openapi()["paths"].items():
        if path in ("/health", PREFIX + "/auth/login"):
            continue
        concrete = path.replace("{cycle_id}", "2026-10-19").replace("{hypothesis_id}", "1")
        concrete = concrete.replace("{user_id}", api.users["member"]["id"])
        for method in methods:
            if method not in ("get", "post", "put", "delete"):
                continue
            response = api.client.request(method, concrete, json={} if method in ("post", "put") else None)
            assert response.status_code == 401, (method, concrete, response.text)
            if method != "get" and not path.startswith(PREFIX + "/auth/"):
                response = api.client.request(method, concrete, headers=viewer, json={} if method in ("post", "put") else None)
                assert response.status_code == 403, (method, concrete, response.text)


def test_statistics_and_optimization_use_workspace_store(api):
    ha, hb = api.login(), api.login("bob")
    create_hypothesis(api, ha)
    stats = {"hypothesis_id": 1, "control_conversions": 10, "control_sample": 200,
             "treatment_conversions": 20, "treatment_sample": 200}
    response = api.client.post(PREFIX + "/growth-v2/evaluate-statistical-significance", json=stats, headers=ha)
    assert response.status_code == 200, response.text
    assert api.client.get(PREFIX + "/growth-v2/evaluations/1", headers=ha).status_code == 200
    assert api.client.get(PREFIX + "/growth-v2/evaluations/1", headers=hb).status_code == 404
    optimization = {"hypothesis_id": 1, "cycle_id": "2026-10-19", "current_cpa_reais": 10,
                    "max_allowed_cpa_reais": 50, "current_spend_reais": 100, "max_budget_reais": 500,
                    "arms": [{"arm_id": "control", "variable_name": "CTA original", "total_impressions": 200, "total_conversions": 10},
                             {"arm_id": "treatment", "variable_name": "CTA novo", "total_impressions": 200, "total_conversions": 20}]}
    response = api.client.post(PREFIX + "/growth-v3/optimize-traffic", json=optimization, headers=ha)
    assert response.status_code == 200, response.text
    assert api.client.get(PREFIX + "/growth-v3/allocations/1", headers=ha).status_code == 200
    assert api.client.get(PREFIX + "/growth-v3/allocations/1", headers=hb).status_code == 404


def test_inactive_owner_cannot_be_removed_or_demoted_by_admin(api):
    headers = api.login("admin")
    owner_id = api.users["alice"]["id"]
    with api.identity.connection() as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (owner_id,))
    url = PREFIX + f"/workspaces/current/members/{owner_id}"
    assert api.client.delete(url, headers=headers).status_code == 403
    assert api.client.put(url, json={"role": "MEMBER"}, headers=headers).status_code == 403
