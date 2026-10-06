let socket = null;


const ids = [

    "progress",
    "speed",
    "finish",
    "crash",
    "offtrack",
    "center",

    "alpha",
    "gamma",
    "epsilon"

];


function $(id) {

    return document.getElementById(id);

}


/* ---------------------------------------
   SLIDERS
--------------------------------------- */

ids.forEach(id => {

    const input = $(id);

    const output = $(id + "V");


    function update() {

        output.textContent =
            input.value;

    }


    input.addEventListener(
        "input",
        () => {

            update();

            sendSettings();

        }
    );


    update();

});


/* ---------------------------------------
   STATUS
--------------------------------------- */

function setStatus(
    text,
    connected
) {

    const element =
        $("connection");


    element.textContent =
        text;


    element.className =
        connected
            ? "connected"
            : "disconnected";

}


/* ---------------------------------------
   CONNECT
--------------------------------------- */

function connect() {

    if (
        socket &&
        socket.readyState === WebSocket.OPEN
    ) {

        return;

    }


    socket = new WebSocket(
        "ws://127.0.0.1:8765"
    );


    socket.onopen = () => {

        setStatus(
            "Bridge Connected",
            true
        );


        socket.send(
            JSON.stringify({

                type: "hello",

                role: "dashboard"

            })
        );


        sendSettings();

    };


    socket.onclose = () => {

        setStatus(
            "Disconnected",
            false
        );

    };


    socket.onerror = () => {

        setStatus(
            "Bridge Error",
            false
        );

    };


    socket.onmessage = event => {

        let message;


        try {

            message =
                JSON.parse(
                    event.data
                );

        }

        catch {

            return;

        }


        /* -----------------------------
           SNAPSHOT
        ----------------------------- */

        if (
            message.type ===
            "snapshot"
        ) {

            if (
                message.settings
            ) {

                Object.entries(
                    message.settings
                ).forEach(
                    ([key, value]) => {

                        if ($(key)) {

                            $(key).value =
                                value;

                            $(key + "V")
                                .textContent =
                                value;

                        }

                    }
                );

            }


            $("episode")
                .textContent =
                message.episode;


            $("states")
                .textContent =
                message.qStates;


            $("best")
                .textContent =
                message.bestTime == null
                    ? "—"
                    :
                    Number(
                        message.bestTime
                    ).toFixed(3) + "s";

        }


        /* -----------------------------
           TELEMETRY
        ----------------------------- */

        if (
            message.type ===
            "telemetry"
        ) {

            $("episode")
                .textContent =
                message.episode;


            $("states")
                .textContent =
                message.qStates;


            $("reward")
                .textContent =
                Number(
                    message.reward
                ).toFixed(3);


            $("best")
                .textContent =
                message.bestTime == null
                    ? "—"
                    :
                    Number(
                        message.bestTime
                    ).toFixed(3) + "s";


            const actions = [

                "LEFT + THROTTLE",

                "THROTTLE",

                "RIGHT + THROTTLE",

                "BRAKE",

                "STRAIGHT + THROTTLE"

            ];


            $("telemetry")
                .textContent =

`Action:
${actions[message.action]}

State:
${message.state}

Exploration:
${Number(
    message.epsilon
).toFixed(3)}

Reward:
${Number(
    message.reward
).toFixed(3)}

Learned Q states:
${message.qStates}`;

        }

    };

}


/* ---------------------------------------
   SEND SETTINGS
--------------------------------------- */

function sendSettings() {

    if (
        !socket ||
        socket.readyState !==
            WebSocket.OPEN
    ) {

        return;

    }


    const values = {};


    ids.forEach(id => {

        values[id] =
            Number(
                $(id).value
            );

    });


    socket.send(
        JSON.stringify({

            type: "settings",

            values

        })
    );

}


/* ---------------------------------------
   COMMANDS
--------------------------------------- */

function command(
    type,
    extra = {}
) {

    if (
        !socket ||
        socket.readyState !==
            WebSocket.OPEN
    ) {

        alert(
            "Connect to the local bridge first."
        );

        return;

    }


    socket.send(
        JSON.stringify({

            type,

            ...extra

        })
    );

}


/* ---------------------------------------
   BUTTONS
--------------------------------------- */

$("connect").onclick =
    connect;


$("train").onclick =
    () => {

        command(
            "train",
            {
                enabled: true
            }
        );

    };


$("stop").onclick =
    () => {

        command(
            "train",
            {
                enabled: false
            }
        );

    };


$("reset").onclick =
    () => {

        command(
            "reset"
        );

    };


$("save").onclick =
    () => {

        command(
            "save_model"
        );

    };


$("load").onclick =
    () => {

        command(
            "load_model"
        );

    };
