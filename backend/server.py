"""
WebSocket server for the multi-agent diagnosis system.
Handles client connections and message routing.
"""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from loguru import logger

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Note: Logging is configured in main.py via config.setup_logging()
# Do not configure logging here to avoid duplicate handlers


# =============================================================================
# WebSocket Connection Manager
# =============================================================================


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._max_connections = 100  # Can be configured via config

    async def connect(self, websocket: WebSocket):
        """Accept and register a new connection."""
        if len(self.active_connections) >= self._max_connections:
            await websocket.close(code=1013, reason="Max connections reached")
            logger.warning(
                f"Connection rejected: max connections ({self._max_connections}) reached"
            )
            return False

        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )
        return True

    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        self.active_connections.discard(websocket)
        logger.info(
            f"Client disconnected. Total connections: {len(self.active_connections)}"
        )

    async def send(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            await websocket.send_text(json.dumps(message))
        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected, message not sent")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except WebSocketDisconnect:
                logger.debug("WebSocket disconnected during broadcast")
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(title="Vehicle Power Diagnosis System", version="1.0.0")

# CORS middleware for frontend deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

# Application state (replacing global variables)
_app_state: Dict[str, Any] = {
    "diagnosis_pipeline": None,
    "ontology_parser": None,
}


def get_app_state() -> Dict[str, Any]:
    """Get application state."""
    return _app_state


def initialize_app(pipeline, parser):
    """Initialize the application with pipeline and parser."""
    _app_state["diagnosis_pipeline"] = pipeline
    _app_state["ontology_parser"] = parser
    logger.info("Application initialized")


# Keep backward compatibility with existing initialize_app import
diagnosis_pipeline = None  # Deprecated, use get_app_state()
ontology_parser = None  # Deprecated, use get_app_state()


# =============================================================================
# Routes
# =============================================================================


@app.get("/")
async def get_root():
    """Serve the frontend or API info."""
    return {
        "service": "Vehicle Power Diagnosis System",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {"websocket": "/ws", "health": "/health"},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ontology_loaded": _app_state.get("ontology_parser") is not None,
        "pipeline_ready": _app_state.get("diagnosis_pipeline") is not None,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for diagnosis pipeline.

    Expected messages from client:
    - {"type": "start", "symptom": "...", "dtc_codes": ["U0100", "P0562"], "role": "owner|technician|customer_service", "signals": {...}}

    Note: Either symptom or dtc_codes (or both) should be provided.

    Messages sent to client:
    - agent_status, msg_bus, wire_animate, reasoning_step, onto_summary
    - rule_matched, hypothesis, conf_factors, conf_final, output, pipeline_done, error
    """
    await manager.connect(websocket)

    try:
        # Wait for messages
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_message(message, websocket)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                await manager.send(
                    {"type": "error", "message": "Invalid JSON format"}, websocket
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {type(e).__name__}: {e}")
        manager.disconnect(websocket)
        try:
            await manager.send({"type": "error", "message": str(e)}, websocket)
        except WebSocketDisconnect:
            pass  # Connection already closed


async def handle_message(message: dict, websocket: WebSocket):
    """Handle incoming WebSocket messages."""
    msg_type = message.get("type")

    # ✨ 新增: 客户端就绪探测
    if msg_type == "ping":
        await manager.send(
            {
                "type": "pong",
                "server_time": asyncio.get_event_loop().time(),
                "version": "1.1.0",
            },
            websocket,
        )
        return

    # ✨ 新增: 客户端准备就绪
    if msg_type == "client_ready":
        client_version = message.get("client_version", "unknown")
        logger.info(f"Client ready, version: {client_version}")

        parser = _app_state.get("ontology_parser")
        pipeline = _app_state.get("diagnosis_pipeline")

        stats = {
            "classes": len(parser.classes) if parser else 0,
            "obj_props": len(parser.object_properties) if parser else 0,
            "data_props": len(parser.datatype_properties) if parser else 0,
            "individuals": len(parser.individuals) if parser else 0,
        }

        await manager.send(
            {
                "type": "backend_status",
                "status": "ready",
                "ontology_loaded": parser is not None,
                "pipeline_ready": pipeline is not None,
                "ontology_stats": stats,
                "mode": "llm" if pipeline and pipeline.use_llm else "legacy",
            },
            websocket,
        )
        return

    if msg_type == "start":
        # Start diagnosis pipeline
        await start_diagnosis(message, websocket)
    else:
        logger.warning(f"Unknown message type: {msg_type}")
        await manager.send(
            {"type": "error", "message": f"Unknown message type: {msg_type}"}, websocket
        )


async def start_diagnosis(message: dict, websocket: WebSocket):
    """Start the diagnosis pipeline."""
    from models import DiagnosisContext, Role

    # Extract parameters
    symptom = message.get("symptom", "")
    role_str = message.get("role", "owner")
    signals = message.get("signals", {})
    dtc_codes = message.get("dtc_codes", [])  # DTC codes support
    demo_mode = message.get("demo", False)  # Demo mode flag
    use_ontology = message.get("use_ontology", True)  # Default: ontology enabled

    # Validate - need either symptom or DTC codes
    if not symptom and not dtc_codes:
        await manager.send(
            {"type": "error", "message": "Either symptom or dtc_codes is required"},
            websocket,
        )
        return

    # Check for demo mode
    if demo_mode:
        await run_demo_mode(manager, websocket, message)
        return

    # Map role
    role_map = {
        "owner": Role.OWNER,
        "technician": Role.TECHNICIAN,
        "customer_service": Role.CUSTOMER_SERVICE,
    }
    role = role_map.get(role_str, Role.OWNER)

    # Create context with DTC codes
    context = DiagnosisContext(
        symptom=symptom, role=role, signals=signals, dtc_codes=dtc_codes
    )
    context.use_ontology = use_ontology

    # Log diagnosis start
    log_msg = f"Starting diagnosis"
    if symptom:
        log_msg += f" for symptom: {symptom[:50]}..."
    if dtc_codes:
        log_msg += f" with DTC codes: {dtc_codes}"
    logger.info(log_msg)

    # === NEW: Send ontology summary BEFORE diagnosis starts ===
    parser = _app_state.get("ontology_parser")
    if parser:
        onto_counts = {
            "classes": len(parser.classes),
            "properties": len(parser.object_properties)
            + len(parser.datatype_properties),
            "rules": len(parser.individuals),
        }
        await manager.send(
            {
                "type": "onto_summary",
                "counts": onto_counts,
                "summary": f"已加载 {onto_counts['classes']} 个车辆概念类, {onto_counts['properties']} 个属性",
            },
            websocket,
        )

    # Create message sender that sends to this specific client
    async def send_to_client(msg: dict):
        await manager.send(msg, websocket)

    # Run pipeline
    try:
        pipeline = _app_state.get("diagnosis_pipeline")
        if pipeline:
            result = await pipeline.run(context, send_to_client)
            logger.info(f"Diagnosis complete. Confidence: {result.final_confidence}%")
        else:
            await manager.send(
                {"type": "error", "message": "Diagnosis pipeline not initialized"},
                websocket,
            )
    except Exception as e:
        logger.error(f"Diagnosis pipeline error ({type(e).__name__}): {e}")
        try:
            await manager.send(
                {"type": "error", "message": f"Pipeline error: {str(e)}"}, websocket
            )
        except WebSocketDisconnect:
            pass  # Connection already closed


async def run_demo_mode(
    manager: ConnectionManager, websocket: WebSocket, message: dict
):
    """Run in demo mode with simulated responses for reliable presentations."""

    symptom = message.get("symptom", "")
    role = message.get("role", "owner")

    logger.info(f"Running in demo mode for: {symptom[:30]}...")

    # Step 1: Ontology summary
    await manager.send(
        {
            "type": "onto_summary",
            "counts": {"classes": 142, "properties": 55, "rules": 28},
            "summary": "已加载 142 个车辆概念类, 55 个属性",
        },
        websocket,
    )
    await asyncio.sleep(0.5)

    # Step 2-7: Reasoning steps
    steps = [
        ("[1] 症状解析", "识别到关键症状: 启动按钮无响应, 电源模式异常"),
        (
            "[2] 本体查询",
            "检索到 12 个相关车辆概念: PowerMode, IgnitionState, VehicleStatus...",
        ),
        ("[3] 规则匹配", "匹配到 5 条相关诊断规则"),
        (
            "[4] 假设生成",
            "生成 3 个诊断假设: H001(电源模式控制), H002(蓄电池), H003(启动机)",
        ),
        ("[5] 置信度计算", "H001: 85%, H002: 45%, H003: 30%"),
        ("[6] 输出生成", f"针对角色 '{role}' 生成诊断报告"),
    ]

    for title, body in steps:
        await manager.send(
            {"type": "reasoning_step", "step": {"title": title, "body": body}},
            websocket,
        )
        await asyncio.sleep(0.4)

    # Step 8: Matched rules
    rules = [
        {
            "id": "R-PM-001",
            "text": "如果电源模式=OFF且启动按钮按下, 则请求启动",
            "src": "VEEA-Spec",
            "conf": "高",
        },
        {
            "id": "R-PM-002",
            "text": "PEPS需要检测到有效钥匙才能切换电源模式",
            "src": "VEEA-Spec",
            "conf": "高",
        },
    ]
    for rule in rules:
        await manager.send({"type": "rule_matched", "rule": rule}, websocket)
        await asyncio.sleep(0.2)

    # Step 9: Hypotheses
    hypotheses = [
        {
            "id": "H001",
            "desc": "PEPS(无钥匙进入/启动系统)故障导致电源模式无法切换",
            "conf": 0.85,
            "factors": ["钥匙信号无效", "电源模式保持OFF"],
        },
        {
            "id": "H002",
            "desc": "蓄电池电量不足或接线松动",
            "conf": 0.45,
            "factors": ["电压过低", "启动无力"],
        },
    ]
    for hypo in hypotheses:
        await manager.send({"type": "hypothesis", "hypothesis": hypo}, websocket)
        await asyncio.sleep(0.2)

    # Step 10: Confidence factors
    await manager.send(
        {
            "type": "conf_factors",
            "factors": [
                {"label": "Symptom Match", "val": 0.9, "display": "90%"},
                {"label": "Signal Match", "val": 0.85, "display": "85%"},
                {"label": "Rule Support", "val": 0.8, "display": "80%"},
                {"label": "Ontology Relevance", "val": 0.75, "display": "75%"},
            ],
        },
        websocket,
    )
    await asyncio.sleep(0.3)

    # Step 11: Final confidence
    await manager.send(
        {"type": "conf_final", "confidence": 0.85, "level": "high"}, websocket
    )

    # Step 12: Output
    output_text = "根据您描述的症状（踩刹车按启动按钮，车辆无法上电），最可能的原因是PEPS无钥匙进入/启动系统故障。建议检查：1) 智能钥匙电池电量 2) 启动按钮背后的PEPS传感器 3) 车身控制模块BCM的通信状态。如无法自行解决，建议联系4S店进行专业诊断。"

    await manager.send(
        {
            "type": "output",
            "html": f"<p>{output_text}</p>",
            "output": {
                "text": output_text,
                "role": role,
                "escalation": False,
                "hint": None,
            },
            "escalation": None,
        },
        websocket,
    )

    # Step 13: Complete
    await manager.send({"type": "pipeline_done", "status": "success"}, websocket)

    logger.info("Demo mode completed successfully")
