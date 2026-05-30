import pyvisa
import time

ADDRESS = "ASRL5::INSTR"  # Set correct address for PS
BAUD_RATE = 115200


class PowerSupply:
    """
    Class for handling the Teledyne power supply
    TODO: Better handling when the power supply was disconnected between two function calls.
    """

    def __init__(self, address, baud_rate):
        """
        Sets up the Teledyne T3PS43203P power supply
        :param address: Device address
        """
        self.rm = pyvisa.ResourceManager()
        self.ps = self.rm.open_resource(address)
        self.ps.baud_rate = baud_rate

    def close_power_supply(self):
        """
        Close down power supply resource and manager.
        """
        self._check_power_supply()
        self.rm.close()
        self.ps.close()

    def _check_power_supply(self):
        if self.ps is None:
            raise ValueError("The power supply resource is not open.")

    def load_memory_register(self, reg_num):
        """
        Loads the values stored in a memory register of the device
        :param reg_num: Register number to be loaded; must be an integer between 0 and 7
        :return:
        """
        self._check_power_supply()
        if reg_num >= 7 or reg_num < 0 or not isinstance(reg_num, int):
            raise ValueError("Register number must be an integer between 0 and 7.")
        self.ps.write(f'*RCL {reg_num}\n')

    def get_out_current(self, channel_id: int) -> float:
        """
        Query out current in volt for given channel.
        :param channel_id: Channel id
        """
        self._check_power_supply()
        if 0 <= channel_id <= 4:
            # The answer for the query is in the format: "0.00V\n", so we have to split it at the "V"
            return float(self.ps.query(f"VOUT{channel_id}?").split("V")[0])

    def turn_channel_on_off(self, switch_on, all_channels=True, channels=None):
        """
        Turns on or off power supply for individual channels
        :param switch_on: True if on, false if off
        :param all_channels: True if every channel must be affected, false otherwise. Default: True
        :param channels: List of channels to be affected. Only needed if allChannels is false. Default: None
        :return:
        """
        self._check_power_supply()
        string_end = "ON" if switch_on else "OFF"
        if all_channels:
            self.ps.write('ALLOUT' + string_end + '\n')
        else:
            if channels is None:
                raise ValueError("Channel list must be specified if you don't want to turn all of them on/off.")
            for channel in channels:
                if 1 <= channel <= 4 and isinstance(channel, int):
                    self.ps.write(f'OUTP{channel}:STAT ' + string_end + '\n')
        time.sleep(2)

    def turn_screen_on_off(self, turn_on):
        """
        Turns power supply LCD screen on or off
        :param turn_on: True if on, false if off
        :return:
        """
        self._check_power_supply()
        string_end = "ON" if turn_on else "OFF"
        self.ps.write("DISP:ENAB " + string_end + '\n')

    # Convenience wrappers so PowerSupply behaves like a simple instrument
    def write(self, cmd: str):
        """Proxy to the underlying VISA resource write."""
        self._check_power_supply()
        self.ps.write(cmd)

    def query(self, cmd: str) -> str:
        """Proxy to the underlying VISA resource query."""
        self._check_power_supply()
        return self.ps.query(cmd)

    def close(self):
        """Close wrapper to match other instrument APIs."""
        try:
            self.close_power_supply()
        except Exception:
            pass

