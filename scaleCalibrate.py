import smbus2
import struct
import time

bus = smbus2.SMBus(1)

deviceAddress= 0x27

rawADCAddress = 0x00
gapAddress = 0x40
offsetAddress = 0x50
weightAddress = 0x60

def readRawADC():
    rawADCBytes = bus.read_i2c_block_data(deviceAddress, rawADCAddress, 4)
    rawADC = rawADCBytes[0] + (rawADCBytes[1] << 8) + (rawADCBytes[2] << 16) + (rawADCBytes[3] << 24)
    return rawADC

def writeGap(gapValue):
    gapBytes = [gapValue & 0xFF, (gapValue >> 8) & 0xFF, (gapValue >> 16) & 0xFF, (gapValue >> 24) & 0xFF]
    bus.write_i2c_block_data(deviceAddress, gapAddress, gapBytes)

def resetOffset():
    bus.write_byte_data(deviceAddress, offsetAddress, 1)

def calibrateScale(knownWeight, rawADCEmpty, rawADCWeight):
    resetOffset()
    time.sleep(1)

    gap = (rawADCWeight - rawADCEmpty)/knownWeight

    # writeGap(int(gap))
    writeGap(5)
    print(f"GAP set to: {int(gap)}")

    print("CALIBRATION COMPLETED")

def getWeight():
    weightBytes = bus.read_i2c_block_data(deviceAddress, weightAddress, 4)
    weight100 = weightBytes[0] + (weightBytes[1] << 8) + (weightBytes[2] << 16) + (weightBytes[3] << 24)
    weight = weight100 / 100.0
    return weight

def calcWeightManual(rawADCEmpty, rawADCCurrent, gapValue):
    weight = (rawADCCurrent - rawADCEmpty) / gapValue
    return round(weight,1)


knownWeight = 32
input("ready?")
rawADCEmpty = readRawADC()

input("ready?")
rawADCWeight = readRawADC()

calibrateScale(knownWeight, rawADCEmpty, rawADCWeight)

while True:
    # print(f"Measured weight: {getWeight()} grams")
    print(f"Raw ADC Value: {readRawADC()}")
    print(f"Current weight: {calcWeightManual(8820860, readRawADC(), -174)} grams") #black white red blue 0x26
    print(f"Current weight: {calcWeightManual(8358900, readRawADC(), 174)} grams") #white orange green yellow 0x27

    time.sleep(2)