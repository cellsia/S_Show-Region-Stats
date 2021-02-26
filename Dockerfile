FROM cytomine/software-python3-base

ADD example.py /app/run.py

ENTRYPOINT ["python", "/app/run.py"]
