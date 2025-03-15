FROM python:3.12-alpine

# Install only the necessary libraries for scapy
RUN apk add --no-cache libpcap libc6-compat && \
    ln -s /usr/lib/libpcap.so.1 /usr/lib/libpcap.so && \
    ln -s /usr/lib/libpcap.so.1 /usr/local/lib/libpcap.so && \
    ln -s /usr/lib/libpcap.so.1 /usr/local/lib/libpcap.so.1

# Set library path
ENV LD_LIBRARY_PATH=/usr/lib:/usr/local/lib

# Install scapy
RUN pip install scapy

# Create app directory
WORKDIR /app

# Copy scripts
COPY master.py node.py /app/