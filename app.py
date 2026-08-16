import re

from cs50 import SQL
from helpers import apology, login_required
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

# Configurar aplicación
app = Flask(__name__)

# Config. sesiones para usar filesystem (en lugar de cookies firmadas)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Config. biblioteca CS50 para usar SQLite
db = SQL("sqlite:///finance.db")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Registrar usuario"""

    # Si el usuario llega por POST (envió el formulario)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validar que los campos no estén vacíos y las contraseñas coincidan
        if not username or not password or not confirmation:
            return apology("debes rellenar todos los campos", 400)
        if password != confirmation:
            return apology("Las contraseñas no coinciden", 400)
        # Cifrar contraseña
        hash_password = generate_password_hash(password)

        # Intentar insertar el usuario en la base de datos
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        except Exception as e:
            return apology(f"Error de base de datos: {e}", 400)

        # Redirigir al usuario al login tras registrarse con éxito
        return redirect("/login")

    # Si el usuario llega por GET (solo quiere ver la página web)
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Iniciar sesión"""

    # Olvidar cualquier user_id previo por seguridad
    session.clear()

    # Si el usuario envió el formulario por POST
    if request.method == "POST":

        # Asegurarse de que escribe usuario y contraseña
        if not request.form.get("username"):
            return apology("debes introducir un nombre de usuario", 403)
        if not request.form.get("password"):
            return apology("debes introducir una contraseña", 403)

        # Buscar en la database si existe el usuario
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("usuario y/o contraseña incorrectos", 403)

        # Recordar usuario con ID
        session["user_id"] = rows[0]["id"]

        # Redirigir al usuario a la página principal (dashboard)
        return redirect("/")

    # Si el usuario entra por GET (solo quiere ver la pantalla de login)
    else:
        return render_template("login.html")


@app.route("/add_supplier", methods=["GET", "POST"])
@login_required
def add_supplier():
    """Añadir un proveedor de confianza"""

    if request.method == "POST":

        name = request.form.get("name")
        account_number = request.form.get("account_number")

        # Validar campos obligatorios
        if not name:
            return apology("debes introducir el nombre del proveedor", 400)

        if not account_number:
            return apology("debes introducir el número de cuenta", 400)

        # 1. Validación de longitud (por ejemplo, mínimo 8 caracteres y máximo 34)
        if len(account_number) < 8 or len(account_number) > 34:
            return apology("el número de cuenta debe tener entre 8 y 34 caracteres", 400)

        # 2. Validación de caracteres extraños (solo permitimos letras y números alfanuméricos)
        # El patrón [^a-zA-Z0-9] detecta si hay símbolos como *, ?, espacios, guiones, etc.
        if re.search(r"[^a-zA-Z0-9]", account_number):
            return apology("el número de cuenta contiene caracteres inválidos o símbolos no permitidos", 400)

        # Guardar el proveedor en la base de datos vinculado al usuario actual
        db.execute(
            "INSERT INTO suppliers (user_id, name, account_number) VALUES (?, ?, ?)",
            session["user_id"], name, account_number
        )

        return redirect("/")

    else:
        return render_template("add_supplier.html")


@app.route("/check", methods=["GET", "POST"])
@login_required
def check():
    if request.method == "POST":
        # Recoger los datos del formulario
        supplier_name = request.form.get("name")
        invoice_number = request.form.get("invoice_number")
        amount = request.form.get("amount")
        account_number = request.form.get("account_number")

        # Validaciones básicas
        if not supplier_name or not invoice_number or not amount or not account_number:
            return apology("debes rellenar todos los campos", 400)

        # Comprobar si el proveedor existe en los registros de confianza
        supplier = db.execute(
            "SELECT * FROM suppliers WHERE user_id = ? AND name = ?",
            session["user_id"], supplier_name
        )

        if len(supplier) != 1:
            # Si no existe, estado sospechoso o fraude
            status = "Sospechosa (No registrado)"
        else:
            # Comprobar si la cuenta coincide con la guardada
            stored_account = supplier[0]["account_number"]
            if stored_account == account_number:
                status = "Aprobada (Segura)"
            else:
                status = "Fraudulenta (Cuenta alterada)"

        # Guardar la factura analizada en la tabla invoices
        db.execute(
            "INSERT INTO invoices (user_id, supplier_name, invoice_number, amount, account_used, status) VALUES (?, ?, ?, ?, ?, ?)",
            session["user_id"], supplier_name, invoice_number, amount, account_number, status
        )

        # Redirigir al dashboard para ver el historial
        return redirect("/")

    else:
        # Si es GET, mostrar el formulario de análisis
        return render_template("check.html")


@app.route("/")
@login_required
def index():
    # Obtener todas las facturas del usuario actual
    invoices = db.execute(
        "SELECT * FROM invoices WHERE user_id = ? ORDER BY date DESC",
        session["user_id"]
    )
    return render_template("index.html", invoices=invoices)


@app.route("/logout")
def logout():
    """Cerrar sesión"""
    # Borrar el user_id de la sesión
    session.clear()

    # Redirigir al usuario a la página de inicio de sesión
    return redirect("/login")


@app.route("/suppliers")
@login_required
def suppliers():
    """Mostrar la lista de proveedores del usuario"""
    suppliers_list = db.execute("SELECT * FROM suppliers WHERE user_id = ?", session["user_id"])
    return render_template("suppliers.html", suppliers=suppliers_list)


@app.route("/delete_supplier", methods=["POST"])
@login_required
def delete_supplier():
    """Eliminar un proveedor del usuario"""
    supplier_id = request.form.get("supplier_id")

    if supplier_id:
        db.execute(
            "DELETE FROM suppliers WHERE id = ? AND user_id = ?",
            supplier_id, session["user_id"]
        )
        flash("Proveedor eliminado correctamente.", "success")

    return redirect("/suppliers")


#Nota: Se utilizó claude code como asistente de IA para depurar errores de configuracion del entorno y revisar la logica del programa.
