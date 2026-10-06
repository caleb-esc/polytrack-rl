window.PolyTrackMods.register({

    id: "rl_controller",


    activate(api) {

        api.log(
            "RL Controller starting..."
        );


        let socket = null;

        let training = false;

        let lastAction = 1;


        /* ----------------------------------
           CONNECT TO PYTHON
        ---------------------------------- */

        function connect() {

            socket = new WebSocket(
                "ws://127.0.0.1:8765"
            );


            socket.onopen = () => {

                api.log(
                    "Connected to RL bridge"
                );


                socket.send(
                    JSON.stringify({

                        type: "hello",

                        role: "game"

                    })
                );

            };


            socket.onclose = () => {

                api.log(
                    "RL bridge disconnected"
                );

            };


            socket.onerror = () => {

                api.log(
                    "Could not connect to RL bridge"
                );

            };


            socket.onmessage =
                event => {

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


                    /* --------------------------
                       TRAINING ENABLED
                    -------------------------- */

                    if (
                        message.type ===
                        "training"
                    ) {

                        training =
                            Boolean(
                                message.enabled
                            );

                        return;

                    }


                    /* --------------------------
                       RESET
                    -------------------------- */

                    if (
                        message.type ===
                        "reset"
                    ) {

                        restartRace();

                        return;

                    }


                    /* --------------------------
                       ACTION
                    -------------------------- */

                    if (
                        message.type ===
                        "action"
                    ) {

                        lastAction =
                            message.action;


                        if (training) {

                            applyAction(
                                lastAction
                            );

                        }

                    }

                };

        }


        /* ----------------------------------
           GET GAME STATE
        ---------------------------------- */

        function readGameState() {

            /*
             *
             * IMPORTANT:
             *
             * This is intentionally isolated.
             *
             * Your PolyTrack version/mod loader
             * needs to expose the car's state here.
             *
             */


            if (
                window.__RL_POLYTRACK_STATE__
            ) {

                return (
                    window
                        .__RL_POLYTRACK_STATE__
                );

            }


            return null;

        }


        /* ----------------------------------
           SEND ACTION TO GAME
        ---------------------------------- */

        function applyAction(
            action
        ) {

            /*
             *
             * 0:
             * left + throttle
             *
             * 1:
             * throttle
             *
             * 2:
             * right + throttle
             *
             * 3:
             * brake
             *
             * 4:
             * straight + throttle
             *
             */


            releaseControls();


            if (action === 0) {

                press(
                    "ArrowLeft"
                );

                press(
                    "ArrowUp"
                );

            }


            if (action === 1) {

                press(
                    "ArrowUp"
                );

            }


            if (action === 2) {

                press(
                    "ArrowRight"
                );

                press(
                    "ArrowUp"
                );

            }


            if (action === 3) {

                press(
                    "ArrowDown"
                );

            }


            if (action === 4) {

                press(
                    "ArrowUp"
                );

            }

        }


        /* ----------------------------------
           KEY HELPERS
        ---------------------------------- */

        function press(key) {

            window.dispatchEvent(

                new KeyboardEvent(
                    "keydown",
                    {
                        key: key
                    }
                )

            );

        }


        function release(key) {

            window.dispatchEvent(

                new KeyboardEvent(
                    "keyup",
                    {
                        key: key
                    }
                )

            );

        }


        function releaseControls() {

            release(
                "ArrowLeft"
            );

            release(
                "ArrowRight"
            );

            release(
                "ArrowUp"
            );

            release(
                "ArrowDown"
            );

        }


        /* ----------------------------------
           RESTART
        ---------------------------------- */

        function restartRace() {

            press("r");

            release("r");

        }


        /* ----------------------------------
           STATE LOOP
        ---------------------------------- */

        const stateLoop =
            setInterval(
                () => {

                    if (
                        !training
                    ) {

                        return;

                    }


                    if (
                        !socket ||
                        socket.readyState !==
                            WebSocket.OPEN
                    ) {

                        return;

                    }


                    const state =
                        readGameState();


                    if (!state) {

                        return;

                    }


                    socket.send(

                        JSON.stringify({

                            type: "state",

                            state: state,

                            lastAction:
                                lastAction

                        })

                    );

                },

                50
            );


        /* ----------------------------------
           START
        ---------------------------------- */

        connect();


        /* ----------------------------------
           CLEANUP
        ---------------------------------- */

        api.addCleanup(
            () => {

                clearInterval(
                    stateLoop
                );


                releaseControls();


                if (socket) {

                    socket.close();

                }

            }
        );

    },


    deactivate(api) {

        api.log(
            "RL Controller stopped"
        );

    }

});
