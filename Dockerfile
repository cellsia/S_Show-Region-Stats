FROM cytomine/software-python3-base

ADD run.py /app/run.py

ENTRYPOINT ["python", "/app/run.py"]