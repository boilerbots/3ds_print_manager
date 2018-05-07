#!/usr/bin/env python3
from argparse import ArgumentParser
import socket, array
import json
import time
import os

class MySocket:
    """demonstration class only
      - coded for clarity, not efficiency
    """

    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(5.0)

    def connect(self, host, port):
        self.sock.connect((host, port))

    def rawSend(self, data):
        totalsent = 0
        while totalsent < len(data):
            sent = self.sock.send(data[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
            #time.sleep(2.0)

    def mysend(self, msg):
        totalsent = 0
        while totalsent < len(msg):
            sent = self.sock.send(msg[totalsent:].encode())
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def myreceive(self):
        chunks = []
        bytes_recd = 0
        end = False
        while not end and (bytes_recd < 4096):
            chunk = self.sock.recv(4096)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            if chunk[-1] == 0:
                end = True
                chunks.append(chunk[:-1])  # strip null character
            else:
                chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
            #print(chunk.decode())
        return b''.join(chunks)

    def flush(self):
        self.sock.settimeout(0.0)
        while True:
            print("flushing")
            try:
                data = self.sock.recv(1024)
                if len(data) == 0:
                    break
            except socket.timeout:
                break
            except socket.error:
                break
        self.sock.settimeout(5.0)

class CubePro:
    def __init__(self, address):
        self.address = address
        self.socket = MySocket()
        self.socket.connect(address, 30304)

    def identify(self):
        ''' Fetch printer details with this message
        '''
        message = '{"header":{"msg_type":1,"msg_method":15,"version":1},"payload":{}}\0'
        self.socket.flush()
        self.socket.mysend(message)
        receive_message = self.socket.myreceive().decode()
        config = json.loads(receive_message)
        if config['header']['msg_method'] == 15:
            self.config = config['payload']
        else:
            print("Error processing config response")
            print("Received: {}\n".format(receive_message))

    def materialCheck(self):
        ''' Fetch material information
        '''
        send_message = '{"header":{"msg_type":1,"msg_method":19,"version":1},"payload":{}}\0'
        self.socket.flush()
        self.socket.mysend(send_message)

        receive_message = self.socket.myreceive().decode()
        material = json.loads(receive_message)
        if material['header']['msg_method'] == 19:
            self.cartridge = material['payload']['cartridge']
        else:
            print("Error processing material response")
            print("Received: {}\n".format(receive_message))

    def sendAndCheck(self, message):
        expected_method = json.loads(message[:-1])['header']['msg_method']

        self.socket.flush()
        self.socket.mysend(message)
        receive_message = self.socket.myreceive().decode()
        config = json.loads(receive_message)
        if config['header']['msg_method'] != expected_method:
            print("Error processing response")
            print("Received: {}\n".format(receive_message))

    def ping(self):
        ''' Ping the printer
        '''
        message = '{"header":{"msg_type":1,"msg_method":3,"version":1},"payload":{}}\0'
        self.sendAndCheck(message)

    def method25(self):
        '''Send this before sending a file.
           Maybe it cancels any print jobs.
        '''
        message = '{"header":{"msg_type":1,"msg_method":25,"version":1},"payload":{}}\0'
        self.sendAndCheck(message)

    def method11(self, cube_file):
        '''Request information about the file we just uploaded.
        '''
        beg = '{"header":{"msg_type":1,"msg_method":11,"version":1},"payload":{"file_name":"'
        end = '","timestamp":""}}\0'
        message = '{}{}{}'.format(beg, os.path.basename(cube_file), end)
        self.sendAndCheck(message)

    def printFile(self, cube_file):
        pf = None
        pf_length = None
        message = None
        with open(cube_file, 'rb') as f:
            pf = f.read();
            pf_length = len(pf)
            print("read file: {}  length={:#x}".format(cube_file, pf_length))
            just_name = os.path.basename(cube_file)
            beg = '{"header":{"msg_type":1,"msg_method":102,"version":1},"payload":{"file_name":"'+just_name+'","file_size":'
            end = '}}\0'
            message = '{}{:E}{}'.format(beg, pf_length, end)
            print("message: {}\n".format(message))
            self.sendAndCheck(message)

        # now upload the file.
        upload_socket = MySocket()
        upload_socket.connect(self.address, 30305)
        header = pf[4:8]+b'\x00\x00\x00\x00'
        upload_socket.flush()
        upload_socket.rawSend(header)
        upload_socket.rawSend(pf)
        time.sleep(5)
        upload_socket.sock.close()

def main():
    # Initialize instance of an argument parser
    parser = ArgumentParser(description='Printer Client')

    # Add optional arguments, with given default values if user gives no args
    parser.add_argument('-r', '--requests', default=10, type=int, help='Total number of requests to send to server')
    parser.add_argument('-w', '--workerThreads', default=2, type=int, help='Max number of worker threads to be created')
    parser.add_argument('-i', '--ip', default='10.0.10.204', help='IP address of printer')
    parser.add_argument('-p', '--port', default=30304, type=int, help='Port over which to connect')
    parser.add_argument('-f', '--file', default='', help='file to send to printer')

    # Get the arguments
    args = parser.parse_args()

    printer = CubePro(args.ip)

    #printer.identify()
    #time.sleep(1)
    #printer.materialCheck()
    #time.sleep(1)

    printer.method25()
    printer.printFile(args.file)
    printer.method11(args.file)

    while False:
        time.sleep(1.0)
        printer.ping()
        print("ping")

if __name__ == "__main__":
    # execute only if run as a script
    main()
