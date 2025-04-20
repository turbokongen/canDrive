# canDrive
Tools for hacking your car. Please consider checking out the tutorials made by Adam Varga about this project:
https://www.youtube.com/playlist?list=PLNiFaO8hU1z0o_6DSxk-jcVAM3UCUR-pY

Adam Varga has created this google sheet, so everybody can freely add their decoded IDs and packets, so it's easier for the community to collaborate:
https://docs.google.com/spreadsheets/d/1eBKiTwEE6aPnfw2EfSHItLeMz00fJq0Y0L99Ym7fKwU/edit?usp=sharing

# Content
- 01_canSniffer_Arduino: This code runs on your ESP32 sniffer device and creates an interface between the car and the GUI.
- 02_canSniffer_GUI: Powerful and easy-to-use graphical sniffer application used for reverse engineering CAN packets. Written in Python.
- 03_canSniffer_HW: Hardware projects for the custom OBD2 module. Made in Altium Designer. **This is only kept for reference**
- 04_canSniffer_FW: Embedded code running on the custom OBD2 module. **This is only kept for reference**
# Description
### 01_canSniffer_Arduino
This code creates the interface between the car and the canSniffer_GUI application. If the RANDOM_CAN define is set to 1, this code is generating random CAN packets in order to test the higher level code. The received packets will be echoed back. If the  RANDOM_CAN define is set to 0, the CAN_SPEED define  has to match the speed of the desired CAN channel in order to receive and transfer from and to the CAN bus.
 Required arduino packages: 
- CAN fork based on Cory J Fowlers MCP_CAN (https://github.com/turbokongen/MCP_CAN_lib)

Required modifications: 
Add the supplied mcp_can zip file library to the Arduino IDE when project open.
The can speed needs to be adjusted to your required setting for your specific application.
### 02_canSniffer_GUI
I recommend to use pyCharm Community edition.
Python 3 is required for this project, 3.8 is preferred. The GUI is based on pyQt. This project contains my decoded packets in save/decodedPackets.csv. The required python packages can be installed with:
```sh
$ pip install -r requirements.txt
```