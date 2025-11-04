import os
import struct
import array
import time
import argparse
import select

import requests
import json
import socket
import threading
import fcntl

# IPC Channel
IPC_SVC_CH_CA53_SECURE = 0
IPC_SVC_CH_CA53_NONSECURE = 1
IPC_SVC_CH_CA72_SECURE = 2
IPC_SVC_CH_CA72_NONSECURE = 3

# IPC CMD ID - Key
TCC_IPC_CMD_CA72_EDUCATION_CAN_DEMO = 0x05          # CMD1 : EDUCATION_CAN
IPC_IPC_CMD_CA72_EDUCATION_CAN_DEMO_START = 0x01    # CMD2 : START : CA72 TO MICOM 
IPC_IPC_CMD_EDUCATION_CAN_DEMO_CA72_START = 0x03    # CMD2 : START : MICOM TO CA72

# IPC PACKET
IPC_SYNC = 0xFF
IPC_START1 = 0x55
IPC_START2 = 0xAA

#SYNC: 1byte 
IPC_PACKET_SYNC_SIZE = 0x01
#START1: 1byte
IPC_PACKET_START1_SIZE = 0x01
#START2: 1byte
IPC_PACKET_START2_SIZE = 0x01
#CMD1: 2byte
IPC_PACKET_CMD1_SIZE = 0x02
#CMD2: 2byte
IPC_PACKET_CMD2_SIZE = 0x02
#LENGTH: 2byte
IPC_PACKET_LENGTH_SIZE = 0x02
#DATA: variable
IPC_PACKET_DATA_SIZE = 0x04
#CRC: 2byte
IPC_PACKET_CRC_SIZE = 0x02

IPC_PACKET_PREPARE_SIZE = 0x09
IPC_PACKET_PREFIX_SIZE = 0x0B
IPC_MAX_PACKET_SIZE = 0x400

CTL_CMD = 0x00
WRITE_CMD = 0x01

# IPC 
IPC_OPEN = 0x0001
IPC_CLOSE = 0x0002
IPC_SEND_PING = 0x0003
IPC_WRITE = 0x0004
IPC_ACK = 0x0005
IPC_NACK = 0x0006

IOCTL_IPC_WRITE = 0x00
IOCTL_IPC_READ = 0x01
IOCTL_IPC_SET_PARAM = 0x02
IOCTL_IPC_GET_PARAM = 0x03
IOCTL_IPC_PING_TEST = 0x04
IOCTL_IPC_FLUSH = 0x05
IOCTL_IPC_ISREADY = 0x06
#sndFile = ""


#IPC ====================

def IPC_CalcCrc16(data, size, init):
    crcCode = init
    crc16_table = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
    ]

    if data is not None:
        for i in range(size):
            temp8 = (crcCode >> 8) & 0xFF
            temp8 ^= data[i]
            temp32 = temp8
            crcCode = (crc16_table[temp32] ^ (crcCode << 8)) & 0xFFFF

    return crcCode
    
def IPC_SendPacketWithIPCHeader(sndFile, channel_bitmask, tx_only_channel_bitmask, canID, pucData):
    ret = 0
    cnt = 0
    crc = 0
    uiCmd3_size = 4
    uiLength = 0  
    packet_size = 0
    total_size = 0
    


    uiCmd1 = TCC_IPC_CMD_CA72_EDUCATION_CAN_DEMO
    uiCmd2 = IPC_IPC_CMD_CA72_EDUCATION_CAN_DEMO_START
    pucData_len = len(pucData)
    #print(f"pucData_len: {pucData_len}")

    if pucData_len <= 0:
        print("Error: No data")
        return

    packet_send = array.array('B', [0] * IPC_MAX_PACKET_SIZE)

    #  SYNC: 1byte ,  START1: 1byte ,  START2: 1byte ,  
    #  CMD1: 2byte ,  CMD2: 2byte ,  LENGTH: 2byte ,  
    #  DATA: variable ,  CRC: 2byte
    #FF 55 AA 00 04 00 01 00 00 00 71 6F
    #xffU\xaa\x00 3
    #\x03\x00\x00\x00\x04\  5
    #x01\x02\x03\x04\ 4
    #x0c\xbe\x00' 3

    # packaging the ipc packet
    packet_send[0] = IPC_SYNC
    packet_send[1] = IPC_START1
    packet_send[2] = IPC_START2
    packet_send[3] = (uiCmd1 >> 8) & 0xFF
    packet_send[4] = uiCmd1 & 0xFF
    packet_send[5] = (uiCmd2 >> 8) & 0xFF
    packet_send[6] = uiCmd2 & 0xFF

    # add uiCmd3 size of 2bype
    uiLength = pucData_len + uiCmd3_size

    packet_send[7] = (uiLength >> 8) & 0xFF
    packet_send[8] = uiLength & 0xFF

    #FF 55 AA 
    #00 05 
    #00 01 
    #00 00 
    #00 00 34
    #print("pucData:", end=" ")
    #for byte in pucData:
        #print(f"{byte:02X}", end=" ")
    #print()

    # uiCmd3 that add channel and tx only channel in packet_send
    packet_send[IPC_PACKET_PREPARE_SIZE] = (channel_bitmask & 0xFF)
    packet_send[IPC_PACKET_PREPARE_SIZE + 1] = tx_only_channel_bitmask & 0xFF
    packet_send[IPC_PACKET_PREPARE_SIZE + 2] = (canID >> 8) & 0xFF
    packet_send[IPC_PACKET_PREPARE_SIZE + 3] = canID & 0xFF

    if pucData_len == 0 or pucData is None: 
        packet_send[IPC_PACKET_PREPARE_SIZE + uiLength] = 0  # dummy data for test
        packet_size = IPC_PACKET_PREPARE_SIZE + 1 + uiLength
    else:
        cnt = 0
        for cnt in range(pucData_len):
            packet_send[IPC_PACKET_PREPARE_SIZE + uiCmd3_size + cnt] = pucData[cnt]

        packet_size = IPC_PACKET_PREPARE_SIZE + uiLength

    # cmd 9 + data 4 + crc 2 = 15

    crc = IPC_CalcCrc16(packet_send, packet_size, 0)
    total_size = packet_size + IPC_PACKET_CRC_SIZE

    # Debugging: Print the packet data before sending
    #print("Calculated CRC:", format(crc, '02X'))
    #print("Packet size:", packet_size)
    #print("total size:", total_size)

    packet_send[packet_size] = (crc >> 8) & 0xFF
    packet_send[packet_size + 1] = crc & 0xFF

    #cmd = [0, (WRITE_CMD << 16) | IPC_WRITE, packet_size, 0, 0, 0]

    # Debugging: Print the packet data before sending
    #print("Packet data before sending:")
    #print(' '.join(format(byte, '02X') for byte in packet_send[:total_size]))

    # Convert array.array to bytes
    packet_bytes = bytes(packet_send[:total_size])

    #sndFile = open(file_path, 'wb')
    sndCnt = 0

    while True:
        try:
            sndFile.write(packet_bytes)
            now = time.time() * 1000
            sndFile.flush()  # 
            #print(f"{sndCnt}: send{packet_bytes} at {now:.0f}")
            # Sleep for 1 second
            #time.sleep(0.5)
            sndCnt+=1
            break

        except OSError as e:
            if e.errno == 62:  # [Errno 62] Timer expired
                #print(f"Timer expired. retry ..")
                time.sleep(0.1)
            else:
                print(f"IPC error {e}")
                break

        except Exception as e:
            print(f"Exception: {e}")
            break

    #sndFile.close()
    return ret

def IPC_ReceivePacketFromIPCHeader(file_path, recv_count=1, recv_timeout=None):
    ret = 0
    revCnt = 0
    start_time = time.time()

    # Read the ipc packet
    #print(f"Read from ipc file_path: {file_path}")

    # Open the file for reading
    file_descriptor = os.open(file_path, os.O_RDWR | os.O_NONBLOCK)

    # Set the file descriptor to non-blocking mode
    flags = fcntl.fcntl(file_descriptor, fcntl.F_GETFL)
    fcntl.fcntl(file_descriptor, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    while True:
        # case send and rev 
        if recv_count is not None and revCnt >= recv_count:
            break

        if recv_timeout is not None and recv_count == 1:
            if time.time() - start_time > recv_timeout:
                #print(f"[RECV] Timeout: No data received within {recv_timeout:.1f} seconds.")
                break

        # Use select to wait for the file to become readable
        ready_to_read, _, _ = select.select([file_descriptor], [], [], 1.0)  # Timeout set to 1 second

        if ready_to_read:
            # Read data from the file
            received_data = os.read(file_descriptor, IPC_MAX_PACKET_SIZE)
            #print(f"{file_path}:: {received_data}")

            #print("Received data in decimal format:")
            #for byte in received_data:
                #print(f"{byte:d}", end=' ')
            #print()  # New line after printing all bytes

            # Convert the data into a byte array
            received_packet = bytearray(received_data)

            # Parse the received data
            received_sync = received_packet[0]
            received_start1 = received_packet[1]
            received_start2 = received_packet[2]
            received_uiCmd1 = (received_packet[3] << 8) | received_packet[4]
            received_uiCmd2 = (received_packet[5] << 8) | received_packet[6]
            received_uiLength = (received_packet[7] << 8) | received_packet[8]

            # Extract pucData
            received_pucData = received_packet[9:9+received_uiLength]

            # Extract CRC
            received_crc = (received_packet[-2] << 8) | received_packet[-1]

            # Calulated CRC
            calculated_crc = IPC_CalcCrc16(received_packet, len(received_packet) - 2, 0)

            # For debugging, print the parsed data
            #print("Received Sync:", format(received_sync, '02X'))
            #print("Received Start1:", format(received_start1, '02X'))
            #print("Received Start2:", format(received_start2, '02X'))
            #print("Received uiCmd1:", format(received_uiCmd1, '02X'))
            #print("Received uiCmd2:", format(received_uiCmd2, '02X'))
            #print("Received uiLength:", received_uiLength)
            #print("Received pucData:", ' '.join(format(byte, '02X') for byte in received_pucData))
            #print ("Received pucData:", received_pucData.decode('ascii'))
            #decoded_str = received_pucData.decode('ascii')
            #print("Received CRC:", format(received_crc, '02X'))
            #print("calculated CRC:", format(calculated_crc, '02X'))

            #if calculated_crc == received_crc:
                #print("CRC check passed!")
            #else:
                #print("CRC check failed!")
            
            revCnt += 1

    if 'file_descriptor' in locals():
        os.close(file_descriptor)

    return ret

def parse_hex_data(hex_data_str):
    # Convert the hex string to bytes
    return bytes([int(hex_data_str[i:i+2], 16) for i in range(0, len(hex_data_str), 2)])

def parse_string_data(string_data):
    # Convert the string to bytes
    return string_data.encode('utf-8')

def parse_channels(bitmask):
    return [str(ch) for ch in range(3) if bitmask & (1 << ch)]

def int_auto_base(x):
    return int(x, 0)  # '0x10' → 16, '10' → 10

def parse_hex16(x):
    try:
        value = int(x, 16)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid hex CAN ID: {x}")
    
    if not (0 <= value <= 0xFFFF):
        raise argparse.ArgumentTypeError(f"CAN ID must be a 16-bit hex value (0x0000 ~ 0xFFFF), got: 0x{value:X}")
    
    return value
