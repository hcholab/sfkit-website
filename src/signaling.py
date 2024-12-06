import asyncio
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List

from quart import Blueprint, Websocket, abort, websocket

from src.api_utils import fetch_study
from src.auth import get_cli_user, get_user_id
from src.utils import constants, custom_logging

bp = Blueprint("signaling", __name__, url_prefix="/api")
logger = custom_logging.setup_logging(__name__)

PID = int


class MessageType(Enum):
    CANDIDATE = "candidate"
    CREDENTIAL = "credential"
    CERTIFICATE = "certificate"
    ERROR = "error"


@dataclass
class Message:
    type: MessageType
    data: str = ""
    studyID: str = ""
    sourcePID: PID = -1
    targetPID: PID = -1

    async def send(self, ws: Websocket):
        msg = asdict(self)
        for key, value in msg.items():
            if isinstance(value, Enum):
                msg[key] = value.value
        if self.type == MessageType.ERROR:
            logger.error("Sending error message: %s", msg)
        await ws.send_json(msg)

    @staticmethod
    async def receive(ws: Websocket):
        msg = await ws.receive_json()
        logger.debug("Received: %s", msg)
        msg["type"] = MessageType(msg["type"])
        return Message(**msg)


# in-memory stores for Websockets
study_barriers: Dict[str, asyncio.Barrier] = {}
study_parties: Dict[str, Dict[PID, Websocket]] = {}

STUDY_ID_HEADER = "X-MPC-Study-ID"


@bp.websocket("/ice")
async def ice_ws():
    user_id = await _get_user_id(websocket)
    if not user_id:
        await Message(MessageType.ERROR, "Missing authentication").send(websocket)
        abort(401)

    study_id = websocket.headers.get(STUDY_ID_HEADER)
    if not study_id:
        await Message(MessageType.ERROR, f"Missing {STUDY_ID_HEADER} header").send(websocket)
        abort(400)

    study_participants = await _get_study_participants(study_id)

    pid = _get_pid(study_participants, user_id)
    if pid < 0:
        await Message(MessageType.ERROR, f"User {user_id} is not in study {study_id}").send(websocket)
        abort(403)

    parties = study_parties.setdefault(study_id, {})
    if pid in parties:
        await Message(
            MessageType.ERROR,
            f"Party {pid} is already connected to study {study_id}",
        ).send(websocket)
        abort(409)

    try:
        # store the current websocket for the party
        parties[pid] = websocket._get_current_object()  # type: ignore
        logger.info("Registered websocket for party %d", pid)

        # using a study-specific barrier,
        # wait until all participants in a study are connected,
        # and then initiate the ICE protocol for it
        barrier = study_barriers.setdefault(study_id, asyncio.Barrier(len(study_participants)))
        async with barrier:
            if pid == 0:
                logger.info("PID %d: All parties have connected: %s", pid, parties)

            while True:
                logger.debug("pid: %d, parties: %s", pid, parties)
                # read the next message and override its PID
                # (this prevents PID spoofing)
                msg = await Message.receive(websocket)
                msg.sourcePID = pid
                msg.studyID = study_id

                # and send it to the other party
                if msg.targetPID < 0:
                    await Message(MessageType.ERROR, f"Missing target PID: {msg}").send(websocket)
                    continue
                elif msg.targetPID not in parties or msg.targetPID == pid:
                    logger.error("Unexpected message is %s. Parties are %s", msg, parties)
                    await Message(
                        MessageType.ERROR,
                        f"Unexpected target id {msg.targetPID}",
                    ).send(websocket)
                    continue
                else:
                    target_ws = parties[msg.targetPID]
                    await msg.send(target_ws)
    except Exception as e:
        logger.error("Terminal connection error for party %d in study %s: %s", pid, study_id, e)
    finally:
        del parties[pid]
        logger.warning("Party %d disconnected from study %s", pid, study_id)


async def _get_user_id(ws: Websocket):
    # sourcery skip: assign-if-exp, reintroduce-else, remove-unnecessary-else, swap-if-else-branches
    if constants.TERRA:
        return await get_user_id(ws)
    else:
        user = await get_cli_user(ws)
        if user:
            return user["username"]
        else:
            await Message(MessageType.ERROR, "Unable_to_read_auth_key").send(ws)


async def _get_study_participants(study_id: str) -> List[str]:
    _, _, doc_ref_dict = await fetch_study(study_id)
    return doc_ref_dict.get("participants", [])


def _get_pid(study: List[str], user_id: str) -> PID:
    return study.index(user_id) if user_id in study else -1
