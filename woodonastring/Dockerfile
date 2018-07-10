FROM python:3-alpine



RUN apk update && \
      apk add --no-cache bash && \
      mkdir -p /state

# more real-time stdout/stderr
ENV PYTHONUNBUFFERED=1


# stuff to be changed at runtime
ENV INFLUXDB_HOST=influxdb
ENV INFLUXDB_PORT=8086
ENV INFLUXDB_USER=
ENV INFLUXDB_PASS=
ENV INFLUXDB_DATABASE=woodonastring
# file to tail
ENV LOGFILE="/logs/access.json"
# where to keep track of position
ENV POSFILE=/state/posfile.txt

WORKDIR /
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *?.py ./

ENTRYPOINT ["./main.py"]
