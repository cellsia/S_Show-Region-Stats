FROM cytomine/software-python3-base

ADD example.py /app/example.py

ENTRYPOINT ["python", "/app/example.py"]
