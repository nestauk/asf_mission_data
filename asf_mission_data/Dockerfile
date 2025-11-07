FROM apache/airflow:3.1.0
USER root
COPY ./requirements.txt /code/requirements.txt

RUN apt-get update && apt-get install gcc -y

RUN python3 -m venv env

USER airflow
RUN source env/bin/activate
RUN pip install --no-cache-dir -r /code/requirements.txt
