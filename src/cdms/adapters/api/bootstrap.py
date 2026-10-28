"""Provisionamento administrativo local. A senha é solicitada sem eco no terminal."""
import argparse
from getpass import getpass
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from pydantic import EmailStr, TypeAdapter
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.config.security import get_password_hash, verify_password
from cdms.config.workspace_storage import identity_db_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--identity-db", type=Path, default=identity_db_path())
    args = parser.parse_args()
    email = str(TypeAdapter(EmailStr).validate_python(args.email))
    password = getpass("Senha (mínimo 12 caracteres): ")
    if len(password) < 12 or len(password) > 1024:
        parser.error("A senha deve ter entre 12 e 1024 caracteres.")
    repo = SQLiteIdentityRepository(args.identity_db)
    user = repo.get_user_by_email(email)
    if user:
        if not user["is_active"] or not verify_password(password, user["hashed_password"]):
            parser.error("Credenciais inválidas para o usuário existente.")
    else:
        if password != getpass("Confirme a senha: "):
            parser.error("As senhas não coincidem.")
        user = repo.create_user(email, get_password_hash(password), args.name)
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", args.workspace.casefold()).strip("-") + "-" + uuid4().hex[:8]
    try:
        workspace_id = repo.create_workspace(args.workspace, slug, user["id"])
    except sqlite3.IntegrityError:
        parser.error("Não foi possível criar o workspace; verifique se o slug já existe.")
    print(f"Usuário: {user['id']}")
    print(f"Workspace: {workspace_id}")


if __name__ == "__main__":
    main()
