# Etapa 13 — Login e workspaces no Studio

O painel `app.py` exige login por padrão. Ele usa as mesmas contas, vínculos, hashes de senha, chave JWT e bancos operacionais da API. O cadastro administrativo já realizado continua válido.

## Primeiro uso

1. Instale os extras necessários, caso ainda não estejam instalados: `python -m pip install -e ".[dev,api,automation]"`.
2. No terminal que iniciará o Streamlit, carregue a mesma `CDMS_SECRET_KEY` configurada para a suíte. Se esse terminal já contém a chave válida, não gere outra.
3. Execute `python -m streamlit run app.py` e abra `http://localhost:8501`.
4. Entre com email e senha cadastrados. O primeiro workspace disponível é aberto; no painel lateral, escolha outro workspace pelo nome e o ciclo de referência, se necessário. No celular, esses controles ficam em **Seções**. Não é preciso copiar token nem digitar UUID.

As variáveis de ambiente pertencem ao processo/terminal: uma chave definida em outro PowerShell não aparece automaticamente no servidor Streamlit já iniciado. Reinicie o servidor após configurar seu ambiente.

Para persistir a chave do painel entre reinícios, é possível usar `.streamlit/secrets.toml`, que está excluído do Git:

```toml
CDMS_SECRET_KEY = "SUBSTITUA_PELA_MESMA_CHAVE_SEGURA_JA_GUARDADA"
```

O texto acima é apenas um marcador; não o use como chave. Uma variável `CDMS_SECRET_KEY` definida no ambiente tem precedência sobre o arquivo. A API continua carregando a chave do ambiente; o arquivo do Streamlit não configura a API automaticamente.

## Armazenamento e execução

O Studio executa os casos de uso no próprio servidor, com acesso direto aos bancos da suíte. Ele não depende de um processo HTTP da API em execução. Login e emissão de tokens usam o serviço `WorkspaceAuth`, também utilizado pelo endpoint de login da API.

Ambos os processos devem apontar para a mesma identidade e raiz de workspaces:

- `CDMS_IDENTITY_DB_PATH`: padrão `data/identity.db`.
- `CDMS_WORKSPACE_DATA_DIR`: padrão `data/workspaces`.
- `CDMS_SECRET_KEY`: chave externa para assinatura e validação.

Os caminhos de configuração são definidos no servidor. O banco operacional é escolhido exclusivamente a partir do UUID do workspace validado na sessão; nomes e caminhos enviados pelo navegador não selecionam bancos.

Os dados de `data/cdms_dev.db` não são importados automaticamente. Uma conta pode entrar e encontrar o workspace vazio, mesmo que existam registros no antigo painel local.

## Sessão e permissões

- Tokens ficam somente na sessão do servidor Streamlit; não são exibidos nem colocados em parâmetros da URL.
- A sessão expira em até 24 horas. Uma nova sessão do navegador pode exigir novo login; não foi implementado “lembrar de mim”.
- Cada execução do painel revalida assinatura, expiração, usuário ativo, versão de tokens e vínculo vigente. O perfil vem do banco, não do papel informado no token.
- Trocar de workspace exige vínculo atual e limpa formulários, uploads e rascunhos da sessão. A troca não estende a expiração do token.
- **Sair** revoga os tokens atuais do usuário em todos os seus workspaces, conforme o comportamento já adotado pela API, e limpa a sessão do painel.
- `OWNER`, `ADMIN` e `MEMBER` podem executar os fluxos operacionais existentes.
- `VIEWER` pode consultar Cockpit, histórico, exportações, backlog e relatórios. Ritual, calibrações, execução de diagnóstico, baseline e alterações de hipóteses são bloqueados antes de renderizar os formulários de gravação. O backlog desse perfil é uma consulta simplificada.
- Cadastro e gestão de membros estão em **Configurações → Gerenciar usuários**, na dock, para OWNER e ADMIN. Todos os perfis podem trocar a própria senha em **Minha conta**. Consulte [Cadastro e gestão de usuários](gestao-de-usuarios.md) para permissões, senhas temporárias e recuperação administrativa.

A configuração do Streamlit mantém proteção XSRF e habilita a restrição de origem (`server.enableCORS=true`). Reinicie o servidor para aplicar alterações de configuração.

## Modo local e demonstração

Para operar deliberadamente a instalação local sem autenticação, configure no servidor:

```powershell
$env:CDMS_STUDIO_MODE = "local"
python -m streamlit run app.py
```

Esse modo mantém os contextos Local e Demo anteriores e não deve ser confundido com um workspace autenticado. O usuário do navegador não pode ativá-lo pela interface. Não há fallback automático para o modo local quando falta chave ou o login falha.

Para voltar ao login:

```powershell
$env:CDMS_STUDIO_MODE = "authenticated"
python -m streamlit run app.py
```

## Verificação

Os testes usam identidades e bancos temporários, sem cadastrar usuários reais nem migrar dados locais:

```powershell
python -m pytest -q tests/ui/test_studio_auth.py tests/integration/test_workspace_api.py
python -m pytest -q tests/ui
```

Cobertura: bloqueio antes do login, credenciais inválidas, seleção e isolamento de workspace, limpeza de rascunhos, gravação no banco selecionado, logout, expiração, assinatura inválida, revogação, desativação, remoção do vínculo, mudança de perfil e configuração sem chave.

Resultado em 2026-10-31: suíte completa `python -m pytest -q` com **219 testes aprovados e 1 ignorado** (Redis de teste não configurado), incluindo os 12 testes novos de autenticação do Studio. Foram emitidos cinco avisos de depreciação de dependências. A validação foi automatizada com AppTest e TestClient; não incluiu inspeção visual em navegador ou publicação do serviço.
