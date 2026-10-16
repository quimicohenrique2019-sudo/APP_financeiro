# Gestão Financeira

Aplicativo CRUD de receitas e despesas com Streamlit e Cloud Firestore. As contas
e os lançamentos são salvos no projeto Firebase da credencial de serviço. Cada
usuário acessa somente os lançamentos associados à sua conta.

## Requisitos

- Python 3.10 ou superior
- Uma conta de serviço do Firebase com acesso ao Cloud Firestore
- Banco Firestore criado no modo Native

## Instalação e execução

No PowerShell, na pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

As credenciais locais ficam em `.streamlit/secrets.toml`. Esse arquivo é ignorado
pelo Git; não o envie ao repositório nem o compartilhe.

## Deploy no Streamlit Community Cloud

1. Crie um repositório GitHub e envie o código, sem o JSON da conta de serviço.
   O arquivo `.gitignore` já ignora arquivos `*-firebase-adminsdk-*.json`.
2. Acesse [share.streamlit.io](https://share.streamlit.io/), entre com o GitHub e
   selecione **Create app**.
3. Escolha o repositório, a branch e `app.py` como arquivo principal. Em
   **Advanced settings**, selecione Python 3.11 ou superior.
4. Abra `.streamlit/secrets.toml` no seu computador e copie todo o conteúdo.
   No painel do app, abra **Settings > Secrets**, cole o conteúdo e salve.
   O arquivo já está preenchido com as credenciais locais e o app lê a seção
   `[firebase]` tanto localmente quanto no Streamlit Cloud.
5. Salve os Secrets e implante/reinicie o app. Confirme que a tela de login
   carrega e que o cadastro, login e lançamentos funcionam.

Não publique, cole em issues/chats, nem adicione os Secrets ao repositório.
Quem já enviou uma chave privada ao GitHub deve revogá-la no Google Cloud IAM,
gerar uma nova e atualizar os Secrets. Como o Admin SDK não é limitado pelas
Firestore Security Rules, restrinja o acesso da conta de serviço via IAM e
proteja os Secrets do app.

## Contas e dados

Crie um usuário na aba **Criar conta** e entre pela aba **Entrar**. O nome de
usuário deve ter de 3 a 32 caracteres (letras, números, ponto, hífen ou
sublinhado) e a senha deve ter pelo menos 10 caracteres. A senha não é salva em
texto puro: o Firestore armazena um hash PBKDF2 com salt individual.

As contas são armazenadas na coleção `users`; receitas e despesas, na coleção
`transactions`. Cada lançamento contém tipo, descrição, categoria, valor e data.
O acesso às credenciais de serviço permite acesso administrativo ao banco:
proteja o arquivo e restrinja as permissões IAM do projeto conforme necessário.
