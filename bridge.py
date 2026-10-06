import asyncio
import json
import os
import random
from collections import defaultdict

from websockets.server import serve


HOST = "127.0.0.1"
PORT = 8765

game_client = None
dashboard_clients = set()

training = False

episode = 0
best_time = None
last_reward = 0.0

Q = defaultdict(lambda: [0.0] * 5)

settings = {
    "progress": 3.0,
    "speed": 1.0,
    "finish": 250.0,
    "crash": 25.0,
    "offtrack": 10.0,
    "center": 1.0,

    "alpha": 0.16,
    "gamma": 0.94,
    "epsilon": 0.18,
}


# ---------------------------------------------------------
# STATE DISCRETIZATION
# ---------------------------------------------------------

def bucket(value, limits):
    for i, limit in enumerate(limits):
        if value < limit:
            return i

    return len(limits)


def make_state(state):
    if not state:
        return "unknown"

    progress = bucket(
        float(state.get("progress", 0)),
        [0.05, 0.15, 0.30, 0.50, 0.70, 0.85, 0.95]
    )

    lateral = bucket(
        float(state.get("lateral", 0)),
        [-0.75, -0.40, -0.15, 0.15, 0.40, 0.75]
    )

    speed = bucket(
        float(state.get("speed", 0)),
        [2, 5, 9, 14, 20, 30]
    )

    heading = bucket(
        abs(float(state.get("headingError", 0))),
        [0.03, 0.08, 0.16, 0.30, 0.60, 1.2]
    )

    airborne = int(bool(state.get("airborne", False)))

    return f"{progress}|{lateral}|{speed}|{heading}|{airborne}"


# ---------------------------------------------------------
# ACTION SELECTION
# ---------------------------------------------------------

def choose_action(state):

    values = Q[state]

    # Exploration
    if random.random() < settings["epsilon"]:
        return random.randrange(5)

    best = max(values)

    choices = [
        i for i, value in enumerate(values)
        if value == best
    ]

    return random.choice(choices)


# ---------------------------------------------------------
# REWARD FUNCTION
# ---------------------------------------------------------

def calculate_reward(previous, current):

    if not current:
        return 0.0

    previous_progress = float(
        previous.get("progress", 0)
    )

    current_progress = float(
        current.get("progress", 0)
    )

    progress_delta = current_progress - previous_progress

    speed = max(
        0,
        float(current.get("speed", 0))
    )

    lateral = abs(
        float(current.get("lateral", 0))
    )

    reward = 0.0

    # Progress
    reward += (
        settings["progress"]
        * progress_delta
    )

    # Speed
    reward += (
        settings["speed"]
        * speed
        * 0.01
    )

    # Staying near racing line
    reward += (
        settings["center"]
        * max(0, 1 - lateral)
        * 0.01
    )

    # Off track
    if current.get("offtrack"):
        reward -= settings["offtrack"]

    # Crash
    if current.get("crashed"):
        reward -= settings["crash"]

    # Finish
    if current.get("finished"):
        reward += settings["finish"]

    return reward


# ---------------------------------------------------------
# Q LEARNING
# ---------------------------------------------------------

def learn(
    state,
    action,
    reward,
    next_state,
    done
):

    current_q = Q[state]

    if done:

        target = reward

    else:

        next_best = max(
            Q[next_state]
        )

        target = (
            reward
            + settings["gamma"]
            * next_best
        )

    current_q[action] += (
        settings["alpha"]
        * (
            target
            - current_q[action]
        )
    )


# ---------------------------------------------------------
# NETWORK HELPERS
# ---------------------------------------------------------

async def send_dashboard(message):

    if not dashboard_clients:
        return

    raw = json.dumps(message)

    await asyncio.gather(
        *[
            client.send(raw)
            for client in list(
                dashboard_clients
            )
        ],
        return_exceptions=True
    )


async def send_game(message):

    global game_client

    if game_client is None:
        return

    try:

        await game_client.send(
            json.dumps(message)
        )

    except Exception:

        game_client = None


# ---------------------------------------------------------
# SAVE / LOAD
# ---------------------------------------------------------

def save_model(path="qtable.json"):

    data = {
        "q": dict(Q),
        "settings": settings
    }

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2
        )


def load_model(path="qtable.json"):

    global Q

    if not os.path.exists(path):
        return

    with open(
        path,
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    Q = defaultdict(
        lambda: [0.0] * 5,
        {
            key: list(value)
            for key, value
            in data.get("q", {}).items()
        }
    )

    settings.update(
        data.get(
            "settings",
            {}
        )
    )


# ---------------------------------------------------------
# CLIENT HANDLER
# ---------------------------------------------------------

async def handler(websocket):

    global game_client
    global training
    global episode
    global best_time
    global last_reward

    role = None

    previous_state = None
    previous_raw_state = None

    try:

        async for raw in websocket:

            try:
                message = json.loads(raw)

            except Exception:
                continue

            message_type = message.get(
                "type"
            )

            # -----------------------------------------
            # HELLO
            # -----------------------------------------

            if message_type == "hello":

                role = message.get(
                    "role"
                )

                if role == "game":

                    game_client = websocket

                    await websocket.send(
                        json.dumps({
                            "type":
                                "bridge_ready"
                        })
                    )

                elif role == "dashboard":

                    dashboard_clients.add(
                        websocket
                    )

                    await websocket.send(
                        json.dumps({
                            "type":
                                "snapshot",

                            "episode":
                                episode,

                            "bestTime":
                                best_time,

                            "qStates":
                                len(Q),

                            "settings":
                                settings
                        })
                    )

            # -----------------------------------------
            # SETTINGS
            # -----------------------------------------

            elif message_type == "settings":

                values = message.get(
                    "values",
                    {}
                )

                for key, value in values.items():

                    if key in settings:

                        settings[key] = float(
                            value
                        )

                await send_game({
                    "type":
                        "settings",

                    "values":
                        settings
                })

            # -----------------------------------------
            # TRAIN
            # -----------------------------------------

            elif message_type == "train":

                training = bool(
                    message.get(
                        "enabled",
                        False
                    )
                )

                await send_game({
                    "type":
                        "training",

                    "enabled":
                        training
                })

            # -----------------------------------------
            # RESET
            # -----------------------------------------

            elif message_type == "reset":

                previous_state = None
                previous_raw_state = None

                await send_game({
                    "type":
                        "reset"
                })

            # -----------------------------------------
            # SAVE
            # -----------------------------------------

            elif message_type == "save_model":

                save_model()

                await websocket.send(
                    json.dumps({
                        "type":
                            "saved"
                    })
                )

            # -----------------------------------------
            # LOAD
            # -----------------------------------------

            elif message_type == "load_model":

                load_model()

                await send_dashboard({
                    "type":
                        "snapshot",

                    "episode":
                        episode,

                    "bestTime":
                        best_time,

                    "qStates":
                        len(Q),

                    "settings":
                        settings
                })

            # -----------------------------------------
            # GAME STATE
            # -----------------------------------------

            elif (
                message_type == "state"
                and role == "game"
            ):

                current = message.get(
                    "state",
                    {}
                )

                state = make_state(
                    current
                )

                # Learn from previous frame
                if previous_raw_state is not None:

                    r = calculate_reward(
                        previous_raw_state,
                        current
                    )

                    last_reward = r

                    if previous_state is not None:

                        action = message.get(
                            "lastAction",
                            1
                        )

                        done = bool(
                            current.get(
                                "finished"
                            )
                            or
                            current.get(
                                "crashed"
                            )
                        )

                        learn(
                            previous_state,
                            action,
                            r,
                            state,
                            done
                        )

                previous_state = state
                previous_raw_state = current

                # Episode finished
                if (
                    current.get("finished")
                    or current.get("crashed")
                ):

                    if current.get(
                        "finished"
                    ):

                        episode += 1

                        race_time = current.get(
                            "time"
                        )

                        if isinstance(
                            race_time,
                            (int, float)
                        ):

                            if best_time is None:

                                best_time = race_time

                            else:

                                best_time = min(
                                    best_time,
                                    race_time
                                )

                    previous_state = None
                    previous_raw_state = None

                # Choose next action
                action = choose_action(
                    state
                )

                await websocket.send(
                    json.dumps({
                        "type":
                            "action",

                        "action":
                            action
                    })
                )

                await send_dashboard({
                    "type":
                        "telemetry",

                    "episode":
                        episode,

                    "bestTime":
                        best_time,

                    "reward":
                        last_reward,

                    "qStates":
                        len(Q),

                    "epsilon":
                        settings["epsilon"],

                    "action":
                        action,

                    "state":
                        state
                })

    finally:

        dashboard_clients.discard(
            websocket
        )

        if game_client is websocket:
            game_client = None


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

async def main():

    print()
    print("====================================")
    print(" PolyTrack RL Local Bridge")
    print("====================================")
    print()
    print(
        f"WebSocket: ws://{HOST}:{PORT}"
    )
    print()
    print(
        "Waiting for dashboard/game..."
    )
    print()

    load_model()

    async with serve(
        handler,
        HOST,
        PORT
    ):

        await asyncio.Future()


if __name__ == "__main__":

    asyncio.run(
        main()
)
