from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import os
import json

app = Flask(__name__)
CORS(app, origins=["https://<TU_USUARIO>.github.io", "http://localhost:3000", "http://127.0.0.1:5500"])

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "<TU_SPREADSHEET_ID>")

SHEET_MAP = {
    "base-olga":     "Base Olga",
    "correos":       "BASE CORREOS ELECTRONICOS",
    "nexura":        "Base NEXURA",
    "traslados":     "Base Traslados Fiscalización",
    "resoluciones":  "RES",
    "fiscalizacion": "Base Traslados Fiscalización",
    "tutelas":       "BASE TUTELAS",
}

HEADERS = {
    "base-olga": [
        "No consecutivo","Canal de ingreso","Area Remitente","No. PLANILLA","No. EXPEDIENTE",
        "Fecha Radicacion expediente","ACTO ADMINISTRA-TIVO","No. ACTO ADMINISTRATIVO Y No. SADE",
        "FECHA ACTO","MES","PLACA","No. DE IDENTIFICACION","CONTRIBUYENTE","CIUDAD-DEPARTAMENTO",
        "OBSERVACIONES","FUNCIONARIO ENCARGADO","FECHA DE RECIBIDO","TIPO DE RENTA",
        "TIPO DE TRAMITE","ITEM","NUMERO DE RESOLUCION","NUMERO DE SADE SALIDA",
        "FECHA RESOLUCION","TIPO DE RESPUESTA","No PLANILLA","FECHA DE PLANILLA",
        "FECHA EJECUTORIA","TRASLADO","FECHA DE VENCIMIENTO","DIAS PENDIENTES","SEMAFORO DE VENCIMIENTO","AÑO INGRESO"
    ],
    "correos": [
        "CANAL DE INGRESO","MES","FECHA ASIGNACION","CORREO FUNCIONARIO ENCARGADO",
        "FUNCIONARIO ENCARGADO","ASUNTO CORREO","FECHA CORREO","CONTRIBUYENTE O SOLICITANTE",
        "CORREO SOLICITANTE","TIPO DE RENTA","TIPO DE TRAMITE","ITEM","PLACA",
        "FECHA RESPUESTA","TIPO DE RESPUESTA","No DE SADE DE SALIDA","OBSERVACIONES",
        "FECHA DE VENCIMIENTO","DIAS PENDIENTES","SEMAFORO","NO EXPEDIENTE","AÑO INGRESO","MES INGRESO"
    ],
    "nexura": [
        "CANAL DE INGRESO","No.","No. radicación","No. radicación externo","Tipo de solicitud",
        "Prioritaria","Canal de ingreso","Tema","Responsable","Fecha de Registro","Fecha ingreso",
        "Fecha límite de respuesta","Fecha de respuesta","Días hábiles restantes",
        "Días hábiles transcurridos","Estado","Tipo de persona","Tipo de documento",
        "Número de documento","Nombre del solicitante","Teléfono de contacto","Email","Término",
        "Requerimiento","FUNCIONARIO ENCARGADO","TIPO DE RENTA","TIPO DE TRAMITE","ITEM",
        "TIPO DE RESPUESTA","FECHA DE RESPUESTA","NUMERO DE SADE DE SALIDA",
        "SEMAFORO DE VENCIMIENTO","DIAS PENDIENTES","No Expediente","AÑO INGRESO","MES INGRESO"
    ],
    "tutelas": [
        "CANAL DE INGRESO","MES","FECHA ASIGNACION","CORREO FUNCIONARIO ENCARGADO",
        "FUNCIONARIO ENCARGADO","ASUNTO CORREO","FECHA CORREO","CONTRIBUYENTE O SOLICITANTE",
        "CORREO SOLICITANTE","TIPO DE RENTA","TIPO DE TRAMITE","ITEM","PLACA","REMITENTE",
        "CORREO REMITENTE","FECHA RESPUESTA DERECHO DE PETICIÓN","FECHA RESPUESTA AL AREA DE JURIDICA",
        "OBSERVACIONES","FECHA DE VENCIMIENTO","DIAS PENDIENTES","SEMAFORO"
    ],
    "resoluciones": [
        "SADE INGRESO","EXPEDIENTE","SADE SALIDA","RESOLUCIÓN NO.","FECHA","TIPO DE RESOLUCION"
    ],
    "traslados": [
        "CANAL DE INGRESO","IT.","No. PLANILLA","No. EXPEDIENTE","ACTO ADMINISTRATIVO",
        "FECHA PLANILLA INGRESO","No. ACTO ADMINISTRATIVO Y No. SADE","FECHA ACTO",
        "PROCESO","No. DE IDENTIFICACION","CONTRIBUYENTE","IMPUESTO","TIPO DE RENTA",
        "TIPO DE TRAMITE","ITEM","TIPO","DIRECCION","CIUDAD","PERIODO","VIGENCIA",
        "FECHA VENCIMIENTO","CAPITAL","SANCION","FUNCIONARIO ENCARGADO","UBICACIÓN",
        "OBSERVACIONES","ESTADO DEL PROCESO","RESOLUCION/SADE SALIDA","FECHA RESOLUCION",
        "NUMERO DE PLANILLA","FECHA PLANILLA","FECHA EJECUTORIA","DIAS PENDIENTES EJECUTORIA",
        "DEPENDENCIA","TIPO DE RESPUESTA","AÑO INGRESO","MES INGRESO"
    ],
}

def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
    else:
        with open("credentials.json") as f:
            creds_info = json.load(f)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)

def serialize(val):
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y")
    if val is None:
        return ""
    return str(val)

def calc_semaforo(fecha_venc_str, estado):
    if estado in ("CONTESTADO", "CERRADO"):
        return "VERDE", 0
    try:
        fv = datetime.strptime(fecha_venc_str, "%Y-%m-%d").date()
        dias = (fv - date.today()).days
        if dias < 0:
            return "ROJO", dias
        elif dias <= 7:
            return "ROJO", dias
        elif dias <= 15:
            return "AMARILLO", dias
        else:
            return "VERDE", dias
    except Exception:
        return "AMARILLO", 0

# ── GET: leer registros de una hoja ──────────────────────────────────────────
@app.route("/api/records/<module>", methods=["GET"])
def get_records(module):
    if module not in SHEET_MAP:
        return jsonify({"error": "Módulo no válido"}), 400
    try:
        gc = get_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(SHEET_MAP[module])
        rows = ws.get_all_records(head=1)
        return jsonify({"data": rows, "total": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── POST: crear nuevo registro ────────────────────────────────────────────────
@app.route("/api/records/<module>", methods=["POST"])
def create_record(module):
    if module not in SHEET_MAP:
        return jsonify({"error": "Módulo no válido"}), 400
    try:
        body = request.get_json()
        gc = get_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(SHEET_MAP[module])

        semaforo, dias = calc_semaforo(
            body.get("fecha_vencimiento", ""),
            body.get("estado", "PENDIENTE")
        )
        body["semaforo"] = semaforo
        body["dias_pendientes"] = dias
        body["anio_ingreso"] = datetime.now().year
        body["mes_ingreso"] = datetime.now().month

        headers = HEADERS.get(module, list(body.keys()))
        row = [serialize(body.get(h.lower().replace(" ", "_").replace(".", "").replace("/", "").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n"), "")) for h in headers]

        ws.append_row(row, value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "semaforo": semaforo, "dias": dias}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── PUT: actualizar registro por número de fila ───────────────────────────────
@app.route("/api/records/<module>/<int:row_index>", methods=["PUT"])
def update_record(module, row_index):
    if module not in SHEET_MAP:
        return jsonify({"error": "Módulo no válido"}), 400
    try:
        body = request.get_json()
        gc = get_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(SHEET_MAP[module])

        semaforo, dias = calc_semaforo(
            body.get("fecha_vencimiento", ""),
            body.get("estado", "PENDIENTE")
        )
        body["semaforo"] = semaforo
        body["dias_pendientes"] = dias

        headers = HEADERS.get(module, list(body.keys()))
        row = [serialize(body.get(h.lower().replace(" ", "_").replace(".", "").replace("/", "").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n"), "")) for h in headers]

        # row_index es 1-based desde el frontend (fila 2 = primera de datos)
        ws.update(f"A{row_index + 1}", [row])
        return jsonify({"ok": True, "semaforo": semaforo, "dias": dias})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── GET: métricas consolidadas ────────────────────────────────────────────────
@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    try:
        gc = get_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        metrics = {}
        for mod, sheet_name in SHEET_MAP.items():
            try:
                ws = sh.worksheet(sheet_name)
                rows = ws.get_all_records(head=1)
                pend  = sum(1 for r in rows if str(r.get("SEMAFORO DE VENCIMIENTO","")).upper() in ("PENDIENTE","AMARILLO","ROJO"))
                venc  = sum(1 for r in rows if str(r.get("SEMAFORO DE VENCIMIENTO","")).upper() == "ROJO")
                cont  = sum(1 for r in rows if str(r.get("SEMAFORO DE VENCIMIENTO","")).upper() in ("CONTESTADO","VERDE","CERRADO"))
                metrics[mod] = {"total": len(rows), "pendientes": pend, "vencidos": venc, "contestados": cont}
            except Exception:
                metrics[mod] = {"total": 0, "pendientes": 0, "vencidos": 0, "contestados": 0}
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── GET: listas de opciones (para dropdowns) ──────────────────────────────────
@app.route("/api/lists", methods=["GET"])
def get_lists():
    try:
        gc = get_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("Listas")
        data = ws.get_all_values()
        listas = {
            "rentas":       [r[0] for r in data[1:] if r[0]],
            "tramites":     [r[2] for r in data[1:] if len(r)>2 and r[2]],
            "items":        [r[3] for r in data[1:] if len(r)>3 and r[3]],
            "tipo_respuesta":[r[5] for r in data[1:] if len(r)>5 and r[5]],
            "canales":      [r[7] for r in data[1:] if len(r)>7 and r[7]],
            "areas":        [r[8] for r in data[1:] if len(r)>8 and r[8]],
            "funcionarios": [r[20] for r in data[1:] if len(r)>20 and r[20]],
        }
        # dedup
        listas = {k: list(dict.fromkeys(v)) for k, v in listas.items()}
        return jsonify(listas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
