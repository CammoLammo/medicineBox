import smbus2
import time

current_device_address = 0x26  # Current address
bus = smbus2.SMBus(1)

def change_i2c_address(new_address):
    """Change the I2C address of the device."""
    try:
        # Write the new address to a specific register
        register = 0xFF  # Hypothetical register for address change (check your device's documentation)
        bus.write_byte_data(current_device_address, register, new_address)
        print(f"Changed I2C address to {hex(new_address)}")
    except Exception as e:
        print(f"Error changing I2C address: {e}")

if __name__ == "__main__":
    new_address = 0x27  # Set the new address you want
    change_i2c_address(new_address)
    time.sleep(1)  # Wait a moment to ensure the change takes effect
