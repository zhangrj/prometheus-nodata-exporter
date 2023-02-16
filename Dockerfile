FROM python:3.6-slim
LABEL maintainer="zhangrongjie"
WORKDIR /usr/src/app
EXPOSE 9198
COPY nodata_exporter.py ./
RUN pip install --no-cache-dir prometheus_api_client \
    && pip install --no-cache-dir prometheus_client
ENTRYPOINT [ "python", "./nodata_exporter.py"]