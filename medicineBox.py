import os
import glob
import smbus2
import time
from datetime import datetime
import mysql.connector
from gpiozero import LED, Buzzer, Button
from RPLCD import CharLCD
import ast
import RPi.GPIO as GPIO

from mysql.connector import Error

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
 
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

bus = smbus2.SMBus(1)

deviceAddressRight = 0x26 #Right Scales
deviceAddressLeft = 0x27 #Left Scales

rawADCAddress = 0x00
gapAddress = 0x40
offsetAddress = 0x50
weightAddress = 0x60

alarmLEDRight = LED(9) #Right Green LED
alarmLEDLeft = LED(21) #Left Blue LED
alarmLED3 = LED(16) #Middle Yellow LED
alarmBuzzer = Buzzer(26)
alarmButtonLeft = Button(6, pull_up=False) #Left Grey Button
alarmButtonRight = Button(5, pull_up=False) #Right Green Button
display = CharLCD(pin_rs=17, pin_e=27, pins_data=[20, 19, 13, 12, 11, 7, 24, 23], numbering_mode=GPIO.BCM)


#LCD Pin Map
#RS - GPIO17 - 11
#E - 27 - 13
#D0 - 20 - 38
#D1 - 19 - 35
#D2 - 13 - 33
#D3 - 12 - 32
#D4 - 11 - 23
#D5 - 7 - 26
#D6 - 24 - 18
#D7 - 23 - 16

def connectDatabase(host, port, database, username, password):
    try:
        connection = mysql.connector.connect(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password
            )
        if connection.is_connected():
            return connection
    except Error as e:
        print("Error", e)
        return None


def getPillData(connection, pillID, field):
    try:
        cursor = connection.cursor()
        readQuery = "SELECT " + field + " from pill WHERE id = %s"
        cursor.execute(readQuery, (pillID, ))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            print("No data found")
            return None
        
    except Error as e:
        print("Error", e)
    finally:
        cursor.close()

def getMaxTemp(connection):
    try:
        cursor = connection.cursor()
        readQuery = "SELECT max_temperature from temperature"
        cursor.execute(readQuery)
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            print("No temperature found")
            return None
        
    except Error as e:
        print("Error", e)
    finally:
        cursor.close()

def updateTemp(connection, tempData):
    displayString = "Temp: " + str(tempData) + "C"
    display.clear()
    display.write_string(displayString)
    try:
        cursor = connection.cursor()
        updateQuery = "UPDATE temperature SET value = %s WHERE id = 1"
        cursor.execute(updateQuery, (tempData, ))
        connection.commit()
        print("Updated temp to: ", tempData)
    except Error as e:
        print("Error", e)
    finally:
        cursor.close()

def updateWeight(connection, weightData, weightID):
    try:
        cursor = connection.cursor()
        updateQuery = "UPDATE pill SET weight = %s WHERE id = %s"
        cursor.execute(updateQuery, (weightData, weightID))
        connection.commit()
        print("Updated weight to: ", weightData)
    except Error as e:
        print("Error", e)
    finally:
        cursor.close()

def resetScale(deviceAddress, gapValue):
    bus.write_byte_data(deviceAddress, offsetAddress, 1)
    time.sleep(1)
    gapBytes = [gapValue & 0xFF, (gapValue >> 8) & 0xFF, (gapValue >> 16) & 0xFF, (gapValue >> 24) & 0xFF]
    bus.write_i2c_block_data(deviceAddress, gapAddress, gapBytes)

def readRawADC(deviceAddress):
    rawADCBytes = bus.read_i2c_block_data(deviceAddress, rawADCAddress, 4)
    rawADC = rawADCBytes[0] + (rawADCBytes[1] << 8) + (rawADCBytes[2] << 16) + (rawADCBytes[3] << 24)
    return rawADC

def calcWeight(rawADCEmpty, rawADCCurrent, gapValue):
    weight = (rawADCCurrent - rawADCEmpty) / gapValue
    return round(weight,3)    

def readTempRaw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def readTemp():
    lines = readTempRaw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = readTempRaw()
    equalPos = lines[1].find('t=')
    if equalPos != -1:
        tempString = lines[1][equalPos+2:]
        tempDegree = float(tempString) / 1000.0
        return tempDegree
    
def sendTaken(takenTime, pillID):
    try:
        cursor = connection.cursor()
        updateQuery = "UPDATE pill SET last_time_taken = %s WHERE id = %s"
        cursor.execute(updateQuery, (takenTime, pillID))
        connection.commit()
        print("Updated time taken to: ", takenTime)
    except Error as e:
        print("Error", e)
    finally:
        cursor.close()

def playAlarm(alarmLED, alarmButton, pillID, connection, adc):
    display.clear()
    pillName = getPillData(connection, pillID, "name")
    pillDoseSize = getPillData(connection, pillID, "dose_amount")
    if(pillID == 1):
        side = "Left"
        address = deviceAddressLeft
        gap = 176
    else:
        side = "Right"
        address = deviceAddressRight
        gap = -175
    displayString = "Take " + str(pillName) + " x" + str(pillDoseSize)
    display.write_string(displayString)
    while(True):
        alarmLED.blink(0.2,0.1, 2, True)
        alarmBuzzer.beep(0.2, 0.1, 2, True)
        if(alarmButton.is_held):
            break
    display.clear()
    alarmLED.off()
    alarmBuzzer.off()
    updateWeight(connection, calcWeight(adc, readRawADC(address), gap), pillID)
    timeTaken = datetime.now()
    timeTakenString = timeTaken.strftime("%H:%M:%S %d/%m/%Y")
    print(timeTakenString)
    sendTaken(timeTakenString, pillID)

def checkAlarm(doseTimes, alarmLED, alarmButton, pillID, connection, adc):
    for time in doseTimes:
        print(str(time))
        checkTime = datetime.strptime(time, '%H:%M:%S').time()
        lastTaken = getPillData(connection, pillID, "last_time_taken")
        if(lastTaken):
            lastTakenObject = datetime.strptime(lastTaken, "%H:%M:%S %d/%m/%Y")
            timeNow = datetime.now()
            timeDistLast = (timeNow - lastTakenObject).total_seconds()/60
        else:
            timeDistLast = 100


        combineTime = datetime.combine(datetime.now().date(), checkTime)
        timeDistCheck = abs((combineTime - datetime.now()).total_seconds()) / 60

        if timeDistCheck < 1 and timeDistLast > 1:
            playAlarm(alarmLED, alarmButton, pillID, connection, adc)

def checkMaxTemp(connection, currentTemp):
    maxTemp = getMaxTemp(connection)
    if currentTemp > maxTemp:
        alarmLED3.blink(0.2,0.1, 10,True)
        alarmBuzzer.beep(0.2, 0.1, 10, True)

def calibrateScale(deviceAddress):
    return readRawADC(deviceAddress)




    
if __name__ == "__main__":
    host = "13.60.241.8"
    port = 3306
    database = "iot_p"
    user = "root"
    password = "123456"
    connection = connectDatabase(host, port, database, user, password)

    ADCLeft = calibrateScale(deviceAddressLeft)
    ADCRight = calibrateScale(deviceAddressRight)
    # resetScale(deviceAddress1, -172)
    # resetScale(deviceAddress2, 172)

    if connection:
        while True:
            currentTemp = readTemp()
            checkMaxTemp(connection, currentTemp)
            currentWeightLeft = calcWeight(ADCLeft, readRawADC(deviceAddressLeft), 174)
            currentWeightRight = calcWeight(ADCRight, readRawADC(deviceAddressRight), -174)
            updateTemp(connection, currentTemp)
            updateWeight(connection, currentWeightLeft, 1)
            updateWeight(connection, currentWeightRight, 2)
            pillDosesLeft = getPillData(connection, 1, "dose_times")
            pillDosesRight = getPillData(connection, 2, "dose_times")

            if pillDosesLeft:
                pillDosesArrLeft = ast.literal_eval(getPillData(connection, 1, "dose_times"))
                checkAlarm(pillDosesArrLeft, alarmLEDLeft, alarmButtonLeft, 1, connection, ADCLeft)
            if pillDosesRight:
                pillDosesArrRight = ast.literal_eval(getPillData(connection, 2, "dose_times"))
                checkAlarm(pillDosesArrRight, alarmLEDRight, alarmButtonRight, 2, connection, ADCRight)
            time.sleep(0.5)
    
    else:
        print("Not connected")


