from flask import Flask, render_template, send_file, request, redirect, url_for, session
from functools import wraps
from scripts.analisisgastos import graficar, graficarTotal, graficarStatus, generarPDF
from scripts.login import loginStatus
from scripts.registro import registrar
from scripts.modificar import modificarDatos
from scripts.perfil import obtenerPerfil
from scripts.ahorros import ahorros_info                             
from scripts.actualizar_reservado import actualizar_dinero_reservado

import psycopg2
import random
import time

app = Flask(__name__)

# Configuración de conexión con PostgreSQL

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    dbname="selfbank",
    user="postgres",
    password="1234",
    options="-c client_encoding=UTF8"
)

app.secret_key = 'mi_clave_secreta'

# Decorador personalizado para verificar autenticación

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def login():
    return render_template('login.html')

@app.route("/error")
def error():
    return render_template('error.html')

@app.route("/login", methods=["GET", "POST"])  
def login_post():
    return loginStatus(conn)

@app.route("/registro", methods=["GET", "POST"])
def registro():
    return registrar(conn)

@app.route("/index")
@login_required
def index():
    user_id = session['user_id']
    
    # Fetch user's debit cards
    cur = conn.cursor()
    cur.execute("""
        SELECT id_tarjeta, nombre_usuario, tipo_tarjeta, dinero_disponible, numero_tarjeta, dinero_reservado, status
        FROM tarjetas
        WHERE id_usuario = %s AND tipo_tarjeta = 'Débito'
        ORDER BY id_tarjeta
    """, (user_id,))
    debit_cards = cur.fetchall()
    
    # Fetch user's credit cards
    cur.execute("""
        SELECT id_tarjeta, nombre_usuario, tipo_tarjeta, dinero_disponible, numero_tarjeta, dinero_reservado, status
        FROM tarjetas
        WHERE id_usuario = %s AND tipo_tarjeta = 'Credito'
        ORDER BY id_tarjeta
    """, (user_id,))
    credit_cards = cur.fetchall()
    cur.close()
    return render_template('index.html', debit_cards=debit_cards, credit_cards=credit_cards)

@app.route("/notificaciones")
@login_required
def notificaciones():
    user_id = session['user_id']
    cur = conn.cursor()
    cur.execute("""
        SELECT descripcion, fecha, status, id_notificacion
        FROM notificaciones 
        WHERE id_usuario = %s 
        ORDER BY fecha DESC
    """, (user_id,))
    notifications = cur.fetchall()
    cur.close()
    return render_template("notificaciones.html", notifications=notifications)

@app.route("/movimientos")
@login_required
def movimientos():
    user_id = session['user_id']
    cur = conn.cursor()
    cur.execute("""
        SELECT descripcion_movimiento, fecha, ingresos, egresos, tipo_tarjeta, id_movimiento, reservado
        FROM movimientos 
        WHERE id_usuario = %s 
        ORDER BY fecha DESC
    """, (user_id,))
    movements = cur.fetchall()
    cur.close()
    return render_template("movimientos.html", movements=movements)

@app.route("/registro_movimiento", methods=["GET", "POST"])
@login_required
def registro_movimiento():
    user_id = session['user_id']
    
    if request.method == "POST":
        descripcion = request.form['descripcion']
        fecha = request.form['fecha']
        ingresos = request.form.get('ingresos', 0)
        egresos = request.form.get('egresos', 0)
        id_tarjeta = request.form['id_tarjeta']
        tipo_tarjeta = request.form[f'tipo_tarjeta_{id_tarjeta}']
        reservado = 'reservado' in request.form
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO movimientos (id_usuario, id_tarjeta, ingresos, egresos, descripcion_movimiento, fecha, tipo_tarjeta, reservado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, id_tarjeta, ingresos, egresos, descripcion, fecha, tipo_tarjeta, reservado))
        conn.commit()
        cur.close()
        
        return redirect(url_for('movimientos'))
    
    # Obtener tarjetas
    cur = conn.cursor()
    cur.execute("""
        SELECT id_tarjeta, tipo_tarjeta, dinero_disponible, numero_tarjeta, nombre_usuario
        FROM tarjetas
        WHERE id_usuario = %s
    """, (user_id,))
    cards = cur.fetchall()
    cur.close()
    
    return render_template("registro_movimiento.html", cards=cards)

@app.route("/analisisgastos")
@login_required
def analisis_gastos():
    return render_template("analisisgastos.html")

@app.route("/graficar")
def graficarRuta():
    return graficar(conn)

@app.route("/graficarMeses")
def graficarMes():
    return graficarTotal(conn)

@app.route("/graficarStatus")
def graficarEstado():
    return graficarStatus(conn)

@app.route('/generarPdf', methods=['POST'])
def PDF():
    generarPDF(conn)

    return '', 204

@app.route("/ahorros")
@login_required
def ahorros():
    return ahorros_info(conn)
    
@app.route("/actu_reservado", methods=["POST"])
@login_required
def actu_reservado():
   return actualizar_dinero_reservado(conn)
    
@app.route('/cambiar_tarjeta', methods=['POST'])
def cambiar_tarjeta():
    # Obtener el nuevo ID de tarjeta enviado desde el formulario
    nueva_tarjeta = request.form['nueva_tarjeta']
    session['id_tarjeta'] = nueva_tarjeta

    # Obtener información adicional desde la sesión
    id_usuario = session['user_id']
    correo = session['correo']

    # Consultar el tipo de tarjeta para el nuevo ID
    cur = conn.cursor()
    cur.execute("""
        SELECT tipo_tarjeta FROM usuariotarjetas WHERE correo = %s AND id_tarjeta = %s and id_usuario = %s
    """, (correo, nueva_tarjeta,id_usuario))  # Usar nueva_tarjeta en la consulta
    resultado = cur.fetchone()

    # Verificar si se obtuvo un resultado válido
    if resultado:
        nuevo_tipo_tarjeta = resultado[0]  # Extraer el tipo de tarjeta
        session['tipo_tarjeta'] = nuevo_tipo_tarjeta
    else:
        return "Error: No se encontró el tipo de tarjeta para el ID proporcionado", 400

    # Redirigir al usuario a la página de ahorros después del cambio
    return redirect('/ahorros')
    
@app.route("/pagos")
@login_required
def pagos():
    return render_template("pagos.html")

@app.route("/logout")
def logout():
    session.pop('user_id', None)  # Eliminar el ID de usuario de la sesión
    return redirect(url_for('login'))

@app.route("/usuario_modifica", methods=["GET", "POST"])
@login_required
def usuario_modifica():
    return modificarDatos(conn)

@app.route("/perfil_user")
@login_required
def perfil_user():
    return obtenerPerfil(conn)

@app.route("/actualizar_status_noti", methods=["POST"])
@login_required
def actualizar_status_noti():
    notification_id = request.form['notification_id']
    status = request.form['status'] == 'true'
    user_id = session['user_id']
    
    cur = conn.cursor()
    cur.execute("""
        UPDATE notificaciones
        SET status = %s
        WHERE id_notificacion = %s AND id_usuario = %s
    """, (status, notification_id, user_id))
    conn.commit()
    cur.close()
    
    return '', 204  # En caso que no haya contenido

@app.route("/faq")
@login_required
def faq():
    return render_template("preguntas_frecuencias.html")

@app.route("/borrar_tarjeta/<int:card_id>", methods=["POST"])
@login_required
def borrar_tarjeta(card_id):
    user_id = session['user_id']
    cur = conn.cursor()
    cur.execute("""
        UPDATE tarjetas
        SET status = FALSE
        WHERE id_tarjeta = %s AND id_usuario = %s
    """, (card_id, user_id))
    conn.commit()
    cur.close()
    return redirect(url_for('index'))



@app.route("/agregar_tarjeta", methods=["GET", "POST"])
@login_required
def agregar_tarjeta():
    user_id = session['user_id']
    if request.method == "POST":
        nombre_usuario = request.form['nombre_usuario']
        tipo_tarjeta = request.form['tipo_tarjeta']
        numero_tarjeta = request.form['numero_tarjeta']
        
        # Generate a random 4-digit PIN using the current time as the seed
        random.seed(time.time())
        pin = random.randint(1000, 9999)
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tarjetas (id_usuario, nombre_usuario, tipo_tarjeta, numero_tarjeta, dinero_disponible, status, pin, dinero_reservado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, nombre_usuario, tipo_tarjeta, numero_tarjeta, 0, True, pin, 0))
        conn.commit()
        cur.close()
        
        return redirect(url_for('index'))
    
    return render_template("agregar_tarjeta.html")

@app.route("/editar_tarjeta/<int:card_id>", methods=["GET", "POST"])
@login_required
def editar_tarjeta(card_id):
    user_id = session['user_id']
    if request.method == "POST":
        nombre_usuario = request.form['nombre_usuario']
        tipo_tarjeta = request.form['tipo_tarjeta']
        numero_tarjeta = request.form['numero_tarjeta']
        cur = conn.cursor()
        cur.execute("""
            UPDATE tarjetas
            SET nombre_usuario = %s, tipo_tarjeta = %s, numero_tarjeta = %s
            WHERE id_tarjeta = %s AND id_usuario = %s
        """, (nombre_usuario, tipo_tarjeta, numero_tarjeta, card_id, user_id))
        conn.commit()
        cur.close()
        return redirect(url_for('index'))

    cur = conn.cursor()
    cur.execute("""
        SELECT id_tarjeta, nombre_usuario, tipo_tarjeta, numero_tarjeta
        FROM tarjetas
        WHERE id_tarjeta = %s AND id_usuario = %s
    """, (card_id, user_id))
    card = cur.fetchone()
    cur.close()
    return render_template("editar_tarjeta.html", card=card)


if __name__ == "__main__":
    app.run(debug=True)
