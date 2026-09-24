"""
Genera el archivo n8n/chaskimarket_pipeline.json (flujo de n8n exportado,
listo para importar con "Import from File" en n8n).

Flujo:
  Schedule Trigger (diario 8am)
    -> Execute Command (corre etl_diario.py)
    -> Code (parsea la última línea de stdout como JSON)
    -> IF: ¿estado == "procesado"?
         -> SI -> IF: ¿tiene_anomalia?
                    -> SI -> Gmail: correo de ALERTA
                    -> NO -> Gmail: correo de RESUMEN diario
         -> NO -> (no hace nada, no había archivos nuevos)
"""
import json
import uuid

RUTA_PROYECTO = "/ruta/a/tu/proyecto/chaskimarket-pipeline"  # <-- AJUSTAR al importar

def nid():
    return str(uuid.uuid4())

n_trigger = nid()
n_exec = nid()
n_code = nid()
n_if_procesado = nid()
n_if_anomalia = nid()
n_gmail_alerta = nid()
n_gmail_resumen = nid()

code_js = '''
// Toma el stdout del nodo "Execute Command" y parsea la última línea
// (el JSON de resumen que imprime etl_diario.py) como un objeto.
const raw = $input.first().json.stdout || "";
const lineas = raw.trim().split("\\n").filter(l => l.trim().length > 0);
const ultima = lineas[lineas.length - 1] || "{}";
let resumen;
try {
  resumen = JSON.parse(ultima);
} catch (e) {
  resumen = { estado: "error_parseo", raw: ultima };
}
return [{ json: resumen }];
'''.strip()

workflow = {
    "name": "ChaskiMarket - Pipeline diario de ventas",
    "nodes": [
        {
            "id": n_trigger,
            "name": "Disparador diario 8am",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-200, 0],
            "parameters": {
                "rule": {
                    "interval": [
                        {"field": "cronExpression", "expression": "0 8 * * *"}
                    ]
                }
            },
        },
        {
            "id": n_exec,
            "name": "Ejecutar ETL Python",
            "type": "n8n-nodes-base.executeCommand",
            "typeVersion": 1,
            "position": [40, 0],
            "parameters": {
                "command": f"cd {RUTA_PROYECTO} && python3 etl_diario.py"
            },
        },
        {
            "id": n_code,
            "name": "Parsear resumen JSON",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [280, 0],
            "parameters": {
                "mode": "runOnceForAllItems",
                "jsCode": code_js,
            },
        },
        {
            "id": n_if_procesado,
            "name": "¿Se procesó un archivo?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [520, 0],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": nid(),
                            "leftValue": "={{ $json.estado }}",
                            "rightValue": "procesado",
                            "operator": {"type": "string", "operation": "equals"},
                        }
                    ],
                }
            },
        },
        {
            "id": n_if_anomalia,
            "name": "¿Hay anomalía?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [760, -80],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": nid(),
                            "leftValue": "={{ $json.tiene_anomalia }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                }
            },
        },
        {
            "id": n_gmail_alerta,
            "name": "Gmail - Enviar alerta",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [1000, -160],
            "parameters": {
                "sendTo": "winercr12383@gmail.com",
                "subject": "=⚠️ ChaskiMarket - Anomalía detectada ({{ $json.fecha }})",
                "message": "=Se detectó una anomalía al procesar las ventas del {{ $json.fecha }}.\\n\\nVentas del día: S/ {{ $json.ventas_total_dia }}\\nPromedio histórico (30 días): S/ {{ $json.promedio_historico_30d }}\\nFilas descartadas: {{ $json.filas_descartadas }} de {{ $json.filas_leidas }} ({{ $json.pct_descartado }})\\n\\nDetalle:\\n{{ JSON.stringify($json.anomalias, null, 2) }}",
                "options": {},
            },
            "credentials": {
                "gmailOAuth2": {"id": "REEMPLAZAR_AL_IMPORTAR", "name": "Gmail account"}
            },
        },
        {
            "id": n_gmail_resumen,
            "name": "Gmail - Enviar resumen",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [1000, 40],
            "parameters": {
                "sendTo": "winercr12383@gmail.com",
                "subject": "=Resumen diario ChaskiMarket - {{ $json.fecha }}",
                "message": "=Pipeline ejecutado correctamente para el {{ $json.fecha }}.\\n\\nVentas del día: S/ {{ $json.ventas_total_dia }}\\nTicket promedio: S/ {{ $json.ticket_promedio }}\\nFilas válidas: {{ $json.filas_validas }} de {{ $json.filas_leidas }}\\n\\nSin anomalías detectadas.",
                "options": {},
            },
            "credentials": {
                "gmailOAuth2": {"id": "REEMPLAZAR_AL_IMPORTAR", "name": "Gmail account"}
            },
        },
    ],
    "connections": {
        "Disparador diario 8am": {"main": [[{"node": "Ejecutar ETL Python", "type": "main", "index": 0}]]},
        "Ejecutar ETL Python": {"main": [[{"node": "Parsear resumen JSON", "type": "main", "index": 0}]]},
        "Parsear resumen JSON": {"main": [[{"node": "¿Se procesó un archivo?", "type": "main", "index": 0}]]},
        "¿Se procesó un archivo?": {
            "main": [
                [{"node": "¿Hay anomalía?", "type": "main", "index": 0}],
                [],
            ]
        },
        "¿Hay anomalía?": {
            "main": [
                [{"node": "Gmail - Enviar alerta", "type": "main", "index": 0}],
                [{"node": "Gmail - Enviar resumen", "type": "main", "index": 0}],
            ]
        },
    },
    "active": False,
    "settings": {"executionOrder": "v1"},
    "meta": {"instanceId": "chaskimarket-demo"},
}

with open("chaskimarket_pipeline.json", "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

print("Generado chaskimarket_pipeline.json")
