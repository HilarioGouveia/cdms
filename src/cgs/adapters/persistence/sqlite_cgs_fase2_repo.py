"""Orçamento transacional por ciclo e avaliações imutáveis, sem importação do modelo legado."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone, date
from decimal import Decimal
import json
import sqlite3
from cgs.application.ports.cgs_fase2_repository import CGSPhase2RepositoryPort
from cgs.domain.entities.budget_allocation import BudgetAllocation, ExperimentRiskTier
from cgs.domain.entities.statistical_validation import BayesianExperimentEvaluation, StatisticalSignificanceVerdict


def cycle_key(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Ciclo inválido.') from None
    if value != parsed.isoformat() or parsed.weekday() != 0:
        raise ValueError('O ciclo deve começar numa segunda-feira.')
    return parsed.isoformat()


class SQLiteCGSPhase2Repository(CGSPhase2RepositoryPort):
    def __init__(self, db_path='data/cdms_dev.db'):
        self.db_path = str(db_path)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self):
        with self._get_connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS experiment_budgets (
                hypothesis_id INTEGER NOT NULL, cycle_id TEXT NOT NULL,
                allocated_amount_cents INTEGER NOT NULL, spent_amount_cents INTEGER NOT NULL DEFAULT 0,
                risk_tier TEXT NOT NULL, max_cpa_target_cents INTEGER, created_at TEXT NOT NULL,
                PRIMARY KEY(hypothesis_id,cycle_id));
            CREATE TABLE IF NOT EXISTS experiment_cycle_limits (cycle_id TEXT PRIMARY KEY, limit_cents INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS experiment_budget_events (
                id INTEGER PRIMARY KEY, hypothesis_id INTEGER, cycle_id TEXT NOT NULL,
                actor TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiment_evaluations (
                id INTEGER PRIMARY KEY, hypothesis_id INTEGER NOT NULL, cycle_id TEXT,
                actor TEXT, payload TEXT NOT NULL, evaluated_at TEXT NOT NULL);
            """)
    @staticmethod
    def _budget(row):
        return BudgetAllocation(row['hypothesis_id'],row['cycle_id'],row['allocated_amount_cents'],
            row['spent_amount_cents'],ExperimentRiskTier(row['risk_tier']),row['max_cpa_target_cents'],
            datetime.fromisoformat(row['created_at'])) if row else None

    def get_budget_by_hypothesis(self, hypothesis_id, cycle_id=None):
        with self._get_connection() as c:
            row = c.execute('SELECT * FROM experiment_budgets WHERE hypothesis_id=?' +
                            (' AND cycle_id=?' if cycle_id else '') + ' ORDER BY cycle_id DESC LIMIT 1',
                            (hypothesis_id,cycle_id) if cycle_id else (hypothesis_id,)).fetchone()
            return self._budget(row)

    def list_budgets_by_cycle(self, cycle_id):
        with self._get_connection() as c:
            return [self._budget(r) for r in c.execute('SELECT * FROM experiment_budgets WHERE cycle_id=?',(cycle_id,))]

    def get_cycle_limit(self, cycle_id, default=500000):
        with self._get_connection() as c:
            row = c.execute('SELECT limit_cents FROM experiment_cycle_limits WHERE cycle_id=?',(cycle_id,)).fetchone()
            return row[0] if row else default

    def set_cycle_limit(self, cycle_id, limit_cents, actor=None):
        cycle_id = cycle_key(cycle_id)
        if type(limit_cents) is not int or limit_cents <= 0:
            raise ValueError('O teto deve ser positivo.')
        with self._get_connection() as c:
            c.execute('BEGIN IMMEDIATE')
            total = c.execute('SELECT COALESCE(SUM(allocated_amount_cents),0) FROM experiment_budgets WHERE cycle_id=?',(cycle_id,)).fetchone()[0]
            if limit_cents < total:
                raise ValueError('O teto não pode ficar abaixo do orçamento já comprometido.')
            c.execute('INSERT INTO experiment_cycle_limits VALUES (?,?) ON CONFLICT(cycle_id) DO UPDATE SET limit_cents=excluded.limit_cents',(cycle_id,limit_cents))
            self._event(c,None,cycle_id,actor,{'limit_cents':limit_cents})

    @staticmethod
    def _event(c,hypothesis_id,cycle_id,actor,payload):
        c.execute('INSERT INTO experiment_budget_events (hypothesis_id,cycle_id,actor,payload,created_at) VALUES (?,?,?,?,?)',
                  (hypothesis_id,cycle_id,actor,json.dumps(payload,default=str),datetime.now(timezone.utc).isoformat()))

    def save_budget_allocation(self, allocation, max_cycle_budget_cents=500000, actor=None):
        cycle_key(allocation.cycle_id)
        with self._get_connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT limit_cents FROM experiment_cycle_limits WHERE cycle_id=?',(allocation.cycle_id,)).fetchone()
            limit = row[0] if row else max_cycle_budget_cents
            committed = c.execute('SELECT COALESCE(SUM(allocated_amount_cents),0) FROM experiment_budgets WHERE cycle_id=? AND hypothesis_id!=?',(allocation.cycle_id,allocation.hypothesis_id)).fetchone()[0]
            if committed + allocation.allocated_amount_cents > limit:
                raise ValueError(f"Teto orçamentário do ciclo '{allocation.cycle_id}' excedido. Disponível: R$ {(limit-committed)/100:.2f}")
            c.execute("""INSERT INTO experiment_budgets VALUES (?,?,?,?,?,?,?) ON CONFLICT(hypothesis_id,cycle_id)
                DO UPDATE SET allocated_amount_cents=excluded.allocated_amount_cents,
                risk_tier=excluded.risk_tier,max_cpa_target_cents=excluded.max_cpa_target_cents""",
                (allocation.hypothesis_id,allocation.cycle_id,allocation.allocated_amount_cents,allocation.spent_amount_cents,
                 allocation.risk_tier.value,allocation.max_cpa_target_cents,allocation.created_at.isoformat()))
            self._event(c,allocation.hypothesis_id,allocation.cycle_id,actor,{'allocated_cents':allocation.allocated_amount_cents,'risk':allocation.risk_tier.value,'cpa_cents':allocation.max_cpa_target_cents})
        return self.get_budget_by_hypothesis(allocation.hypothesis_id,allocation.cycle_id)

    def record_spend(self,hypothesis_id,cycle_id,spent_cents,actor=None):
        if type(spent_cents) is not int or spent_cents < 0:
            raise ValueError('Gasto inválido.')
        with self._get_connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT spent_amount_cents FROM experiment_budgets WHERE hypothesis_id=? AND cycle_id=?',(hypothesis_id,cycle_id)).fetchone()
            if not row:
                raise ValueError('Cadastre o orçamento antes de registrar o gasto.')
            if spent_cents < row[0]:
                raise ValueError('O gasto acumulado não pode diminuir.')
            if spent_cents != row[0]:
                c.execute('UPDATE experiment_budgets SET spent_amount_cents=? WHERE hypothesis_id=? AND cycle_id=?',(spent_cents,hypothesis_id,cycle_id))
                self._event(c,hypothesis_id,cycle_id,actor,{'spent_cents':spent_cents})

    def budget_history(self,cycle_id):
        with self._get_connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM experiment_budget_events WHERE cycle_id=? ORDER BY id DESC',(cycle_id,))]

    def save_statistical_evaluation(self,evaluation,actor=None):
        if evaluation.cycle_id:
            cycle_key(evaluation.cycle_id)
        with self._get_connection() as c:
            c.execute('INSERT INTO experiment_evaluations (hypothesis_id,cycle_id,actor,payload,evaluated_at) VALUES (?,?,?,?,?)',
                (evaluation.hypothesis_id,evaluation.cycle_id,actor,json.dumps(asdict(evaluation),default=str),evaluation.evaluated_at.isoformat()))

    @staticmethod
    def _evaluation(row):
        if not row:
            return None
        data=json.loads(row['payload'])
        for key in ('probability_to_beat_control','lift_pct','sample_adequacy_ratio','difference_low_pp','difference_high_pp','significance_threshold_pct'):
            if key in data and data[key] is not None:
                data[key]=Decimal(data[key])
        data['verdict']=StatisticalSignificanceVerdict(data['verdict'])
        data['evaluated_at']=datetime.fromisoformat(data['evaluated_at'])
        return BayesianExperimentEvaluation(**data)

    def get_evaluation_by_hypothesis(self,hypothesis_id,cycle_id=None):
        history=self.evaluation_history(hypothesis_id,cycle_id)
        return history[0] if history else None

    def evaluation_history(self,hypothesis_id,cycle_id=None):
        with self._get_connection() as c:
            rows=c.execute('SELECT * FROM experiment_evaluations WHERE hypothesis_id=?'+(' AND cycle_id=?' if cycle_id else '')+' ORDER BY id DESC',
                           (hypothesis_id,cycle_id) if cycle_id else (hypothesis_id,)).fetchall()
            return [self._evaluation(row) for row in rows]

    def cycle_evaluations(self,cycle_id):
        with self._get_connection() as c:
            rows=c.execute('SELECT * FROM experiment_evaluations WHERE id IN (SELECT MAX(id) FROM experiment_evaluations WHERE cycle_id=? GROUP BY hypothesis_id) ORDER BY id DESC',(cycle_id,)).fetchall()
            return [self._evaluation(row) for row in rows]
