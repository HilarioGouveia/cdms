"""Execução idempotente de ingestão com revalidação do solicitante e retentativas."""
from cdms.application.ports.platform_connector import PlatformError


class SyncPlatformMetricsUseCase:
    def __init__(self, repository, connector_factory, vault, authorize):
        self.repo, self.connector_factory, self.vault, self.authorize = repository, connector_factory, vault, authorize

    def execute(self, job_id):
        job = self.repo.claim(job_id)
        if job is None:
            return self.repo.get_job(job_id)
        if not self.authorize(job["requested_by"]):
            return self.repo.fail(job, "ACCESS_REVOKED")
        connection = self.repo.get_connection(job["connection_id"])
        if not connection or not connection["is_active"] or connection["revision"] != job["connection_revision"]:
            return self.repo.fail(job, "CONNECTION_CHANGED")
        try:
            token = self.vault.decrypt(connection["encrypted_credentials"])
            connector = self.connector_factory(connection, token)
            payload = connector.fetch_weekly_metrics(connection["account_id"], job["cycle_id"])
            if not self.authorize(job["requested_by"]):
                return self.repo.fail(job, "ACCESS_REVOKED")
            self.repo.finish(job, payload)
        except PlatformError as exc:
            return self.repo.fail(job, exc.code, retryable=exc.retryable)
        except RuntimeError:
            return self.repo.fail(job, "CREDENTIALS_UNAVAILABLE")
        except ValueError:
            return self.repo.fail(job, "CONNECTION_OR_PERIOD_CHANGED")
        except Exception:
            return self.repo.fail(job, "SYNC_FAILED")
        return self.repo.get_job(job_id)
