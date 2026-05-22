# wphs-3d-printer

The code for the project is in the `wphs-3d-printer` folder on the 
Raspberry Pi. The code can be found online at 
https://github.com/ion098/wphs-3d-printer.

To run the code, click `startup.sh` and select `Execute in Terminal`.

You can end the code by pressing `Ctrl+C` 3 times.

## Setup:

The project is configured using a file called `config.toml`, in the 
`wphs-3d-printer` folder. Each camera is defined as follows:

	[[cameras]]
	id = 1234
	token = "ABCD123"

Repeat this text for each camera, replacing the id and token with the 
actual values.

The token can be found in the PrusaConnect dashboard for the camera.
To add a new camera, press "Add Other Camera" in PrusaConnect. The ID 
is a number that starts from 0 and identifies the camera out of all 
the cameras attached.  To find the ID, run `ffplay /dev/video1234`, 
replacing 1234 with the ID to test. Start at 0 and increment by one 
to figure out which ID is which camera (some IDs will not match any
camera, you`ll just get an error message). IMPORTANT: This ID changes 
everytime the Pi is restarted or loses power.
