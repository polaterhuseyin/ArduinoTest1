# Arduino UNO R4 WiFi — GUI Test Interface

A professional Python GUI application for testing and controlling an **Arduino UNO R4 WiFi** microcontroller over USB serial communication. Provides real-time ADC input monitoring with live waveform visualization, GPIO digital output control, PWM generation, and DAC output management.

## Features

### 📊 Real-Time ADC Monitoring
- Displays live readings from 3 analog input channels (A1, A2, A3)
- 14-bit resolution (0-16383) for UNO R4 WiFi
- Live animated waveform graph with color-coded traces
- Progress bars showing normalized ADC values
- A0 reserved for DAC output

### 🔌 Digital GPIO Control
- Control digital pins 2, 3, 4, 5
- Toggle between HIGH/LOW states via buttons
- Real-time state indication

### 🌊 PWM Output
- Pin 9 PWM generation
- 0-255 duty cycle slider control
- Real-time value display

### 🔧 DAC Output (UNO R4 WiFi Exclusive)
- True analog output via A0 on UNO R4 WiFi
- 0-255 output range
- Slider with live value feedback

### 📡 Serial Communication
- 115200 baud rate
- Bidirectional command/response protocol
- Raw command entry for advanced control
- Color-coded serial log (RX/TX/INFO/ERROR)

### 🎨 Modern Dark UI
- Cyan/orange accent colors
- Organized three-column layout:
  - **Left**: Connection control, ADC readings, raw commands
  - **Center**: Live waveform graph
  - **Right**: GPIO, PWM, and DAC controls
- Serial activity log with timestamps

## Installation

### Requirements
```bash
pip install pyserial matplotlib
```

### Supported Platforms
- **Windows**: USB-C → COM port
- **Linux**: USB-C → /dev/ttyACM0
- **macOS**: USB-C → /dev/ttyACM0

## Cross-Platform Serial Port

The GUI automatically detects available serial ports. On Windows, the Arduino will appear as a COM port (e.g., `COM3`). Make sure you:
1. Close the Arduino IDE Serial Monitor before connecting
2. Unplug/replug the USB-C cable if connection fails
3. No other application is using the same serial port

## Usage

### Starting the GUI
```bash
python main.py
```

### Workflow
1. **Connect**: Select a COM port from the dropdown and click **CONNECT**
2. **Monitor ADC**: Watch real-time analog readings update on the graph and value displays
3. **Test Hardware**: 
   - Toggle GPIO pins for digital outputs
   - Adjust PWM slider and send to pin 9
   - Adjust DAC slider and send to A0
4. **Send Custom Commands**: Enter raw commands in the text field (advanced)
5. **View Log**: Monitor all serial communication in the bottom log panel

### Status Indicators
- 🟢 **GREEN dot**: Connected and active
- 🔴 **RED dot**: Disconnected or error state

## Serial Protocol

### Arduino → GUI (Data Reception)
The Arduino sends ADC readings as comma-separated values:
```
ADC0:8192,ADC1:4096,ADC2:16000
```

**Mapping**:
- `ADC0` → Display as **A1**
- `ADC1` → Display as **A2**
- `ADC2` → Display as **A3**
- 14-bit range: 0-16383 (0V-3.3V)

### GUI → Arduino (Command Format)

#### Digital GPIO Control
```
GPIO:<pin>:<0|1>
```
Example: `GPIO:3:1` → Set pin 3 HIGH

**Supported pins**: 2, 3, 4, 5

#### PWM Output
```
PWM:<pin>:<0-255>
```
Example: `PWM:9:128` → 50% duty cycle on pin 9

#### DAC Output (UNO R4 Exclusive)
```
DAC:<0-255>
```
Example: `DAC:200` → Output 200/255 on A0

## Arduino Board Details

### Arduino UNO R4 WiFi Specifications
- **Microcontroller**: Renesas RA4M1
- **ADC Resolution**: 14-bit (vs. classic UNO: 10-bit)
- **ADC Range**: 0-16383 (0V-3.3V)
- **DAC**: True analog output on A0 (unique to R4 WiFi)
- **Connection**: USB-C port

### Pin Configuration Used
- **Analog Inputs**: A1, A2, A3 (14-bit ADC)
- **Analog Output**: A0 (DAC)
- **Digital Outputs**: Pins 2, 3, 4, 5 (GPIO control)
- **PWM Output**: Pin 9

## Configuration

Edit the `main.py` file to customize:

```python
BAUD_RATE    = 115200          # Serial communication speed
MAX_SAMPLES  = 200             # Waveform graph sample history
ADC_CHANNELS = ["A1", "A2", "A3"]  # ADC channels to monitor
GPIO_PINS    = [2, 3, 4, 5]    # GPIO pins for digital control
ADC_MAX      = 16383           # ADC maximum value (14-bit)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No serial ports detected" | Ensure Arduino is plugged in via USB-C; check Device Manager (Windows) or `dmesg` (Linux) |
| "Cannot load Activate.ps1" | Run PowerShell as Admin, then: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Connection fails immediately | Close Arduino IDE Serial Monitor; unplug/replug USB-C cable |
| ADC values not updating | Verify Arduino firmware is sending `ADC0:...,ADC1:...,ADC2:...` format at correct baud rate |
| PWM/DAC not responding | Check that pin numbers match Arduino firmware implementation |

## Code Architecture

### Main Components

**SerialManager** — Background thread handling serial I/O
- Manages USB connection lifecycle
- Non-blocking read/write with background thread
- Thread-safe queue for data exchange

**ArduinoGUI** — Main Tkinter application
- `_build_ui()` — Constructs 3-column layout
- `_build_connection()` — Port selection and ADC display
- `_build_plot()` — Matplotlib animated waveform
- `_build_gpio()` — GPIO/PWM/DAC controls
- `_poll_queue()` — Processes incoming serial data
- `_parse_data()` — Converts Arduino format to internal representation

**FuncAnimation** — Real-time matplotlib waveform graph
- 100ms refresh rate
- Deque buffers for efficient memory use
- Color-coded traces per channel

## License

This is a test utility for Arduino development. Use as needed in your projects.


## Additional Info

Other changes
