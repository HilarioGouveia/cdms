# Etapa 4 — Autenticação real e isolamento por workspace na API

## Arquitetura adotada

A API usa um banco central de identidade (`data/identity.db`) e um banco operacional por workspace (`data/workspaces/<uuid-sem-hifens>.db`). Os UUIDs são gerados pelo servidor. Após validar o JWT e o vínculo atual do usuário, a dependência de armazenamento escolhe o banco desse workspace. Nenhum caminho é recebido do cliente.

Esta implementação usa isolamento físico por arquivo, em vez de acrescentar filtros `workspace_id` a cada consulta dos repositórios locais. Assim, baseline ativa, IDs de hipóteses e decisões, ciclos semanais, orçamento e estatísticas permanecem independentes entre workspaces, incluindo casos em que os IDs numéricos ou datas coincidem.

O banco local `data/cdms_dev.db` não é importado nem atribuído automaticamente a um proprietário. O Streamlit continua no modo local. Autenticação da interface Streamlit, migração de dados locais para um workspace e isolamento lógico em um banco compartilhado não fazem parte desta etapa.

## Configuração e primeiro acesso

Instale o projeto com os extras de API e desenvolvimento:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api,automation]"
```

Gere uma chave para a sessão atual do PowerShell e mantenha uma cópia protegida para reutilizar nos próximos inícios da API:

```powershell
$env:CDMS_SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

A API recusa chaves ausentes, curtas ou a chave demonstrativa antiga. Trocar a chave invalida tokens existentes. Não salve a chave no repositório.

Provisione usuário e workspace pelo comando administrativo local:

```powershell
.\.venv\Scripts\python.exe -m cdms.adapters.api.bootstrap --email owner@example.com --name "Proprietário" --workspace "Meu workspace"
```

O comando solicita uma senha de 12 a 1024 caracteres sem eco, pede confirmação para contas novas e imprime os IDs do usuário e do workspace. Executar novamente com um usuário existente exige a senha dele e cria outro workspace; não redefine sua senha. `--identity-db` permite escolher explicitamente outro banco de identidade para provisionamento administrativo.

Inicie a API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn cdms.adapters.api.main:app --port 8000
```

Em `http://localhost:8000/docs`, execute `POST /api/v1/auth/login` com email, senha e UUID do workspace. Use o `access_token` retornado como Bearer no botão Authorize. O login antigo de demonstração deixou de existir.

Não há cadastro público de usuários nesta etapa. Para trabalhar com outro usuário, provisione-o administrativamente; um proprietário ou administrador autorizado pode conceder acesso ao workspace usando o ID desse usuário.

## Perfis e revogação

| Perfil | Leitura de dados do workspace | Operações de negócio | Gestão de membros |
|---|---|---|---|
| OWNER | Sim | Sim | Sim, inclusive ADMIN |
| ADMIN | Sim | Sim | MEMBER e VIEWER |
| MEMBER | Sim | Sim | Não |
| VIEWER | Sim | Não | Não |

Todos os perfis podem trocar a própria senha e fazer logout. O proprietário não pode ser removido ou rebaixado pelos endpoints de membros, inclusive se sua conta estiver desativada. Não existe papel de administrador global que ignore o workspace.

A cada requisição, a API consulta o usuário ativo, o vínculo atual e a versão dos tokens. O papel no JWT não concede privilégios. Mudança de papel vale para tokens já emitidos; remoção do vínculo ou desativação bloqueia o acesso. `POST /auth/logout` revoga todos os tokens atuais do usuário, em todos os seus workspaces. `POST /auth/password` exige a senha atual, grava um novo hash e também revoga tokens anteriores.

Novas senhas usam PBKDF2-SHA256 com 600.000 iterações. Hashes bcrypt existentes podem ser verificados; a troca de senha grava o formato atual. Tokens exigem assinatura HS256, emissor, audiência, expiração, identificação do usuário, workspace, versão e ID do token.

## Endpoints

- `/api/v1/auth/login`, `/logout`, `/password`: autenticação e revogação.
- `/api/v1/workspaces` e `/current`: apenas os workspaces vinculados ao usuário.
- `/api/v1/workspaces/current/members`: consulta por gestores; PUT e DELETE por ID aplicam as regras de papel.
- `/api/v1/growth`: baseline, auditorias, hipóteses, preparação de propostas e relatórios.
- `/api/v1/rituals`: gravação, listagem, leitura por ciclo e calibrações; mantém o vínculo atômico CGS/CDMS da etapa 3.
- `/api/v1/growth-v2`: orçamento e significância estatística vinculados a uma hipótese do mesmo workspace.
- `/api/v1/growth-v3`: otimização e consulta de alocação vinculadas a uma hipótese do mesmo workspace.
- `/api/v1/automation/ai-suggestions`: usa somente auditoria existente no workspace; retorna 404 se ela não existe.
- `/api/v1/automation/connect-platform`: retorna 501 até a implementação da conexão real, sem simular uma conexão concluída.

O esquema OpenAPI em `/docs` contém os corpos completos. Campos extras nos payloads são rejeitados. IDs de hipóteses são locais ao workspace: um mesmo número em outro workspace identifica outro registro, nunca seleciona o banco daquele workspace.

CORS fica desabilitado por padrão. Se necessário para um cliente web, configure `CDMS_CORS_ORIGINS` com origens explícitas separadas por vírgula.

## Testes e limites

Os testes HTTP usam TestClient, bancos temporários de identidade e operação, usuários reais de teste e login pela API. Eles cobrem credenciais inválidas, expiração e alteração de tokens, troca de papel, revogação, desativação, proteção do proprietário, permissões de todas as rotas e tentativas de acesso entre dois workspaces, inclusive com IDs e ciclos coincidentes.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_workspace_api.py
.\.venv\Scripts\python.exe -m pytest -q
```

Este desenho é voltado ao armazenamento SQLite local da API. SSO, recuperação de senha por email, controles distribuídos de tentativas de login, autenticação do Streamlit e infraestrutura de publicação não foram implementados nesta etapa. Integrações reais de plataformas e execução de workers continuam como próxima etapa.


## Resultado registrado em 2026-10-28

- Suíte completa: **124 testes aprovados** em Windows/Python 3.11.9, incluindo 36 testes HTTP novos de workspace e os seis cenários de interface existentes.
- `pip check`: nenhuma dependência quebrada.
- `git diff --check`: sem problemas nas alterações.
- Provisionamento administrativo validado com banco temporário para conta nova e para reutilização da conta em outro workspace.
- Importação da API e geração do OpenAPI verificadas sem carregar o módulo Streamlit.
- Banco local de desenvolvimento conferido por SHA-256 antes e depois dos testes, sem alteração nesta etapa.
- Foram emitidos 40 avisos de depreciação: um do TestClient/Starlette sobre HTTPX e 39 dos gráficos internos do Streamlit sobre pandas. Não houve falhas.

As verificações usam bancos temporários e não criam usuários reais no banco de desenvolvimento. Para usar a API manualmente, é necessário configurar a chave e executar o provisionamento descrito acima.
