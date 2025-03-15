#!/usr/bin/env python3
import socket
import struct
import os
import random
import threading
import time

CONTAINER_ID = os.environ.get("CONTAINER_ID", "0")
CLUSTER = os.environ.get("CLUSTER", "A").upper()

# UDP Broadcast Listener on Port 5000
def udp_broadcast_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 5000))
    while True:
        data, server = sock.recvfrom(512)
        if data:
            message = data.decode()
            if message.startswith("BROADCAST|"):
                msg_content = message.split("|", 1)[1]
                send_back = f"[Node {CONTAINER_ID}] Received broadcast message: \"{msg_content}\""
                print(send_back, flush=True)
                sock.sendto(send_back.encode(), server)
# UDP Anycast Listener on Port 6000
def udp_anycast_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 6000))
    while True:
        data, server = sock.recvfrom(512)
        if data:
            message = data.decode()
            if message.startswith("ANYCAST|"):
                msg_content = message.split("|", 1)[1]
                send_back = f"[Node {CONTAINER_ID}] Received anycast message: \"{msg_content}\" from {server}"
                print(send_back, flush=True)
                simulated_distance = random.randint(1, 100)
                delay = simulated_distance / 100.0
                time.sleep(delay)
                sock.sendto(send_back.encode(), server)

#Multicast Listener on Port 10000 (for multicast messages)
def multicast_listener():
    multicast_groups = ["224.2.25.91", "224.2.25.92", "224.2.25.93"]
        # Randomly select a group for this node to join.
    selected_group = random.choice(multicast_groups)
    print(f"[Node {CONTAINER_ID}] Selected multicast group: {selected_group}", flush=True)

    server_address = ("", 10000)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(server_address)
    # Join only the randomly selected multicast group.
    mreq = struct.pack("4sL", socket.inet_aton(selected_group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        data, server = sock.recvfrom(512)
        if data:
            message = data.decode()
            if message.startswith("MULTICAST|"):
                msg_content = message.split("|", 1)[1]
                send_back = f"[Node {CONTAINER_ID}] Received multicast message: \"{msg_content}\" from {server}"
                print(send_back, flush=True)
                sock.sendto(send_back.encode(), server)

# Inter-cluster Communication 
def send_inter_cluster_to_master(message, target_node):
    local_master_ip = os.environ.get("LOCAL_MASTER_IP")
    if not local_master_ip:
        if os.environ.get("CLUSTER", "A").upper() == "A":
            local_master_ip = "172.18.0.2"
        else:
            local_master_ip = "172.19.0.2"
    full_message = f"INTER_NODE_REQUEST|{target_node}|{message}"
    print(f"[Node {os.environ.get('CONTAINER_ID','?')}] Sending inter-cluster request to local master at {local_master_ip}: \"{full_message}\"", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Increase timeout to 5 seconds to allow for delays in master's processing
        sock.settimeout(5)
        sock.sendto(full_message.encode(), (local_master_ip, 7100))
        data, server = sock.recvfrom(512)
        print(f"[Node {os.environ.get('CONTAINER_ID','?')}] Received send_back from master: {data.decode()}", flush=True)
        sock.close()
    except Exception as e:
        print(f"[Node {os.environ.get('CONTAINER_ID','?')}] Error sending inter-cluster request: {e}", flush=True)

def send_random_inter_cluster_message(message):
    # Randomly selects a target node (from 1 to 8) because there are 8 nodes in a cluster.
    # Randomly select a target node ID as a string.
    target_node = str(random.randint(1, 8))
    print(f"[Node {os.environ.get('CONTAINER_ID','?')}] Randomly selected target node id: {target_node}", flush=True)
    send_inter_cluster_to_master(message, target_node)

# Existing inter-cluster listener on node side:
def inter_cluster_node_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 8000))
    print(f"[Node {os.environ.get('CONTAINER_ID','?')}] Inter-cluster node listener started on port 8000", flush=True)
    while True:
        data, server = sock.recvfrom(512)
        if data:
            message = data.decode()
            if message.startswith("INTER_NODE|"):
                msg_content = message.split("|", 1)[1]
                send_back = f"[Node {os.environ.get('CONTAINER_ID','?')}] Received inter-cluster message: \"{msg_content}\""
                print(send_back, flush=True)
                sock.sendto(send_back.encode(), server)

def main():
    threading.Thread(target=udp_broadcast_listener, daemon=True).start() #for UDP broadcast messages on port 5000.
    threading.Thread(target=udp_anycast_listener, daemon=True).start() #for anycast messages on port 6000.
    threading.Thread(target=multicast_listener, daemon=True).start() #handle multicast messages on port 10000.
    threading.Thread(target=inter_cluster_node_listener, daemon=True).start()  # Added listener for inter-cluster messages
    time.sleep(2)
    print(f"[Node {CONTAINER_ID}] Connected to master node", flush=True)
    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
