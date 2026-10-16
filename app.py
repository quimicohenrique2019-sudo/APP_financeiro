import os
from datetime import date, datetime, time, timezone
from pathlib import Path

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1 import FieldFilter

from security import hash_password, normalize_username, verify_password


DEFAULT_CREDENTIALS = (
    Path(__file__).resolve().parent
    / "app-financeiro-af829-firebase-adminsdk-fbsvc-540a3296ba.json"
)
TRANSACTION_TYPES = ("Receita", "Despesa")
CATEGORIES = (
    "Alimentação",
    "Casa",
    "Educação",
    "Lazer",
    "Saúde",
    "Salário",
    "Transporte",
    "Outros",
)


@st.cache_resource
def get_firestore_client():
    if "firebase" in st.secrets:
        firebase_credential = credentials.Certificate(dict(st.secrets["firebase"]))
    else:
        credentials_path = Path(
            os.environ.get("FIREBASE_CREDENTIALS", str(DEFAULT_CREDENTIALS))
        ).expanduser()
        if not credentials_path.is_file():
            raise FileNotFoundError(
                "Credencial do Firebase não encontrada. Configure o secret "
                "[firebase] no Streamlit Cloud ou defina FIREBASE_CREDENTIALS "
                "com o caminho do arquivo JSON da conta de serviço."
            )
        firebase_credential = credentials.Certificate(str(credentials_path))

    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(firebase_credential)
    return firestore.client(app=app)


def create_account(db, username: str, password: str) -> bool:
    user_ref = db.collection("users").document(username)
    salt, password_hash = hash_password(password)
    try:
        user_ref.create(
            {
                "username": username,
                "salt": salt,
                "password_hash": password_hash,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except AlreadyExists:
        return False
    return True


def authenticate(db, username: str, password: str) -> bool:
    snapshot = db.collection("users").document(username).get()
    if not snapshot.exists:
        return False

    user = snapshot.to_dict()
    return verify_password(password, user["salt"], user["password_hash"])


def get_transactions(db, username: str) -> list[dict]:
    records = db.collection("transactions").where(
        filter=FieldFilter("user_id", "==", username)
    ).stream()
    transactions = []
    for record in records:
        data = record.to_dict()
        data["id"] = record.id
        transactions.append(data)
    return sorted(
        transactions,
        key=lambda item: item["transaction_date"],
        reverse=True,
    )


def save_transaction(
    db,
    username: str,
    transaction_type: str,
    description: str,
    category: str,
    amount: float,
    transaction_date: date,
) -> None:
    now = datetime.now(timezone.utc)
    db.collection("transactions").add(
        {
            "user_id": username,
            "type": transaction_type,
            "description": description.strip(),
            "category": category,
            "amount": amount,
            "transaction_date": datetime.combine(
                transaction_date, time.min, tzinfo=timezone.utc
            ),
            "created_at": now,
            "updated_at": now,
        }
    )


def update_transaction(db, username: str, transaction_id: str, values: dict) -> None:
    reference = db.collection("transactions").document(transaction_id)
    snapshot = reference.get()
    if not snapshot.exists or snapshot.to_dict().get("user_id") != username:
        raise ValueError("Lançamento não encontrado para este usuário.")
    reference.update(
        {
            "type": values["type"],
            "description": values["description"].strip(),
            "category": values["category"],
            "amount": values["amount"],
            "transaction_date": datetime.combine(
                values["transaction_date"], time.min, tzinfo=timezone.utc
            ),
            "updated_at": datetime.now(timezone.utc),
        }
    )


def delete_transaction(db, username: str, transaction_id: str) -> None:
    reference = db.collection("transactions").document(transaction_id)
    snapshot = reference.get()
    if not snapshot.exists or snapshot.to_dict().get("user_id") != username:
        raise ValueError("Lançamento não encontrado para este usuário.")
    reference.delete()


def as_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def render_authentication(db) -> None:
    st.title("Gestão Financeira")
    st.caption("Entre ou crie sua conta para organizar suas finanças.")
    login_tab, registration_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab:
        with st.form("login_form"):
            username_input = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
        if submitted:
            try:
                username = normalize_username(username_input)
            except ValueError as error:
                st.error(str(error))
            else:
                if authenticate(db, username, password):
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")

    with registration_tab:
        with st.form("registration_form"):
            username_input = st.text_input("Escolha um usuário")
            password = st.text_input("Escolha uma senha", type="password")
            password_confirmation = st.text_input(
                "Confirme a senha", type="password"
            )
            submitted = st.form_submit_button(
                "Cadastrar", use_container_width=True
            )
        if submitted:
            try:
                username = normalize_username(username_input)
                if len(password) < 10:
                    raise ValueError("A senha deve ter pelo menos 10 caracteres.")
                if password != password_confirmation:
                    raise ValueError("As senhas não conferem.")
                created = create_account(db, username, password)
            except ValueError as error:
                st.error(str(error))
            else:
                if created:
                    st.success("Conta criada. Agora você já pode entrar.")
                else:
                    st.error("Esse usuário já está cadastrado.")


def transaction_form(defaults: dict | None = None, key_prefix: str = "new") -> dict:
    defaults = defaults or {}
    categories = list(CATEGORIES)
    current_category = defaults.get("category", CATEGORIES[-1])
    if current_category not in categories:
        categories.append(current_category)

    with st.form(f"{key_prefix}_transaction_form"):
        transaction_type = st.selectbox(
            "Tipo",
            TRANSACTION_TYPES,
            index=TRANSACTION_TYPES.index(defaults.get("type", "Despesa")),
            key=f"{key_prefix}_type",
        )
        description = st.text_input(
            "Descrição", value=defaults.get("description", ""), key=f"{key_prefix}_description"
        )
        category = st.selectbox(
            "Categoria",
            categories,
            index=categories.index(current_category),
            key=f"{key_prefix}_category",
        )
        amount = st.number_input(
            "Valor (R$)",
            min_value=0.01,
            value=float(defaults.get("amount", 0.01)),
            step=1.0,
            format="%.2f",
            key=f"{key_prefix}_amount",
        )
        transaction_date = st.date_input(
            "Data",
            value=as_date(defaults.get("transaction_date", date.today())),
            key=f"{key_prefix}_date",
        )
        submitted = st.form_submit_button(
            "Salvar lançamento", use_container_width=True
        )

    return {
        "submitted": submitted,
        "type": transaction_type,
        "description": description,
        "category": category,
        "amount": amount,
        "transaction_date": transaction_date,
    }


def render_dashboard(db, username: str) -> None:
    st.sidebar.write(f"Usuário: **{username}**")
    if st.sidebar.button("Sair", use_container_width=True):
        del st.session_state["username"]
        st.rerun()

    st.title("Gestão Financeira")
    transactions = get_transactions(db, username)
    income = sum(item["amount"] for item in transactions if item["type"] == "Receita")
    expenses = sum(item["amount"] for item in transactions if item["type"] == "Despesa")
    metric_income, metric_expenses, metric_balance = st.columns(3)
    metric_income.metric("Receitas", f"R$ {income:,.2f}")
    metric_expenses.metric("Despesas", f"R$ {expenses:,.2f}")
    metric_balance.metric("Saldo", f"R$ {income - expenses:,.2f}")

    list_tab, create_tab, edit_tab, delete_tab = st.tabs(
        ["Lançamentos", "Novo lançamento", "Editar lançamento", "Excluir lançamento"]
    )

    with list_tab:
        if transactions:
            rows = [
                {
                    "Data": as_date(item["transaction_date"]).strftime("%d/%m/%Y"),
                    "Tipo": item["type"],
                    "Descrição": item["description"],
                    "Categoria": item["category"],
                    "Valor (R$)": item["amount"],
                }
                for item in transactions
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum lançamento cadastrado.")

    with create_tab:
        values = transaction_form()
        if values["submitted"]:
            if not values["description"].strip():
                st.error("Informe uma descrição para o lançamento.")
            else:
                save_transaction(
                    db,
                    username,
                    values["type"],
                    values["description"],
                    values["category"],
                    values["amount"],
                    values["transaction_date"],
                )
                st.success("Lançamento cadastrado.")
                st.rerun()

    with edit_tab:
        if not transactions:
            st.info("Cadastre um lançamento antes de editar.")
        else:
            options = {item["id"]: item for item in transactions}
            selected_id = st.selectbox(
                "Selecione o lançamento",
                options,
                format_func=lambda record_id: (
                    f'{as_date(options[record_id]["transaction_date"]):%d/%m/%Y} · '
                    f'{options[record_id]["description"]} · '
                    f'R$ {options[record_id]["amount"]:.2f}'
                ),
                key="edit_selected_id",
            )
            values = transaction_form(options[selected_id], "edit")
            if values["submitted"]:
                if not values["description"].strip():
                    st.error("Informe uma descrição para o lançamento.")
                else:
                    update_transaction(db, username, selected_id, values)
                    st.success("Lançamento atualizado.")
                    st.rerun()

    with delete_tab:
        if not transactions:
            st.info("Não há lançamentos para excluir.")
        else:
            options = {item["id"]: item for item in transactions}
            selected_id = st.selectbox(
                "Selecione o lançamento para excluir",
                options,
                format_func=lambda record_id: (
                    f'{as_date(options[record_id]["transaction_date"]):%d/%m/%Y} · '
                    f'{options[record_id]["description"]} · '
                    f'R$ {options[record_id]["amount"]:.2f}'
                ),
                key="delete_selected_id",
            )
            with st.form("delete_transaction_form"):
                confirmed = st.checkbox("Confirmo que desejo excluir este lançamento.")
                submitted = st.form_submit_button(
                    "Excluir lançamento", use_container_width=True
                )
            if submitted:
                if not confirmed:
                    st.error("Confirme a exclusão para continuar.")
                else:
                    delete_transaction(db, username, selected_id)
                    st.success("Lançamento excluído.")
                    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Gestão Financeira", page_icon="💰", layout="wide")
    try:
        db = get_firestore_client()
    except (FileNotFoundError, ValueError) as error:
        st.error(f"Não foi possível conectar ao Firebase: {error}")
        st.stop()

    username = st.session_state.get("username")
    if username:
        render_dashboard(db, username)
    else:
        render_authentication(db)


if __name__ == "__main__":
    main()
