import os
import io
from datetime import datetime

from flask import Flask, request, render_template, send_file, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave")

# En Render se define la variable de entorno DATABASE_URL con la URI de Supabase.
# Localmente puedes exportarla en tu shell o pegarla aquí como fallback de prueba.
db_url = os.environ.get("DATABASE_URL", "postgresql://usuario:password@host:5432/postgres")
# Supabase entrega a veces el prefijo "postgres://"; SQLAlchemy moderno requiere "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Parámetros del cálculo tributario (ajustables sin tocar la lógica)
ALICUOTA = 0.02          # 2% sobre la base imponible omitida
RECARGO_PCT = 0.50       # 50% de multa sobre el impuesto omitido


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class Contribuyente(db.Model):
    __tablename__ = "contribuyentes"
    id = db.Column(db.Integer, primary_key=True)
    rif = db.Column(db.String(20), unique=True, nullable=False)
    razon_social = db.Column(db.String(200), nullable=False)
    direccion = db.Column(db.Text)

    declaraciones = db.relationship("Declaracion", backref="contribuyente", lazy=True)


class Declaracion(db.Model):
    __tablename__ = "declaraciones"
    id = db.Column(db.Integer, primary_key=True)
    contribuyente_id = db.Column(db.Integer, db.ForeignKey("contribuyentes.id"), nullable=False)
    periodo = db.Column(db.String(20), nullable=False)
    ingresos_declarados = db.Column(db.Numeric(14, 2), nullable=False)
    ingresos_reales = db.Column(db.Numeric(14, 2), nullable=False)
    diferencia = db.Column(db.Numeric(14, 2))
    impuesto_omitido = db.Column(db.Numeric(14, 2))
    recargo = db.Column(db.Numeric(14, 2))
    reparo_fiscal = db.Column(db.Numeric(14, 2))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Lógica de auditoría fiscal
# ---------------------------------------------------------------------------
def calcular_reparo_fiscal(ingresos_declarados, ingresos_reales,
                            alicuota=ALICUOTA, recargo_pct=RECARGO_PCT):
    """
    Contrapone ingresos declarados vs. ingresos reales auditados y calcula
    el reparo fiscal. Si no hay omisión (ingresos_reales <= declarados),
    todos los montos resultantes son cero.
    """
    ingresos_declarados = float(ingresos_declarados)
    ingresos_reales = float(ingresos_reales)

    diferencia = max(0.0, ingresos_reales - ingresos_declarados)
    impuesto_omitido = diferencia * alicuota
    recargo = impuesto_omitido * recargo_pct
    reparo_fiscal = impuesto_omitido + recargo

    return {
        "diferencia": round(diferencia, 2),
        "impuesto_omitido": round(impuesto_omitido, 2),
        "recargo": round(recargo, 2),
        "reparo_fiscal": round(reparo_fiscal, 2),
    }


# ---------------------------------------------------------------------------
# Generación del PDF (Acta de Reparo Fiscal)
# ---------------------------------------------------------------------------
def generar_pdf_acta(contribuyente, declaracion, resultado):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                             topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], alignment=1, fontSize=16
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo", parent=styles["Normal"], alignment=1, fontSize=10,
        textColor=colors.grey
    )

    elementos = []
    elementos.append(Paragraph("ACTA DE REPARO FISCAL", titulo_style))
    elementos.append(Paragraph(
        f"Emitida el {datetime.utcnow().strftime('%d/%m/%Y')}", subtitulo_style
    ))
    elementos.append(Spacer(1, 0.8 * cm))

    datos_contribuyente = [
        ["RIF", contribuyente.rif],
        ["Razón Social", contribuyente.razon_social],
        ["Dirección", contribuyente.direccion or "-"],
        ["Período Fiscalizado", declaracion.periodo],
    ]
    tabla1 = Table(datos_contribuyente, colWidths=[5 * cm, 10 * cm])
    tabla1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla1)
    elementos.append(Spacer(1, 0.8 * cm))

    elementos.append(Paragraph("Determinación de la Omisión", styles["Heading2"]))
    datos_calculo = [
        ["Concepto", "Monto"],
        ["Ingresos declarados", f"{declaracion.ingresos_declarados:,.2f}"],
        ["Ingresos reales auditados", f"{declaracion.ingresos_reales:,.2f}"],
        ["Base imponible omitida", f"{resultado['diferencia']:,.2f}"],
        [f"Impuesto omitido ({ALICUOTA * 100:.0f}%)", f"{resultado['impuesto_omitido']:,.2f}"],
        [f"Recargo/multa ({RECARGO_PCT * 100:.0f}%)", f"{resultado['recargo']:,.2f}"],
        ["REPARO FISCAL TOTAL", f"{resultado['reparo_fiscal']:,.2f}"],
    ]
    tabla2 = Table(datos_calculo, colWidths=[9 * cm, 6 * cm])
    tabla2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f4d03f")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla2)
    elementos.append(Spacer(1, 1 * cm))

    elementos.append(Paragraph(
        "Este documento constituye un acta de reparo fiscal generada por el "
        "sistema de auditoría tributaria a partir de la diferencia entre los "
        "ingresos declarados por el contribuyente y los ingresos reales "
        "verificados en la fiscalización correspondiente.",
        styles["Normal"]
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/auditar", methods=["POST"])
def auditar():
    rif = request.form.get("rif", "").strip()
    razon_social = request.form.get("razon_social", "").strip()
    direccion = request.form.get("direccion", "").strip()
    periodo = request.form.get("periodo", "").strip()

    try:
        ingresos_declarados = float(request.form.get("ingresos_declarados", "0"))
        ingresos_reales = float(request.form.get("ingresos_reales", "0"))
    except ValueError:
        flash("Los montos deben ser numéricos.")
        return redirect(url_for("index"))

    if not rif or not razon_social or not periodo:
        flash("RIF, razón social y período son obligatorios.")
        return redirect(url_for("index"))

    # Busca o crea el contribuyente
    contribuyente = Contribuyente.query.filter_by(rif=rif).first()
    if contribuyente is None:
        contribuyente = Contribuyente(rif=rif, razon_social=razon_social, direccion=direccion)
        db.session.add(contribuyente)
        db.session.flush()  # asigna id sin cerrar la transacción

    resultado = calcular_reparo_fiscal(ingresos_declarados, ingresos_reales)

    declaracion = Declaracion(
        contribuyente_id=contribuyente.id,
        periodo=periodo,
        ingresos_declarados=ingresos_declarados,
        ingresos_reales=ingresos_reales,
        diferencia=resultado["diferencia"],
        impuesto_omitido=resultado["impuesto_omitido"],
        recargo=resultado["recargo"],
        reparo_fiscal=resultado["reparo_fiscal"],
    )
    db.session.add(declaracion)
    db.session.commit()

    pdf_buffer = generar_pdf_acta(contribuyente, declaracion, resultado)
    nombre_archivo = f"Acta_Reparo_{rif}_{periodo}.pdf"

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/pdf",
    )


@app.route("/historial")
def historial():
    declaraciones = Declaracion.query.order_by(Declaracion.fecha_registro.desc()).limit(50).all()
    return render_template("historial.html", declaraciones=declaraciones)


with app.app_context():
    db.create_all()  # crea las tablas si no existen (idempotente; el schema.sql ya las crea también)


if __name__ == "__main__":
    app.run(debug=True)
