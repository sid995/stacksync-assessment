# Declare shared ARG at top
ARG BUILD=cloud

# -------- Stage 1: Build nsjail --------
FROM debian:bookworm-slim AS builder

ARG BUILD
ENV BUILD=cloud

RUN apt-get update && apt-get install -y \
  git make gcc g++ flex bison pkg-config \
  libprotobuf-dev protobuf-compiler libnl-route-3-dev \
  ca-certificates

WORKDIR /root
RUN git clone https://github.com/google/nsjail.git
WORKDIR /root/nsjail

# Cloud-only patch to bypass gVisor securebits check
RUN if [ "$BUILD" = "cloud" ]; then \
  sed -i '/PR_SET_SECUREBITS.*KEEP_CAPS/,+1 s/return false;/\/\/ return false; \/\/ cloud run bypass/' user.cc && \
  sed -i '/prctl(PR_SET_SECUREBITS, 0UL/,+2 s/return false;/\/\/ return false; \/\/ cloud run bypass/' user.cc; \
  fi

# Build and strip nsjail
RUN env -u BUILD make && strip nsjail

# -------- Stage 2: Runtime --------
FROM python:3.11-slim

ARG BUILD
ENV BUILD=${BUILD}

WORKDIR /app

# Copy static nsjail binary and shared library
COPY --from=builder /root/nsjail/nsjail /usr/local/bin/nsjail
COPY --from=builder /usr/lib/x86_64-linux-gnu/libprotobuf.so.32 /usr/lib/x86_64-linux-gnu/libprotobuf.so.32

# Install minimal required system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
  libnl-route-3-200 && \
  rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# ------------------
# Cloud-only sandbox setup
# ------------------
RUN if [ "$BUILD" = "cloud" ]; then \
  mkdir -p /sandbox/usr/local/bin \
           /sandbox/usr/local/lib \
           /sandbox/lib/x86_64-linux-gnu \
           /sandbox/usr/lib/x86_64-linux-gnu \
           /sandbox/lib64 \
           /sandbox/tmp \
           /sandbox/usr/bin \
           /sandbox/dev \
           /sandbox/proc; \
  \
  # Copy Python executable (must be copied for chroot to work)
  cp /usr/local/bin/python3 /sandbox/usr/local/bin/python3 && \
  chmod +x /sandbox/usr/local/bin/python3 && \
  # Copy essential Python shared library
  cp /usr/local/lib/libpython3.11.so.1.0 /sandbox/usr/local/lib/libpython3.11.so.1.0 && \
  # Copy dynamic linker (essential for execution)
  cp /lib64/ld-linux-x86-64.so.2 /sandbox/lib64/ld-linux-x86-64.so.2 && \
  # Copy only essential system libraries
  cp /lib/x86_64-linux-gnu/libc.so.6 /sandbox/lib/x86_64-linux-gnu/libc.so.6 && \
  cp /lib/x86_64-linux-gnu/libm.so.6 /sandbox/lib/x86_64-linux-gnu/libm.so.6 && \
  cp /lib/x86_64-linux-gnu/libz.so.1 /sandbox/lib/x86_64-linux-gnu/libz.so.1 && \
  cp /lib/x86_64-linux-gnu/libpthread.so.0 /sandbox/lib/x86_64-linux-gnu/libpthread.so.0 && \
  # Copy libgcc_s and libstdc++ (usually needed)
  (cp /lib/x86_64-linux-gnu/libgcc_s.so.1 /sandbox/lib/x86_64-linux-gnu/libgcc_s.so.1 || \
   cp /usr/lib/x86_64-linux-gnu/libgcc_s.so.1 /sandbox/usr/lib/x86_64-linux-gnu/libgcc_s.so.1) && \
  cp /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /sandbox/usr/lib/x86_64-linux-gnu/libstdc++.so.6 && \
  # Copy libffi if it exists
  (cp /lib/x86_64-linux-gnu/libffi.so.8 /sandbox/lib/x86_64-linux-gnu/libffi.so.8 || \
   cp /usr/lib/x86_64-linux-gnu/libffi.so.8 /sandbox/usr/lib/x86_64-linux-gnu/libffi.so.8 || true) && \
  # Create Python stdlib - copy COMPLETE standard library to avoid dependency issues
  mkdir -p /sandbox/usr/local/lib/python3.11 && \
  # Copy the entire Python standard library (safest approach)
  cp -r /usr/local/lib/python3.11/* /sandbox/usr/local/lib/python3.11/ && \
  # Create python symlink in /usr/bin (internal to sandbox)
  ln -s /usr/local/bin/python3 /sandbox/usr/bin/python && \
  # Create minimal dev nodes if needed
  touch /sandbox/dev/null /sandbox/dev/zero && \
  # Set permissions
  chmod 666 /sandbox/dev/null /sandbox/dev/zero && \
  chmod -R a-w /sandbox || true; \
  fi

# Copy app source code and config
COPY . .
COPY ./nsjail.cfg /etc/nsjail.cfg

EXPOSE 8080
CMD ["python3", "main.py"]