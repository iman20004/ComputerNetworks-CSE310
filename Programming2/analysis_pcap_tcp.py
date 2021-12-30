import sys
import dpkt
import socket
import struct

# constants
sender_ip = "130.245.145.12"
receiver_ip = "128.208.2.198"
packets = []
flow_list = []


# packet structure
class Packet:
    def __init__(self, time, buf):
        self.time = time
        self.buf = buf
        self.eth = dpkt.ethernet.Ethernet(buf)
        self.tcp = self.eth.data
        # The internet protocol layer
        self.IP = buf[14:34]
        self.srcIp = self.IP[12:16]
        self.destIp = self.IP[16:20]
        # The transport layer
        self.TCP = buf[34:]
        self.srcPort = self.TCP[0:2]
        self.destPort = self.TCP[2:4]
        self.seqNum = self.TCP[4:8]
        self.ackNum = self.TCP[8:12]
        # Get all the flags (boolean values) using bitwise operator
        self.flags = self.TCP[13]
        self.FIN = ((0x1 & self.flags) == 0x1)
        self.SYN = ((0x2 & self.flags) == 0x2)
        self.Push = ((0x8 & self.flags) == 0x8)
        self.ACK = ((0x10 & self.flags) == 0x10)
        # Get payload to check piggyback case
        self.payload = self.buf[66:]


# Flow structure
class Flow:
    def __init__(self, packet):
        self.transactions = []
        self.packets = [packet]
        self.throughput = 0
        self.start_time = 0
        self.cwnds = []
        self.triple_dup_ack = 0
        self.timeout = 0


# Transaction object
class trans:
    def __init__(self, send):
        self.send = send
        self.receive = None
        self.num_acks = 0
        self.flag = False


# Printing all the analysis done
def printFlow():
    counter = 0
    for flow in flow_list:
        counter += 1
        # Part A (1st bullet point)
        print("---------------------------------Flow Number " + str(counter) + "----------------------------------")
        print("Source Port: " + str(int.from_bytes(flow.packets[0].srcPort, "big")) +
              " ------ Source IP: " + socket.inet_ntoa(flow.packets[0].srcIp))
        print("Destination Port: " + str(int.from_bytes(flow.packets[0].destPort, "big")) +
              " ---- Destination IP: " + socket.inet_ntoa(flow.packets[0].destIp) + "\n")


        # Part A (2nd bullet point)
        first_sent = None
        second_sent = None
        first_rec = None
        second_rec = None

        # Get first 2 transactions
        for t in flow.transactions:
            if first_sent is not None and second_sent is None and t.receive is not None:
                second_sent = t.send
                second_rec = t.receive
                break

            if first_sent is None and t.receive is not None:
                first_sent = t.send
                first_rec = t.receive

        option = dpkt.tcp.parse_opts(flow.packets[0].tcp.data.opts)
        count = option[5][1]
        scale = 2 ** int.from_bytes(count, "big")
        rwnd1 = first_sent.tcp.data.win * scale
        rwnd2 = first_rec.tcp.data.win * scale
        rwnd3 = second_sent.tcp.data.win * scale
        rwnd4 = second_rec.tcp.data.win * scale

        print("Transaction 1: ")
        print("From Sender to Receiver -> [Sequence Number = " + str(first_sent.tcp.data.seq) +
              "]  [Acknowledgement Number = " + str(first_sent.tcp.data.ack) +
              "]  [Receive Window Size = " + str(rwnd1) + "]")
        print("From Receiver to Sender -> [Sequence Number = " + str(first_rec.tcp.data.seq) +
              "]  [Acknowledgement Number = " + str(first_rec.tcp.data.ack) +
              "]  [Receive Window Size = " + str(rwnd2) + "]")

        print("Transaction 2: ")
        print("From Sender to Receiver -> [Sequence Number = " + str(second_sent.tcp.data.seq) +
              "]  [Acknowledgement Number = " + str(second_sent.tcp.data.ack) +
              "]  [Receive Window Size = " + str(rwnd3) + "]")
        print("From Receiver to Sender -> [Sequence Number = " + str(second_rec.tcp.data.seq) +
              "]  [Acknowledgement Number = " + str(second_rec.tcp.data.ack) +
              "]  [Receive Window Size = " + str(rwnd4) + "]" + "\n")

        # Part A (3rd bullet point)
        total_time = flow.packets[len(flow.packets) - 2].time - flow.start_time
        throughput = flow.throughput / total_time

        print("Throughput: " + str(throughput) + " bytes per second")

        # Part B (1st)
        portA = flow.packets[0].srcPort
        portB = flow.packets[0].destPort
        ack_store = []
        for p in flow.packets:
            if portA == p.srcPort and portB == p.destPort and len(p.tcp.data.data) != 0:
                ack_store.append(p.tcp.data.seq + len(p.payload))
            if portB == p.srcPort and portA == p.destPort and p.SYN is False:
                for ack in ack_store:
                    if p.tcp.data.ack == ack:
                        flow.cwnds.append(len(ack_store))
                        ack_store = []
                        break

        print("Congestion window sizes: [", end="  ")
        num = min(len(flow.cwnds), 3)
        for i in range(num):
            print(flow.cwnds[i], end="  ")

        print("]")
        print("Retransmissions [Triple Duplicate ACKs, Timeout]: [" + str(flow.triple_dup_ack) +
              ", " + str(flow.timeout) + "]")
        print("-------------------------------------------------------------------------------")
        print("\n")


def collectFlows():
    transaction_map = {}
    # Check every packet and sort into flows and transactions
    for p in packets:
        # If syn flag, then it will be a new flow
        if p.SYN is True and p.ACK is False:
            flow = Flow(p)  # create a flow with first syn packet
            flow_list.append(flow)  # add flow to list of flows
        else:  # Otherwise the packet is part of an existing flow
            for f in flow_list:
                client_port = f.packets[0].srcPort  # Get src and dest ports from first syn packet
                receiver_port = f.packets[0].destPort

                # If sender packet
                if client_port == p.srcPort and receiver_port == p.destPort:
                    f.packets.append(p)

                    # If data packet is being sent over
                    if len(p.tcp.data.data) != 0:

                        # For throughput calculation, bytes and time
                        f.throughput += len(p.TCP)
                        if f.start_time == 0:
                            f.start_time = p.time

                        # Existing transaction, so retransmission
                        if p.tcp.data.seq + len(p.payload) in transaction_map:
                            transaction = transaction_map.get(p.tcp.data.seq)
                            if transaction.flag is True:
                                f.triple_dup_ack += 1
                            else:
                                f.timeout += 1
                        # Otherwise new transaction
                        else:
                            transaction = trans(p)
                            transaction_map[p.tcp.data.seq + len(p.payload)] = transaction
                            f.transactions.append(transaction)
                    break

                # if receiver packet
                if receiver_port == p.srcPort and client_port == p.destPort and p.SYN is False:
                    f.packets.append(p)
                    transaction = transaction_map.get(p.tcp.data.ack)
                    if transaction is not None:
                        transaction.num_acks += 1
                        if transaction.num_acks == 4:
                            transaction.flag = True
                        if transaction.num_acks == 1:
                            transaction.receive = p
                    break


def collectPackets(pcap):
    # Go through every packet in the pcap file
    for timestamp, buf in pcap:
        # Only check packets with TCP protocol, otherwise ignore
        protocol = buf[23]
        if protocol != 0x06:
            continue

        # Next check the source and destination ip address of the packet

        # Convert hardcoded sender ip address to unsigned long
        packed_sender = socket.inet_aton(sender_ip)
        sender = struct.unpack("!L", packed_sender)[0]

        # Convert hardcoded receiver ip address to unsigned long
        packed_receiver = socket.inet_aton(receiver_ip)
        receiver = struct.unpack("!L", packed_receiver)[0]

        # Get sender and receiver ip addresses from packet
        IP = buf[14:34]
        src = IP[12:16]
        src_ip = int.from_bytes(src, "big")

        dest = IP[16:20]
        dest_ip = int.from_bytes(dest, "big")

        if src_ip != sender and src_ip != receiver:
            continue
        if dest_ip != sender and dest_ip != receiver:
            continue

        # Then create a packet and append to our constant 'packets' which is an array of all the packets
        packet = Packet(timestamp, buf)
        packets.append(packet)


def main(fileName):
    try:
        file = open(fileName, 'rb')  # Open the binary file for reading
        pcap = dpkt.pcap.Reader(file)
    except:
        print("Could not find this pcap file!")
        return  # Could not find the pcap file

    collectPackets(pcap)  # Collect all packets in pcap file -> packets[]
    collectFlows()  # Get all the flows in pcap file -> flow-list[] and make transactions
    print("Number of TCP flows initiated from the sender: ", len(flow_list), "\n\n")
    printFlow()


if __name__ == '__main__':
    try:
        fileName = sys.argv[1]
        #fileName = 'assignment2.pcap'
        if ".pcap" in fileName:
            main(fileName)
        else:
            print("Not valid! Please enter a PCAP file!")  # User did not enter a file of type pcap
    except:
        print("Please input a file name for packet analysis!")  # No file entered by user
