#!/usr/bin/env python3
import socket
import struct
import os
import time
import threading
import sys
from scapy.all import IP, UDP

START_TIME = time.time()
CLUSTER = os.environ.get("CLUSTER", "A").upper()
LOG_FILE = "/app/logs/comm_log.csv"
if CLUSTER == "A":
    MASTER_IP = "172.18.0.2"
    BROADCAST_ADDRESS = "172.18.0.255"
    OTHER_MASTER_IP = "172.20.0.3"  # Cluster B's master
elif CLUSTER == "B":
    MASTER_IP = "172.19.0.2"
    BROADCAST_ADDRESS = "172.19.0.255"
    OTHER_MASTER_IP = "172.20.0.2"  # Cluster A's master
else:
    print("Invalid CLUSTER environment variable. Must be A or B.\n")
    sys.exit(1)

# Logging function
def log_message(msg_type, src_cluster, dst_cluster, src_ip, dst_ip, protocol, length, flags):
    timestamp = time.time() - START_TIME
    line = f"{msg_type},{timestamp:.7f},{src_cluster},{dst_cluster},{src_ip},{dst_ip},{protocol},{length},{flags}\n"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print(f"Logging error: {e}", flush=True)

# Intra-cluster Communication Functions
def send_intra_broadcast(message):
    # Sends a UDP broadcast message to all containers in the cluster.
    full_message = f"BROADCAST|{message}"
    print(f"[Master Node] Sending broadcast message to all containers from {BROADCAST_ADDRESS}: \"{message}\"", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2)
        sock.sendto(full_message.encode(), (BROADCAST_ADDRESS, 5000))
        start_time = time.time()
        while time.time() - start_time < 2:
            try:
                data, server = sock.recvfrom(512)
                print(f"{server}: {data.decode()}", flush=True)
            except socket.timeout:
                break
        sock.close()
        log_message("IntraBroadcast", f"Cluster {CLUSTER}", f"Cluster {CLUSTER}", MASTER_IP, BROADCAST_ADDRESS, "UDP", len(message), "0x010")
    except Exception as e:
        print(f"[Master Node] Error sending broadcast message: {e}", flush=True)

def send_intra_anycast(message):
    # Sends a UDP anycast message to the nearest container in the cluster.
    full_message = f"ANYCAST|{message}"
    print("[Master Node] Sending anycast message to nearest container", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2)
        sock.sendto(full_message.encode(), (BROADCAST_ADDRESS, 6000))
        data, server = sock.recvfrom(512)
        print(f"{server}: {data.decode()}", flush=True)
        sock.close()
        log_message("IntraAnycast", f"Cluster {CLUSTER}", f"Cluster {CLUSTER}", MASTER_IP, BROADCAST_ADDRESS, "UDP", len(message), "0x011")
    except Exception as e:
        print(f"[Master Node] Error sending anycast message: {e}", flush=True)

def send_multicast_message(message):
    # Sends a UDP multicast message to group 224.2.25.91 on port 10000.
    # Randomly selects a multicast group from the available containers.
    multicast_group = ("224.2.25.91", 10000)
    full_message = f"MULTICAST|{message}"
    print(f"[Master Node] Sending multicast message to group {multicast_group}: \"{message}\"", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        sock.settimeout(2)
        sock.sendto(full_message.encode(), multicast_group)
        start_time = time.time()
        while time.time() - start_time < 2:
            try:
                data, server = sock.recvfrom(512)
                print(f"{server}: {data.decode()}", flush=True)
            except socket.timeout:
                break
        sock.close()
        log_message("Multicast", f"Cluster {CLUSTER}", f"Cluster {CLUSTER}", MASTER_IP, multicast_group[0], "UDP", len(message), "0x012")
    except Exception as e:
        print(f"[Master Node] Error sending multicast message: {e}", flush=True)

# Inter-cluster Communication 
def send_inter_cluster(message, target_node):
    # Sends an inter-cluster message from this master to the other cluster's master on port 7000.
    full_message = f"INTER|{target_node}|{message}"
    print(f"[Master Node] Sending inter-cluster message to other master: \"{full_message}\"", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.sendto(full_message.encode(), (OTHER_MASTER_IP, 7000))
        data, server = sock.recvfrom(512)
        print(f"[Master Node] Received inter-cluster response from {server}: {data.decode()}", flush=True)
        sock.close()
        log_message("InterCluster", f"Cluster {CLUSTER}", f"Cluster {'B' if CLUSTER=='A' else 'A'}",
                    MASTER_IP, OTHER_MASTER_IP, "UDP", len(message), "0x011")
    except Exception as e:
        print(f"[Master Node] Error sending inter-cluster message: {e}", flush=True)

# Listener for inter-cluster messages received on UDP port 7000
def inter_cluster_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 7000))
    while True:
        data, server = sock.recvfrom(512)
        message = data.decode()
        if message.startswith("INTER|"):
            parts = message.split("|", 2)
            if len(parts) == 3:
                target_node = parts[1]
                msg_content = parts[2]
                send_back = f"[Cluster {CLUSTER} Master] Received inter-cluster message for node {target_node}: \"{msg_content}\" from {server}"
                print(send_back, flush=True)
                deliver_message_to_node(target_node, msg_content)
                sock.sendto(send_back.encode(), server)
            else:
                print(f"[Cluster {CLUSTER} Master] Invalid inter-cluster message format: {message}", flush=True)
# Forward an inter-cluster message
def deliver_message_to_node(target_node, msg_content):
    if CLUSTER == "A":
        base_ip = "172.18.0."
    elif CLUSTER == "B":
        base_ip = "172.19.0."
    else:
        print(f"[Master Node] Unknown cluster: {CLUSTER}", flush=True)
        return

    node_ip_last_octet = int(target_node) + 2  # e.g. Node 1 → .3, Node 2 → .4, etc.
    node_ip = base_ip + str(node_ip_last_octet)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        full_message = f"INTER_NODE|{msg_content}"
        print(f"[Cluster {CLUSTER} Master] Forwarding inter-cluster message to node {target_node} at {node_ip}: \"{msg_content}\"", flush=True)
        sock.sendto(full_message.encode(), (node_ip, 8000))
        try:
            data, addr = sock.recvfrom(512)
            print(f"[Cluster {CLUSTER} Master] Received send_back from node {target_node} at {addr}: {data.decode()}", flush=True)
        except socket.timeout:
            print(f"[Cluster {CLUSTER} Master] No send_back received from node {target_node}", flush=True)
        sock.close()
    except Exception as e:
        print(f"[Cluster {CLUSTER} Master] Error forwarding message to node {target_node}: {e}", flush=True)

# Listens for inter-cluster message requests
def inter_cluster_from_node_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 7100))
    print(f"[Master Node] Node inter-cluster listener started on port 7100", flush=True)
    while True:
        data, server = sock.recvfrom(512)
        message = data.decode()
        if message.startswith("INTER_NODE_REQUEST|"):
            parts = message.split("|", 2)
            if len(parts) == 3:
                target_node = parts[1]
                msg_content = parts[2]
                send_back = f"[Master Node] Received inter-cluster request from node {target_node}, message: \"{msg_content}\""
                print(send_back, flush=True)
                # Forward the message to the other cluster's master.
                send_inter_cluster(msg_content, target_node)
                sock.sendto(send_back.encode(), server)
            else:
                print(f"[Master Node] Invalid inter-cluster request format: {message}", flush=True)


def main():
    if os.environ.get("ROLE", "").lower() != "master":
        sys.stderr.write("This script is for master nodes only.\n")
        sys.exit(1)
    
    threading.Thread(target=inter_cluster_listener, daemon=True).start() # Listens for inter-cluster messages
    threading.Thread(target=inter_cluster_from_node_listener, daemon=True).start() # Handles inter-cluster message
    time.sleep(5)  # Wait for nodes to be ready
    
    if CLUSTER == "A":
        print(f"[Master Node] (Cluster A) Starting intra-cluster communications...", flush=True)
        send_intra_broadcast('Hello, everyone!')
        time.sleep(1)
        send_intra_anycast("Hello, neareast container!")
        time.sleep(1)
        send_multicast_message("Hello, group!")
    elif CLUSTER == "B":
        print(f"[Master Node] (Cluster B) Starting intra-cluster communications...", flush=True)
        send_multicast_message("Hello, Group B!")
        time.sleep(1)
        send_intra_broadcast("Hello, Cluster B!")
    
    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
