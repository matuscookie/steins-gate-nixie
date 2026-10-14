Steins;Gate Nixie Clock & Divergence Meter

A desktop widget in the style of the nixie tube divergence meter from Steins;Gate.
<img width="597" height="174" alt="image" src="https://github.com/user-attachments/assets/2c5e9bd5-88d4-4f95-9afb-116ded3ea8ca" />

Features
Clock mode: HH:MM:SS across eight tubes, with blinking colons, 12/24-hour time, and an automatic cathode "cleaning" spin at the top of every hour.
Divergence meter mode: shows world line values such as 1.048596, with presets for Steins Gate, Alpha, Beta, Gamma, and Start, plus a random world line.
Wire-style digits: thin glowing wires, with the unlit digits visible stacked inside each tube.
Dark smoked glass (default) or clear glass that shows your desktop through the tubes.
Borderless, draggable, always-on-top window, with four sizes.
Future Gadget Lab pin on the side. Click it to flip between clock and meter.

Requirements
Python 3 with tkinter (included with most Python installs for Windows and macOS)
Optional: Pillow for smoother pin scaling (pip install pillow)

On Linux you may need to install tkinter first, for example sudo apt install python3-tk.
Run
bash
python steins_gate_nixie.py

The logo is embedded in the script, so that one file is all you need.

Controls
Action	What it does
Drag (left mouse)	Move the widget anywhere
Double-click	Cathode spin (clock) or new random world line (meter)
Click the pin	Switch between clock and divergence meter
Right-click	Menu: mode, world lines, 12/24h, blinking colons, clear glass, size, always on top, quit
Esc	Close

Notes
On Windows, the area around the tubes is truly see-through. On macOS and Linux it shows as a flat near-black background instead.
To use a different image for the pin, put a fgl_pin.png next to the script and it will replace the built-in one.
With clear glass on, grab the widget by a tube's outline, the mesh, or the base. Empty glass areas are click-through on Windows.

This is a unofficial fan made project enjoy 
El phsy congro...
