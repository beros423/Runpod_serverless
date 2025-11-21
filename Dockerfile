FROM python:3.10-slim

WORKDIR /
COPY requirements.txt /requirements.txt
RUN pip install -r requirements.txt

COPY main/ /main/
COPY rp_handler.py /

# Run ollama serve in background, then exec the container CMD (python)
RUN curl -fsSL https://ollama.com/install.sh | sh
ENTRYPOINT ["sh", "-c", "ollama serve & sleep 3 && ollama pull kronos483/Llama-3.2-3B-PubMed:latest && exec \"$@\"", "--"]

# Start the container
CMD ["python3", "-u", "rp_handler.py"]