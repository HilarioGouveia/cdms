# Cadastro e gestão de usuários

No Studio autenticado, abra **Configurações → Gerenciar usuários** na dock. A tela está
disponível para OWNER e ADMIN e lista apenas os membros do workspace atual.

## Adicionar uma pessoa

Informe nome, email e perfil. Para uma conta nova, defina uma senha temporária
com 12 a 1024 caracteres e entregue-a por um canal privado. O usuário entra
normalmente e deve definir uma senha diferente antes de acessar qualquer dado
operacional. Depois da troca, precisa entrar novamente. Não há envio automático
de convite ou recuperação por email nesta versão.

Se o email já estiver cadastrado, a conta é vinculada ao workspace com o perfil
escolhido; seu nome e senha existentes são preservados. Não é criado outro
workspace. Uma conta já vinculada não é alterada pelo formulário de cadastro.

## Perfis e acesso

- OWNER: proprietário protegido; pode cadastrar e alterar administradores.
- ADMIN: cadastra e gerencia MEMBER e VIEWER.
- MEMBER: opera os fluxos do workspace.
- VIEWER: consulta os dados sem executar alterações operacionais.

Em **Gerenciar acesso**, selecione uma pessoa, escolha a ação e confirme.
É possível mudar o perfil, remover o vínculo ou definir uma nova senha
temporária. O proprietário e o próprio acesso não podem ser alterados nessa
tela. A remoção vale apenas para o workspace atual e preserva a conta e os dados
operacionais. Os acessos são revalidados em cada execução/requisição.

## Senhas

Todos os perfis podem usar **Minha conta → Trocar minha senha**, informando a
senha atual e confirmando a nova. A alteração revoga as sessões anteriores.
A redefinição administrativa também revoga sessões e exige nova troca no login.

Como a senha pertence à conta inteira, a redefinição por um gestor só é permitida
para usuários vinculados exclusivamente ao workspace atual. Contas compartilhadas
devem trocar a própria senha ou recorrer ao operador da instalação. O proprietário
que perder a senha também deve recorrer ao operador; não há recuperação pública
sem verificação de identidade.

## Aparência por usuário

Em **Minha conta → Tema**, escolha **Claro** ou **Escuro**. A preferência é
salva na conta, vale para todos os seus workspaces e é carregada nos próximos
logins. Sair limpa a preferência da sessão, sem apagar a escolha salva.

A aparência do painel, seus controles HTML e os gráficos que usam os tokens do
Studio acompanham a preferência. Componentes nativos renderizados em canvas,
como a grade de dados do Streamlit, ainda seguem o tema configurado no servidor.
Não há alteração global de configuração quando uma pessoa troca de tema.

## API de usuários

Os endpoints usam autenticação Bearer e o workspace da sessão:

- `POST /api/v1/workspaces/current/members`: `email`, `full_name`, `role`,
  `temporary_password` (obrigatória para contas novas).
- `GET /api/v1/workspaces/current/members`: lista de membros.
- `PUT /api/v1/workspaces/current/members/{user_id}`: altera/adiciona vínculo,
  com `role`.
- `DELETE /api/v1/workspaces/current/members/{user_id}`: remove vínculo.
- `POST /api/v1/workspaces/current/members/{user_id}/password`:
  `temporary_password`.
- `POST /api/v1/auth/password`: `current_password` e `new_password`.

Tokens de contas com senha temporária não acessam os endpoints de workspace.
Eles podem executar a troca de senha e são revogados depois dela.

A coluna `must_change_password` é adicionada automaticamente ao abrir o banco
de identidade. Contas existentes mantêm suas senhas e não são forçadas a trocar.
Nenhuma conta de teste é criada no banco real pelos testes automatizados.
